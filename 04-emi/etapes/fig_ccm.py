"""8 W en DCM contre 40 W en CCM -- deux machines, pas deux points.

CE QUI A CHANGE DANS LE BANC, et pourquoi il fallait le changer avant de
lancer. La sortie raide est legitime en DCM, ou Ipk = Vin.D.T/L ne depend
pas de Vout. En CCM le courant vaut [Vin - (1-D).Vout] / R_boucle : une
soustraction de grands nombres divisee par 50 mohms, et 0,4 % de rapport
cyclique le fait passer de 0 a 4,8 A. Sur une charge RESISTIVE, le meme
ecart ne deplace Vout que de 1,9 V -- le fil du rasoir n'etait pas le CCM,
c'etait la source raide.

CE QUI A ETE VERIFIE PLUTOT QUE SUPPOSE
  etablissement   600 periodes = 8,5 R.C ; a 200 periodes Vout derivait
                  encore de 378 mV sur la fenetre de mesure
  rapport cyclique  estime a 0,7527 par D = 1 - (Vin - I.Rb)/(Vout + Vf),
                  une iteration de Newton donne 0,750929 et Vout = 80,001 V
  Cout            2,2 uF contre 10 uF : 999,30 contre 999,19 mW, soit
                  0,01 % -- le choix de banc ne deplace pas le resultat
  inductance      I crete 2,845 A contre Isat = 4,4 A, 35 % de marge
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
sys.path.insert(0, str(ICI.parents[2] / ".claude/skills/sim-commun"))
from simcommun.lecture import lire                           # noqa: E402

plt.style.use("dark_background")
F, G, V = "#11141a", "#171b23", "#9aa4b5"
BL, VE, OR, RO, MA = "#4dabf7", "#51cf66", "#ffa94d", "#ff6b6b", "#cc8fff"

CAS = (("s3.raw", "8 W — DCM", BL, 19.0, None, 96.31, 298.69),
       ("c40.raw", "40 W — CCM", OR, 20.0, 160.0, 97.55, 999.30))
# (element, 8 W, 40 W)
PERTES = (("$R_p$ inductance", 139.30, 164.86),
          ("MOSFET", 89.36, 414.81),
          ("diode", 65.16, 367.49),
          ("$R_s$ + $R_c$", 4.87, 52.14))


def pose(a):
    a.set_facecolor(G)
    a.grid(alpha=.16, color=V, lw=.6)
    a.tick_params(colors=V, labelsize=8.5)
    for s in a.spines.values():
        s.set_color("#2b3240")


def main() -> int:
    fig = plt.figure(figsize=(15.4, 9.6), facecolor=F)
    gs = fig.add_gridspec(2, 3, width_ratios=[1.25, 1.25, 1.05],
                          hspace=.34, wspace=.26, left=.058, right=.983,
                          top=.822, bottom=.082)

    for k, (f, lib, c, vin, rl, rend, pert) in enumerate(CAS):
        r = lire(str(ICI / f))
        t = np.asarray(r.x)
        vg = np.asarray(r.trace("V(ng)")).real
        mo = np.where((vg[:-1] < 5.0) & (vg[1:] >= 5.0))[0]
        sl = slice(mo[-3], mo[-1] + 1)
        tt = (t[sl] - t[sl][0]) * 1e6
        g = lambda n: np.asarray(r.trace(n)).real[sl]
        il, vs = g("I(L1)"), g("V(nsw)")

        a = fig.add_subplot(gs[0, k])
        pose(a)
        a.plot(tt, il, color=c, lw=1.6)
        a.fill_between(tt, 0, il, color=c, alpha=.16)
        a.axhline(0, color=RO, ls="--", lw=1.0)
        a.axhline(4.4, color=RO, ls=":", lw=1.2)
        a.text(.02, 4.4, " $I_{sat}$ = 4,4 A", color=RO, fontsize=8.2,
               va="bottom", transform=a.get_yaxis_transform())
        a.set_ylim(-0.45, 5.0)
        a.set_xlabel("temps  [µs]", color=V, fontsize=9)
        if k == 0:
            a.set_ylabel("courant inductance  I(L1)  [A]", color=V,
                         fontsize=9.5)
        a.set_title(lib, color=c, fontsize=12.5, pad=11, weight="bold")
        etat = ("le courant S'ANNULE à chaque période"
                if il.min() < .05 else "le courant NE S'ANNULE JAMAIS")
        a.text(.5, .95, f"$I_{{crête}}$ {il.max():.3f} A   "
               f"$I_{{min}}$ {il.min():+.3f} A\n{etat}\n"
               f"marge sur $I_{{sat}}$ : {100*(4.4-il.max())/4.4:.0f} %",
               transform=a.transAxes, ha="center", va="top", color=V,
               fontsize=8.6, linespacing=1.6)

        a = fig.add_subplot(gs[1, k])
        pose(a)
        a.plot(tt, vs, color=c, lw=1.4)
        a.axhline(80, color=VE, ls=":", lw=1.0)
        a.axhline(150, color=RO, ls="--", lw=1.2)
        a.text(.02, 150, " calibre 150 V", color=RO, fontsize=8.2,
               va="bottom", transform=a.get_yaxis_transform())
        a.set_ylim(-18, 168)
        a.set_xlabel("temps  [µs]", color=V, fontsize=9)
        if k == 0:
            a.set_ylabel("nœud de commutation  [V]", color=V, fontsize=9.5)
        a.text(.5, .94, f"max {vs.max():.1f} V   —   "
               f"{100*(150-vs.max())/150:.0f} % de marge",
               transform=a.transAxes, ha="center", va="top", color=VE,
               fontsize=9, weight="bold")

    # --- le bilan s'inverse -------------------------------------------
    a = fig.add_subplot(gs[:, 2])
    pose(a)
    y = np.arange(len(PERTES))[::-1]
    h = .36
    for i, (nom, p8, p40) in enumerate(PERTES):
        a.barh(y[i] + h / 2, 100 * p8 / 298.69, h, color=BL, edgecolor=F)
        a.barh(y[i] - h / 2, 100 * p40 / 999.30, h, color=OR, edgecolor=F)
        a.text(100 * p8 / 298.69 + 1.5, y[i] + h / 2, f"{p8:.0f} mW",
               va="center", color=BL, fontsize=8.2)
        a.text(100 * p40 / 999.30 + 1.5, y[i] - h / 2, f"{p40:.0f} mW",
               va="center", color=OR, fontsize=8.2)
    a.set_yticks(y)
    a.set_yticklabels([p[0] for p in PERTES], fontsize=9.5)
    a.set_xlim(0, 68)
    a.set_xlabel("part des pertes  [%]", color=V, fontsize=9.5)
    a.grid(False, axis="y")
    a.set_title("LE BILAN S'INVERSE", color="#e6e9ef", fontsize=12,
                pad=11, weight="bold")
    a.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=BL),
                      plt.Rectangle((0, 0), 1, 1, color=OR)],
             labels=["8 W — DCM, 299 mW", "40 W — CCM, 999 mW"],
             fontsize=8.4, facecolor=G, edgecolor="#2b3240", labelcolor=V,
             loc="lower right")
    a.text(.97, .42, "les semiconducteurs portent\n51 % à 8 W, 78 % à 40 W\n\n"
           "le $R_p$ de l'inductance dissipe\nla sonnerie de TEMPS MORT —\n"
           "en CCM il n'y en a plus",
           transform=a.transAxes, ha="right", va="top", color=V,
           fontsize=8.4, linespacing=1.6)

    fig.text(.5, .958, "8 W EN DCM CONTRE 40 W EN CCM — DEUX MACHINES, "
             "PAS DEUX POINTS", ha="center", color="#e6e9ef", fontsize=14,
             weight="bold")
    fig.text(.5, .922, "frontière à 15,3 W · charge résistive 160 Ω · "
             "$C_{out}$ 2,2 µF · 600 périodes d'établissement = 8,5 $R\\!\\cdot\\!C$ · "
             "$V_{out}$ = 80,001 V après une itération de Newton",
             ha="center", color=V, fontsize=9.4)
    fig.text(.5, .028, "RENDEMENT 96,31 % à 8 W  →  97,55 % à 40 W. "
             "Les pertes de sonnerie, quasi fixes, s'amortissent sur cinq "
             "fois plus de puissance.   ·   $C_{out}$ 2,2 contre 10 µF : "
             "999,30 contre 999,19 mW, soit 0,01 % — le choix de banc ne "
             "déplace pas le résultat.", ha="center", color=VE, fontsize=9)
    plt.savefig(ICI / "ccm40.png", dpi=104, facecolor=F)
    print("  ccm40.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
