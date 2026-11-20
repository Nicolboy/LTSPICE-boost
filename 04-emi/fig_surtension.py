"""DEUX graphes, DEUX fichiers.

    illustrations/surtension_vs_vitesse.png   surtension = f(vitesse de commutation)
    illustrations/surtension_vs_maille.png    surtension = f(inductance de boucle)

Chacun porte les DEUX diodes : C6D04065A (SiC 650 V Wolfspeed) et V8PA22
(Schottky Si 200 V Vishay), modeles constructeur dans les deux cas.

    dV = L_boucle . di/dt        et        Irr = sqrt(2 Qrr di/dt)

En ABSCISSE DU PREMIER GRAPHE : le di/dt REELLEMENT MESURE, pas le reglage
de Rg. C'est la grandeur physique, et c'est elle qui rend les deux graphes
comparables entre eux.

LECTURE OBLIGATOIRE DE LA V8PA22 : elle est ECRETEE a 220,6 V des que le
pic depasse son claquage. Les points plats a 140,6 V de depassement ne sont
donc PAS une mesure du pic -- ils sont le niveau d'ecretage, et la colonne
avalanche dit ce qui a ete dissipe pour l'obtenir. Marques par une croix.
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
RG_REF, LB_REF = 10.0, 20e-9
DIO = (("sic", "C6D04065A — SiC 650 V", 768.0, "#54d6a0", "o"),
       ("si",  "V8PA22 — Schottky Si 200 V", 220.0, "#ff6b6b", "s"))
SOUS = ("boost 19 V → 80 V, 47 W, 400 kHz · SER2211-473 47 µH (CCM) · "
        "EPC2207 GaN")


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
    return dict(dv=-vd.min() - 80.0, vinv=-vd.min(), av=pav,
                didt=np.abs(np.diff(idio)[b] / dt[b]).max() / 1e9,
                ecrete=(-vd.min()) >= vbr - 1.0)


def _cadre(titre):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10.5, 7.0), dpi=170)
    fig.patch.set_facecolor("#15171c")
    ax.set_facecolor("#15171c")
    ax.grid(True, which="both", color="#2c3038", lw=0.6, zorder=1)
    ax.tick_params(colors="#9aa0a6")
    ax.set_ylabel("dépassement au-delà des 80 V de sortie (V)", color="#e8eaed")
    ax.set_title(titre + "\n" + SOUS, color="#e8eaed", fontsize=12, pad=14)
    ax.set_ylim(0, 170)
    return fig, ax


def _legende(ax, ou="lower right"):
    lg = ax.legend(loc=ou, facecolor="#1d2026", edgecolor="#2c3038",
                   fontsize=9)
    for t in lg.get_texts():
        t.set_color("#e8eaed")


def _trace_vitesse(ax, compact=False):
    """Surtension = f(vitesse de commutation), maille fixee a 20 nH."""
    for dio, nom, vbr, col, mk in DIO:
        xs, ys, ec, rgv = [], [], [], []
        for rg in RG:
            e = mesure(f"sur_rg_{dio}_{rg:g}", vbr)
            if e:
                xs.append(e["didt"]); ys.append(e["dv"])
                ec.append(e["ecrete"]); rgv.append(rg)
        xs, ys, ec = np.array(xs), np.array(ys), np.array(ec)
        o = np.argsort(xs)
        ax.plot(xs[o], ys[o], "-", color=col, lw=1.2, alpha=0.6, zorder=3)
        ax.plot(xs[~ec], ys[~ec], mk, color=col, ms=9, zorder=4,
                label=nom + " — pic réel")
        if ec.any():
            ax.plot(xs[ec], ys[ec], "x", color=col, ms=11, mew=2.4, zorder=4,
                    label=nom + " — ÉCRÊTÉ, en avalanche")
        if dio == "sic":
            for k, (x, y, r) in enumerate(zip(xs, ys, rgv)):
                ax.annotate(f"{r:g} Ω", (x, y), textcoords="offset points",
                            xytext=(8, (-14, 9, -14, 9, -14, 9)[k % 6]),
                            color=col, fontsize=8.6)
        else:
            if ec.any() and not compact:
                ax.annotate("de 1 à 22 Ω — AUCUN EFFET." + chr(10)
                            + "Le di/dt de la coupure est celui du" + chr(10)
                            + "recouvrement de la diode, pas de la grille.",
                            (xs[ec].mean(), ys[ec].mean()),
                            textcoords="offset points", xytext=(-250, 20),
                            color=col, fontsize=9.2,
                            arrowprops=dict(arrowstyle="->", color=col, lw=1.2))
            for x, y, r in zip(xs[~ec], ys[~ec], np.array(rgv)[~ec]):
                ax.annotate(f"{r:g} Ω", (x, y), textcoords="offset points",
                            xytext=(8, -15), color=col, fontsize=8.6)
    xl = np.logspace(np.log10(0.8), np.log10(45), 120)
    ax.plot(xl, LB_REF * xl * 1e9, "--", color="#ffd166", lw=1.8, zorder=2,
            label=r"$\Delta V = L_\sigma\,di/dt$ — droite, pas un ajustement")
    ax.set_xscale("log")
    ax.set_xlim(0.9, 50)
    ax.set_xlabel("di/dt mesuré à la coupure de la diode (A/ns)",
                  color="#e8eaed")
    _legende(ax, "lower right")


def _trace_maille(ax, compact=False):
    """Surtension = f(inductance de boucle), Rg fixe a 10 ohms."""
    for dio, nom, vbr, col, mk in DIO:
        xs, ys, ec, lv, dd = [], [], [], [], []
        for lb in LB:
            e = mesure(f"sur_lb_{dio}_{lb*1e9:.0f}n", vbr)
            if e:
                xs.append(lb * 1e9); ys.append(e["dv"])
                ec.append(e["ecrete"]); lv.append(lb); dd.append(e["didt"])
        xs, ys, ec = np.array(xs), np.array(ys), np.array(ec)
        o = np.argsort(xs)
        ax.plot(xs[o], ys[o], "-", color=col, lw=1.2, alpha=0.6, zorder=3)
        ax.plot(xs[~ec], ys[~ec], mk, color=col, ms=9, zorder=4,
                label=nom + " — pic réel")
        if ec.any():
            ax.plot(xs[ec], ys[ec], "x", color=col, ms=11, mew=2.4, zorder=4,
                    label=nom + " — ÉCRÊTÉ, en avalanche")
        # L x di/dt point par point, SANS aucun ajustement
        pred = np.array([l * d * 1e9 for l, d in zip(lv, dd)])
        ax.plot(xs[o], pred[o], ":", color=col, lw=2.0, zorder=5,
                label=r"$L_\sigma\times di/dt$ mesuré — "
                      + ("SiC" if dio == "sic" else "Si"))
        for x, y, d in zip(xs, ys, dd):
            ax.annotate(f"{d:.1f} A/ns", (x, y), textcoords="offset points",
                        xytext=(-16, -19), color=col, fontsize=8.2, alpha=0.9)
    ax.set_xscale("log")
    from matplotlib.ticker import FixedLocator, NullFormatter, NullLocator
    ax.xaxis.set_major_locator(FixedLocator([2, 5, 10, 20, 40]))
    ax.xaxis.set_minor_locator(NullLocator())     # sinon « 3x10^0 » parasite
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xticklabels(["2", "5", "10", "20", "40"])
    ax.set_xlim(1.7, 48)
    ax.set_xlabel("inductance de boucle de commutation $L_\\sigma$ (nH)",
                  color="#e8eaed")
    ax.annotate("La courbe s'infléchit parce que la boucle" + chr(10)
                + "freine son propre di/dt : doubler $L_\\sigma$" + chr(10)
                + "ne double pas la surtension.",
                (40, 87.6), textcoords="offset points", xytext=(-240, 26),
                color="#9aa0a6", fontsize=9.2,
                arrowprops=dict(arrowstyle="->", color="#9aa0a6", lw=1.2))
    _legende(ax, "upper left")


T_VIT = ("Surtension inverse contre VITESSE DE COMMUTATION — "
         "$R_g$ de 1 à 47 Ω, maille fixée à 20 nH")
T_MAI = ("Surtension inverse contre INDUCTANCE DE BOUCLE — "
         "2 à 40 nH, $R_g$ fixé à 10 Ω")


def _ecrire(fig, nom):
    fig.subplots_adjust(left=.085, right=.975, top=.86, bottom=.085)
    p = ILL / nom
    p.unlink(missing_ok=True)
    fig.savefig(p, facecolor=fig.get_facecolor())
    print("->", p.name)


def graphe_vitesse():
    fig, ax = _cadre(T_VIT)
    _trace_vitesse(ax)
    _ecrire(fig, "surtension_vs_vitesse.png")


def graphe_maille():
    fig, ax = _cadre(T_MAI)
    _trace_maille(ax)
    _ecrire(fig, "surtension_vs_maille.png")


def graphe_combine():
    """Les deux cote a cote -- la vue d'un coup d'oeil, pour le README.

    ELLE SORT DU MEME CODE que les deux figures separees. Une illustration
    qu'un script ne regenere plus devient perimee au premier changement de
    donnees : c'est exactement ainsi qu'elle etait devenue orpheline, et
    c'est pour cela que je l'avais effacee au lieu de la remettre en ligne.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.style.use("dark_background")
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(15.5, 6.8), dpi=170)
    fig.patch.set_facecolor("#15171c")
    for a in (ax, bx):
        a.set_facecolor("#15171c")
        a.grid(True, which="both", color="#2c3038", lw=0.6, zorder=1)
        a.tick_params(colors="#9aa0a6")
        a.set_ylim(0, 170)
    ax.set_ylabel("dépassement au-delà des 80 V de sortie (V)",
                  color="#e8eaed")
    _trace_vitesse(ax, compact=True)
    _trace_maille(bx, compact=True)
    ax.set_title("vitesse de commutation — $R_g$ 1 → 47 Ω, maille 20 nH",
                 color="#e8eaed", fontsize=11)
    bx.set_title("inductance de boucle — 2 → 40 nH, $R_g$ = 10 Ω",
                 color="#e8eaed", fontsize=11)
    fig.suptitle("Surtension inverse sur la diode — les deux leviers" + chr(10)
                 + SOUS, color="#e8eaed", fontsize=12.5, y=0.99)
    fig.subplots_adjust(left=.062, right=.985, top=.80, bottom=.095,
                        wspace=.15)
    p = ILL / "surtension_diode.png"
    p.unlink(missing_ok=True)
    fig.savefig(p, facecolor=fig.get_facecolor())
    print("->", p.name)


def tableau():
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
                print(f"{'boucle':>10s} {dio:>5s} {lb*1e9:6.0f} nH "
                      f"{e['didt']:6.2f}A/ns {lb*e['didt']*1e9:7.1f} V "
                      f"{e['dv']:7.1f} V {e['av']:8.1f} mW"
                      + ("   ÉCRÊTÉ" if e["ecrete"] else ""))


if __name__ == "__main__":
    graphe_vitesse()
    graphe_maille()
    graphe_combine()
    tableau()
