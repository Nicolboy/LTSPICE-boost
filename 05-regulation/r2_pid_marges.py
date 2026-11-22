"""R2 -- marges du PID CCM sur le plant mesure a 50 W de 2 a 97,5 kHz.

Trois bandes multi-tons (r2_multitons50*.npy : 2-20, 20-60, 60-97,5 kHz,
51 tons). Interpolation DIRECTE entre points mesures (log|H| et phase
deroulee, lineaires en log f) -- pas de polynome sur deux decades.
Repond a la reserve du gendarme : au-dela de 60 kHz la derivee fait
remonter |L| et la marge de gain n'etait pas etablie (3,9 a 5,7 dB
selon l'hypothese de plant).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
FSW, T, D0 = 200e3, 5e-6, 0.7489

rows = []
for nom, fmin in (("r2_multitons50.npy", 0), ("r2_multitons50_haute.npy", 20000),
                  ("r2_multitons50_tres_haute.npy", 60000)):
    R = np.load(ICI / nom, allow_pickle=True).item()
    rows += [r for r in R["rows"] if r[0] > fmin]
rows.sort()
f = np.array([r[0] for r in rows])
mag = np.array([r[1] for r in rows])
ph = np.unwrap(np.radians([r[2] for r in rows]))
ff = np.geomspace(f[0], f[-1], 20000)
H = np.exp(np.interp(np.log(ff), np.log(f), np.log(mag))
           + 1j * np.interp(np.log(ff), np.log(f), ph))
z = np.exp(1j * 2 * np.pi * ff / FSW)


def boucle(kp, ki, kd):
    C = kp + ki * T * (z ** -1 / (1 - z ** -1) + D0) + kd / T * (1 - z ** -1)
    return C * z ** -2 * H


def marges(kp, ki, kd):
    L = boucle(kp, ki, kd)
    m, p = np.abs(L), np.degrees(np.unwrap(np.angle(L)))
    c = np.where(np.diff(np.sign(m - 1)) != 0)[0]
    i = c[-1]
    out = dict(fc=ff[i], mp=180 + p[i], croisements=len(c))
    # tous les passages de la phase a -180 (mod 360) au-dela du croisement
    k = np.where(np.diff(np.floor((p + 180) / 360)) != 0)[0]
    k = k[k > i]
    out["mg"] = [(-20 * np.log10(m[j]), ff[j]) for j in k]
    out["Lmax_hf"] = (20 * np.log10(m[ff > out["fc"] * 1.5].max()),
                      ff[ff > out["fc"] * 1.5][np.argmax(m[ff > out["fc"] * 1.5])])
    return out


print(f"  plant 50 W mesure : {len(f)} tons de {f[0]/1e3:.0f} a {f[-1]/1e3:.1f} kHz\n")
for nom, (kp, ki, kd) in (("PI 50 W", (0.00558, 8.0, 0.0)),
                          ("PID retenu", (0.0140, 20.0, 1.04e-6))):
    o = marges(kp, ki, kd)
    print(f"  {nom:10s} Kp {kp} Ki {ki} Kd {kd:.3g}")
    print(f"     croisement {o['fc']/1e3:.2f} kHz, MP {o['mp']:.0f} deg")
    for mg, fg in o["mg"]:
        print(f"     passage a -180 deg a {fg/1e3:5.1f} kHz : marge de gain {mg:.1f} dB")
    print(f"     |L| max au-dela de 1,5 x fc : {o['Lmax_hf'][0]:+.1f} dB a "
          f"{o['Lmax_hf'][1]/1e3:.1f} kHz\n")
np.save(ICI / "r2_pid_marges.npy", dict(f=f, mag=mag, ph=ph), allow_pickle=True)
