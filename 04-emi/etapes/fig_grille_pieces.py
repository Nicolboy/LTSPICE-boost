"""Deux choses a montrer : le balayage de grille, et l'ecart entre les
deux pieces -- celle que je simule et celle qui sera montee.

LE BALAYAGE. J'avais annonce un compromis entre surtension et pertes de
commutation. Il n'existe pas : V(nsw) varie de 0,2 V sur une plage de
21x. L'ecretage vient de la diode de CORPS, qui se moque de la vitesse.

LES DEUX PIECES. Je simule l'IPD530N15N3, dont je n'ai PAS la fiche. Le
prototype sera monte avec le FDD770N15A, dont j'ai la fiche mais dont le
modele cree 76,8 mW et ne peut pas servir a une etude de pertes.

La methode d'extraction a ete ETALONNEE sur la piece connue :
    Coss a 75 V   66,6 pF extraits contre 64 typ   -> +4 %
    Qg a 10 V      8,57 nC extraits contre 8,4 typ -> +2 %
    Qoss a 37,5 V  7,6 nC extraits contre 14 typ   -> -46 %

Les deux premieres valident la methode. La troisieme dit que le modele
sous-estime la capacite a BASSE tension d'un facteur 1,8 -- et en DCM le
noeud de commutation y sejourne pendant tout le temps mort.
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

# balayage de grille, duty 0,588, .options cshunt=1e-15
RG = np.array([2.2, 4.7, 10.0, 22.0, 47.0])
MOS = np.array([89.05, 87.95, 89.39, 92.64, 107.16])
VMAX = np.array([81.8, 81.9, 81.9, 82.0, 82.0])
TOT = np.array([298.79, 297.81, 298.72, 302.30, 319.24])
REND = np.array([96.32, 96.31, 96.31, 96.28, 96.16])

# LES DEUX FICHES EN MAIN. Plus aucune valeur extraite ici : la fiche
# IPD530N15N3 Rev 2.6 est arrivee, et elle a VALIDE l'extraction a mieux
# qu'un pour cent -- Coss 79,9 contre 80 typ, Qg 8,74 contre 8,7, Qoss
# 22,0 contre 22. La methode etait bonne ; on n'en a plus besoin.
# (grandeur, Infineon typ, Infineon max, onsemi typ, onsemi max, unite)
PIECES = (("$R_{ds(on)}$", 44.0, 53.0, 61.0, 77.0, "mΩ"),
          ("$C_{oss}$ @ 75 V", 80.0, 106.0, 64.0, 85.0, "pF"),
          ("$Q_g$ @ 10 V", 8.7, 12.0, 8.4, 11.0, "nC"),
          ("$Q_{rr}$", 229.0, 229.0, 109.0, 109.0, "nC"))


def pose(a):
    a.set_facecolor(G)
    a.grid(alpha=.16, color=V, lw=.6)
    a.tick_params(colors=V, labelsize=8.5)
    for s in a.spines.values():
        s.set_color("#2b3240")


def main() -> int:
    fig = plt.figure(figsize=(15.2, 8.2), facecolor=F)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1, 1.15], wspace=.30,
                          left=.058, right=.982, top=.825, bottom=.105)

    # A — le compromis qui n'existe pas
    a = fig.add_subplot(gs[0, 0])
    pose(a)
    a.semilogx(RG, VMAX, "o-", color=OR, lw=1.8, ms=8)
    a.axhline(150, color=RO, ls="--", lw=1.2)
    a.axhline(80, color=VE, ls=":", lw=1.0)
    a.set_ylim(60, 162)
    a.set_xticks(RG)
    a.set_xticklabels([f"{x:g}" for x in RG])
    a.set_xticks([], minor=True)
    a.set_xlabel("résistance de grille  [Ω]", color=V, fontsize=9.5)
    a.set_ylabel("$V_{nsw}$ maximum  [V]", color=V, fontsize=10)
    a.text(.5, 150, " calibre 150 V", color=RO, fontsize=8.4, va="bottom",
           transform=a.get_yaxis_transform())
    a.text(.5, 80, " $V_{out}$ = 80 V", color=VE, fontsize=8.4, va="bottom",
           transform=a.get_yaxis_transform())
    a.annotate("", xy=(2.2, 81.8), xytext=(47, 82.0),
               arrowprops=dict(arrowstyle="<->", color=MA, lw=1.4))
    a.text(10, 90, "0,2 V d'écart\nsur une plage de 21×", ha="center",
           color=MA, fontsize=9.5, linespacing=1.5)
    a.set_title("LE COMPROMIS N'EXISTE PAS", color="#e6e9ef", fontsize=11.5,
                pad=11, weight="bold")
    a.text(.5, .055, "l'écrêtage vient de la DIODE DE CORPS,\nqui se moque "
           "de la vitesse de commutation", transform=a.transAxes,
           ha="center", color=V, fontsize=8.4, linespacing=1.5)

    # B — ce que la grille coute vraiment
    a = fig.add_subplot(gs[0, 1])
    pose(a)
    a.semilogx(RG, MOS, "o-", color=BL, lw=1.8, ms=8, label="MOSFET")
    a.semilogx(RG, TOT - MOS, "s--", color=V, lw=1.3, ms=6,
               label="tout le reste")
    a.axvspan(2.0, 10.5, color=VE, alpha=.10)
    a.text(4.6, 200, "équivalents", ha="center", color=VE, fontsize=9,
           weight="bold")
    a.set_xticks(RG)
    a.set_xticklabels([f"{x:g}" for x in RG])
    a.set_xticks([], minor=True)
    a.set_ylim(60, 240)
    a.set_xlabel("résistance de grille  [Ω]", color=V, fontsize=9.5)
    a.set_ylabel("pertes  [mW]", color=V, fontsize=10)
    a.legend(fontsize=8.4, facecolor=G, edgecolor="#2b3240", labelcolor=V,
             loc="center left")
    a.set_title("CE QUE LA GRILLE COÛTE", color="#e6e9ef", fontsize=11.5,
                pad=11, weight="bold")
    a.text(.5, .055, "+20 % sur le MOSFET de 2,2 à 47 Ω —\nles 10 Ω retenus "
           "ont de la marge des deux côtés", transform=a.transAxes,
           ha="center", color=V, fontsize=8.4, linespacing=1.5)

    # C — la piece simulee contre la piece montee
    a = fig.add_subplot(gs[0, 2])
    pose(a)
    y = np.arange(len(PIECES))[::-1]
    for i, (nom, it, im, ot, om, u) in enumerate(PIECES):
        yy = y[i]
        a.barh(yy + .17, 100.0, .32, color=VE, alpha=.60, edgecolor=F)
        if om > ot:
            a.barh(yy + .17, 100 * om / ot - 100, .32, left=100, color=VE,
                   alpha=.25, edgecolor=F)
        a.barh(yy - .19, 100 * it / ot, .32, color=BL, edgecolor=F)
        if im > it:
            a.barh(yy - .19, 100 * (im - it) / ot, .32, left=100 * it / ot,
                   color=BL, alpha=.35, edgecolor=F)
        a.text(100 * max(im, om) / ot + 4, yy,
               f"{it:g}–{im:g}  contre  {ot:g}–{om:g} {u}" if im > it
               else f"{it:g}  contre  {ot:g} {u}",
               va="center", color="#e6e9ef", fontsize=8.2)
    a.axvline(100, color=V, ls=":", lw=1.0)
    a.set_yticks(y)
    a.set_yticklabels([p[0] for p in PIECES], fontsize=10)
    a.set_xlim(0, 310)
    a.set_xlabel("rapport au typique onsemi  [%]", color=V, fontsize=9.5)
    a.grid(False, axis="y")
    a.set_title("SIMULÉE ≠ MONTÉE", color="#e6e9ef", fontsize=11.5,
                pad=11, weight="bold")
    a.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=BL),
                      plt.Rectangle((0, 0), 1, 1, color=VE, alpha=.55),
                      plt.Rectangle((0, 0), 1, 1, color=VE, alpha=.22)],
             labels=["IPD530N15N3 — fiche Rev 2.6",
                     "FDD770N15A — fiche, typique",
                     "jusqu'au maximum"],
             fontsize=7.6, facecolor=G, edgecolor="#2b3240", labelcolor=V,
             loc="lower right")

    fig.text(.5, .955, "LA RÉSISTANCE DE GRILLE, ET L'ÉCART ENTRE LA PIÈCE "
             "SIMULÉE ET CELLE QUI SERA MONTÉE", ha="center",
             color="#e6e9ef", fontsize=13.5, weight="bold")
    fig.text(.5, .918, "méthode d'extraction étalonnée sur la pièce dont j'ai "
             "la fiche : $C_{oss}$ +4 %, $Q_g$ +2 %  —  puis CONFIRMÉE par la "
             "fiche Infineon : $C_{oss}$ −0,1 %, $Q_g$ +0,5 %, $Q_{oss}$ 0,0 %",
             ha="center", color=V, fontsize=9.4)
    fig.text(.5, .030, "CE QUI CHANGE POUR LE PROTOTYPE — l'Infineon stocke "
             "2,1× la charge de recouvrement (229 contre 109 nC). La "
             "simulation est donc le cas PESSIMISTE : la pièce montée "
             "devrait faire un peu mieux.", ha="center", color=VE,
             fontsize=9.2)
    plt.savefig(ICI / "grille_pieces.png", dpi=104, facecolor=F)
    print("  grille_pieces.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
