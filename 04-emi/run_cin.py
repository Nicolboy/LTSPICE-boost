"""Compare trois reseaux d'entree sur le meme banc EMI, mode differentiel.

POURQUOI TROIS ET NON UN. La demande etait de remplacer le 10 uF X5R par
100 nF et 1 nF. Le reseau HF seul ne tient pas le rail -- 60,9 V crete-a-crete
sur 19 V, en regime ETABLI (verifie sur huit fenetres successives, a courant
moyen stable).

LE MECANISME EST UNE RESONANCE, PAS UNE PRIVATION DE CHARGE. Le noeud
d'entree est pris entre deux inductances : 5 uH du LISN et 4,7 uH du boost.
C_in y voit un resonateur de 2,42 uH, pas une source. Reduire la capacite
remonte f0 de 16,2 kHz (0,04 fsw, le filtre filtre) a 321,7 kHz (0,80 fsw,
le bouchon amplifie), avec un Q d'environ 345 faute du moindre amortissement.
L'impedance vue a 400 kHz passe de 0,01 a 11,1 ohm, soit +61 dB.

  J'avais d'abord explique l'effondrement par un bilan de charge sur le
  temps mort -- 1,19 uC, 11,8 V sur 101 nF. C'etait la mauvaise physique :
  l'inductance d'entree ne laisse pas le condensateur se vider seul, elle
  forme un bouchon avec lui. Regle a retenir : la resonance LC d'un filtre
  d'entree doit rester LOIN SOUS la frequence de decoupage. La meme
  inductance filtre quand f0 << fsw et amplifie quand f0 -> fsw.

Plutot que de trancher a sa place entre « remplacer » et « ajouter », on
simule les deux et on laisse les nombres decider. La variante `hf` est
conservee precisement pour MONTRER qu'elle ne tient pas -- un resultat
negatif mesure vaut mieux qu'un refus argumente.
"""
import math
import sys
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(ICI))
sys.path.insert(0, str(RACINE / ".claude/skills/sim-spice/scripts"))
sys.path.insert(0, str(RACINE / ".claude/skills/sim-commun"))

import gen_emi_dm as g                                    # noqa: E402
from ltspice_run import exige                             # noqa: E402
from simcommun.lecture import lire                        # noqa: E402

RES = ICI / "results"
RES.mkdir(exist_ok=True)
RP = 5903.0            # amortissement median de l'inductance, cf. nuage
DBUV = lambda v: 20.0 * math.log10(max(v, 1e-18) / 1e-6)

# Bandes CISPR 25 methode en tension. ATTENTION aux TROUS : le gabarit ne
# couvre pas le spectre en continu, il vise des bandes de service radio.
# Le fondamental a 400 kHz tombe dans le trou 0,3-0,53 MHz.
BANDES = [(0.15e6, 0.3e6, "0,15-0,3", 70.0), (0.53e6, 1.8e6, "0,53-1,8", 50.0),
          (5.9e6, 6.2e6, "5,9-6,2", 45.0), (26e6, 41e6, "26-41", 36.0),
          (41e6, 88e6, "41-88", 30.0), (88e6, 108e6, "88-108", 30.0)]


def spectre(t, v, t0, t1):
    """FFT sur une fenetre ENTIERE de periodes de decoupage.

    Une fenetre non entiere etale chaque raie sur plusieurs bins et fausse
    son amplitude : c'est la fuite spectrale, et sur un peigne d'harmoniques
    elle se voit tout de suite. On reechantillonne a pas constant parce que
    le pas de LTspice est variable.
    """
    n = 1 << 16
    tt = np.linspace(t0, t1, n, endpoint=False)
    vv = np.interp(tt, t, v)
    vv = vv - vv.mean()
    sp = np.fft.rfft(vv * np.hanning(n)) / n * 4.0        # Hanning : x2 ; crete : x2
    f = np.fft.rfftfreq(n, (t1 - t0) / n)
    return f, np.abs(sp)


def mesure(nom, ind, cin):
    txt = g.netlist(cin=cin, ind=ind)
    cir = RES / f"cin_{nom}.cir"
    cir.write_text(txt, encoding="utf-8")
    r = exige(cir)
    return r, lire(r["raw"])


# Trois variantes, et chacune repond a une question precise :
#   47u_complet    l'architecture retenue -- la reference
#   47u_sans_amor  ce que la resistance de 500 mOhm rapporte reellement
#   4u7_complet    ce que le choix 47 uH plutot que 4,7 uH a rapporte
CAS = [("47u_complet",   "47u", "complet"),
       ("47u_sans_amor", "47u", "sans_amor"),
       ("4u7_complet",   "4u7", "complet")]


