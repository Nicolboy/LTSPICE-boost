"""Surfaces 3D isometriques : dV = f(Rg, L_boucle), quatre combinaisons.

Meme convention que les surfaces du chapitre 2 (`make_captures.py`) : vue
trois quarts tournee de 180 degres, echelle de couleur COMMUNE aux quatre
panneaux, mailles absentes marquees au sol.

CE QUE LA COULEUR DIT. Elle code la surtension, comme le relief -- mais la
redondance est voulue : sur une vue isometrique, un panneau peut cacher son
propre relief. La couleur reste lisible de face.

LES ZONES ECRETEES SONT MARQUEES. Une Schottky 200 V en avalanche ne mesure
plus son pic : elle mesure son claquage. Ces mailles portent un point noir,
et leur altitude est un PLANCHER, pas une valeur.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RES, ILL = ICI / "results" / "surface", ICI / "illustrations"
ILL.mkdir(exist_ok=True)

RG = (1.0, 2.2, 4.7, 10.0, 22.0, 47.0)
LB = (2e-9, 5e-9, 10e-9, 20e-9, 40e-9)
COMB = (("4u7", "si",  "DCM — V8PA22, Schottky Si 200 V", 220.0),
        ("4u7", "inf", "DCM — IDH04G65C6, SiC 650 V", 650.0),
        ("47u", "si",  "CCM — V8PA22, Schottky Si 200 V", 220.0),
        ("47u", "inf", "CCM — IDH04G65C6, SiC 650 V", 650.0))

BG, GRILLE, TXT, TXT2 = "#11141a", "#2b3240", "#e6e9ef", "#9aa4b5"
ELEV, AZIM = 28, 120          # 3/4 tourne de 180 deg, comme au chapitre 2


def grille(d, ind, dio, champ="dv"):
    z = np.full((len(RG), len(LB)), np.nan)
    ecr = np.zeros_like(z, dtype=bool)
    for i, rg in enumerate(RG):
        for j, lb in enumerate(LB):
            e = d.get(f"{ind}|{dio}|{rg}|{lb}")
            if e:
                z[i, j] = e[champ]
                ecr[i, j] = e["ecrete"]
    return z, ecr


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, Normalize

    d = json.loads((RES / "surface.json").read_text(encoding="utf-8"))
    cmap = LinearSegmentedColormap.from_list(
        "surt", ["#1b4d4b", "#2f8f7a", "#86c66a", "#f2d35a", "#f08a4b",
                 "#e2524f"])

    gs = {(i, dd): grille(d, i, dd) for i, dd, _, _ in COMB}
    tous = np.concatenate([g[~np.isnan(g)] for g, _ in gs.values()])
    lo, hi = 0.0, float(np.nanmax(tous))
    norme = Normalize(lo, hi)

    X, Y = np.meshgrid(np.arange(len(LB)), np.arange(len(RG)))
    fig = plt.figure(figsize=(14.5, 11.0), dpi=150, facecolor=BG)
    fig.suptitle("Surtension inverse sur la diode — surface complète "
                 "$\\Delta V = f(R_g,\\ L_\\sigma)$",
                 color=TXT, fontsize=15.5, fontweight=650, y=0.975)
    fig.text(0.5, 0.936,
             "boost 19 V → 80 V, 47 W, 400 kHz · EPC2207 GaN · "
             "vue 3/4 tournée de 180° · échelle commune aux quatre panneaux",
             color=TXT2, fontsize=10.5, ha="center")

    for k, (ind, dio, titre, vbr) in enumerate(COMB):
        ax = fig.add_subplot(2, 2, k + 1, projection="3d")
        ax.set_facecolor(BG)
        z, ecr = gs[(ind, dio)]
        zc = np.clip(np.nan_to_num(z, nan=lo), lo, hi)
        ax.plot_surface(X, Y, zc, facecolors=cmap(norme(zc)), rstride=1,
                        cstride=1, linewidth=0, antialiased=True, shade=False)
        ax.plot_wireframe(X, Y, zc, rstride=1, cstride=1, color="#0d1016",
                          linewidth=0.45)
        for i in range(len(RG)):
            for j in range(len(LB)):
                if np.isnan(z[i, j]):
                    ax.scatter([j], [i], [lo], marker="x", s=46,
                               c="#7a8398", linewidths=1.6)
                elif ecr[i, j]:
                    # ECRETE : l'altitude est un plancher, pas une mesure
                    ax.scatter([j], [i], [z[i, j]], marker="o", s=30,
                               c="#0d1016", edgecolors="#e2524f",
                               linewidths=1.4, depthshade=False)
        ax.view_init(elev=ELEV, azim=AZIM)
        ax.set_xticks(range(len(LB)))
        ax.set_xticklabels([f"{l*1e9:.0f}" for l in LB], fontsize=8.5)
        ax.set_yticks(range(len(RG)))
        ax.set_yticklabels([f"{r:g}" for r in RG], fontsize=8.5)
        ax.set_xlabel("$L_\\sigma$ (nH)", color=TXT2, fontsize=9.5, labelpad=2)
        ax.set_ylabel("$R_g$ (Ω)", color=TXT2, fontsize=9.5, labelpad=2)
        ax.set_zlim(lo, hi)
        ax.tick_params(colors=TXT2, labelsize=8.5)
        for a in (ax.xaxis, ax.yaxis, ax.zaxis):
            a.pane.set_facecolor(BG)
            a.pane.set_edgecolor(GRILLE)
            a._axinfo["grid"]["color"] = GRILLE
        nav = int(ecr.sum())
        ax.set_title(titre + (f"\n{nav} mailles en AVALANCHE sur {ecr.size}"
                              if nav else "\naucune avalanche"),
                     color=TXT if not nav else "#e2524f", fontsize=10.5,
                     pad=2, fontweight=600)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norme)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=fig.axes, shrink=0.52, aspect=34, pad=0.02)
    cb.set_label("dépassement au-delà des 80 V de sortie (V)", color=TXT2,
                 fontsize=10)
    cb.ax.tick_params(colors=TXT2, labelsize=9)
    cb.outline.set_edgecolor(GRILLE)
    fig.text(0.5, 0.025,
             "● cerclé rouge : diode ÉCRÊTÉE par son claquage — l'altitude "
             "est un plancher, pas une mesure.    ✕ : point non convergé.",
             color=TXT2, fontsize=9.5, ha="center")

    p = ILL / "surtension_surface_3d.png"
    p.unlink(missing_ok=True)
    fig.savefig(p, facecolor=BG)
    print("->", p)

    # ---- lecture chiffree des coins qui nous interessent ----
    print(f"\n{'mode':>5s} {'diode':>5s} {'Rg':>6s} {'Lσ':>6s} "
          f"{'dépass.':>9s} {'dV/dt':>9s} {'état':>12s}")
    for ind, dio, _, vbr in COMB:
        for rg in (10.0, 22.0):
            for lb in (2e-9, 5e-9):
                e = d.get(f"{ind}|{dio}|{rg}|{lb}")
                if not e:
                    continue
                marge = vbr - 80.0 - e["dv"]
                print(f"{ind:>5s} {dio:>5s} {rg:5.0f}Ω {lb*1e9:4.0f}nH "
                      f"{e['dv']:7.1f} V {e['dvdt']:6.1f}V/ns "
                      f"{('AVALANCHE' if e['ecrete'] else f'marge {marge:.0f} V'):>12s}")


if __name__ == "__main__":
    main()
