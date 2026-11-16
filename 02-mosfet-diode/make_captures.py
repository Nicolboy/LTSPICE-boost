"""Captures 3D du chapitre 2 etendu, depuis le CSV du balayage.

Vue 3/4 tournee de 180 degres autour de l'axe Z vertical par rapport a la
vue par defaut : on regarde la surface depuis le coin (haute frequence,
faible puissance), ce qui place au premier plan le coin ou les pertes de
commutation dominent -- justement celui qui separe les pieces.

Deux couples retenus :
  SOT-223 (FDT86113LZ, Coss 46 pF)  -- le plus petit Coss du lot
  EPC2052 (GaN, Coss 195 pF)        -- le GaN le plus performant en conduction
croises avec les deux diodes (Schottky et ultrafast PN).

Echelle de couleur COMMUNE a tous les panneaux d'une figure : sans cela
deux surfaces tres inegales se ressemblent, et la vue ment.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ICI = Path(__file__).resolve().parent
CSV = ICI / "results" / "stage1_dpt_sweep.csv"
DEST = ICI / "illustrations"

BG, GRILLE, TXT, TXT2 = "#11141a", "#2b3240", "#e6e9ef", "#9aa4b5"
CMAP = LinearSegmentedColormap.from_list(
    "pertes", ["#3ddc84", "#ffb13d", "#ff6b6b"])
# rendement : plus c est haut mieux c est -> palette inversee, pour que le
# vert reste "bon" SANS toucher aux donnees (sinon la barre de couleur ment)
CMAP_ETA = LinearSegmentedColormap.from_list(
    "rendement", ["#ff6b6b", "#ffb13d", "#3ddc84"])
ELEV, AZIM = 28, 120          # 3/4 tourne de 180 deg (defaut matplotlib : -60)

COUPLES = [("FDT86113LZ", "Schottky"), ("FDT86113LZ", "Ultrafast"),
           ("EPC2052", "Schottky"), ("EPC2052", "Ultrafast")]
NOMS = {"FDT86113LZ": "Si SOT-223 · FDT86113LZ · Coss 46 pF",
        "EPC2052": "GaN BGA · EPC2052 · Coss 195 pF"}


def charge():
    rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
    fsw = sorted({float(r["fsw_khz"]) for r in rows})
    pout = sorted({float(r["pout_w"]) for r in rows})
    idx = {(r["switch"], r["diode"], float(r["fsw_khz"]), float(r["pout_w"])): r
           for r in rows}
    return fsw, pout, idx


def maille(idx, sw, dio, fsw, pout, cle, mult=1.0):
    z = np.full((len(pout), len(fsw)), np.nan)
    for i, p in enumerate(pout):
        for j, f in enumerate(fsw):
            r = idx.get((sw, dio, f, p))
            if r:
                z[i, j] = float(r[cle]) * mult
    return z


def figure(idx, fsw, pout, cle, mult, titre, unite, nom, vmin=None, vmax=None,
           eta=False):
    grilles = {c: maille(idx, c[0], c[1], fsw, pout, cle, mult) for c in COUPLES}
    tous = np.concatenate([g[~np.isnan(g)] for g in grilles.values()])
    lo = vmin if vmin is not None else float(np.nanmin(tous))
    hi = vmax if vmax is not None else float(np.percentile(tous, 95))
    norme = Normalize(lo, hi)
    cmap = CMAP_ETA if eta else CMAP

    X, Y = np.meshgrid(np.arange(len(fsw)), np.arange(len(pout)))
    fig = plt.figure(figsize=(14, 10.4), dpi=150, facecolor=BG)
    fig.suptitle(titre, color=TXT, fontsize=15, fontweight=650, y=0.975)
    fig.text(0.5, 0.937, f"vue 3/4 tournée de 180° · échelle commune aux "
             f"quatre panneaux · {unite}", color=TXT2, fontsize=11,
             ha="center")

    for k, c in enumerate(COUPLES):
        ax = fig.add_subplot(2, 2, k + 1, projection="3d")
        ax.set_facecolor(BG)
        z = grilles[c]
        zc = np.clip(z, lo, hi)
        cols = cmap(norme(zc))
        # facecolors et edgecolors s'excluent dans plot_surface : la grille
        # est donc ajoutee a part, en fil de fer par-dessus
        ax.plot_surface(X, Y, zc, facecolors=cols, rstride=1, cstride=1,
                        linewidth=0, antialiased=True, shade=False)
        ax.plot_wireframe(X, Y, zc, rstride=1, cstride=1,
                          color="#0d1016", linewidth=0.45)
        # cellules absentes, marquees au sol
        for i in range(len(pout)):
            for j in range(len(fsw)):
                if np.isnan(z[i, j]):
                    ax.scatter([j], [i], [lo], marker="x", s=42,
                               c="#7a8398", linewidths=1.6)
        ax.view_init(elev=ELEV, azim=AZIM)
        ax.set_xticks(range(len(fsw)))
        ax.set_xticklabels([f"{f:.0f}k" for f in fsw], fontsize=8.5)
        ax.set_yticks(range(len(pout)))
        ax.set_yticklabels([f"{p:.0f}W" for p in pout], fontsize=8.5)
        ax.set_zlim(lo, hi)
        ax.tick_params(colors=TXT2, labelsize=8.5)
        for a in (ax.xaxis, ax.yaxis, ax.zaxis):
            a.pane.set_facecolor(BG)
            a.pane.set_edgecolor(GRILLE)
            a._axinfo["grid"]["color"] = GRILLE
        ax.set_title(f"{NOMS[c[0]]}\ndiode {c[1]}", color=TXT, fontsize=10.5,
                     pad=4, fontweight=600)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norme)
    cb = fig.colorbar(sm, ax=fig.axes, shrink=0.55, pad=0.02, aspect=28)
    cb.set_label(unite, color=TXT2, fontsize=10)
    cb.ax.tick_params(colors=TXT2, labelsize=9)
    cb.outline.set_edgecolor(GRILLE)

    p = DEST / nom
    fig.savefig(p, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    print(f"  {p.name}  ({p.stat().st_size // 1024} ko)")
    return grilles


if __name__ == "__main__":
    DEST.mkdir(parents=True, exist_ok=True)
    fsw, pout, idx = charge()
    print(f"grille {len(fsw)} frequences x {len(pout)} puissances\n")

    figure(idx, fsw, pout, "p_total", 1e3,
           "Perte totale — SOT-223 contre GaN EPC2052, deux diodes",
           "perte totale [mW]", "20-captures-perte-totale.png")
    figure(idx, fsw, pout, "eta_pct", 1.0,
           "Rendement — SOT-223 contre GaN EPC2052, deux diodes",
           "rendement η [%] (fenêtre 90-99 : 85-100 aplatirait les écarts)",
           "21-captures-rendement.png",
           vmin=90.0, vmax=99.0, eta=True)
    figure(idx, fsw, pout, "p_cond_diode", 1e3,
           "Perte de la diode seule — Schottky contre ultrafast PN",
           "perte diode [mW]", "22-captures-perte-diode.png")
