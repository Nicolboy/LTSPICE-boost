"""DCM 5 W, Kp = 1, MLCC HF en place dans les deux cas : echantillonnage en
debut de periode (sur le rallumage) contre 0,95 T (avant le rallumage, loin
des fronts). Seul changement : l'instant d'echantillonnage."""
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
import r2_fig_dcm_mlcc as base                              # noqa: E402
import ltspice_run                                          # noqa: E402

T, KS = base.T, base.KS
# 0,998 T : fin de la fenetre S+H du F28P551 juste avant la commande de
# fermeture. Datasheet tms320f28p551sg, Table 6-20 : fenetre min 67 ns,
# valeur figee ~5 ns avant la fin de la fenetre. La rampe retombe a
# 0,999 T et la grille est commandee ~3 ns plus tard (D ~ 0,44) : figer a
# 0,998 T place l'echantillon ~8 ns avant la commande, hors de tout front.
fs = [base.netlist("zd_ech_debut", True, True),
      base.netlist("zd_ech_095", True, 0.95),
      base.netlist("zd_ech_c2000", True, 0.998)]
res = ltspice_run.lance_lot(fs, procs=3)
for f in fs:
    if not res[f.stem]["ok"]:
        raise SystemExit(f"{f.stem} : {res[f.stem]['diagnostic']}")
L = [base.lit(f) for f in fs]
noms = ("début de période (sur le rallumage)",
        "0,95 T (avant le rallumage)",
        "0,998 T : fin de fenêtre S+H C2000, juste avant la fermeture")
coul = ("#ffcc44", "#66aaff", "#66dd66")
plt.style.use("dark_background")
fig, ax = plt.subplots(2, 3, figsize=(18, 8.5))
fig.suptitle("DCM 5 W, Kp = 1, MLCC HF de la fiche en place — seul "
             "changement : l'instant d'échantillonnage", fontsize=12)
k0 = 150
for j, ((t, g, von, pic, dk, shk), nom, c) in enumerate(zip(L, noms, coul)):
    m = (t >= k0 * T) & (t < (k0 + 2) * T)
    a = ax[0, j]
    a.plot((t[m] - k0 * T) * 1e6, g["V(nout)"][m], lw=0.5, color="#888888",
           label="V(nout)")
    a.plot((t[m] - k0 * T) * 1e6, g["V(nvm)"][m], lw=1.0, color="#66aaff",
           label="mesure filtrée 1 µs")
    a.plot((t[m] - k0 * T) * 1e6, g["V(nsh)"][m], lw=1.6, color=c,
           label="échantillon")
    a.set_ylim(75, 85)
    a.set_xlabel("t  [µs]")
    a.set_ylabel("[V]")
    a.legend(fontsize=8, loc="upper right")
    a.set_title(nom, fontsize=10, color=c)
    a = ax[1, j]
    a.plot(KS * T * 1e3, dk, "o-", ms=3, lw=0.8, color=c)
    a.set_ylim(0.425, 0.455)
    a.set_xlabel("t  [ms]")
    a.set_ylabel("D par période")
    a.set_title(f"échantillon σ {shk.std()*1e3:.2f} mV → D σ {dk.std():.5f}, "
                f"D moyen {dk.mean():.4f}", fontsize=10)
    print(f"{nom:52s} echantillon sigma {shk.std()*1e3:.3f} mV  D sigma "
          f"{dk.std():.5f}  D moy {dk.mean():.4f}  echantillon moy {shk.mean():.4f}")
for a in ax.flat:
    a.grid(alpha=0.25); a.grid(alpha=0.1, which="minor")
    a.xaxis.set_minor_locator(AutoMinorLocator())
fig.tight_layout()
out = ICI / "r2_dcm_phase.png"
fig.savefig(out, dpi=120)
for f in fs:
    f.with_suffix(".raw").unlink()
print(f"figure : {out}")
