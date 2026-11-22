"""DCM, Kp = 1, mesure echantillonnee : d'ou vient la gigue de D ?

Banc : 5 W (avant l'echelon de 1 ms), FDD770N15A, Wurth 10 uF/100 V,
mesure filtree 1 us puis echantillonnee en debut de periode.
Relance zd_diag.cir (2 ms, sauvegarde etendue), trace, puis efface le .raw.
"""
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
sys.path.insert(0, str(ICI))
import r2_ziegler_dcm as d                                   # noqa: E402,F401
import ltspice_run                                           # noqa: E402
sys.path.insert(0, str(ICI.parent.parent / ".claude/skills/sim-commun"))
from simcommun.lecture import lire                           # noqa: E402

T = 5e-6
f = ICI / "zd_diag.cir"
r = ltspice_run.lance(f)
if not r["ok"]:
    raise SystemExit(r["diagnostic"])
x = lire(str(f.with_suffix(".raw")))
t = np.asarray(x.x)
g = lambda s: np.asarray(x.trace(s)).real                    # noqa: E731
sw, sh, vm, vo, nc, il = (g("V(nsw)"), g("V(nsh)"), g("V(nvm)"),
                          g("V(nout)"), g("V(nctrl)"), g("I(L1)"))

ks = np.arange(120, 200)                                     # 0,6 a 1 ms
von = np.interp(ks * T + 0.5e-9, t, sw)
dk = np.interp(ks * T + 0.5e-6, t, nc)
shk = np.interp(ks * T + 0.5e-6, t, sh)

plt.style.use("dark_background")
fig, ax = plt.subplots(4, 1, figsize=(16, 13))
fig.suptitle("DCM 5 W, Kp = 1, mesure filtrée 1 µs puis échantillonnée en début "
             "de période — d'où vient la gigue de D ?", fontsize=12)

# 1. noeud de commutation et courant sur 6 periodes
k0 = 150
m = (t >= k0 * T) & (t < (k0 + 6) * T)
a = ax[0]
a.plot((t[m] - k0 * T) * 1e6, sw[m], lw=0.8, color="#66aaff", label="V(nsw)")
a.set_ylabel("V(nsw)  [V]")
b = a.twinx()
b.plot((t[m] - k0 * T) * 1e6, il[m], lw=0.8, color="#ffcc44", label="I(L1)")
b.set_ylabel("I(L1)  [A]", color="#ffcc44")
for k in range(7):
    a.axvline(k * 5, color="#888888", lw=0.7, ls="--")
a.set_title("6 périodes : après la conduction de la diode, la self sonne contre "
            "Coss — le rallumage (traits) tombe à une phase différente à chaque "
            "période", fontsize=10)
a.set_xlabel("t − t₀  [µs]")

# 2. tension de drain au rallumage, periode par periode
a = ax[1]
a.plot(ks * T * 1e3, von, "o-", ms=3, lw=0.8, color="#66aaff")
a.set_ylabel("V(nsw) au rallumage  [V]")
a.set_title(f"tension au rallumage : {von.min():.0f} à {von.max():.0f} V "
            f"(σ {von.std():.1f} V) — la sonnerie n'est pas synchrone de la "
            "découpe", fontsize=10)

# 3. mesure filtree et echantillon
m = (t >= k0 * T) & (t < (k0 + 6) * T)
a = ax[2]
a.plot((t[m] - k0 * T) * 1e6, vo[m], lw=0.6, color="#888888", label="V(nout)")
a.plot((t[m] - k0 * T) * 1e6, vm[m], lw=1.0, color="#66dd66",
       label="mesure filtrée 1 µs")
a.plot((t[m] - k0 * T) * 1e6, sh[m], lw=1.4, color="#ff66ff",
       label="échantillon (bloqueur)")
a.set_ylim(79.85, 80.15)
a.set_ylabel("[V]")
a.set_xlabel("t − t₀  [µs]")
a.legend(fontsize=8.5, loc="upper right")
a.set_title("l'échantillon est pris au début de chaque période, sur la mesure "
            "filtrée", fontsize=10)

# 4. echantillon et D, periode par periode
a = ax[3]
a.plot(ks * T * 1e3, (shk - shk.mean()) * 1e3, "o-", ms=3, lw=0.8,
       color="#ff66ff", label="échantillon − moyenne  [mV]")
a.plot(ks * T * 1e3, -(dk - dk.mean()) * 1e3, "s--", ms=3, lw=0.8,
       color="#ffcc44", label="−(D − moyenne) × 1000")
a.set_xlabel("t  [ms]")
a.legend(fontsize=8.5)
a.set_title(f"échantillon σ {shk.std()*1e3:.1f} mV  →  D σ {dk.std():.4f} "
            f"= Kp × σ, période par période", fontsize=10)
for a in ax:
    a.grid(alpha=0.25)
    a.grid(alpha=0.1, which="minor")
    a.xaxis.set_minor_locator(AutoMinorLocator())
fig.tight_layout()
out = ICI / "r2_dcm_kp1_gigue.png"
fig.savefig(out, dpi=120)
f.with_suffix(".raw").unlink()
print(f"figure : {out}")
print(f"corr(V rallumage[k], echantillon[k+1]) = "
      f"{np.corrcoef(von[:-1], shk[1:])[0, 1]:+.2f}")
