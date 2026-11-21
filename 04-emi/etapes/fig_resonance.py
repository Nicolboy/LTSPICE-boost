"""La résonance haute fréquence pendant la conduction du MOSFET.

Le concepteur a relevé trois régimes sur le courant de diode. Le troisième
est le moins intuitif : une oscillation rapide ALORS QUE LE MOSFET CONDUIT,
donc alors que la diode est bloquée et ne transfère aucune énergie.

CE N'EST PAS LA BOUCLE QU'ON SUPPOSE. L'inductance principale de 47 µH n'y
est pour rien : à 237 MHz elle présente 70 kΩ, elle se comporte en source
de courant. La preuve est directe — les étapes 0 et 1 donnent EXACTEMENT la
même fréquence, 465,9 MHz, alors que l'inductance passe d'une L pure au
modèle Coilcraft complet. Seul le changement de DIODE déplace la raie.

La maille est petite et parasite :

    masse -> canal du MOSFET (Ron) -> nsw -> Lb (maille) -> nda
          -> Cj de la diode BLOQUÉE -> nout -> source raide -> masse

soit un RLC série dont L est l'inductance de routage et C la capacité de
jonction. Excitation : le saut de V(nsw) à la fermeture.

VÉRIFIÉ PAR TROIS VOIES INDÉPENDANTES
  1. f suit 1/(2.pi.sqrt(Lb.Cj)) sur 16x de plage de Lb, écart +2 %
  2. l'amplitude suit deltaV.sqrt(Cj/Lb), soit deltaV / Z0
  3. le deltaV déduit de I.Z0 retrouve le V(nsw) mesuré avant le front
     à 1 % près sur l'étape 1
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
from matplotlib.patches import FancyBboxPatch                # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parents[2] / ".claude/skills/sim-commun"))
from simcommun.lecture import lire                           # noqa: E402

plt.style.use("dark_background")
F, G, V = "#11141a", "#171b23", "#9aa4b5"
OR, VE, BL, RO, MA = "#f0b23d", "#54d6a0", "#4d9fff", "#ff6b6b", "#c58bff"

# relevés du balayage de maille, étape 2 (V8PA22), dtmax = 0,1 ns
LBS = np.array([2.5, 5.0, 10.0, 20.0, 40.0]) * 1e-9
FM = np.array([481.3, 342.1, 242.3, 171.2, 121.2]) * 1e6
AM = np.array([871.0, 636.0, 453.0, 325.0, 236.0])          # mA
CJ, DV = 45.19e-12, 6.5


def pose(a):
    a.set_facecolor(G)
    a.grid(alpha=.16, color=V, lw=.6)
    a.tick_params(colors=V, labelsize=8.5)
    for s in a.spines.values():
        s.set_color("#2b3240")


def ticks_lb(a):
    """Graduations EXPLICITES sur l'axe des mailles.

    Les graduations mineures que matplotlib pose d'office sur un axe
    logarithmique se chevauchaient au point d'etre illisibles -- une
    figure qu'on ne peut pas lire ne demontre rien.
    """
    a.set_xticks(LBS * 1e9)
    a.set_xticklabels([f"{x:g}" for x in LBS * 1e9])
    a.set_xticks([], minor=True)
    a.set_xlim(2.0, 50.0)


def main() -> int:
    fig = plt.figure(figsize=(15.5, 10.6), facecolor=F)
    gs = fig.add_gridspec(2, 3, height_ratios=[1.12, 1], hspace=.36,
                          wspace=.27, left=.058, right=.983, top=.872,
                          bottom=.078)

    # A — les trois régimes, relevés sur l'étape 2
    r = lire(str(ICI / "s2.raw"))
    t = np.asarray(r.x)
    vg = np.asarray(r.trace("V(ng)")).real
    mo = np.where((vg[:-1] < 2.5) & (vg[1:] >= 2.5))[0]
    sl = slice(mo[-3], mo[-2] + 1)
    tt = (t[sl] - t[sl][0]) * 1e6
    idd = np.asarray(r.trace("I(Vd)")).real[sl]
    ferme = vg[sl] > 2.5

    a = fig.add_subplot(gs[0, :2])
    pose(a)
    a.axvspan(tt[ferme][0], tt[ferme][-1], color=BL, alpha=.10)
    a.plot(tt, idd, color=VE, lw=1.45)
    a.fill_between(tt, 0, idd, where=idd > .02, color=VE, alpha=.20)
    a.axhline(0, color="#49546a", lw=.9)
    a.set_ylim(-.78, 1.95)
    a.set_xlim(0, tt[-1])
    a.set_xlabel("temps  [µs]", color=V, fontsize=9)
    a.set_ylabel("courant diode  I(Vd)  [A]", color=V, fontsize=9.5)
    an = dict(fontsize=8.5, va="top", linespacing=1.5)
    a.text(.015, .975, "3   MOSFET FERMÉ\n237 MHz\nmaille $L_b$ – $C_j$\n"
           "courant de DÉPLACEMENT\ndans la diode bloquée",
           transform=a.transAxes, color=BL, **an)
    a.text(.335, .975, "1   TRANSFERT\nla diode conduit\ndécroissance "
           "linéaire\nde pente $(V_{out}-V_{in})/L$", transform=a.transAxes,
           color=VE, **an)
    a.text(.615, .975, "2   TEMPS MORT\n~3 MHz\nmaille 47 µH – $C_{noeud}$\n"
           "amortie par $R_p$ = 7,3 kΩ", transform=a.transAxes, color=MA, **an)
    a.set_title("LES TROIS RÉGIMES DU COURANT DE DIODE — étape 2, V8PA22",
                color="#e6e9ef", fontsize=12, pad=11, weight="bold")

    # B — la maille résonante
    a = fig.add_subplot(gs[0, 2])
    a.set_facecolor(G)
    a.axis("off")
    a.set_xlim(0, 10)
    a.set_ylim(0, 10)
    a.add_patch(FancyBboxPatch((.4, 1.0), 9.2, 7.9,
                               boxstyle="round,pad=.1", fc="#1d2330",
                               ec=BL, lw=1.6))
    a.text(5, 9.4, "LA MAILLE QUI RÉSONNE", ha="center", color=BL,
           fontsize=10.5, weight="bold")
    for x, y, nom, val, c in (
            (1.5, 7.75, "canal du MOSFET", "$R_{on}$ = 53 mΩ", OR),
            (1.5, 6.30, "maille de routage", "$L_b$ = 10 nH", BL),
            (1.5, 4.85, "jonction de la diode BLOQUÉE", "$C_j$ = 45 pF", VE),
            (1.5, 3.40, "sortie", "source raide, 0 Ω", V)):
        a.plot([1.0], [y], "o", color=c, ms=7, zorder=3)
        a.text(x, y + .26, nom, color="#e6e9ef", fontsize=8.5, va="center")
        a.text(x, y - .36, val, color=c, fontsize=8.5, va="center")
    a.plot([1.0, 1.0], [3.40, 7.75], color="#39445a", lw=1.4, zorder=1)
    a.text(5, 2.30, r"$f_0 = 1/2\pi\sqrt{L_b C_j}$ = 237 MHz", ha="center",
           color="#e6e9ef", fontsize=10.5)
    a.text(5, 1.72, r"$Z_0 = \sqrt{L_b/C_j}$ = 14,9 Ω", ha="center",
           color="#e6e9ef", fontsize=10.5)
    a.text(5, 1.22, "les 47 µH ne sont PAS dans cette maille", ha="center",
           color=RO, fontsize=8.6, style="italic")

    lb = np.logspace(np.log10(2e-9), np.log10(5e-8), 90)

    # C — la fréquence suit 1/sqrt(Lb)
    a = fig.add_subplot(gs[1, 0])
    pose(a)
    a.loglog(lb * 1e9, 1 / (2 * np.pi * np.sqrt(lb * CJ)) / 1e6, color=V,
             lw=1.3, ls="--", label=r"$1/2\pi\sqrt{L_b C_j}$, $C_j$ = 45,2 pF")
    a.loglog(LBS * 1e9, FM / 1e6, "o", color=BL, ms=8, label="mesuré")
    a.set_xlabel("inductance de maille  [nH]", color=V, fontsize=9)
    a.set_ylabel("fréquence  [MHz]", color=V, fontsize=9.5)
    ticks_lb(a)
    a.set_yticks([100, 200, 300, 500])
    a.set_yticklabels(["100", "200", "300", "500"])
    a.set_yticks([], minor=True)
    a.legend(fontsize=7.6, facecolor=G, edgecolor="#2b3240", labelcolor=V)
    a.set_title("la loi tient sur 16× de plage, écart +2 %", color=BL,
                fontsize=9.5, pad=8)

    # D — l'amplitude suit deltaV / Z0
    a = fig.add_subplot(gs[1, 1])
    pose(a)
    a.loglog(lb * 1e9, DV * np.sqrt(CJ / lb) * 1e3, color=V, lw=1.3, ls="--",
             label=r"$\Delta V\sqrt{C_j/L_b}$, $\Delta V$ = 6,5 V")
    a.loglog(LBS * 1e9, AM, "o", color=VE, ms=8, label="mesuré")
    a.set_xlabel("inductance de maille  [nH]", color=V, fontsize=9)
    a.set_ylabel("amplitude  [mA]", color=V, fontsize=9.5)
    ticks_lb(a)
    a.set_yticks([200, 300, 500, 900])
    a.set_yticklabels(["200", "300", "500", "900"])
    a.set_yticks([], minor=True)
    a.legend(fontsize=7.6, facecolor=G, edgecolor="#2b3240", labelcolor=V)
    a.set_title("resserrer la maille AUGMENTE le courant", color=VE,
                fontsize=9.5, pad=8)

    # E — l'énergie, invariante
    a = fig.add_subplot(gs[1, 2])
    pose(a)
    e = .5 * CJ * DV ** 2 * 1e9
    a.semilogx(lb * 1e9, np.full_like(lb, e), color=RO, lw=2)
    a.semilogx(LBS * 1e9, .5 * LBS * (AM * 1e-3) ** 2 * 1e9, "o",
               color=RO, ms=8)
    a.set_ylim(0, e * 2.3)
    a.set_xlabel("inductance de maille  [nH]", color=V, fontsize=9)
    a.set_ylabel("énergie de la maille  [nJ]", color=V, fontsize=9.5)
    ticks_lb(a)
    a.text(.5, .84, r"$\frac{1}{2}L_b I^2 = \frac{1}{2}C_j \Delta V^2$"
           f" = {e:.2f} nJ", transform=a.transAxes, ha="center", color=RO,
           fontsize=11)
    a.text(.5, .68, "INVARIANTE", transform=a.transAxes, ha="center",
           color=RO, fontsize=11.5, weight="bold")
    a.text(.5, .20, "le routage ne réduit pas l'énergie,\nil la déplace en "
           "fréquence.\nLes leviers sont $C_j$ et $\\Delta V$.",
           transform=a.transAxes, ha="center", color=V, fontsize=8.7,
           linespacing=1.55)
    a.set_title("l'énergie, elle, ne bouge pas", color=RO, fontsize=9.5, pad=8)

    fig.text(.5, .962, "LA RÉSONANCE HAUTE FRÉQUENCE PENDANT LA CONDUCTION "
             "DU MOSFET", ha="center", color="#e6e9ef", fontsize=14.5,
             weight="bold")
    fig.text(.5, .928, "maille de routage $L_b$ et capacité de jonction de la "
             "diode bloquée $C_j$, excitées par le saut de $V_{nsw}$ à la "
             "fermeture", ha="center", color=V, fontsize=10)
    plt.savefig(ICI / "resonance_hf.png", dpi=104, facecolor=F)
    print("  resonance_hf.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
