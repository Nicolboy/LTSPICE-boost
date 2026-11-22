"""Six oscillogrammes : echelons croissants (haut) et decroissants (bas),
les deux PI superposes. <Vout> par periode sur 75-85 V (plage demandee
par le concepteur), D par periode en dessous. Memes echelles partout,
t = 0 a l'echelon. Mesures : excursion depuis le pre-echelon, retour a
+-0,1 V de la valeur finale, efficace residuel de Vout sur la derniere ms.
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
import r2_echelons as e                                      # noqa: E402

COUL = {"ccm": "#ff9944", "dcm": "#66dd66", "ccm2": "#66aaff", "pid": "#ff66ff"}
LISTE = sys.argv[1:] or ["ccm", "dcm"]
LIB = {"ccm": "PI CCM 30 W (Kp 0,0093, Ki 12)", "dcm": "PI DCM (Kp 0,61, Ki 785)",
       "ccm2": "PI CCM 50 W (Kp 0,0056, Ki 8)",
       "pid": "PID CCM 50 W (Kp 0,014, Ki 20, Kd 1,04e-6)"}


def mesures(D):
    tb, vb = D["tb"], D["vb"]
    ts = e.N_AVANT * e.T
    av = (tb > ts - 0.5e-3) & (tb < ts)
    ap = tb > ts
    fin = tb > tb[-1] - 1e-3
    v0, vf = float(vb[av].mean()), float(vb[fin].mean())
    x = vb[ap] - v0
    exc = float(x[np.argmax(np.abs(x))])
    hors = np.where(np.abs(vb[ap] - vf) > 0.1)[0]
    t_ret = float(tb[ap][hors[-1]] - ts) * 1e3 if len(hors) else 0.0
    resid = float(np.std(vb[fin]))
    ccm_ap = float(np.mean(D["imin"][ap] > 0.02))
    return dict(v0=v0, vf=vf, exc=exc, t_ret=t_ret, resid=resid, ccm=ccm_ap)


plt.style.use("dark_background")
fig = plt.figure(figsize=(19, 14))
fig.suptitle("R2 — six échelons de charge, deux réglages PI appliqués chacun "
             "seul (aucun basculement) — banc complet — " + " / ".join(LIB[x] for x in LISTE) + "\n⟨Vout⟩ par période "
             "(75-85 V) et D par période, t = 0 à l'échelon ; frontière "
             "DCM/CCM 15,3 W", fontsize=12)
gs = fig.add_gridspec(4, 3, height_ratios=[2, 1, 2, 1], hspace=0.8)
for idx, (p1, p2) in enumerate(e.ECHELONS):
    r, c = divmod(idx, 3)
    a = fig.add_subplot(gs[2 * r, c])
    b = fig.add_subplot(gs[2 * r + 1, c], sharex=a)
    titre = [f"{p1} → {p2} W   ({e.mode(p1)}/{e.mode(p2)})"]
    for pi in LISTE:
        f = ICI / f"ze_{p1}_{p2}_{pi}.npz"
        if not f.exists():
            titre.append(f"{LIB[pi]} : simulation morte")
            continue
        D = np.load(f)
        t = (D["tb"] - e.N_AVANT * e.T) * 1e3
        a.plot(t, D["vb"], lw=0.9, color=COUL[pi], label=LIB[pi])
        b.plot(t, D["db"], lw=0.8, color=COUL[pi])
        m = mesures(D)
        etat = ("OSCILLE" if m["resid"] > 0.15 else
                f"{m['exc']:+.2f} V, {m['t_ret']:.1f} ms")
        titre.append(f"{pi.upper()} : {etat}"
                     + (f", CCM {m['ccm']*100:.0f} %" if 0 < m["ccm"] < 0.99 else ""))
        print(f"  {p1:2d}->{p2:2d} W  {pi}  pre {m['v0']:.3f}  exc {m['exc']:+.3f} V"
              f"  retour {m['t_ret']:.2f} ms  final {m['vf']:.3f}  residu "
              f"{m['resid']*1e3:.0f} mV  CCM apres {m['ccm']*100:.0f} %")
    a.set_title("\n".join(titre), fontsize=9)
    a.set_ylim(75, 85)
    a.axhline(80, color="#777777", lw=0.6, ls=":")
    b.set_ylim(0.3, 0.95)
    for x in (a, b):
        x.axvline(0, color="#aaaaaa", lw=0.8, ls="--")
        x.grid(alpha=0.25)
        x.set_xlim(-1, 7)
    if c == 0:
        a.set_ylabel("⟨Vout⟩ [V]")
        b.set_ylabel("D")
    b.set_xlabel("t depuis l'échelon [ms]", fontsize=8)
    if idx == 0:
        a.legend(fontsize=8, loc="lower right")
out = ICI / f"r2_echelons_{'_'.join(LISTE)}.png"
fig.savefig(out, dpi=115, bbox_inches="tight")
print(f"figure : {out}")
