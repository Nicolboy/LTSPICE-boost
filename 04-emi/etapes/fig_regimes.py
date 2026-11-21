"""Où part la puissance, régime par régime.

Chiffres relevés par `bilan_regimes.py`. Les totaux par étape retrouvent
exactement ceux de `valide.py` (81,84 / 206,06 / 285,31 mW) : le découpage
est exhaustif et disjoint, il ne perd ni ne double rien.

CE QUE LA FIGURE MONTRE, et qui n'était pas prévu : à l'étape 2, le TEMPS
MORT coûte plus cher que le TRANSFERT. 46 % des pertes se font pendant le
quart de période où le convertisseur ne transfère rien.

La résonance HF, elle, pèse 0,09 % du total. Elle n'est pas un problème
thermique -- c'est un problème de spectre, et il se jugera à l'étape 5.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent

plt.style.use("dark_background")
F, G, V = "#11141a", "#171b23", "#9aa4b5"
VE, MA, BL, RO = "#54d6a0", "#c58bff", "#4d9fff", "#ff6b6b"

ETAPES = ("ÉTAPE 0\ntout idéal", "ÉTAPE 1\n+ SER2211", "ÉTAPE 2\n+ V8PA22")
# [transfert, temps mort, conduction] en mW
PERTES = np.array([[50.08, 6.71, 25.06],
                   [139.08, 20.20, 46.79],
                   [109.91, 131.87, 43.54]])
DUREE = np.array([[18.1, 25.4, 56.5],
                  [17.4, 26.1, 56.5],
                  [17.7, 25.8, 56.5]])
HF = np.array([0.408, 0.387, 0.255])            # résonance Lb-Cj, mW
# détail par élément, étape 2 : (nom, transfert, temps mort, conduction)
DETAIL2 = (("$R_p$ inductance", 91.37, 75.17, 27.75, MA),
           ("diode", 14.42, 53.96, -1.92, VE),
           ("MOSFET", 1.14, 0.64, 14.68, "#f0b23d"),
           ("$R_s$ + $R_c$", 2.98, 2.10, 3.02, V))
REG = ("1  transfert", "2  temps mort", "3  conduction")
COUL = (VE, MA, BL)


def pose(a):
    a.set_facecolor(G)
    a.grid(alpha=.16, color=V, lw=.6, axis="y")
    a.tick_params(colors=V, labelsize=8.5)
    for s in a.spines.values():
        s.set_color("#2b3240")


def main() -> int:
    fig = plt.figure(figsize=(15.0, 8.4), facecolor=F)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 1, 1.15], wspace=.28,
                          left=.058, right=.982, top=.835, bottom=.095)

    # A — pertes empilées par régime
    a = fig.add_subplot(gs[0, 0])
    pose(a)
    x = np.arange(3)
    bas = np.zeros(3)
    for k in range(3):
        a.bar(x, PERTES[:, k], .58, bottom=bas, color=COUL[k], label=REG[k],
              edgecolor=F, lw=1.2)
        for i in range(3):
            if PERTES[i, k] > 14:
                a.text(i, bas[i] + PERTES[i, k] / 2,
                       f"{PERTES[i, k]:.0f}\n{100*PERTES[i,k]/PERTES[i].sum():.0f} %",
                       ha="center", va="center", color="#11141a", fontsize=8.6,
                       weight="bold")
        bas += PERTES[:, k]
    for i in range(3):
        a.text(i, bas[i] + 7, f"{bas[i]:.0f} mW", ha="center",
               color="#e6e9ef", fontsize=9.5, weight="bold")
    a.set_xticks(x)
    a.set_xticklabels(ETAPES, fontsize=9)
    a.set_ylabel("pertes  [mW]", color=V, fontsize=10)
    a.set_ylim(0, 325)
    a.legend(fontsize=8.5, facecolor=G, edgecolor="#2b3240", labelcolor=V,
             loc="upper left")
    a.set_title("OÙ PART LA PUISSANCE", color="#e6e9ef", fontsize=11.5,
                pad=11, weight="bold")

    # B — pertes rapportées à la durée du régime
    a = fig.add_subplot(gs[0, 1])
    pose(a)
    dens = PERTES / (DUREE / 100.0)
    w = .26
    for k in range(3):
        a.bar(x + (k - 1) * w, dens[:, k], w * .92, color=COUL[k],
              edgecolor=F, lw=1.1)
    a.set_xticks(x)
    a.set_xticklabels(ETAPES, fontsize=9)
    a.set_ylabel("puissance instantanée moyenne  [mW]", color=V, fontsize=10)
    a.set_title("rapportée à la DURÉE du régime", color="#e6e9ef",
                fontsize=11.5, pad=11, weight="bold")
    a.set_ylim(0, 1020)
    # CE PANNEAU CORRIGE UNE CONCLUSION FAUSSE. Lue sur le panneau de
    # gauche seul, l'étape 2 donne « le temps mort coûte plus que le
    # transfert » -- 132 contre 110 mW. Rapporté à la durée, c'est
    # l'inverse : 511 contre 621 mW. Le temps mort coûte plus cher parce
    # qu'il DURE plus longtemps, pas parce qu'il dissipe plus fort.
    a.text(.5, .975, "le temps mort coûte plus cher en absolu\nparce qu'il "
           "DURE plus longtemps —\nrapporté au temps, c'est le transfert\nqui "
           "dissipe le plus fort", transform=a.transAxes, ha="center",
           va="top", color=V, fontsize=8.6, linespacing=1.6)

    # C — détail de l'étape 2, l'étape réelle
    a = fig.add_subplot(gs[0, 2])
    pose(a)
    y = np.arange(len(DETAIL2))[::-1]
    for i, (nom, tr, mo, co, c) in enumerate(DETAIL2):
        yy = y[i]
        g0 = 0.0
        for val, cc in ((tr, VE), (mo, MA), (co, BL)):
            a.barh(yy, val, .56, left=g0, color=cc, edgecolor=F, lw=1.1)
            if abs(val) > 20:
                a.text(g0 + val / 2, yy, f"{val:.0f}", ha="center",
                       va="center", color="#11141a", fontsize=8.6,
                       weight="bold")
            g0 += val
        a.text(g0 + 4, yy, f"{tr+mo+co:.0f} mW", va="center", color="#e6e9ef",
               fontsize=9)
    a.set_yticks(y)
    a.set_yticklabels([d[0] for d in DETAIL2], fontsize=9.5)
    a.set_xlabel("pertes  [mW]", color=V, fontsize=10)
    a.set_xlim(-8, 235)
    a.grid(alpha=.16, color=V, lw=.6, axis="x")
    a.grid(False, axis="y")
    a.set_title("ÉTAPE 2, par élément", color="#e6e9ef", fontsize=11.5,
                pad=11, weight="bold")
    a.text(.97, .14, "la diode dissipe 54 mW\nALORS QU'ELLE EST BLOQUÉE",
           transform=a.transAxes, ha="right", color=VE, fontsize=8.8,
           linespacing=1.5)

    fig.text(.5, .955, "LE BILAN DE PUISSANCE, RÉGIME PAR RÉGIME",
             ha="center", color="#e6e9ef", fontsize=14.5, weight="bold")
    fig.text(.5, .918, "découpage exhaustif et disjoint — chaque total "
             "retrouve celui de la validation, à la dernière décimale",
             ha="center", color=V, fontsize=9.6)
    fig.text(.5, .030, f"La résonance HF $L_b$–$C_j$ pèse "
             f"{HF[2]:.2f} mW, soit {100*HF[2]/PERTES[2].sum():.2f} % du "
             f"total de l'étape 2. Vérifiée par deux voies indépendantes, "
             f"1 % d'écart sur l'étape 1. Ce n'est pas un problème "
             f"thermique.", ha="center", color=RO, fontsize=9.4)
    plt.savefig(ICI / "regimes.png", dpi=104, facecolor=F)
    print("  regimes.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
