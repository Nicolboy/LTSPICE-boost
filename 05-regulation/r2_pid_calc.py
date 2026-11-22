"""R2 -- reglage PID CCM calcule sur le plant MESURE a 50 W (pire point).

Plant : r2_multitons50.py, 35 tons de 2 a 60 kHz (deux bandes). Lissage de
log|H| et de la phase par polynomes en log f (degre 5), grille fine.

Correcteur, tel que le banc l'implemente (etape0 : kp, ki, kd ; mesure
echantillonnee a 0,998 T, retard d'une periode : la periode n utilise
s[n-2]) :
  C(z) = Kp + Ki.T.( z^-1/(1-z^-1) + D ) + (Kd/T).(1 - z^-1)
  L(z) = C(z) . z^-2 . H(z)
Marges : phase a |L| = 1 (dernier croisement), gain la ou arg L = -180.
Ki : meme zero d'integrale que le PI retenu (Ki/Kp ~ 1430 /s, soit
8/0,0056), pour ne changer qu'une chose a la fois -- la derivee.

Criteres : MG >= 6 dB et MP >= 45 deg ; parmi les reglages qui les
tiennent, le plus grand croisement (bande passante).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
FSW, T, D0 = 200e3, 5e-6, 0.7489
KI_SUR_KP = 8.0 / 0.00558

R = np.load(ICI / "r2_multitons50.npy", allow_pickle=True).item()
RH = np.load(ICI / "r2_multitons50_haute.npy", allow_pickle=True).item()
# deux bandes fusionnees : 2-20 kHz et 20-60 kHz (le 20 kHz n'est garde
# qu'une fois). La premiere version, 2-20 kHz seule, rendait une marge de
# gain "infinie" : la phase ne repassait a -180 qu'au-dela de 20 kHz.
rows = list(R["rows"]) + [r for r in RH["rows"] if r[0] > 20000]
f = np.array([r[0] for r in rows])
mag = np.array([r[1] for r in rows])
ph = np.unwrap(np.radians([r[2] for r in rows]))
pm_ = np.polyfit(np.log(f), np.log(mag), 5)
pp_ = np.polyfit(np.log(f), ph, 5)
ff = np.geomspace(f[0], f[-1], 6000)   # 2-60 kHz, mesure
H = np.exp(np.polyval(pm_, np.log(ff)) + 1j * np.polyval(pp_, np.log(ff)))
disp = np.std(np.exp(np.polyval(pm_, np.log(f))) / mag - 1)
z = np.exp(1j * 2 * np.pi * ff / FSW)


def marges(kp, kd, ki=None):
    ki = KI_SUR_KP * kp if ki is None else ki
    C = kp + ki * T * (z ** -1 / (1 - z ** -1) + D0) + kd / T * (1 - z ** -1)
    L = C * z ** -2 * H
    mag_, phd = np.abs(L), np.degrees(np.unwrap(np.angle(L)))
    # croisement |L| = 1 : le DERNIER (la bande passante)
    c = np.where(np.diff(np.sign(mag_ - 1)) != 0)[0]
    if len(c) == 0:
        return None
    i = c[-1]
    fc, mp = ff[i], 180 + phd[i]
    # marge de gain : premier passage de la phase a -180 au-dela de fc
    g = np.where((np.diff(np.sign(phd + 180)) != 0) & (np.arange(len(ff) - 1) >= i))[0]
    mg = -20 * np.log10(mag_[g[0]]) if len(g) else np.inf
    fg = ff[g[0]] if len(g) else np.nan
    return fc, mp, mg, fg


print(f"  plant CCM 50 W mesure, {len(f)} tons de {f[0]/1e3:.0f} a {f[-1]/1e3:.0f} kHz, dispersion |H| autour du lissage"
      f" {disp*100:.1f} %\n")
print("  REFERENCE, PI retenu (Kp 0,00558, Ki 8, Kd 0) :")
m = marges(0.00558, 0.0, 8.0)
print(f"     croisement {m[0]/1e3:.2f} kHz, MP {m[1]:.0f} deg, MG {m[2]:.1f} dB"
      f" a {m[3]/1e3:.2f} kHz\n")
best = []
for kp in np.geomspace(0.002, 0.03, 40):
    for kd in np.geomspace(1e-8, 3e-6, 60):
        m = marges(kp, kd)
        if m is None:
            continue
        fc, mp, mg, fg = m
        if mp >= 45 and mg >= 6:
            best.append((fc, kp, kd, mp, mg, fg))
best.sort(reverse=True)
print("  PID tenant MG >= 6 dB et MP >= 45 deg, croisement le plus haut :")
for fc, kp, kd, mp, mg, fg in best[:8]:
    print(f"     Kp {kp:.5f}  Ki {KI_SUR_KP*kp:6.2f}  Kd {kd:.3e}  ->  croisement"
          f" {fc/1e3:5.2f} kHz  MP {mp:4.0f} deg  MG {mg:4.1f} dB a {fg/1e3:5.2f} kHz")
if best:
    fc, kp, kd, mp, mg, fg = best[0]
    np.save(ICI / "r2_pid_calc.npy", dict(kp=kp, ki=KI_SUR_KP * kp, kd=kd,
                                          fc=fc, mp=mp, mg=mg), allow_pickle=True)
# PI seul, pour comparer a marges egales
pis = []
for kp in np.geomspace(0.001, 0.03, 80):
    m = marges(kp, 0.0)
    if m and m[1] >= 45 and m[2] >= 6:
        pis.append((m[0], kp, m[1], m[2]))
pis.sort(reverse=True)
if pis:
    print(f"\n  PI seul aux memes criteres : meilleur croisement {pis[0][0]/1e3:.2f}"
          f" kHz a Kp {pis[0][1]:.5f} (MP {pis[0][2]:.0f}, MG {pis[0][3]:.1f} dB)")
else:
    print("\n  PI seul : AUCUN reglage ne tient MG 6 dB et MP 45 deg")


# ---------------------------------------------------------------------
# REGLAGE RETENU, trace depuis ce fichier (verdict du gendarme : le choix
# n'etait ni sauvegarde ni reproductible). Choisi dans la liste ci-dessus
# avec MP >= 50 deg plutot que le croisement maximal (MP 46 deg).
KP_R, KI_R, KD_R = 0.0140, 20.0, 1.04e-6
m = marges(KP_R, KD_R, KI_R)
print(f"\n  RETENU Kp {KP_R} Ki {KI_R} Kd {KD_R:.3g} : croisement {m[0]/1e3:.2f} kHz,"
      f" MP {m[1]:.0f} deg, MG {m[2]:.1f} dB a {m[3]/1e3:.2f} kHz (bande 2-60 kHz)")
# HORS BANDE : la derivee fait remonter |L| jusqu'a fsw/2. On borne la
# marge sous deux hypotheses de plant entre 60 et 100 kHz.
fx = np.linspace(60e3, 99.9e3, 400)
zx = np.exp(1j * 2 * np.pi * fx / FSW)
Hk = H[-1]
Cx = (KP_R + KI_R * T * (zx ** -1 / (1 - zx ** -1) + D0)
      + KD_R / T * (1 - zx ** -1))
for nom, Hx in (("|H| plat (pire)", Hk * np.ones_like(fx)),
                ("|H| en 1/f", Hk * f[-1] / fx)):
    Lx = np.abs(Cx * zx ** -2 * Hx)
    print(f"     60-100 kHz, {nom:16s} : |L| max {20*np.log10(Lx.max()):+.1f} dB"
          f" a {fx[np.argmax(Lx)]/1e3:.0f} kHz -> marge >= {-20*np.log10(Lx.max()):.1f} dB"
          f" si la phase y passe -180")
np.save(ICI / "r2_pid_retenu.npy",
        dict(kp=KP_R, ki=KI_R, kd=KD_R, fc=m[0], mp=m[1], mg_bande=m[2],
             fg=m[3], bande="2-60 kHz, 50 W"), allow_pickle=True)
