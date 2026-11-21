"""Le bilan de puissance des quatre etapes, et le detail de la derniere.

POINT RETENU : IPD530N15N3, Rg = 10 ohms, Vgs = 10 V, duty 0,588,
.options cshunt=1e-15 (qui deplace le resultat de 0,03 %, c'est mesure).

CE QUE LE BILAN DIT, et qui n'etait pas prevu : a 8 W en DCM, pres de la
MOITIE des pertes est dans la resistance parallele de l'inductance --
139,30 mW sur 296,25, soit 47 %. Les deux semi-conducteurs reunis en
portent 51 %. Le levier n'est pas la ou on le cherchait.

UNE LIMITE DE LA DECOMPOSITION PAR REGIME. Des qu'un element STOCKE, le
decoupage par regime attribue a la dissipation ce qui n'est que du
transfert d'un regime vers un autre. Le Coss du transistor fait circuler
+188,9 / -131,5 / -57,2 mW entre transfert, temps mort et conduction, qui
se compensent a 0,20 mW sur le cycle. D'ou un S1 a -38,27 mW pendant le
temps mort, qui n'est pas une generation d'energie. Les TOTAUX par element
restent justes ; la repartition par regime ne vaut que pour les elements
purement dissipatifs. Les etapes 0 a 2 n'avaient aucune capacite de noeud,
la faute ne pouvait pas s'y voir.
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
OR, VE, BL, RO, MA = "#f0b23d", "#54d6a0", "#4d9fff", "#ff6b6b", "#c58bff"

ETAPES = ("ÉTAPE 0\ntout idéal", "ÉTAPE 1\n+ SER2211",
          "ÉTAPE 2\n+ V8PA22", "ÉTAPE 3\n+ IPD530N15N3")
PIN = np.array([8.6437, 7.9949, 8.2088, 8.0200])
POUT = np.array([8.5613, 7.7866, 7.9224, 7.7237])
REND = np.array([99.05, 97.39, 96.51, 96.31])
# inductance (Rp+Rs+Rc), MOSFET, diode
DETAIL = np.array([[3.86, 22.11, 55.88],
                   [139.34, 14.89, 51.83],
                   [202.38, 16.46, 66.46],
                   [144.17, 86.91, 65.16]])
NOMS = ("inductance", "MOSFET", "diode")
COUL = (MA, BL, VE)


def pose(a):
    a.set_facecolor(G)
    a.grid(alpha=.16, color=V, lw=.6, axis="y")
    a.tick_params(colors=V, labelsize=8.5)
    for s in a.spines.values():
        s.set_color("#2b3240")


def main() -> int:
    fig = plt.figure(figsize=(15.2, 8.6), facecolor=F)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.3, 1, 1], wspace=.27,
                          left=.058, right=.982, top=.820, bottom=.125)

    # A — les quatre etapes
    a = fig.add_subplot(gs[0, 0])
    pose(a)
    x = np.arange(4)
    bas = np.zeros(4)
    for k in range(3):
        a.bar(x, DETAIL[:, k], .60, bottom=bas, color=COUL[k], label=NOMS[k],
              edgecolor=F, lw=1.2)
        for i in range(4):
            if DETAIL[i, k] > 22:
                a.text(i, bas[i] + DETAIL[i, k] / 2,
                       f"{DETAIL[i,k]:.0f}\n{100*DETAIL[i,k]/DETAIL[i].sum():.0f} %",
                       ha="center", va="center", color="#11141a",
                       fontsize=8.6, weight="bold")
        bas += DETAIL[:, k]
    for i in range(4):
        a.text(i, bas[i] + 8, f"{bas[i]:.0f} mW", ha="center",
               color="#e6e9ef", fontsize=9.5, weight="bold")
        a.text(i, -30, f"η {REND[i]:.2f} %", ha="center", color=VE,
               fontsize=9, weight="bold")
    a.set_xticks(x)
    a.set_xticklabels(ETAPES, fontsize=8.8)
    a.set_ylabel("pertes  [mW]", color=V, fontsize=10)
    a.set_ylim(0, 345)
    a.legend(fontsize=8.6, facecolor=G, edgecolor="#2b3240", labelcolor=V,
             loc="upper left")
    a.set_title("LES QUATRE ÉTAPES", color="#e6e9ef", fontsize=11.5,
                pad=11, weight="bold")

    # B — le detail de l'etape 3
    a = fig.add_subplot(gs[0, 1])
    pose(a)
    EL = (("$R_p$ inductance", 139.30, MA), ("MOSFET", 86.91, BL),
          ("diode", 65.16, VE), ("$R_s$ inductance", 3.53, V),
          ("$R_c$ inductance", 1.34, "#49546a"))
    y = np.arange(len(EL))[::-1]
    for i, (n, p, c) in enumerate(EL):
        a.barh(y[i], p, .58, color=c, edgecolor=F, lw=1.1)
        a.text(p + 4, y[i], f"{p:.2f} mW   {100*p/296.25:.1f} %",
               va="center", color="#e6e9ef", fontsize=8.8)
    a.set_yticks(y)
    a.set_yticklabels([e[0] for e in EL], fontsize=9.5)
    a.set_xlim(0, 235)
    a.set_xlabel("pertes  [mW]", color=V, fontsize=9.5)
    a.grid(alpha=.16, color=V, lw=.6, axis="x")
    a.grid(False, axis="y")
    a.set_title("ÉTAPE 3, PAR ÉLÉMENT", color="#e6e9ef", fontsize=11.5,
                pad=11, weight="bold")
    a.text(.97, .08, "l'inductance porte 47 %\nles deux semiconducteurs 51 %",
           transform=a.transAxes, ha="right", color=MA, fontsize=9,
           linespacing=1.5)

    # C — les recoupements
    a = fig.add_subplot(gs[0, 2])
    a.set_facecolor(G)
    a.axis("off")
    a.set_xlim(0, 10)
    a.set_ylim(0, 10)
    a.set_title("CE QUI VALIDE LE CHIFFRE", color="#e6e9ef", fontsize=11.5,
                pad=11, weight="bold")
    lig = (("énergie par cycle", "", ""),
           ("  entrée", "40,100 µJ", "8,0200 W"),
           ("  sortie", "38,619 µJ", "7,7237 W"),
           ("  pertes", "1,482 µJ", "296,31 mW"),
           ("", "", ""),
           ("W2  bilan fermé", "somme", "296,25 mW"),
           ("", "résidu", "0,02 %"),
           ("", "", ""),
           ("W1  fenêtre entière", "4 périodes", "5,000 µs"),
           ("", "", ""),
           ("cycle à cycle", "écart-type", "0,000 %"),
           ("", "dérive 7 cycles", "0,000 %"),
           ("", "stockage max", "0,196 nJ"),
           ("", "", ""),
           ("DCM, formule fermée", "40,46 µJ", "écart 4,6 %"),
           ("", "", ""),
           ("grille — budget à part", "du driver", "15,35 mW"))
    for i, (g1, g2, g3) in enumerate(lig):
        yy = 9.4 - i * .55
        gras = g1.startswith(("W", "cycle", "énergie", "DCM", "grille"))
        a.text(.2, yy, g1, color="#e6e9ef" if gras else V,
               fontsize=9 if gras else 8.6,
               weight="bold" if gras else "normal")
        a.text(6.2, yy, g2, color=V, fontsize=8.6, ha="right")
        a.text(9.8, yy, g3, color=VE if g3 else V, fontsize=8.8, ha="right",
               weight="bold" if g3 else "normal")

    fig.text(.5, .955, "BILAN DE PUISSANCE — 19 V → 80 V, 7,72 W, 200 kHz, DCM",
             ha="center", color="#e6e9ef", fontsize=14, weight="bold")
    fig.text(.5, .918, "IPD530N15N3 · $R_g$ = 10 Ω · $V_{gs}$ = 10 V · "
             "SER2211-473 47 µH · V8PA22 · maille 10 nH",
             ha="center", color=V, fontsize=9.6)
    fig.text(.5, .030, "RÉSERVE — dès qu'un élément STOCKE, la répartition par "
             "régime n'a plus de sens : le $C_{oss}$ fait circuler "
             "+189 / −131 / −57 mW entre transfert, temps mort et conduction. "
             "Les totaux par élément, eux, restent justes.",
             ha="center", color=RO, fontsize=9)
    plt.savefig(ICI / "bilan.png", dpi=104, facecolor=F)
    print("  bilan.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
