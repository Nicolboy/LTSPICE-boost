"""P seul contre PI Ziegler-Nichols, meme banc, memes echelles (RETEX Q)."""
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
import r2_ziegler as z                                       # noqa: E402
import r2_pi as pi                                           # noqa: E402

CAS = (("zkf1_1", "P seul, Kp 0,00965", "#66dd66"),
       ("pi_zn", f"PI Ziegler-Nichols, Kp {pi.KP:.5f}, Ki {pi.KI:.1f} /V/s",
        "#ff66ff"))
plt.style.use("dark_background")
fig, axs = plt.subplots(2, 2, figsize=(16, 8), sharex=True,
                        gridspec_kw=dict(height_ratios=(3, 2)))
fig.suptitle("R2 — échelon 40 → 30 W à t = 1 ms, CCM, FDD770N15A + Würth "
             "10 µF/100 V, mesure filtrée 1 µs — mêmes échelles", fontsize=12)
ts = z.N_AVANT / z.FSW
for j, (tag, lib, c) in enumerate(CAS):
    d = dict(np.load(ICI / f"{tag}.npz"))
    m = pi.mesures(d)
    v = m["verdict"]
    a, b = axs[0, j], axs[1, j]
    a.plot(d["tb"] * 1e3, d["vb"], lw=0.9, color=c)
    b.plot(d["tb"] * 1e3, d["db"], lw=0.9, color=c)
    for x in (a, b):
        x.axvline(ts * 1e3, color="#aaaaaa", lw=0.8, ls="--")
        x.grid(alpha=0.25); x.grid(alpha=0.1, which="minor")
        x.xaxis.set_minor_locator(AutoMinorLocator())
        x.yaxis.set_minor_locator(AutoMinorLocator())
    a.axhline(80, color="#666666", lw=0.6, ls=":")
    a.set_title(f"{lib}\n{v['cls'].split(' (')[0]} — {v['f']/1e3:.2f} kHz, "
                f"enveloppe {v['app']:.2f} V c-à-c, DCM {v['dcm']*100:.0f} %",
                fontsize=10, color=c)
    a.set_ylim(77, 83)
    b.set_ylim(0.6, 0.9)
    b.set_xlabel("t  [ms]")
axs[0, 0].set_ylabel("⟨V(nout)⟩ par période  [V]")
axs[1, 0].set_ylabel("⟨D⟩ par période")
fig.tight_layout()
out = ICI / "r2_pi_zn.png"
fig.savefig(out, dpi=130)
print(f"figure : {out}")
