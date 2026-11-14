"""Volet EMI/resonance (README S9) -- spectre CEM CONDUIT estime
via un LISN simplifie (gen_boost2_tech.build(add_lisn=True)) + FFT
(numpy) de la tension mesuree sur la branche 50Ohm du LISN. PAS une
mesure certifiee -- ordre de grandeur qualitatif, compare a un gabarit
CISPR 22/32 classe B usuel (le plus souvent cite en illustration, pas
necessairement LE standard applicable a une alimentation DC -- a
confirmer si une conformite reelle est visee un jour).

Combinaison retenue (voir README S9, "Choix definitif etage 1") : NVD6824NL +
VS-6CWQ10FN-M3, point nominal 20V->80V/40W, 200kHz, L=47uH.

Necessite `spicelib` (lecture du .raw LTspice) -- `pip install
spicelib` si absent. Le package `ltspice` (alternative plus simple)
s'est trouve incompatible avec le format .raw de LTspice 26.1.1 lors de
l'implementation (erreur de parsing binaire) -- utiliser spicelib.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from spicelib import RawRead

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from find_duty2 import find_duty

L = 47e-6
DCR = 8.95e-3
FSW = 200e3
SWITCH = "NVD6824NL"
DIODE = "VS-6CWQ10FN-M3"
F0_RESONANCE_HZ = 47.55e6  # deja calcule, doc S4 -- NVD6824NL+VS-6CWQ10FN-M3

# Gabarit CISPR 22/32 classe B, limite quasi-crete usuelle (dBuV) --
# illustratif seulement (mains AC, pas forcement applicable tel quel a
# une alimentation DC -- voir docstring).
CISPR_B_FREQ_HZ = [0.15e6, 0.5e6, 0.5e6, 5e6, 5e6, 30e6]
CISPR_B_DBUV = [66, 56, 56, 56, 60, 60]


def build_and_export(raw_path="_emi_conducted.asc"):
    d, r = find_duty(20.0, 80.0, 40.0, FSW, L, DCR, SWITCH, DIODE,
                      tmp_out=raw_path, add_lisn=True)
    print(f"Point : D={d:.4f} Vout={r['vout_avg']:.2f}V "
          f"eta={r['pout_avg']/r['pin_avg']*100:.2f}%")
    return raw_path.replace(".asc", ".raw")


def fft_spectrum(raw_path, signal="V(n_lisn_meas)", dt_resample=2e-9):
    raw = RawRead(raw_path)
    t = raw.get_trace("time").get_wave()
    v = raw.get_trace(signal).get_wave()
    t = np.asarray(t, dtype=float)
    v = np.asarray(v, dtype=float)

    t_uniform = np.arange(t[0], t[-1], dt_resample)
    v_uniform = np.interp(t_uniform, t, v)

    window = np.hanning(len(v_uniform))
    coherent_gain = window.mean()
    spec = np.fft.rfft(v_uniform * window)
    freqs = np.fft.rfftfreq(len(v_uniform), d=dt_resample)

    n = len(v_uniform)
    amplitude = np.abs(spec) * 2 / (n * coherent_gain)
    amplitude[0] /= 2  # DC n'est pas double
    return freqs, amplitude


def amplitude_to_dbuv(amplitude_v):
    floor = 1e-9  # evite log(0)
    return 20 * np.log10(np.maximum(amplitude_v, floor) / 1e-6)


def make_plot(freqs, amp_v, out="plots/emi_conducted_spectrum.png"):
    dbuv = amplitude_to_dbuv(amp_v)
    mask = (freqs >= 100e3) & (freqs <= 100e6)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.semilogx(freqs[mask] / 1e6, dbuv[mask], color="C0", lw=0.8,
                label="Spectre LISN simule (ce chapitre)")
    ax.plot(np.array(CISPR_B_FREQ_HZ) / 1e6, CISPR_B_DBUV, color="C3",
            ls="--", lw=1.5,
            label="CISPR 22/32 classe B, quasi-crete (illustratif)")
    ax.axvline(FSW / 1e6, color="k", ls=":", lw=1,
               label=f"fsw={FSW/1e3:.0f}kHz")
    ax.axvline(F0_RESONANCE_HZ / 1e6, color="g", ls=":", lw=1,
               label=f"f0 resonance calculee ({F0_RESONANCE_HZ/1e6:.1f}MHz)")
    ax.axvspan(0.1, 30, color="grey", alpha=0.08,
               label="Bande CEM conduite usuelle (150kHz-30MHz)")
    ax.set_xlabel("Frequence (MHz)")
    ax.set_ylabel("Niveau (dBuV)")
    ax.set_title("Spectre CEM conduit estime (LISN simplifie, pas une "
                  "mesure certifiee) -- NVD6824NL + VS-6CWQ10FN-M3")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print(f"Ecrit {out}")


def main():
    raw_path = build_and_export()
    freqs, amp_v = fft_spectrum(raw_path)
    make_plot(freqs, amp_v)

    # Pics marquants (fsw et harmoniques, + resonance) pour la doc.
    for label, f_target in [("fsw", FSW), ("2*fsw", 2 * FSW),
                             ("3*fsw", 3 * FSW), ("f0 resonance",
                                                   F0_RESONANCE_HZ)]:
        idx = np.argmin(np.abs(freqs - f_target))
        print(f"{label:16s} ~{freqs[idx]/1e3:.0f}kHz : "
              f"{amplitude_to_dbuv(amp_v[idx]):.1f} dBuV")


if __name__ == "__main__":
    main()