def main():
    tsw = 1.0 / g.FSW
    t0, t1 = 24 * tsw, 40 * tsw
    out = {}
    for nom, ind, var in CAS:
        cin = g.VARIANTES[var]
        ctot = sum(c for _, c, _, _, _ in cin)
        print()
        print(f"=== {nom}  ({g.INDUCTANCES[ind][0]}, {ctot*1e6:.0f} uF) "
              + "=" * 28)
        try:
            r, raw = mesure(nom, ind, cin)
        except Exception as e:
            print("   ECHEC :", type(e).__name__, str(e)[:200])
            continue
        t = np.asarray(raw.x)
        vmp = np.asarray(raw.trace("V(mp)")).real
        vin = np.asarray(raw.trace("V(nin)")).real
        il = np.asarray(raw.trace("I(Vl)")).real
        m = (t >= t0) & (t <= t1)
        ond = vin[m].max() - vin[m].min()
        imin, imax = il[m].min(), il[m].max()
        print(f"   entree {vin[m].mean():6.2f} V, ondulation {ond*1e3:7.1f} mV"
              f"   |  I(L) {imin:5.2f}..{imax:5.2f} A"
              f"  -> {'CCM' if imin > 0.05 else 'DCM (le courant touche zero)'}")
        f, a = spectre(t, vmp, t0, t1)
        out[nom] = (f, a, ond, vin[m].mean())
        for lab, fr in (("H1 400 kHz", 400e3), ("H2 800 kHz", 800e3),
                        ("H3 1,2 MHz", 1.2e6), ("H4 1,6 MHz", 1.6e6)):
            i = np.argmin(abs(f - fr))
            print(f"      {lab:14s} {DBUV(a[i]):7.2f} dBuV")
    return out


