"""Les courbes de l'etape 3 : le transistor reel contre l'interrupteur ideal.

TROIS CHOSES A MONTRER, et qu'aucun tableau ne rend.

1. LA DIODE DE CORPS. Prediction faite AVANT de lancer : l'interrupteur
   ideal laissait V(nsw) descendre a -78 V, le transistor reel l'ecretera.
   Mesure : -3,11 V. La surtension positive tombe avec elle, de 129 a
   81,9 V, parce que c'etait la meme oscillation.

2. OU PASSENT LES 86,89 mW. Le transistor dissipe 5 fois ce que
   l'interrupteur ideal annoncait. La puissance instantanee dit si c'est
   de la conduction ou de la commutation -- deux leviers opposes.

3. LE MODELE QUI CREE DE L'ENERGIE. Le FDD770N15A affiche -76,80 mW aux
   bornes. Sur la courbe, ca se voit : la puissance instantanee passe
   massivement sous zero pendant la conduction de la diode de corps,
   la ou son module de recouvrement inverse travaille.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
sys.path.insert(0, str(ICI.parents[2] / ".claude/skills/sim-commun"))
import etape                                                 # noqa: E402
from simcommun.lecture import lire                           # noqa: E402

EXE = r"C:\Program Files\ADI\LTspice\LTspice.exe"
plt.style.use("dark_background")
F, G, V = "#11141a", "#171b23", "#9aa4b5"
OR, VE, BL, RO, MA = "#f0b23d", "#54d6a0", "#4d9fff", "#ff6b6b", "#c58bff"
DUTY = 0.588            # recale pour Pout comparable a l'etape 2


def pose(a):
    a.set_facecolor(G)
    a.grid(alpha=.16, color=V, lw=.6)
    a.tick_params(colors=V, labelsize=8.5)
    for s in a.spines.values():
        s.set_color("#2b3240")


def produit(tag, **kw):
    f = ICI / f"{tag}.cir"
    if not f.with_suffix(".raw").exists():
        f.write_text(etape.etape0(ser=True, v8pa22=True, charge=False,
                                  n_etab=40, n_mes=8, dtmax=0.5e-9,
                                  duty=DUTY, **kw), encoding="utf-8")
        subprocess.run([EXE, "-b", str(f)], capture_output=True, timeout=2400)
    return f.with_suffix(".raw")


def fenetre(raw, n=2):
    r = lire(str(raw))
    t = np.asarray(r.x)
    vg = np.asarray(r.trace("V(ng)")).real
    mo = np.where((vg[:-1] < 2.5) & (vg[1:] >= 2.5))[0]
    sl = slice(mo[-1 - n], mo[-1] + 1)
    return r, t, sl, mo


def main() -> int:
    cas = {"s2": produit("e3_sw", mos=False),
           "s3": produit("e3_ipd", mos="ipd530"),
           "fd": produit("e3_fdd", mos="fdd770")}
    fig = plt.figure(figsize=(15.5, 11.2), facecolor=F)
    gs = fig.add_gridspec(3, 2, hspace=.40, wspace=.19, left=.062,
                          right=.983, top=.868, bottom=.062,
                          height_ratios=[1, 1, 1])

    # --- 1. la diode de corps ecrete ------------------------------------
    a = fig.add_subplot(gs[0, :])
    pose(a)
    for k, (c, lab) in ((("s2"), (OR, "étape 2 — interrupteur idéal")),
                        (("s3"), (BL, "étape 3 — IPD530N15N3"))):
        r, t, sl, _ = fenetre(cas[k])
        tt = (t[sl] - t[sl][0]) * 1e6
        vs = np.asarray(r.trace("V(nsw)")).real[sl]
        a.plot(tt, vs, color=c, lw=1.35, label=f"{lab}   "
               f"[{vs.min():+.1f} ; {vs.max():.1f}] V")
    a.axhline(80, color=VE, ls=":", lw=1.0)
    a.axhline(0, color="#49546a", lw=.8)
    a.axhline(150, color=RO, ls="--", lw=1.1)
    a.text(.004, 150, " calibre 150 V", color=RO, fontsize=8.4,
           va="bottom", transform=a.get_yaxis_transform())
    a.set_ylim(-128, 182)
    a.set_xlabel("temps  [µs]", color=V, fontsize=9)
    a.set_ylabel("V(nsw)  [V]", color=V, fontsize=9.5)
    a.legend(fontsize=8.6, facecolor=G, edgecolor="#2b3240", labelcolor=V,
             loc="lower right")
    a.set_title("1 — LA DIODE DE CORPS ÉCRÊTE, ET LA SURTENSION TOMBE AVEC ELLE",
                color="#e6e9ef", fontsize=11.5, pad=11, weight="bold")
    # UN AXE BORNE CACHE CE QU'IL FAUT VOIR, deuxieme fois dans la session :
    # la premiere, 228 V masquaient 742 V ; ici -95 coupait les -113,2 V,
    # c'est-a-dire la mesure meme qu'on veut montrer.
    a.text(.012, .33, "prédit AVANT de lancer : l'interrupteur idéal n'a pas "
           "de diode de corps,\nson excursion négative alimentait l'excursion "
           "positive", transform=a.transAxes, va="top", color=V, fontsize=8.5,
           linespacing=1.5)

    # --- 2. la grille, enfin ralentie -----------------------------------
    a = fig.add_subplot(gs[1, 0])
    pose(a)
    r, t, sl, mo = fenetre(cas["s3"], n=1)
    j = int(mo[-2])
    w = (t > t[j] - 20e-9) & (t < t[j] + 110e-9)
    tz = (np.asarray(r.x)[w] - t[j]) * 1e9
    a.plot(tz, np.asarray(r.trace("V(ng)")).real[w], color=V, lw=1.2,
           ls="--", label="V(ng)  sortie du driver")
    a.plot(tz, np.asarray(r.trace("V(ngg)")).real[w], color=MA, lw=1.6,
           label="V(ngg)  grille du boîtier")
    a.plot(tz, np.asarray(r.trace("V(nsw)")).real[w] / 10.0, color=OR,
           lw=1.1, label="V(nsw) / 10")
    a.axhline(0, color="#49546a", lw=.8)
    a.set_xlabel("ns après le front de commande", color=V, fontsize=9)
    a.set_ylabel("[V]", color=V, fontsize=9.5)
    a.legend(fontsize=7.8, facecolor=G, edgecolor="#2b3240", labelcolor=V)
    a.set_title("2 — LES 10 Ω DE GRILLE PRENNENT ENFIN LEUR SENS",
                color="#e6e9ef", fontsize=11, pad=10, weight="bold")
    a.text(.97, .06, "le `.model SW` n'avait aucun $Q_g$ :\nune résistance de "
           "grille n'y changeait rien", transform=a.transAxes, ha="right",
           color=V, fontsize=8.2, linespacing=1.5)

    # --- 3. ou passent les 86,89 mW -------------------------------------
    a = fig.add_subplot(gs[1, 1])
    pose(a)
    r, t, sl, mo = fenetre(cas["s3"], n=1)
    tt = (t[sl] - t[sl][0]) * 1e6
    g = lambda n: np.asarray(r.trace(n)).real[sl]
    pm = g("V(nsw)") * (g("I(Vsl)") - g("I(Vd)") - g("I(Cosn)"))
    a.plot(tt, pm, color=BL, lw=1.25)
    a.fill_between(tt, 0, pm, where=pm > 0, color=BL, alpha=.22)
    a.axhline(0, color="#49546a", lw=.9)
    a.set_xlabel("temps  [µs]", color=V, fontsize=9)
    a.set_ylabel("puissance instantanée  [W]", color=V, fontsize=9.5)
    a.set_title("3 — OÙ PASSENT LES 86,89 mW", color="#e6e9ef",
                fontsize=11, pad=10, weight="bold")
    a.text(.5, .94, "les pics sont aux COMMUTATIONS, pas en conduction :\n"
           "à 8 W la conduction ne pèse que ~8 mW sur 53 mΩ",
           transform=a.transAxes, ha="center", va="top", color=V,
           fontsize=8.3, linespacing=1.5)

    # --- 4. le modele qui cree de l'energie -----------------------------
    a = fig.add_subplot(gs[2, :])
    pose(a)
    for k, c, lab, tot in (("s3", BL, "IPD530N15N3 — Infineon", +89.36),
                           ("fd", RO, "FDD770N15A — onsemi", -76.80)):
        r, t, sl, _ = fenetre(cas[k], n=1)
        tt = (t[sl] - t[sl][0]) * 1e6
        g = lambda n: np.asarray(r.trace(n)).real[sl]
        p = (g("V(nsw)") * (g("I(Vsl)") - g("I(Vd)") - g("I(Cosn)"))
             + g("V(ngg)") * g("I(Rgx)"))
        a.plot(tt, p, color=c, lw=1.3,
               label=f"{lab}   moyenne {tot:+.2f} mW")
        if k == "fd":
            a.fill_between(tt, 0, p, where=p < 0, color=c, alpha=.26)
    a.axhline(0, color="#e6e9ef", lw=1.0)
    a.set_xlabel("temps  [µs]", color=V, fontsize=9)
    a.set_ylabel("puissance TOTALE aux bornes\ndrain + grille  [W]",
                 color=V, fontsize=9.5)
    a.legend(fontsize=8.6, facecolor=G, edgecolor="#2b3240", labelcolor=V,
             loc="upper right")
    a.set_title("4 — UN MODÈLE QUI CRÉE DE L'ÉNERGIE", color="#e6e9ef",
                fontsize=11.5, pad=11, weight="bold")
    a.text(.012, .09, "la surface rouge sous zéro est de l'énergie FOURNIE par "
           "un composant passif.\nSon module de recouvrement inverse "
           "(tau=70, igain=700, sources H) en est la cause.\n"
           "Il convergeait sur les cinq valeurs de $R_g$ — l'Infineon, lui, "
           "ne passe qu'à 10 Ω.", transform=a.transAxes, color=V,
           fontsize=8.5, linespacing=1.55)

    fig.text(.5, .962, "ÉTAPE 3 — LE TRANSISTOR RÉEL REMPLACE L'INTERRUPTEUR "
             "IDÉAL", ha="center", color="#e6e9ef", fontsize=14.5,
             weight="bold")
    fig.text(.5, .930, "Infineon IPD530N15N3, D-PAK 150 V · $R_g$ = 10 Ω · "
             "$V_{gs}$ = 10 V · duty recalé à 0,588 pour une puissance "
             "comparable", ha="center", color=V, fontsize=9.8)
    plt.savefig(ICI / "etape3.png", dpi=104, facecolor=F)
    print("  etape3.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
