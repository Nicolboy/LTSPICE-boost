"""Formes d'onde sur 3 periodes en regime etabli, aux neuf points
d'exploitation, pour les deux architectures.

POINTS. Ils couvrent la plage d'entree 12-25 V, avec la contrainte que
50 W n'est demande qu'a partir de 19 V :

    12 V : 5, 10, 20 W      20 V : 5, 15, 45 W      25 V : 5, 15, 45 W

CE QU'ILS VERIFIENT. Le seuil DCM/CCM vaut Vin^2 (1-Vin/Vout)/(2 f L),
donc il va en Vin^2 et se deplace d'un facteur 4 sur la plage :

    archi 1 (4,7 uH)   : 32,6 W a 12 V, 79,8 a 20 V, 114 a 25 V
    archi 2 (104,8 uH) : 1,46 W a 12 V, 3,58 a 20 V, 5,12 a 25 V

L'archi 1 est donc en DCM sur TOUS ces points, et l'archi 2 en CCM
partout SAUF a 25 V / 5 W, qui tombe pile sur son seuil (5,12 W). C'est
le cas de transition de mode, celui qui decide de l'EMI.

METHODE. Le rapport cyclique est ajuste par secante sur la puissance de
sortie mesuree, et non calcule : l'expression analytique change de forme
entre DCM et CCM, et c'est precisement aux points de bascule qu'on ne
veut pas en dependre.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                       / ".claude/skills/sim-spice/scripts"))
import gen_ccm_ltspice as c2                                  # noqa: E402
import gen_dcm_ltspice as d1                                  # noqa: E402
from ltspice_run import lance                                 # noqa: E402

ICI = Path(__file__).resolve().parent
TRAVAIL = ICI / "results" / "formes"
FIGURES = ICI / "illustrations" / "formes_onde"

POINTS = [(12.0, 5.0), (12.0, 10.0), (12.0, 20.0),
          (20.0, 5.0), (20.0, 15.0), (20.0, 45.0),
          (25.0, 5.0), (25.0, 15.0), (25.0, 45.0)]

N_PER = 3            # periodes tracees
TOL_P = 0.02         # 2 % sur la puissance visee


def seuil_dcm(vin, vout, fsw, l_h):
    return vin**2 * (1.0 - vin / vout) / (2.0 * fsw * l_h)


# --------------------------------------------------------------- lancement

def _run(nom, texte):
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    cir = TRAVAIL / f"{nom}.cir"
    cir.write_text(texte, encoding="ascii")
    r = lance(cir)
    if not r["ok"]:
        raise RuntimeError(f"{nom} : {r['diagnostic']}")
    return r


def point_archi1(vin, pout, dtmax=0.1e-9):
    d1.VIN = vin
    d = d1.duty_dcm(pout)
    hist = []
    for k in range(6):
        r = _run(f"a1_{vin:.0f}V_{pout:.0f}W", d1.netlist((d,), dtmax=dtmax))
        p = r["meas"]["pout"]
        hist.append((d, p))
        if abs(p - pout) / pout < TOL_P:
            break
        d = _secante(hist, pout, d, lambda x: x * np.sqrt(pout / max(p, 1e-3)))
    return r, d


def point_archi2(vin, pout, dtmax=0.125e-9):
    c2.VIN = vin
    i_l = pout / vin
    d = c2.duty_ccm(i_l)
    hist = []
    for k in range(6):
        r = _run(f"a2_{vin:.0f}V_{pout:.0f}W",
                 c2.netlist((d,), i_l, dtmax=dtmax))
        p = r["meas"]["pout"]
        hist.append((d, p))
        if abs(p - pout) / pout < TOL_P:
            break
        # en CCM la puissance monte avec D de facon tres raide : on borne
        # le pas pour ne pas sortir du domaine de convergence.
        pas = (pout - p) * c2.L_H / (c2.VOUT * (c2.N_MES / c2.FSW)) / max(i_l, .2)
        d += float(np.clip(_secante(hist, pout, d, lambda x: x + pas) - d,
                           -0.01, 0.01))
    return r, d


def _secante(hist, cible, d, repli):
    if len(hist) >= 2 and abs(hist[-1][1] - hist[-2][1]) > 1e-6:
        (d0, p0), (d1_, p1) = hist[-2], hist[-1]
        return d1_ + (cible - p1) * (d1_ - d0) / (p1 - p0)
    return repli(d)


# ------------------------------------------------------------------ trace

def trace(raw_path, titre, fsw, fichier, t_debut=0.0):
    from spicelib.raw.raw_read import RawRead
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    r = RawRead(str(raw_path))
    t = np.abs(np.asarray(r.get_trace("time").get_wave(), dtype=float))
    # L'archi 1 ecrit avec tstart>0 : LTspice y met des temps RELATIFS et
    # un Offset d'en-tete, donc le fichier commence deja au regime etabli.
    # L'archi 2 ecrit depuis 0 (tstart=0 impose par un bug de solveur) :
    # il faut y sauter explicitement a la fenetre etablie, sinon on trace
    # le DEMARRAGE en croyant tracer le regime permanent.
    t = t - t[0] - t_debut
    sig = {n: np.asarray(r.get_trace(n).get_wave(), dtype=float).real
           for n in ("V(nsw)", "I(L1)", "V(nda)", "V(nd)")}
    tsw = 1.0 / fsw
    m = (t >= 0) & (t <= N_PER * tsw)
    ts = t[m] * 1e6

    fig, ax = plt.subplots(3, 1, figsize=(9, 7), sharex=True)
    ax[0].plot(ts, sig["V(nsw)"][m], lw=.8, color="#1f77b4")
    ax[0].set_ylabel("noeud de\ncommutation (V)")
    ax[1].plot(ts, sig["I(L1)"][m], lw=.8, color="#d62728")
    ax[1].axhline(0, color="k", lw=.5, ls=":")
    ax[1].set_ylabel("courant\ninductance (A)")
    vd = sig["V(nda)"][m] - sig["V(nd)"][m]
    ax[2].plot(ts, vd, lw=.8, color="#2ca02c")
    ax[2].axhline(-200, color="r", lw=.7, ls="--")
    ax[2].text(ts[-1], -200, " calibre 200 V", color="r", va="bottom",
               ha="right", fontsize=8)
    ax[2].set_ylabel("tension\ndiode (V)")
    ax[2].set_xlabel("temps (µs)")
    for a in ax:
        a.grid(alpha=.3)
        for k in range(N_PER + 1):
            a.axvline(k * tsw * 1e6, color="k", lw=.4, alpha=.25)
    fig.suptitle(titre, fontsize=10)
    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / fichier, dpi=110)
    plt.close(fig)

    imin, imax = float(sig["I(L1)"][m].min()), float(sig["I(L1)"][m].max())
    return dict(ipk=imax, imin=imin, vsw=float(sig["V(nsw)"][m].max()),
                vdrev=float(vd.min()),
                mode="DCM" if imin < 0.05 * max(imax, 1e-9) else "CCM")


# ------------------------------------------------------------------- main

if __name__ == "__main__":
    quels = sys.argv[1] if len(sys.argv) > 1 else "les-deux"
    print(f"{'point':<12}{'archi':<8}{'Pvise':>7}{'Pobt':>7}{'mode':>6}"
          f"{'Ipk':>7}{'Imin':>7}{'Vsw':>7}{'Vdiode':>8}")
    for vin, pout in POINTS:
        for nom, fn, gen in (("archi 1", point_archi1, d1),
                             ("archi 2", point_archi2, c2)):
            if quels != "les-deux" and quels not in nom.replace(" ", ""):
                continue
            try:
                r, d = fn(vin, pout)
            except Exception as exc:                        # noqa: BLE001
                print(f"{vin:.0f}V/{pout:.0f}W  {nom}  !! {exc}")
                continue
            tag = f"{nom.replace(' ','')}_{vin:.0f}V_{pout:.0f}W"
            t_deb = 0.0 if gen is d1 else 250e-9 + c2.N_ETAB / c2.FSW
            st = trace(r["raw"], f"{nom} — {vin:.0f} V, {pout:.0f} W "
                       f"(obtenu {r['meas']['pout']:.1f} W)",
                       gen.FSW, tag + ".png", t_deb)
            print(f"{vin:>4.0f}V/{pout:>4.0f}W {nom:<8}{pout:>7.1f}"
                  f"{r['meas']['pout']:>7.1f}{st['mode']:>6}"
                  f"{st['ipk']:>7.2f}{st['imin']:>7.2f}{st['vsw']:>7.0f}"
                  f"{st['vdrev']:>8.0f}", flush=True)
    print(f"\nfigures -> {FIGURES}")