def figure(o):
    """Deux panneaux : les spectres, puis l'ECART entre les deux variantes.

    Le panneau du bas existe parce que le haut ne peut pas le montrer : le
    bulk et le bulk+HF se superposent a 0,02 dB pres sous 2 MHz. Tracer deux
    courbes confondues et affirmer qu'elles different quelque part serait
    une figure qui demande d'etre crue sur parole.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.style.use("dark_background")
    fig, (ax, bx) = plt.subplots(
        2, 1, figsize=(13, 8.8), dpi=170, sharex=True,
        gridspec_kw={"height_ratios": [2.45, 1], "hspace": 0.1})
    for a in (fig.patch,):
        a.set_facecolor("#15171c")
    for a in (ax, bx):
        a.set_facecolor("#15171c")
        a.grid(True, which="both", color="#2c3038", lw=0.6, zorder=1)
        a.tick_params(colors="#9aa0a6")

    # le cas invalide passe DERRIERE et en transparence : il est la pour
    # etre vu disqualifie, pas pour dominer la figure.
    STYLE = {"4u7_complet": ("#ff6b6b", 1.0, "-", 0.55, 2,
              "SER1360-472, 4,7 µH — DCM"),
             "47u_sans_amor": ("#ffa94d", 1.0, "--", 0.8, 3,
              "SER2211-473, 47 µH — CCM, sans la branche amortie"),
             "47u_complet": ("#54d6a0", 1.8, "-", 0.97, 4,
              "SER2211-473, 47 µH — CCM, réseau complet  ← retenu")}
    for k in ("4u7_complet", "47u_sans_amor", "47u_complet"):
        if k not in o:
            continue
        f, a_, _, _ = o[k]
        c, lw, ls, al, z, lab = STYLE[k]
        m = (f >= 1e5) & (f <= 1.2e8)
        ax.plot(f[m], [DBUV(v) for v in a_[m]], ls, color=c, lw=lw,
                alpha=al, label=lab, zorder=z)

    # gabarit : des SEGMENTS par bande, jamais une ligne continue -- les
    # trous du gabarit sont le fait le plus important de cette figure.
    for i, (f0, f1, lab, lim) in enumerate(BANDES):
        ax.plot([f0, f1], [lim, lim], color="#ffd166", lw=3.0, zorder=6,
                solid_capstyle="butt",
                label="CISPR 25 classe 3, détecteur moyenne" if i == 0 else None)
        for a in (ax, bx):
            a.axvspan(f0, f1, color="#ffd166", alpha=0.055, zorder=0)
    ax.axvline(4e5, color="#9aa0a6", ls=":", lw=1.2, zorder=2)
    ax.annotate("fondamental 400 kHz —" + "\n" + "DANS UN TROU du gabarit",
                xy=(4e5, 72), xytext=(1.1e5, 100), color="#ffd166",
                fontsize=9.5, ha="left",
                arrowprops=dict(arrowstyle="->", color="#ffd166", lw=1.2))
    ax.set_ylim(-15, 125)
    ax.set_ylabel("tension aux bornes du LISN (dBµV)", color="#e8eaed")
    ax.set_title("Mode différentiel conduit — ce que le choix d'inductance rapporte\n"
                 "boost 19 V → 80 V, 47 W, 400 kHz · LISN CISPR 25 5 µH · "
                 "entrée 220 µF ∥ (1000 µF + 500 mΩ) ∥ 1 µF",
                 color="#e8eaed", fontsize=12.5, pad=13)
    lg = ax.legend(loc="upper right", facecolor="#1d2026",
                   edgecolor="#2c3038", fontsize=9.5)
    for t in lg.get_texts():
        t.set_color("#e8eaed")

    # ---- panneau du bas : ce que le decouplage HF rapporte vraiment ----
    if "4u7_complet" in o and "47u_complet" in o:
        f, ab, _, _ = o["4u7_complet"]
        _, ah, _, _ = o["47u_complet"]
        # L'ecart ne se lit QUE SUR LES RAIES. Entre elles il n'y a que le
        # plancher numerique, et en diviser un par un autre produit un
        # bruit de +/-5 dB qui n'a aucun sens physique -- il donnerait a
        # croire que le decouplage HF degrade parfois le spectre.
        # On echantillonne donc le peigne, au maximum local autour de
        # chaque multiple de la frequence de decoupage.
        fh, dh = [], []
        df = f[1] - f[0]
        for k in range(1, int(1.2e8 / g.FSW) + 1):
            fk = k * g.FSW
            if fk < 1e5 or fk > 1.2e8:
                continue
            i0 = int(round((fk - 2 * df) / df))
            w = slice(max(i0, 0), min(i0 + 5, len(f)))
            j = w.start + int(np.argmax(ab[w]))
            if ab[j] < 1e-6 * 10 ** (-5 / 20.0):    # sous 0 dBuV : plancher
                continue
            fh.append(f[j])
            dh.append(20 * np.log10(max(ah[j], 1e-18) / max(ab[j], 1e-18)))
        bx.plot(fh, dh, "o-", color="#54d6a0", lw=1.1, ms=2.6,
                alpha=0.92, zorder=3,
                label=f"47 µH CCM moins 4,7 µH DCM, sur {len(fh)} raies")
        bx.axhline(-18.5, color="#9aa0a6", ls=":", lw=1.0, zorder=2)
        lb = bx.legend(loc="upper left", facecolor="#1d2026",
                       edgecolor="#2c3038", fontsize=9)
        for t in lb.get_texts():
            t.set_color("#e8eaed")
        bx.axhline(0, color="#9aa0a6", lw=1.0, ls="--", zorder=2)
        bx.set_ylim(-46, 10)
        bx.set_ylabel("gain du 47 µH CCM (dB)", color="#e8eaed",
                      fontsize=10)
        bx.annotate("17 à 20 dB retirés dans les bandes du gabarit." + "\n"
                    + "Le gain s'efface au-delà de 30 MHz : là, ce n'est"
                    + "\n" + "plus le mode de conduction qui domine.",
                    xy=(1.5e6, -19), xytext=(2.4e5, -41), color="#54d6a0",
                    fontsize=9.5,
                    arrowprops=dict(arrowstyle="->", color="#54d6a0", lw=1.1))
    bx.set_xscale("log")
    bx.set_xlim(1e5, 1.2e8)
    bx.set_xlabel("fréquence (Hz)", color="#e8eaed")
    # pas de tight_layout : hspace est deja pose a la main, et il se
    # plaint des axes partages.
    fig.subplots_adjust(left=.075, right=.985, top=.90, bottom=.085)
    # Les figures vont dans `illustrations/`, pas dans `results/` :
    # ce dernier est ignore par git (contenu regenerable et volumineux),
    # et une image citee par le README doit etre versionnee avec lui.
    ILL = ICI / "illustrations"
    ILL.mkdir(exist_ok=True)
    p = ILL / "cin_comparaison.png"
    p.unlink(missing_ok=True)
    fig.savefig(p, facecolor=fig.get_facecolor())
    print(f"\nfigure -> {p}")


if __name__ == "__main__":
    o = main()
    if len(o) < 2:
        sys.exit("pas assez de variantes abouties pour comparer")
    np.savez(RES / "cin_spectres.npz",
             **{f"{k}_{n}": v for k, (f, a, ond, vm) in o.items()
                for n, v in (("f", f), ("a", a), ("ond", ond), ("vm", vm))})
    figure(o)
    print("\n\n" + "=" * 68)
    print("COMPARAISON PAR BANDE CISPR 25 -- crete dans la bande, en dBuV")
    print("=" * 68)
    print(f"{'bande (MHz)':>14s} {'limite cl.3 AV':>15s} " +
          " ".join(f"{k:>10s}" for k in o))
    for f0, f1, lab, lim in BANDES:
        l = [f"{lab:>14s}", f"{lim:>13.0f}  "]
        for k, (f, a, _, _) in o.items():
            m = (f >= f0) & (f <= f1)
            l.append(f"{DBUV(a[m].max()) if m.any() else float('nan'):>10.1f}")
        print(" ".join(l))
    print("\n  Le fondamental a 400 kHz ne figure dans AUCUNE bande :")
    print("  CISPR 25 laisse un trou entre 0,3 et 0,53 MHz.")
