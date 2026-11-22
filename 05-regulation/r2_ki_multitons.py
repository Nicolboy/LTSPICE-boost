"""R2 -> PI : limite de Ki par une SECONDE methode (sans simulation).

Plant CCM mesure par injection multi-tons (r2_multitons.py, 9 tons de 3 a
7 kHz, |H| disperse a 1 % autour d'un lissage du second degre). On y
branche le PI TEL QUE LE BANC L'IMPLEMENTE :

  - nsh2 = s[n-2] est constant sur la periode n (retard d'une periode) ;
  - l'integrale V(nint) est une integration CONTINUE de Ki.(Vref - nsh2) :
    sur une periode elle croit de Ki.T.e[n] ; au blocage (t = D.T dans la
    periode, D ~ 0,75) elle vaut I[n-1] + D.Ki.T.e[n] ;
  - d[n] = Kp.e[n] + I[n-1] + D.Ki.T.e[n],  e[n] = -s[n-2] (ecart).
  Donc C(z) = Kp + Ki.T.( z^-1/(1 - z^-1) + D )  et  L = C(z).z^-2.H(z).

Limite : Ki tel que |L| = 1 la ou arg L = -180 deg (bissection sur Ki),
a Kp = 0,00932. A comparer a la k-section : sigma s'annule entre
Ki 29,7 et 31,7 (encadrement du script [24,5 ; 26,2], biais DCM).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
FSW, T, D0, KP = 200e3, 5e-6, 0.7519, 0.00932

R = np.load(ICI / "r2_multitons_resultats.npy", allow_pickle=True).item()
rows = R["ccm"]["rows"]
f = np.array([r[0] for r in rows])
mag = np.array([r[1] for r in rows])
phH = np.unwrap(np.radians([r[2] for r in rows]))
pm = np.polyfit(np.log(f), np.log(mag), 2)          # lissage, 1 % de dispersion
pp = np.polyfit(f, phH, 2)
ff = np.linspace(f[0], f[-1], 40001)
H = np.exp(np.polyval(pm, np.log(ff))) * np.exp(1j * np.polyval(pp, ff))
z = np.exp(1j * 2 * np.pi * ff / FSW)


def boucle(ki):
    C = KP + ki * T * (z ** -1 / (1 - z ** -1) + D0)
    return C * z ** -2 * H


def marge(ki):
    """|L| au premier passage de arg L a -180 deg dans la bande mesuree."""
    L = boucle(ki)
    ph = np.degrees(np.unwrap(np.angle(L)))
    i = np.where(np.diff(np.sign(ph + 180)) != 0)[0]
    if len(i) == 0:
        return None, None
    return abs(L[i[0]]), ff[i[0]]


print(f"  plant CCM multi-tons, PI du banc (Kp {KP}), bande {f[0]/1e3:.0f}-"
      f"{f[-1]/1e3:.0f} kHz")
for ki in (0, 5, 12, 20, 25, 30, 35, 45, 57):
    m, fc = marge(ki)
    print(f"     Ki {ki:5.1f}  |L| a -180 deg = "
          f"{'-' if m is None else f'{m:.3f}'}  a "
          f"{'-' if fc is None else f'{fc/1e3:.2f} kHz'}"
          f"  -> {'STABLE' if (m is not None and m < 1) else 'instable' if m else '?'}")
lo, hi = 0.0, 100.0
for _ in range(60):
    mid = 0.5 * (lo + hi)
    m, _ = marge(mid)
    if m is not None and m < 1:
        lo = mid
    else:
        hi = mid
m, fc = marge(lo)
print(f"\n  LIMITE Ki (seconde methode) : {lo:.2f} /V/s, oscillation a "
      f"{fc/1e3:.2f} kHz")
print("  k-section : sigma = 0 entre Ki 29,7 et 31,7, a 3,48 kHz")
