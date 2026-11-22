"""R2 -- PID CCM a derivee sur DEUX echantillons, calcule sur le plant mesure.

Plant 50 W, 50 tons de 2 a 97,5 kHz (r2_pid_marges : interpolation directe).
Correcteur du banc (etape0, kd2=True) :
  C(z) = Kp + Ki.T.(z^-1/(1-z^-1) + D) + Kd/(2T).(1 - z^-2) ;  L = C z^-2 H
Le terme (1 - z^-2) est nul a fsw/2, ou la derivee simple faisait tomber
la marge de gain a ~4,5 dB.
Criteres, sur TOUTE la bande jusqu'a fsw/2 : MP >= 45 deg ; marge de gain
>= 6 dB a CHAQUE passage a -180 deg ET au point de Nyquist (L reel a
fsw/2, H pris a sa valeur mesuree la plus haute, 97,5 kHz) ; marge de
module min|1+L| >= 0,5. Ki/Kp fixe comme avant (1434 /s).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import r2_pid_marges as pm                                    # noqa: E402

T, D0, FSW = pm.T, pm.D0, pm.FSW
KI_SUR_KP = 8.0 / 0.00558
ff = np.append(pm.ff, FSW / 2)                 # + point de Nyquist
H = np.append(pm.H, pm.H[-1])
z = np.exp(1j * 2 * np.pi * ff / FSW)


def boucle(kp, ki, kd, deux=True):
    der = kd / (2 * T) * (1 - z ** -2) if deux else kd / T * (1 - z ** -1)
    C = kp + ki * T * (z ** -1 / (1 - z ** -1) + D0) + der
    return C * z ** -2 * H


def marges(kp, ki, kd, deux=True):
    L = boucle(kp, ki, kd, deux)
    m, p = np.abs(L), np.degrees(np.unwrap(np.angle(L)))
    c = np.where(np.diff(np.sign(m - 1)) != 0)[0]
    if len(c) == 0:
        return None
    i = c[-1]
    k = np.where(np.diff(np.floor((p + 180) / 360)) != 0)[0]
    k = k[k > i]
    mgs = [-20 * np.log10(m[j]) for j in k] + [-20 * np.log10(m[-1])]   # + Nyquist
    return dict(fc=ff[i], mp=180 + p[i], mg=min(mgs), mod=float(np.min(np.abs(1 + L))),
                mg_nyq=-20 * np.log10(m[-1]))


print("  PID derivee simple (retenu au commit 0a42a35) :")
o = marges(0.014, 20.0, 1.04e-6, deux=False)
print(f"     fc {o['fc']/1e3:.2f} kHz  MP {o['mp']:.0f}  MG min {o['mg']:.1f} dB"
      f" (Nyquist {o['mg_nyq']:.1f})  min|1+L| {o['mod']:.2f}\n")
ok = []
for kp in np.geomspace(0.004, 0.03, 45):
    for kd in np.geomspace(1e-7, 6e-6, 60):
        o = marges(kp, KI_SUR_KP * kp, kd)
        if o and o["mp"] >= 45 and o["mg"] >= 6 and o["mod"] >= 0.5:
            ok.append((o["fc"], kp, kd, o))
ok.sort(key=lambda x: -x[0])
print("  PID derivee sur deux echantillons, criteres tenus, croisement le plus haut :")
for fc, kp, kd, o in ok[:6]:
    print(f"     Kp {kp:.5f} Ki {KI_SUR_KP*kp:6.2f} Kd {kd:.3e} -> fc {fc/1e3:5.2f} kHz"
          f"  MP {o['mp']:3.0f}  MG min {o['mg']:4.1f} dB (Nyquist {o['mg_nyq']:4.1f})"
          f"  min|1+L| {o['mod']:.2f}")
# retenu : le plus haut croisement avec MP >= 50 (meme regle que la premiere fois)
ret = next((x for x in ok if x[3]["mp"] >= 50), None)
if ret:
    fc, kp, kd, o = ret
    kp, kd = round(kp, 4), float(f"{kd:.3g}")
    o = marges(kp, round(KI_SUR_KP * kp, 1), kd)
    print(f"\n  RETENU (MP >= 50, arrondi) : Kp {kp} Ki {round(KI_SUR_KP*kp, 1)} Kd {kd}"
          f" -> fc {o['fc']/1e3:.2f} kHz  MP {o['mp']:.0f}  MG min {o['mg']:.1f} dB"
          f" (Nyquist {o['mg_nyq']:.1f})  min|1+L| {o['mod']:.2f}")
    np.save(ICI / "r2_pid2_retenu.npy", dict(kp=kp, ki=round(KI_SUR_KP * kp, 1),
            kd=kd, kd2=True, **o, bande="2-97,5 kHz + Nyquist, 50 W"), allow_pickle=True)

# ---------------------------------------------------------------------
# ADOPTE (seance du 2026-11-22) : Kp ramene a celui du PID simple, Ki et
# Kd ajustes pour garder MP >= 45 deg et MG >= 6 dB sur toute la bande,
# Nyquist compris. Valide sur les six echelons (r2_echelons.py pid3).
KP_A, KI_A, KD_A = 0.0138, 19.8, 9.2e-7
o = marges(KP_A, KI_A, KD_A)
print(f"\n  ADOPTE Kp {KP_A} Ki {KI_A} Kd {KD_A} : fc {o['fc']/1e3:.2f} kHz  MP {o['mp']:.0f}"
      f"  MG min {o['mg']:.1f} dB (Nyquist {o['mg_nyq']:.1f})  min|1+L| {o['mod']:.2f}")
np.save(ICI / "r2_pid_adopte.npy", dict(kp=KP_A, ki=KI_A, kd=KD_A, kd2=True, **o,
        bande="2-97,5 kHz + Nyquist, 50 W"), allow_pickle=True)
