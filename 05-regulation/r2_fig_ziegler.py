"""Oscillogrammes de la k-section Ziegler-Nichols -- reponses a l'echelon.

Banc : echelon de charge 40 -> 30 W a t = 1 ms, CCM, Vin 20 V, Vref 80 V,
MOSFET onsemi FDD770N15A, sortie Wurth 860130874006 (10 uF / 100 V,
bibliotheque locale), mesure de Vout filtree (RC 1 us, entree ADC).

Un panneau par Kp, trie par Kp decroissant (la k-section part des fortes
valeurs). MEMES ECHELLES sur tous les panneaux -- RETEX Q : un axe borne
par panneau a deja cache un depassement de 4 V trois fois.

Trace : moyenne de V(nout) PAR PERIODE (blocs disjoints sur grille
uniforme 256 points/periode, RETEX R -- jamais de moyenne d'echantillons
a pas variable). Repere vertical : l'echelon.
"""
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

G = 322.0
COUL = {"decroit": "#66dd66", "ENTRETENU": "#ffcc44",
        "croit": "#ff6666"}
COUL_NL = "#ff66ff"           # cycle limite borne par non-linearite


def charge_cas():
    """Kp de chaque .npz, relu dans la netlist (source de verite)."""
    cas = []
    for f in sorted(ICI.glob(f"zk{z.SUFFIXE}*_*.npz")):
        cir = f.with_suffix(".cir").read_text(encoding="utf-8")
        kp = float(cir.split("Bctrl")[1].split("+ ")[1].split("*")[0])
        d = dict(np.load(f))
        cas.append((kp, f.stem, d, z.verdict(d)))
    return sorted(cas, key=lambda c: -c[0])


def main():
    cas = charge_cas()
    n = len(cas)
    nc = 4
    nl = int(np.ceil(n / nc))
    plt.style.use("dark_background")
    fig, axs = plt.subplots(nl, nc, figsize=(16, 3.0 * nl + 1.2),
                            sharex=True, sharey=True, squeeze=False)
    fig.suptitle(
        "R2 — réponses à l'échelon 40 → 30 W (t = 1 ms), P pur, CCM, "
        "FDD770N15A + Würth 10 µF/100 V, mesure filtrée 1 µs\n"
        "⟨V(nout)⟩ par période, mêmes échelles partout", fontsize=12)
    ts = z.N_AVANT / z.FSW
    for a, (kp, tag, d, v) in zip(axs.flat, cas):
        c = COUL.get(v["cls"], COUL_NL)
        a.plot(d["tb"] * 1e3, d["vb"], lw=0.9, color=c)
        a.axvline(ts * 1e3, color="#aaaaaa", lw=0.8, ls="--")
        a.axhline(80, color="#666666", lw=0.6, ls=":")
        lib = ("cycle limite" if v["cls"].startswith("cycle") else v["cls"])
        a.set_title(f"Kp {kp:.5f}  (K {kp*G:.2f})\n{lib} — r {v['r']:.2f}, "
                    f"σ {v['sig']:+.0f}/s, {v['f']/1e3:.2f} kHz"
                    + (f", DCM {v['dcm']*100:.0f} %" if v['dcm'] else ""),
                    fontsize=9, color=c)
        a.grid(alpha=0.25, which="major")
        a.grid(alpha=0.10, which="minor")
        a.xaxis.set_minor_locator(AutoMinorLocator())
        a.yaxis.set_minor_locator(AutoMinorLocator())
    for a in axs.flat[n:]:
        a.set_visible(False)
    for a in axs[-1]:
        a.set_xlabel("t  [ms]")
    for a in axs[:, 0]:
        a.set_ylabel("⟨V(nout)⟩  [V]")
    axs[0, 0].set_ylim(77.0, 83.0)
    fig.tight_layout()
    out = ICI / "r2_ziegler_reponses.png"
    fig.savefig(out, dpi=130)
    print(f"figure : {out}  ({n} cas)")
    for kp, tag, d, v in cas:
        m = d["tb"] > ts + 1e-3
        print(f"  {tag:10s} Kp {kp:.5f}  Vout [{d['vb'][m].min():.3f}, "
              f"{d['vb'][m].max():.3f}]  {v['cls']}")


if __name__ == "__main__":
    main()
