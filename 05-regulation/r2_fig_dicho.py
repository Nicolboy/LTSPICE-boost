"""Figure du verdict R2 : trois gains de part et d'autre de la limite.

Memes echelles verticales sur les trois panneaux -- RETEX section Q,
trois fois la meme faute d'axe borne, on ne la refait pas une quatrieme.

Le troisieme panneau vient de `diag0063` : le cas Kp = 0,0063 relance
avec sauvegarde depuis t = 0, parce que la version standard (fenetre a
partir de 0,6 ms) meurt a 304 us sans rien laisser a lire. Son axe des
temps n'est donc pas celui des deux autres -- d'ou sharex=False.

Le titre de chaque panneau porte la frequence et le taux de
decroissance MESURES par `enveloppe()`, et la frequence PREDITE par la
formule fermee f0.sqrt(1+Kp.G) avec f0 = 3,9 kHz et G = 321 mesures en
R1. La premiere version annoncait "4,5 kHz" et "entretenue" sur un cas
a 5,7 kHz qui decroissait : le titre affirmait, il ne mesurait pas.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent.parent / ".claude/skills/sim-commun"))
sys.path.insert(0, str(ICI))
from r2_proportionnel import _vm, enveloppe                  # noqa: E402

F0, G0 = 3.9e3, 321.0
CAS = (("d0p002", 0.002, "#66dd66"),
       ("d0p003557", 0.0035566, "#ffcc44"),
       ("diag0063", 0.0063246, "#ff6666"))

plt.style.use("dark_background")
fig, ax = plt.subplots(3, 1, figsize=(11, 8.5), sharey=True)
fig.suptitle("R2 — P pur à 40 W CCM : moyenne de V(nout) sur 1 période\n"
             "la limite de stabilité est entre Kp = 0,0036 et 0,0063",
             fontsize=11)

for a, (tag, kp, coul) in zip(ax, CAS):
    tm, vm, dm = _vm(ICI / f"{tag}.cir")
    if tag.startswith("diag"):
        # le demarrage depuis .ic dure ~10 periodes : on lit apres
        m = tm > 50e-6
        tm, vm = tm[m], vm[m]
    fo, sig, zeta = enveloppe(tm, vm)
    k = kp * G0
    verdict = "stable" if sig < 0 else "INSTABLE"
    a.plot(tm * 1e3, vm, lw=1.1, color=coul)
    a.axhline(80, color="#aaaaaa", lw=0.7, ls="--")
    a.set_title(f"Kp = {kp:.4f}  (Kp·G = {k:.2f})  — {verdict} :  "
                f"{fo/1e3:.2f} kHz mesurés, {F0*np.sqrt(1+k)/1e3:.2f} kHz "
                f"prédits,  σ = {sig:+.0f} /s,  ζ = {zeta:+.4f}",
                fontsize=9.5)
    a.set_ylabel("⟨V(nout)⟩  [V]")
    a.set_xlabel("t  [ms]")
    a.grid(alpha=0.25)
    print(f"{tag:10s} Kp {kp:.5f}  K {k:.2f}  f {fo:7.0f} Hz "
          f"(predit {F0*np.sqrt(1+k):5.0f})  sigma {sig:+8.1f}  "
          f"zeta {zeta:+.4f}  {verdict}")
ax[2].annotate("mort numérique à 304 µs\n(nœud interne du modèle Infineon)",
               xy=(0.98, 0.80), xycoords="axes fraction", ha="right",
               fontsize=8.5, color="#ff9999")
fig.tight_layout()
out = ICI / "r2_dichotomie.png"
fig.savefig(out, dpi=130)
print(f"figure : {out}")
