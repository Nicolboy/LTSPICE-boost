"""Figure de la carte de stabilite R2 -- echelon 5 -> 10 W, Cout 10 uF.

x : Kp (log, avec Kp.G a 10 W en axe secondaire)
y : facteur d'amortissement zeta (> 0 amorti, < 0 amplifie)
z : frequence d'oscillation, en second panneau partageant x

Les cas APERIODIQUES sont places a zeta = 1 en marqueur creux : leur
zeta vaut AU MOINS 1, il n'est pas mesure. La sous-harmonique fsw/2, si
elle existe, est un second mode, porte a part sur le panneau frequence.
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
sys.path.insert(0, str(ICI))
from r2_carte import dcm, P2                                 # noqa: E402

rows = list(np.load(ICI / "r2_carte_resultats.npy", allow_pickle=True))
_, G2, _ = dcm(P2)
COUL = {"aperiodique": "#66dd66", "amorti": "#66aaff",
        "entretenu": "#ffcc44", "irregulier": "#ff9944",
        "divergent": "#ff6666", "grand signal": "#ff66ff"}
LIB = {"aperiodique": "apériodique (ζ ≥ ~0,83 : dépassement < 1 %)",
       "amorti": "amorti (ζ lu sur le dépassement)",
       "entretenu": "entretenu : cycle limite à fsw/2",
       "irregulier": "irrégulier, borné (spectre large)",
       "divergent": "divergent",
       "grand signal": "grand signal : rafales, butée de D"}

plt.style.use("dark_background")
fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True,
                             gridspec_kw=dict(height_ratios=(3, 2)))
fig.suptitle("R2 — domaine de stabilité du P pur : échelon 5 → 10 W "
             "(DCM), Vin 20 V, Vout 80 V, Cout 10 µF", fontsize=11)

for cls, c in COUL.items():
    r = [x for x in rows if x.get("cls") == cls]
    if not r:
        continue
    kp = [x["kp"] for x in r]
    if cls == "aperiodique":
        a1.scatter(kp, [1.0] * len(r), s=60, facecolors="none",
                   edgecolors=c, lw=1.5, label=LIB[cls])
    else:
        a1.scatter(kp, [x["zeta"] for x in r], s=60, color=c, label=LIB[cls])
        a2.scatter(kp, [x["f"] for x in r], s=60, color=c)
a2.axhline(1e5, color="#888888", lw=0.7, ls=":")
a2.text(1.2e-3, 1.1e5, "fsw/2 = 100 kHz", fontsize=8, color="#aaaaaa")
a2.text(1.2e-3, 3e3, "aucune oscillation lisible pour Kp < 0,5 :\n"
        "plant DCM du premier ordre", fontsize=8.5, color="#66dd66")
# drapeaux grand signal
gs = [x for x in rows if x.get("butee") or x.get("ccm")]
for x in gs:
    a1.axvline(x["kp"], color="#555555", lw=6, alpha=0.35, zorder=0)
if gs:
    a1.plot([], [], color="#555555", lw=6, alpha=0.5,
            label="butée de D ou passage CCM")

a1.axhline(0, color="#aaaaaa", lw=0.8, ls="--")
a1.set_ylabel("ζ   (amorti > 0 > amplifié)")
a1.set_xscale("log")
a1.grid(alpha=0.25, which="both")
a1.set_ylim(-0.15, 1.1)
a1.legend(fontsize=8.5, loc="lower left")
a2.set_yscale("log")
a2.set_ylabel("fréquence d'oscillation  [Hz]")
a2.set_xlabel("Kp")
a2.grid(alpha=0.25, which="both")
a2.set_ylim(2e3, 2e5)
a2.set_xlim(7e-4, 1.4e1)
sec = a1.secondary_xaxis("top", functions=(lambda k: k * G2,
                                           lambda K: K / G2))
sec.set_xlabel("Kp·G à 10 W  (G = %.0f V)" % G2)
fig.tight_layout()
out = ICI / "r2_carte.png"
fig.savefig(out, dpi=130)
print(f"figure : {out}")
