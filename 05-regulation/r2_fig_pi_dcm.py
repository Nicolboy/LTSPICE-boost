"""PI regle en CCM applique en DCM, contre le P a fort gain que tolere le
DCM (Kp 1,17, k-section zr2_1). Meme echelon 5 -> 10 W, memes echelles,
temps compte depuis l'echelon."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
T = 5e-6
# Comparaison HOMOGENE (verdict du gendarme) : deux PI, chacun a 0,45 de
# la limite de SON mode, meme zero d'integrale, pre-echelon etabli.
CAS = (("pi_ccm", 600, "PI réglé en CCM : Kp 0,0093, Ki 12 /V/s (0,45·Ku CCM)",
        "#ff9944"),
       ("pi_dcm", 600, "PI réglé en DCM : Kp 0,61, Ki 785 /V/s (0,45·Ku DCM)",
        "#66dd66"))
plt.style.use("dark_background")
fig, ax = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
fig.suptitle("R2 DCM — échelon 5 → 10 W : PI réglé en CCM contre PI réglé en "
             "DCM (même proportion de leur limite, même zéro d'intégrale)\n"
             "banc complet, pré-échelon établi, mêmes échelles, t = 0 à "
             "l'échelon", fontsize=12)
for tag, n0, lib, c in CAS:
    D = np.load(ICI / f"{tag}.npz")
    t = (D["tb"] - n0 * T) * 1e3
    ax[0].plot(t, D["vb"], lw=1.0, color=c, label=lib)
    ax[1].plot(t, D["db"], lw=0.9, color=c, label=lib)
    ap = t > 0
    fin = t > t[-1] - 1.0
    vf = D["vb"][fin].mean()
    hors = np.where(np.abs(D["vb"][ap] - vf) > 0.1)[0]
    print(f"{tag:6s} creux {D['vb'][ap].min():.3f} V  final {vf:.3f} V  "
          f"retour +-0,1 V {t[ap][hors[-1]] if len(hors) else 0:.2f} ms")
ax[0].set_ylim(75, 85)
ax[0].axhline(80, color="#888888", lw=0.7, ls=":")
ax[0].set_ylabel("⟨Vout⟩ par période  [V]")
ax[1].set_ylim(0.3, 0.8)
ax[1].set_ylabel("D par période")
ax[1].set_xlabel("t depuis l'échelon  [ms]")
for a in ax:
    a.axvline(0, color="#aaaaaa", lw=0.8, ls="--")
    a.grid(alpha=0.25); a.grid(alpha=0.1, which="minor")
    a.xaxis.set_minor_locator(AutoMinorLocator())
    a.legend(fontsize=9, loc="lower right")
ax[0].set_xlim(-1, 7)
fig.tight_layout()
out = ICI / "r2_pi_dcm.png"
fig.savefig(out, dpi=120)
print(f"figure : {out}")
