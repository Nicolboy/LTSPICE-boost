"""Deux graphes : surtension contre vitesse de commutation, contre maille.

    dV = L_maille . di/dt

On porte en ABSCISSE LE di/dt MESURE, pas le reglage de Rg : c'est la
grandeur physique, et elle rend les deux balayages comparables. Les deux
droites de reference tracent L.di/dt avec le L du cas, sans aucun ajustement.

LECTURE OBLIGATOIRE DE LA V8PA22 : elle est ECRETEE a 220,6 V des que le pic
depasse son claquage. Les points plats a 140,6 V de depassement ne sont donc
pas une mesure du pic -- ils sont le niveau d'ecretage, et la puissance
d'avalanche dit ce qui a ete dissipe pour l'obtenir.
"""
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
for q in (ICI, RACINE / ".claude/skills/sim-commun"):
    sys.path.insert(0, str(q))
from simcommun.lecture import lire                        # noqa: E402

RES, ILL = ICI / "results", ICI / "illustrations"
ILL.mkdir(exist_ok=True)
RG = (1.0, 2.2, 4.7, 10.0, 22.0, 47.0)
LB = (2e-9, 5e-9, 10e-9, 20e-9, 40e-9)
LB_REF = 20e-9
DIO = (("sic", "C6D04065A — SiC 650 V", 768.0, "#54d6a0", "o"),
       ("si",  "V8PA22 — Schottky Si 200 V", 220.0, "#ff6b6b", "s"))


