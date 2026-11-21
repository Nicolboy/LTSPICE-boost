"""Coss n'est pas une capacite, c'est une fonction qu'il faut integrer.

J'avais ecrit, en guise d'hypothese : « Coss n'est pas constante, donc la
sonnerie libre l'echantillonne la ou elle est grande ». C'etait la bonne
direction et la mauvaise formulation. Coss(v) est une FONCTION, et selon
ce qu'on calcule on en prend une integrale DIFFERENTE. Il y a au moins
trois grandeurs, qui ne se valent pas :

  Coss(V)     capacite DIFFERENTIELLE au point de polarisation V.
              C'est ce que mesure un pont a 1 MHz et ce que la fiche
              publie sous « Coss, Vds = 75 V ».

  Co(tr)      capacite equivalente en TEMPS : celle qui donnerait la
              meme duree de charge a courant constant.
                  Co(tr)(V) = (1/V) . integrale(0->V) Coss(v) dv
                            = Qoss(V) / V

  Co(er)      capacite equivalente en ENERGIE : celle qui stockerait la
              meme energie.
                  Co(er)(V) = (2/V^2) . integrale(0->V) v.Coss(v) dv
                            = 2.Eoss(V) / V^2

La fiche onsemi publie les deux premieres cote a cote et l'ecart s'y lit :
Coss 64 pF contre Coss(er) 113 pF a 75 V, soit un facteur 1,8.

CE QUE CA CORRIGE DANS CE QUE J'AI ECRIT

  « 69 pF deduits du temps mort » n'a aucun sens. La forme d'onde y est
  ECRETEE par la diode de corps -- le drain reste plat a 0 V pendant
  300 ns. Un pic de FFT sur un signal ecrete ne designe aucune resonance.

  « 511 pF en sonnerie libre » est une mesure PETIT SIGNAL autour d'une
  tension basse. Elle doit se comparer a Coss(v) a cette tension-la, pas
  a une moyenne.

  Pour une excursion 0 -> 80 V, c'est Co(tr) qui fixe le temps de
  transition et Co(er) qui fixe l'energie commutee. Aucune des deux
  n'est le 80 pF de la fiche.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parents[2]
sys.path.insert(0, str(RAC / ".claude/skills/sim-commun"))
from simcommun.lecture import lire                           # noqa: E402

EXE = r"C:\Program Files\ADI\LTspice\LTspice.exe"
LIB = RAC / "lib_spice_commun"
plt.style.use("dark_background")
F, G, V = "#11141a", "#171b23", "#9aa4b5"
BL, VE, OR, RO, MA = "#4dabf7", "#51cf66", "#ffa94d", "#ff6b6b", "#cc8fff"

MOD = {
    "IPD530N15N3": ('X1 nd 0 0 IPD530N15N3_L1',
                    f'.inc "{(LIB / "Infineon" / "OptiMOS3_150V_LTSpice.lib").as_posix()}"',
                    dict(coss=(80.0, 106.0), qoss=(22.0, 29.0), vref=75.0,
                         ciss=(667.0, 887.0), coer=None)),
    "FDD770N15A": ('X1 nd 0 0 FDD770N15A',
                   (LIB / "onsemi" / "FDD770N15A.lib").read_text(
                       encoding="utf-8", errors="replace"),
                   dict(coss=(64.0, 85.0), qoss=(14.0, None), vref=75.0,
                        v_qoss=37.5, ciss=(575.0, 765.0), coer=113.0)),
}


def courbe(nom: str):
    """Coss(v) par la charge a courant constant. Rend (v, Coss, Qoss, Eoss).

    La source est un ECHELON et non un `DC` : avec `Rfuite` = 1 Gohm et
    1 mA, le point de repos mettrait le noeud a 1 MV, et `.ic` ne
    l'emporte pas puisque l'OP est calcule d'abord.
    """
    inst, bib, _ = MOD[nom]
    n = "\n".join((
        f"* Coss(v) de {nom}, rampe a courant constant",
        inst,
        "Ig   0    nd   PULSE(0 1m 0 1n 1n 1 2)",
        "Rfuite nd 0    1g",
        ".options plotwinsize=0 cshunt=1e-15",
        ".tran 0 200u 0 20n",
        ".save V(nd)", bib, ".end"))
    f = ICI / f"cv_{nom}.cir"
    f.write_text(n, encoding="utf-8")
    subprocess.run([EXE, "-b", str(f)], capture_output=True, timeout=1800)
    r = lire(str(f.with_suffix(".raw")))
    t = np.asarray(r.x)
    v = np.asarray(r.trace("V(nd)")).real
    m = (v >= 0.0) & (v < 149.0)
    t, v = t[m] - t[m][0], v[m]
    # Qoss = I.t, exact et sans aucune derivee.
    q = 1e-3 * t
    # Eoss = integrale de v dQ, exacte elle aussi.
    e = np.concatenate(([0.0], np.cumsum(np.diff(q) * (v[1:] + v[:-1]) / 2)))

    # COSS PAR BINNING EN TENSION, et non par une derivee point a point.
    #
    # Premiere version : `1e-3 / max(gradient(v, t), 1e-9)`. La rampe
    # marque des paliers numeriques ou dV/dt frole zero, et le quotient
    # y explosait a 1e6 F -- des pics a 1e18 pF en travers de la figure,
    # qui ecrasaient toute l'echelle.
    #
    # Coss = dQ/dV se lit sur des INTERVALLES de tension : dans chaque
    # bin, Coss = (Q_fin - Q_debut) / largeur du bin. Aucun quotient par
    # une quantite qui peut s'annuler.
    bords = np.unique(np.concatenate([
        np.linspace(0.0, 2.0, 25), np.geomspace(2.0, 149.0, 160)]))
    idx = np.searchsorted(v, bords)
    idx = np.clip(idx, 0, len(v) - 1)
    ok = np.diff(idx) > 0
    vb = (bords[:-1][ok] + bords[1:][ok]) / 2
    cb = np.diff(q[idx])[ok] / np.diff(bords)[ok]
    # LISSAGE LEGER, et uniquement sur l'affichage de Coss. Le binning
    # laisse un bruit de quelques pour cent qui vient de la finesse des
    # intervalles, pas du composant. Qoss et Eoss, eux, ne sont PAS
    # lisses : ce sont des integrales exactes de I.t, et c'est sur elles
    # que reposent Co(tr) et Co(er).
    k = np.ones(7) / 7
    cb = np.convolve(cb, k, mode="same")
    cb[:3], cb[-3:] = cb[3], cb[-4]
    coss = np.interp(v, vb, cb)
    for ext in ("cir", "raw", "log", "op.raw"):
        f.with_suffix("." + ext).unlink(missing_ok=True)
    return v, coss, q, e


def main() -> int:
    print("  TROIS CAPACITES EQUIVALENTES, ET ELLES NE SE VALENT PAS\n")
    res = {}
    for nom in MOD:
        v, c, q, e = courbe(nom)
        res[nom] = (v, c, q, e)
        fi = MOD[nom][2]
        vr = fi["vref"]
        cd = float(np.interp(vr, v, c)) * 1e12          # differentielle
        vq = fi.get("v_qoss", vr)        # la fiche peut specifier Qoss
        qr = float(np.interp(vq, v, q)) * 1e9           # a une AUTRE tension
        er = float(np.interp(vr, v, e)) * 1e9           # Eoss en nJ
        ctr = qr / vq * 1e3                             # pF
        coer = 2 * er * 1e-9 / vr ** 2 * 1e12           # pF
        print(f"  === {nom}, a {vr:g} V ===")
        print(f"    Coss(V)  differentielle   {cd:7.1f} pF   "
              f"fiche {fi['coss'][0]:g}"
              f"{' / ' + str(fi['coss'][1]) if fi['coss'][1] else ''} pF")
        print(f"    Qoss a {vq:g} V{'':12s}{qr:7.1f} nC   "
              f"fiche {fi['qoss'][0]:g}"
              f"{' / ' + str(fi['qoss'][1]) if fi['qoss'][1] else ''} nC")
        print(f"    Co(tr) = Qoss/V           {ctr:7.1f} pF   "
              f"soit {ctr/cd:.2f}x la differentielle")
        print(f"    Eoss                      {er:7.2f} nJ")
        print(f"    Co(er) = 2.Eoss/V^2       {coer:7.1f} pF   "
              f"fiche {fi['coer'] if fi['coer'] else '--'}"
              f"{' pF' if fi['coer'] else ''}")
        print()

    # --- ce que ca dit des DEUX frequences relevees -------------------
    v, c, q, e = res["IPD530N15N3"]
    L = 47e-6
    print("  CE QUE CELA DIT DES DEUX FREQUENCES RELEVEES\n")
    print(f"  {'capacite retenue':28s} {'valeur':>9s} {'f = 1/2pi.sqrt(LC)':>20s}")
    print("  " + "-" * 62)
    cas = (("Coss(75 V) differentielle", float(np.interp(75, v, c))),
           ("Coss(5 V) differentielle", float(np.interp(5, v, c))),
           ("Co(tr) sur 0-80 V", float(np.interp(80, v, q)) / 80.0),
           ("Co(er) sur 0-80 V",
            2 * float(np.interp(80, v, e)) / 80.0 ** 2))
    for lib, cc in cas:
        print(f"  {lib:28s} {cc*1e12:6.0f} pF "
              f"{1/(2*np.pi*np.sqrt(L*cc))/1e6:17.2f} MHz")
    print()
    print("  mesure en SONNERIE LIBRE          511 pF             1,03 MHz")
    print("  -> compatible avec Coss a BASSE tension, pas avec Co(tr)")
    print()
    print("  Le \"69 pF du temps mort\" est a retirer : la forme d'onde y est")
    print("  ECRETEE par la diode de corps, un pic de FFT n'y designe aucune")
    print("  resonance.")

    # ================= FIGURE =========================================
    fig = plt.figure(figsize=(15.2, 8.4), facecolor=F)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1], wspace=.24,
                          left=.062, right=.982, top=.818, bottom=.115)
    a = fig.add_subplot(gs[0, 0])
    a.set_facecolor(G)
    a.grid(alpha=.16, color=V, lw=.6, which="both")
    a.tick_params(colors=V, labelsize=8.5)
    for s in a.spines.values():
        s.set_color("#2b3240")
    for nom, c_ in (("IPD530N15N3", BL), ("FDD770N15A", VE)):
        vv, cc, _, _ = res[nom]
        m = (vv > 0.3) & (vv < 145)
        a.loglog(vv[m], cc[m] * 1e12, color=c_, lw=1.6, label=nom)
        fi = MOD[nom][2]
        a.plot([fi["vref"]], [fi["coss"][0]], "o", color=c_, ms=9,
               mec="#e6e9ef", mew=1.2)
    a.set_xlabel("$V_{ds}$  [V]", color=V, fontsize=10)
    a.set_ylabel("$C_{oss}(v)$  différentielle  [pF]", color=V, fontsize=10)
    a.set_xlim(0.3, 150)
    a.legend(fontsize=9, facecolor=G, edgecolor="#2b3240", labelcolor=V)
    a.set_title("$C_{oss}$ EST UNE FONCTION, PAS UNE VALEUR",
                color="#e6e9ef", fontsize=12, pad=11, weight="bold")
    a.text(.04, .08, "les points cerclés sont les valeurs de fiche,\n"
           "relevées à une seule tension", transform=a.transAxes,
           color=V, fontsize=8.6, linespacing=1.5)

    a = fig.add_subplot(gs[0, 1])
    a.set_facecolor(G)
    a.grid(alpha=.16, color=V, lw=.6)
    a.tick_params(colors=V, labelsize=8.5)
    for s in a.spines.values():
        s.set_color("#2b3240")
    vv, cc, qq, ee = res["IPD530N15N3"]
    m = (vv > 1) & (vv < 145)
    ctr = qq[m] / vv[m]
    coer = 2 * ee[m] / vv[m] ** 2
    a.plot(vv[m], cc[m] * 1e12, color=BL, lw=1.6,
           label="$C_{oss}(v)$  différentielle")
    a.plot(vv[m], ctr * 1e12, color=OR, lw=1.8,
           label="$C_{o(tr)} = Q_{oss}/V$  — le TEMPS")
    a.plot(vv[m], coer * 1e12, color=MA, lw=1.8, ls="--",
           label="$C_{o(er)} = 2E_{oss}/V^2$  — l'ÉNERGIE")
    a.axvline(80, color=VE, ls=":", lw=1.1)
    a.text(82, 700, " excursion\n du montage", color=VE, fontsize=8.6,
           linespacing=1.4)
    a.set_yscale("log")
    a.set_xlim(0, 145)
    a.set_xlabel("$V_{ds}$  [V]", color=V, fontsize=10)
    a.set_ylabel("capacité équivalente  [pF]", color=V, fontsize=10)
    a.legend(fontsize=8.8, facecolor=G, edgecolor="#2b3240", labelcolor=V)
    a.set_title("IPD530N15N3 — TROIS INTÉGRALES DE LA MÊME COURBE",
                color="#e6e9ef", fontsize=12, pad=11, weight="bold")

    fig.text(.5, .952, "$C_{oss}$ N'EST PAS UNE CAPACITÉ — C'EST UNE FONCTION "
             "QU'IL FAUT INTÉGRER", ha="center", color="#e6e9ef",
             fontsize=13.5, weight="bold")
    fig.text(.5, .912, "et l'intégrale à prendre dépend de ce qu'on calcule : "
             "une durée de transition, une énergie commutée, ou une "
             "fréquence de résonance petit signal",
             ha="center", color=V, fontsize=9.6)
    plt.savefig(ICI / "coss.png", dpi=104, facecolor=F)
    print("\n  coss.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
