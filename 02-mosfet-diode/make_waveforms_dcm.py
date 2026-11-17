"""Formes d'onde de l'architecture 1 (GaN, DCM permanent, 400 kHz).

Deux figures :
  1. trois points de charge (5 / 20 / 40 W), quatre periodes, au NOEUD
     CHAUD -- c'est lui qui porte le dV/dt, la resonance de temps mort et
     l'ecretage en troisieme quadrant ;
  2. balayage de l'INDUCTANCE DE MAILLE (10 / 20 / 40 / 80 nH), le seul
     parametre non source du modele : plutot que de le postuler, on
     mesure ce qu'il coute.

Le rapport cyclique est TRIMME par secante sur la puissance visee : la
formule DCM analytique suppose un rendement et neglige les chutes, elle
sort a +5 a -7 % selon le point.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent.parent
sys.path[:0] = [str(ICI), str(RACINE / ".claude/skills/sim-spice/scripts"),
                str(RACINE / ".claude/skills/sim-commun")]

import bilan_dcm as b                         # noqa: E402
import gen_dcm_gan as g                       # noqa: E402
import pertes_inductance as pi                # noqa: E402
from ngspice_run import lance                 # noqa: E402

DEST = ICI / "illustrations"
TRAVAIL = Path(os.environ.get("TEMP", "/tmp")) / "dcm_ondes"
BG, GRILLE, TXT, TXT2 = "#11141a", "#2b3240", "#e6e9ef", "#9aa4b5"
C_V, C_IL, C_ID, C_IS = "#4da3ff", "#3ddc84", "#ffb13d", "#ff6b6b"
C_LB = ("#4da3ff", "#3ddc84", "#ffb13d", "#ff6b6b")


def run(pout: float, duty: float | None, dossier: Path,
        l_boucle: float | None = None):
    dossier.mkdir(parents=True, exist_ok=True)
    f = dossier / "run.cir"
    f.write_text(g.netlist(pout, duty=duty, l_boucle=l_boucle), encoding="utf-8")
    r = lance(f, dossier, verbose=False)
    if not r["ok"]:
        return None, None
    m = b.mesures(Path(r["raw"]))
    x = b.bilan(m)
    return x, m


def trim(pout: float, dossier: Path, l_boucle=None, tol: float = 0.01):
    """Secante sur le rapport cyclique pour viser pout a tol pres."""
    d0 = g.duty_dcm(pout)
    x0, m0 = run(pout, d0, dossier / "a", l_boucle)
    if x0 is None:
        return None, None, None
    d1 = d0 * (pout / x0["p_out"]) ** 0.5        # Pout ~ D^2 en DCM
    x1, m1 = run(pout, d1, dossier / "b", l_boucle)
    for i in range(6):
        if x1 is None:
            return None, None, None
        if abs(x1["p_out"] / pout - 1) < tol:
            return d1, x1, m1
        d2 = d1 + (pout - x1["p_out"]) * (d1 - d0) / (x1["p_out"] - x0["p_out"])
        d0, x0 = d1, x1
        d1, (x1, m1) = d2, run(pout, d2, dossier / f"it{i}", l_boucle)
    return d1, x1, m1


def _instant_coupure(m: dict) -> float:
    """Premier front descendant de la grille dans la fenetre enregistree."""
    vg, t = m["V(ng)"], m["t"]
    bas = vg < 2.5
    i = int(np.argmax(bas[1:] & ~bas[:-1])) + 1
    return float(t[i])


# ----------------------------------------------------------------- fig 1
def figure_puissance(cas):
    fig, axs = plt.subplots(3, 1, figsize=(13, 11.5), dpi=150, facecolor=BG)
    fig.suptitle("Architecture 1 — GaN EPC2007C en DCM permanent, "
                 "400 kHz, 4,7 µH, 20 V → 80 V",
                 color=TXT, fontsize=14.5, fontweight=650, y=0.977)
    fig.text(0.5, 0.947, "nœud de commutation · quatre périodes · maille de "
             "commutation 20 nH · rapport cyclique trimmé sur la puissance visée",
             color=TXT2, fontsize=10.5, ha="center")

    for ax, (p, duty, x, m) in zip(axs, cas):
        t = (m["t"] - m["t"][0]) * 1e6
        ax.set_facecolor(BG)
        ax.plot(t, m["V(nsw)"], color=C_V, lw=1.5, label="V(nœud)")
        ax.axhline(0, color=TXT2, lw=0.7, ls=":")
        ax.axhline(-2.1, color="#ff6b6b", lw=1.0, ls="--")
        ax.text(t[-1], -5.2, "V_SD = −2,1 V : conduction 3ᵉ quadrant du GaN ",
                color="#ff6b6b", fontsize=8.5, va="center", ha="right")
        ax.set_ylabel("tension  [V]", color=TXT2, fontsize=10)
        ax.set_ylim(-13, 97)

        a2 = ax.twinx()
        a2.plot(t, m["I(L1)"], color=C_IL, lw=1.4, label="I(L)")
        a2.plot(t, m["I(Vd)"], color=C_ID, lw=1.0, alpha=0.85, label="I(diode)")
        a2.plot(t, m["I(Vs)"], color=C_IS, lw=1.0, alpha=0.85, label="I(canal)")
        a2.set_ylabel("courant  [A]", color=TXT2, fontsize=10)
        a2.axhline(0, color=TXT2, lw=0.5, ls=":")

        for a in (ax, a2):
            a.tick_params(colors=TXT2, labelsize=9)
            for s in a.spines.values():
                s.set_color(GRILLE)
        ax.grid(True, color=GRILLE, lw=0.6, alpha=0.7)
        ax.set_axisbelow(True)
        fer = pi.p_fer_mw(g.FSW, x["i_pk"])
        tot = x["pertes_spice"] * 1e3 + fer
        ax.set_title(
            f"{p:.0f} W  —  D = {duty:.4f},  I_pk = {x['i_pk']:.2f} A,  "
            f"temps mort {100*b.frac_morte(m):.0f} %   |   "
            f"diode {x['diode']*1e3:.0f} · canal {x['canal']*1e3:.0f} · "
            f"3ᵉQ {x['q3']*1e3:.0f} · cuivre {x['cuivre']*1e3:.0f} · "
            f"fer {fer:.0f} mW  →  η = {100*p/(p+tot*1e-3):.2f} %",
            color=TXT, fontsize=10.2, pad=6, fontweight=600)
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = a2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, fontsize=9, ncol=4, loc="upper right",
                  facecolor="#1a1f28", edgecolor=GRILLE, labelcolor=TXT
                  ).get_frame().set_alpha(0.95)
    axs[-1].set_xlabel("temps  [µs]", color=TXT2, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    p = DEST / "30-dcm-formes-onde.png"
    fig.savefig(p, facecolor=BG)
    plt.close(fig)
    return p


# ----------------------------------------------------------------- fig 2
def figure_boucle(cas, pout):
    fig, axs = plt.subplots(1, 2, figsize=(14, 5.6), dpi=150, facecolor=BG,
                            gridspec_kw=dict(width_ratios=[1.35, 1]))
    fig.suptitle(f"Inductance de maille de commutation — "
                 f"le seul paramètre non sourcé du modèle  ({pout:.0f} W)",
                 color=TXT, fontsize=14, fontweight=650, y=0.975)
    fig.text(0.5, 0.925, "balayée plutôt que postulée · 10 nH = 4 couches avec "
             "plan à 100 µm · 80 nH = retour lointain et boîtiers traversants",
             color=TXT2, fontsize=10, ha="center")

    for ax in axs:
        ax.set_facecolor(BG)
        ax.tick_params(colors=TXT2, labelsize=9)
        for s in ax.spines.values():
            s.set_color(GRILLE)
        ax.grid(True, color=GRILLE, lw=0.6, alpha=0.7)
        ax.set_axisbelow(True)

    for (lb, x, m), c in zip(cas, C_LB):
        t0 = m["t"][0]
        axs[0].plot((m["t"] - t0) * 1e6, m["V(nsw)"], color=c, lw=1.3,
                    label=f"{lb*1e9:.0f} nH")
        tc = _instant_coupure(m)
        msk = (m["t"] >= tc - 5e-9) & (m["t"] <= tc + 70e-9)
        axs[1].plot((m["t"][msk] - tc) * 1e9, m["V(nsw)"][msk], color=c, lw=1.5,
                    label=f"{lb*1e9:.0f} nH")

    axs[0].axhline(80, color=TXT2, lw=0.8, ls="--")
    axs[0].text(0.02, 80, " V_out = 80 V", color=TXT2, fontsize=8.5,
                va="bottom", transform=axs[0].get_yaxis_transform())
    axs[0].axhline(-2.1, color="#ff6b6b", lw=0.9, ls="--")
    axs[0].set_xlabel("temps  [µs]", color=TXT2, fontsize=10)
    axs[0].set_ylabel("V(nœud)  [V]", color=TXT2, fontsize=10)
    axs[0].set_title("quatre périodes complètes", color=TXT, fontsize=11, pad=5)

    axs[1].axhline(80, color=TXT2, lw=0.8, ls="--")
    axs[1].set_xlabel("temps depuis la coupure  [ns]", color=TXT2, fontsize=10)
    axs[1].set_title("zoom sur le front de coupure", color=TXT, fontsize=11, pad=5)
    for ax in axs:
        ax.legend(fontsize=9, loc="lower right", facecolor="#1a1f28",
                  edgecolor=GRILLE, labelcolor=TXT,
                  title="maille").get_frame().set_alpha(0.95)
    fig.tight_layout(rect=(0, 0, 1, 0.915))
    p = DEST / "31-dcm-inductance-maille.png"
    fig.savefig(p, facecolor=BG)
    plt.close(fig)
    return p


if __name__ == "__main__":
    DEST.mkdir(parents=True, exist_ok=True)

    print("=== figure 1 : trois points de charge ===")
    cas1 = []
    for pw in (5.0, 20.0, 40.0):
        d, x, m = trim(pw, TRAVAIL / f"p{pw:.0f}")
        if x is None:
            print(f"  {pw:4.0f} W : ECHEC")
            continue
        assert x["ecart"] < 0.02, f"bilan non ferme a {pw} W : {x['ecart']:.1%}"
        print(f"  {pw:4.0f} W : D={d:.4f} Pout={x['p_out']:6.2f} "
              f"Ipk={x['i_pk']:.2f} A Vmin={x['v_min']:+.2f} V "
              f"bouclage {100*x['ecart']:.2f} %")
        cas1.append((pw, d, x, m))
    if cas1:
        print("->", figure_puissance(cas1))

    print("\n=== figure 2 : balayage de l'inductance de maille (20 W) ===")
    POUT_REF = 20.0
    cas2, ref = [], None
    print(f"  {'maille':>7} {'V_pk':>7} {'depass.':>8} {'f_res':>8} "
          f"{'pertes':>8} {'surcout':>8}")
    for lb in g.L_BOUCLES:
        d, x, m = trim(POUT_REF, TRAVAIL / f"lb{lb*1e9:.0f}", l_boucle=lb)
        if x is None:
            print(f"  {lb*1e9:5.0f} nH : ECHEC")
            continue
        assert x["ecart"] < 0.02, f"bilan non ferme a {lb*1e9:.0f} nH"
        # frequence de resonance de la maille avec le Coss, lue sur les
        # deux premiers maxima apres la coupure
        tc = _instant_coupure(m)
        msk = (m["t"] >= tc) & (m["t"] <= tc + 60e-9)
        tt, vv = m["t"][msk], m["V(nsw)"][msk]
        pics = [i for i in range(1, len(vv) - 1)
                if vv[i] > vv[i-1] and vv[i] >= vv[i+1] and vv[i] > 80]
        f_res = 1.0 / (tt[pics[1]] - tt[pics[0]]) if len(pics) >= 2 else float("nan")
        pertes = x["pertes_spice"] * 1e3
        ref = pertes if ref is None else ref
        print(f"  {lb*1e9:5.0f} nH {x['v_pk']:6.1f} V {x['v_pk']-80:7.1f} V "
              f"{f_res/1e6:7.1f}M {pertes:7.1f}m {pertes-ref:+7.1f}m")
        cas2.append((lb, x, m))
    if cas2:
        print("->", figure_boucle(cas2, POUT_REF))