def mesure(stem, vbr):
    f = RES / f"{stem}.raw"
    if not f.exists() or f.stat().st_size == 0:
        return None
    r = lire(f)
    t = np.asarray(r.x)
    m = (t >= 20e-6) & (t <= 25e-6)
    t = t[m]
    vda = np.asarray(r.trace("V(nda)")).real[m]
    idio = np.asarray(r.trace("I(Vd)")).real[m]
    vd = vda - 80.0
    pav = np.trapezoid(np.where(vd < -(vbr - 5), -vd * np.abs(idio), 0.0),
                       t) / (t[-1] - t[0]) * 1e3
    dt = np.diff(t)
    b = dt > 0
    didt = np.abs(np.diff(idio)[b] / dt[b]).max() / 1e9
    return dict(dv=-vd.min() - 80.0, vinv=-vd.min(), av=pav, didt=didt,
                ecrete=(-vd.min()) >= vbr - 1.0)


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.style.use("dark_background")

    fig, (ax, bx) = plt.subplots(1, 2, figsize=(14.5, 6.6), dpi=170)
    fig.patch.set_facecolor("#15171c")
    for a in (ax, bx):
        a.set_facecolor("#15171c")
        a.grid(True, which="both", color="#2c3038", lw=0.6, zorder=1)
        a.tick_params(colors="#9aa0a6")

    # ---------- gauche : vitesse de commutation, a maille fixe ----------
    for dio, nom, vbr, col, mk in DIO:
        xs, ys, ec, rgv = [], [], [], []
        for rg in RG:
            e = mesure(f"sur_rg_{dio}_{rg:g}", vbr)
            if not e:
                continue
            xs.append(e["didt"]); ys.append(e["dv"])
            ec.append(e["ecrete"]); rgv.append(rg)
        xs, ys = np.array(xs), np.array(ys)
        ec = np.array(ec)
        ax.plot(xs[~ec], ys[~ec], mk, color=col, ms=8, zorder=4,
                label=nom + " — pic réel")
        if ec.any():
            ax.plot(xs[ec], ys[ec], "x", color=col, ms=10, mew=2.2, zorder=4,
                    label=nom + " — ÉCRÊTÉ (avalanche)")
        o = np.argsort(xs)
        ax.plot(xs[o], ys[o], "-", color=col, lw=1.1, alpha=0.55, zorder=3)
        # Les points a Rg faible se tassent : le di/dt ne bouge presque pas.
        # On etage les etiquettes au lieu de les empiler.
        if dio == "sic":
            for k, (x, y, r) in enumerate(zip(xs, ys, rgv)):
                ax.annotate(f"{r:g} Ω", (x, y), textcoords="offset points",
                            xytext=(7, (-13, 9, -13, 9, -13, 9)[k % 6]),
                            color=col, fontsize=8.2, alpha=0.85)
        else:
            # Les points ecretes se superposent TOUS au meme endroit, et c'est
            # le fait a montrer : de 1 a 22 ohms, ni le di/dt ni le pic ne
            # bougent. Les nommer cinq fois masquerait ce que leur amas dit.
            if ec.any():
                ax.annotate("1 à 22 Ω — aucun effet :" + chr(10)
                            + "le di/dt est celui du" + chr(10)
                            + "recouvrement, pas de la grille",
                            (xs[ec].mean(), ys[ec].mean()),
                            textcoords="offset points", xytext=(-176, 12),
                            color=col, fontsize=8.6,
                            arrowprops=dict(arrowstyle="->", color=col, lw=1.1))
            for x, y, r in zip(xs[~ec], ys[~ec], np.array(rgv)[~ec]):
                ax.annotate(f"{r:g} Ω", (x, y), textcoords="offset points",
                            xytext=(7, -14), color=col, fontsize=8.2)
    xl = np.linspace(0.3, 45, 100)
    ax.plot(xl, LB_REF * xl * 1e9, "--", color="#ffd166", lw=1.6, zorder=2,
            label=r"$\Delta V = L_\sigma\,di/dt$  ($L_\sigma$ = 20 nH)")
    ax.set_xscale("log")
    ax.set_xlabel("di/dt mesuré à la coupure (A/ns)", color="#e8eaed")
    ax.set_ylabel("dépassement au-delà de 80 V (V)", color="#e8eaed")
    ax.set_title("Vitesse de commutation — $R_g$ de 1 à 47 Ω\n"
                 "maille fixée à 20 nH", color="#e8eaed", fontsize=11.5)
    ax.set_ylim(0, 170)

    # ---------- droite : inductance de maille, a Rg fixe ----------
    for dio, nom, vbr, col, mk in DIO:
        xs, ys, ec, lv, dd = [], [], [], [], []
        for lb in LB:
            e = mesure(f"sur_lb_{dio}_{lb*1e9:.0f}n", vbr)
            if not e:
                continue
            xs.append(lb * 1e9); ys.append(e["dv"])
            ec.append(e["ecrete"]); lv.append(lb); dd.append(e["didt"])
        xs, ys, ec = np.array(xs), np.array(ys), np.array(ec)
        bx.plot(xs[~ec], ys[~ec], mk, color=col, ms=8, zorder=4,
                label=nom + " — pic réel")
        if ec.any():
            bx.plot(xs[ec], ys[ec], "x", color=col, ms=10, mew=2.2, zorder=4,
                    label=nom + " — ÉCRÊTÉ (avalanche)")
        o = np.argsort(xs)
        bx.plot(xs[o], ys[o], "-", color=col, lw=1.1, alpha=0.55, zorder=3)
        # L x di/dt, point par point, SANS aucun ajustement
        pred = np.array([l * d * 1e9 for l, d in zip(lv, dd)])
        bx.plot(xs[o], pred[o], ":", color=col, lw=1.8, alpha=0.95, zorder=5,
                label=r"$L_\sigma\times di/dt$ mesuré — " + dio.upper())
    bx.set_xscale("log")
    from matplotlib.ticker import FixedLocator, NullFormatter, NullLocator
    bx.xaxis.set_major_locator(FixedLocator([2, 5, 10, 20, 40]))
    bx.xaxis.set_minor_locator(NullLocator())      # sinon « 3x10^0 » parasite
    bx.xaxis.set_minor_formatter(NullFormatter())
    bx.set_xticklabels(["2", "5", "10", "20", "40"])
    bx.set_xlabel("inductance de maille $L_\\sigma$ (nH)", color="#e8eaed")
    bx.set_title("Inductance de maille — 2 à 40 nH\n"
                 "$R_g$ fixé à 10 Ω", color="#e8eaed", fontsize=11.5)
    bx.set_ylim(0, 170)

    # legende en bas a droite a gauche : le coin haut-gauche porte
    # l'annotation de l'amas ecrete, et la courbe monte vers la droite.
    for a, ou in ((ax, "lower right"), (bx, "upper left")):
        lg = a.legend(loc=ou, facecolor="#1d2026",
                      edgecolor="#2c3038", fontsize=8.6)
        for t in lg.get_texts():
            t.set_color("#e8eaed")
    fig.suptitle("Surtension inverse sur la diode — les deux leviers du concepteur\n"
                 "boost 19 V → 80 V, 47 W, 400 kHz · SER2211-473 47 µH (CCM) · "
                 "EPC2207 GaN",
                 color="#e8eaed", fontsize=12.5, y=0.99)
    fig.subplots_adjust(left=.062, right=.985, top=.80, bottom=.095, wspace=.17)
    p = ILL / "surtension_diode.png"
    p.unlink(missing_ok=True)
    fig.savefig(p, facecolor=fig.get_facecolor())
    print("figure ->", p)

    # ---------- tableau ----------
    print(f"\n{'balayage':>10s} {'diode':>5s} {'réglage':>9s} {'di/dt':>9s} "
          f"{'L.di/dt':>9s} {'dépass.':>9s} {'avalanche':>10s}")
    for dio, _, vbr, _, _ in DIO:
        for rg in RG:
            e = mesure(f"sur_rg_{dio}_{rg:g}", vbr)
            if e:
                print(f"{'vitesse':>10s} {dio:>5s} {rg:7.1f} Ω "
                      f"{e['didt']:6.2f}A/ns {LB_REF*e['didt']*1e9:7.1f} V "
                      f"{e['dv']:7.1f} V {e['av']:8.1f} mW"
                      + ("   ÉCRÊTÉ" if e["ecrete"] else ""))
        for lb in LB:
            e = mesure(f"sur_lb_{dio}_{lb*1e9:.0f}n", vbr)
            if e:
                print(f"{'maille':>10s} {dio:>5s} {lb*1e9:6.0f} nH "
                      f"{e['didt']:6.2f}A/ns {lb*e['didt']*1e9:7.1f} V "
                      f"{e['dv']:7.1f} V {e['av']:8.1f} mW"
                      + ("   ÉCRÊTÉ" if e["ecrete"] else ""))


if __name__ == "__main__":
    main()
