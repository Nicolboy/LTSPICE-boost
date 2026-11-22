"""Figure du temoin R2 (Kp=0,002) -- et UNE question qu'elle doit trancher.

L'ondulation basse frequence de la moyenne par periode vaut 0,732 V.
Deux lectures possibles :
  a) residu de l'ondulation de decoupage mal annulee par la fenetre
     glissante (dont la largeur est estimee, pas exacte) ;
  b) CYCLE LIMITE a la resonance du plant (~3,9 kHz) : le pic multiplie
     le gain par Q = R/Z0 = 160/18,5 = 8,6, donc Kp.G au pic ~ 5 > 1
     meme quand Kp.G(DC) = 0,64. L'oscillation serait reelle, bornee
     par les non-linearites -- et expliquerait l'echec a Kp = 0,01
     (croissance jusqu'aux butees puis mort du modele).
La frequence dominante tranche : ~200 kHz -> (a) ; ~4 kHz -> (b).
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
from simcommun.lecture import lire                           # noqa: E402

FSW = 200e3

r = lire(str(ICI / "p_temoin.raw"))
t = np.asarray(r.x)
v = np.asarray(r.trace("V(nout)")).real
d = np.asarray(r.trace("V(nctrl)")).real

# REECHANTILLONNAGE UNIFORME AVANT TOUTE MOYENNE : les pas de LTspice se
# resserrent sur les fronts, une moyenne par echantillons est ponderee
# par la densite de pas (79,933 V lus contre 80,087 V vrais, constate).
np_ = 256
n = max(int(round((t[-1] - t[0]) * FSW)) * np_, 4 * np_)
tu = np.linspace(t[0], t[-1], n)
vu, du = np.interp(tu, t, v), np.interp(tu, t, d)


def gliss(y):
    c = np.concatenate(([0.0], np.cumsum(y)))
    return (c[np_:] - c[:-np_]) / np_


vm, dm = gliss(vu), gliss(du)
tm = tu[np_ // 2: np_ // 2 + len(vm)]

# fenetre d'analyse : les derniers 60 % (regime etabli)
m = tm > tm[0] + 0.4 * (tm[-1] - tm[0])
tv, vv, dv = tm[m], vm[m], dm[m]

# frequence dominante de l'ondulation de la MOYENNE (reechantillonnee
# uniforme avant FFT -- les pas de LTspice ne le sont pas)
tu = np.linspace(tv[0], tv[-1], 1 << 14)
vu = np.interp(tu, tv, vv) - np.mean(vv)
sp = np.abs(np.fft.rfft(vu * np.hanning(len(vu))))
fr = np.fft.rfftfreq(len(vu), tu[1] - tu[0])
k = np.argmax(sp[1:]) + 1
f_dom = fr[k]
print(f"frequence dominante de l'ondulation moyenne : {f_dom/1e3:.2f} kHz")
print(f"amplitude cc de la moyenne glissante : {vv.max()-vv.min():.3f} V")
print(f"ondulation brute (avec decoupage)    : {v[m.nonzero()[0]].max()-v[np.nonzero(m)[0]].min():.3f} V"
      if False else "")

plt.style.use("dark_background")
fig, ax = plt.subplots(3, 1, figsize=(11, 8), sharex=False,
                       gridspec_kw=dict(height_ratios=(2, 1, 1)))
fig.suptitle("R2 témoin — P pur, Kp = 0,002 (Kp·G(DC) = 0,64), 40 W CCM",
             fontsize=12)

w = tm * 1e6
ax[0].plot(t * 1e6, v, lw=0.4, color="#4a6a8a", label="V(nout) brut")
ax[0].plot(w, vm, lw=1.4, color="#ffb347", label="moyenne sur 1 période")
ax[0].axhline(80, color="#66dd66", lw=0.8, ls="--", label="consigne 80 V")
ax[0].set_ylabel("V(nout)  [V]")
ax[0].legend(loc="lower right", fontsize=8)
ax[0].set_title(f"fenêtre complète — ondulation de la moyenne "
                f"{vv.max()-vv.min():.2f} V cc, dominante {f_dom/1e3:.1f} kHz",
                fontsize=10)

# zoom mesurable : 5 alternances de la dominante, en fin de fenetre
nz = 5 / max(f_dom, 1.0)
mz = tm > tm[-1] - nz
ax[1].plot(tm[mz] * 1e6, vm[mz], lw=1.2, color="#ffb347")
ax[1].axhline(80, color="#66dd66", lw=0.8, ls="--")
ax[1].set_ylabel("moyenne  [V]")
ax[1].set_title(f"zoom : 5 périodes de la dominante ({f_dom/1e3:.1f} kHz)",
                fontsize=10)

ax[2].plot(w, dm, lw=1.0, color="#dd77dd")
ax[2].axhline(0.750929, color="#888888", lw=0.8, ls="--",
              label="duty₀ = 0,7509")
ax[2].set_ylabel("rapport cyclique")
ax[2].set_xlabel("t  [µs]")
ax[2].legend(loc="lower right", fontsize=8)

for a in ax:
    a.grid(alpha=0.25)
fig.tight_layout()
out = ICI / "r2_temoin.png"
fig.savefig(out, dpi=130)
print(f"figure : {out}")
