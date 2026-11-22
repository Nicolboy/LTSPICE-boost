"""Oscillogrammes de la k-section DCM -- echelon 5 -> 10 W a t = 1 ms.

Banc : FDD770N15A, Wurth 10 uF/100 V + MLCC HF de la fiche, mesure filtree
1 us puis echantillonnee a 0,998 T (fin de fenetre S+H du F28P551 avant
la fermeture du MOSFET). Un panneau par Kp, Kp decroissant, MEMES ECHELLES.

En DCM le mode qui decroche est l'ALTERNANCE de D d'un cycle a l'autre :
la moyenne de Vout par periode n'en montre presque rien (quelques mV). On
trace donc D par periode (en haut, la bande s'epaissit quand D alterne)
et <Vout> par periode (en bas, plage 75-85 V).
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
import r2_ziegler_dcm as d                                   # noqa: E402
import r2_ziegler as z                                       # noqa: E402

cas = []
for f in sorted(ICI.glob(f"{d.PREFIXE}[0-9]_*.npz")):
    cir = f.with_suffix(".cir").read_text(encoding="utf-8")
    kp = float(cir.split("Bctrl")[1].split("+ ")[1].split("*")[0])
    D = dict(np.load(f))
    cas.append((kp, D, d.verdict(D)))
cas.sort(key=lambda c: -c[0])

n, nc = len(cas), 4
nl = int(np.ceil(n / nc))
plt.style.use("dark_background")
fig = plt.figure(figsize=(18, 4.2 * nl + 1))
fig.suptitle("R2 DCM — échelon 5 → 10 W à t = 1 ms, P pur, FDD770N15A + Würth "
             "10 µF + MLCC HF, mesure échantillonnée à 0,998 T"
             + (" + retard d'une période" if d.RETARD else "") + " (C2000)\n"
             "en haut : D par période (la bande s'épaissit quand D alterne) — "
             "en bas : ⟨Vout⟩ par période, 75-85 V", fontsize=12)
gs = fig.add_gridspec(nl * 2, nc, height_ratios=[1.3, 1] * nl)
ts = d.N_AVANT / z.FSW
for i, (kp, D, v) in enumerate(cas):
    r, c = divmod(i, nc)
    col = "#66dd66" if v["stable"] else "#ff66ff"
    a = fig.add_subplot(gs[2 * r, c])
    b = fig.add_subplot(gs[2 * r + 1, c], sharex=a)
    a.plot(D["tb"] * 1e3, D["db"], lw=0.5, color=col)
    a.set_ylim(0, 1)
    a.axvline(ts * 1e3, color="#aaaaaa", lw=0.8, ls="--")
    a.set_title(f"Kp {kp:.4f}  (K10W {kp*d.G10:.0f}) — "
                f"{'stable' if v['stable'] else 'INSTABLE'}\n"
                f"alternance D {v['alt']:.4f} ({v['c_alt']}), "
                f"CCM {v['ccm']*100:.0f} %", fontsize=9, color=col)
    b.plot(D["tb"] * 1e3, D["vb"], lw=0.8, color=col)
    b.set_ylim(75, 85)
    b.axvline(ts * 1e3, color="#aaaaaa", lw=0.8, ls="--")
    b.axhline(80, color="#666666", lw=0.6, ls=":")
    for x in (a, b):
        x.grid(alpha=0.25)
    if c == 0:
        a.set_ylabel("D")
        b.set_ylabel("⟨Vout⟩ [V]")
    b.set_xlabel("t  [ms]", fontsize=8)
fig.tight_layout()
out = ICI / f"r2_ziegler_dcm_{d.PREFIXE}_reponses.png"
fig.savefig(out, dpi=110)
print(f"figure : {out}  ({n} cas)")
