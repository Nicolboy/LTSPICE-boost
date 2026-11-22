"""DCM 5 W, Kp = 1 : le pic de sortie au rallumage, sans et avec le MLCC HF
de la fiche (1 uF X7R 1812 + 0,2 ohm). UN seul changement entre les deux
cas ; echantillonnage inchange (debut de periode). Memes echelles.
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
import r2_ziegler_dcm as d                                   # noqa: E402
import r2_ziegler as z                                       # noqa: E402
import etape                                                 # noqa: E402
import ltspice_run                                           # noqa: E402
sys.path.insert(0, str(ICI.parent.parent / ".claude/skills/sim-commun"))
from simcommun.lecture import lire                           # noqa: E402

T = 5e-6
KS = np.arange(120, 200)          # 0,6 a 1 ms, regime 5 W


def netlist(tag, hf, ech=True):
    n = etape.etape0(p=d.P1, vin=z.VIN, charge=True, rl=d.R1, cout=z.COUT,
                     ser=True, v8pa22=True, mos=z.MOS, n_etab=0, n_mes=400,
                     dtmax=200e-9, kp=1.0, vref=z.VREF,
                     echelon=(d.R_AJ, d.N_AVANT / z.FSW), sobre=True,
                     cout_we=z.COUT_WE, tau_mes=z.TAU_MES, echant=ech,
                     cout_hf=hf)
    n = n.replace(".save V(nout)", ".save V(nsh) V(nvm) V(nsw) V(nout)")
    f = ICI / f"{tag}.cir"
    f.write_text(n, encoding="utf-8")
    return f


def lit(f):
    x = lire(str(f.with_suffix(".raw")))
    t = np.asarray(x.x)
    g = {s: np.asarray(x.trace(s)).real for s in
         ("V(nsw)", "V(nout)", "V(nvm)", "V(nsh)", "V(nctrl)", "I(Vd)")}
    von, pic, dk, shk = [], [], [], []
    for k in KS:
        t0 = k * T
        m = (t >= t0 - 2e-9) & (t < t0 + 300e-9)
        base = np.interp(t0 - 50e-9, t, g["V(nout)"])
        dv = g["V(nout)"][m] - base
        von.append(np.interp(t0, t, g["V(nsw)"]))
        pic.append(dv.max() - dv.min())
        dk.append(np.interp(t0 + 0.5e-6, t, g["V(nctrl)"]))
        shk.append(np.interp(t0 + 0.5e-6, t, g["V(nsh)"]))
    return t, g, np.array(von), np.array(pic), np.array(dk), np.array(shk)


def main():
    fs = [netlist("zd_sansHF", False), netlist("zd_avecHF", True)]
    res = ltspice_run.lance_lot(fs, procs=2)
    for f in fs:
        if not res[f.stem]["ok"]:
            raise SystemExit(f"{f.stem} : {res[f.stem]['diagnostic']}")
    L = [lit(f) for f in fs]
    noms = ("sans MLCC HF", "avec MLCC HF 1 µF + 0,2 Ω (fiche)")
    coul = ("#ff6666", "#66dd66")
    plt.style.use("dark_background")
    fig, ax = plt.subplots(3, 2, figsize=(16, 11))
    fig.suptitle("DCM 5 W, Kp = 1 — le pic de sortie au rallumage du MOSFET, "
                 "sans et avec le découplage HF de la fiche (seul changement)",
                 fontsize=12)
    k0 = 150
    for j, ((t, g, von, pic, dk, shk), nom, c) in enumerate(zip(L, noms, coul)):
        # 1. zoom sur le rallumage : V(nout) et I(Vd)
        m = (t >= k0 * T - 20e-9) & (t < k0 * T + 150e-9)
        a = ax[0, j]
        a.plot((t[m] - k0 * T) * 1e9, g["V(nout)"][m], lw=0.9, color=c)
        a.set_ylim(75, 85)              # plage demandee par le concepteur
        a.set_ylabel("V(nout)  [V]")
        a.set_xlabel("t − rallumage  [ns]")
        b = a.twinx()
        b.plot((t[m] - k0 * T) * 1e9, g["I(Vd)"][m], lw=0.7,
               color="#ffcc44", alpha=0.8)
        b.set_ylim(-3, 3)
        b.set_ylabel("I diode  [A]", color="#ffcc44")
        hors = " — DÉBORDE la plage 75-85 V" if pic.max() > 10 else ""
        a.set_title(f"{nom}\npic sur nout : {pic.min():.2f} à {pic.max():.2f} V "
                    f"crête-à-crête{hors}", fontsize=10, color=c)
        # 2. une periode : nout, mesure filtree, echantillon
        m = (t >= k0 * T) & (t < (k0 + 2) * T)
        a = ax[1, j]
        a.plot((t[m] - k0 * T) * 1e6, g["V(nout)"][m], lw=0.5, color="#888888",
               label="V(nout)")
        a.plot((t[m] - k0 * T) * 1e6, g["V(nvm)"][m], lw=1.0, color="#66aaff",
               label="mesure filtrée 1 µs")
        a.plot((t[m] - k0 * T) * 1e6, g["V(nsh)"][m], lw=1.4, color=c,
               label="échantillon")
        a.set_ylim(75, 85)
        a.set_xlabel("t  [µs]")
        a.set_ylabel("[V]")
        a.legend(fontsize=8, loc="upper right")
        # 3. D periode par periode
        a = ax[2, j]
        a.plot(KS * T * 1e3, dk, "o-", ms=3, lw=0.8, color=c)
        a.set_ylim(0.425, 0.455)
        a.set_xlabel("t  [ms]")
        a.set_ylabel("D par période")
        a.set_title(f"échantillon σ {shk.std()*1e3:.2f} mV → D σ {dk.std():.4f}"
                    f"   (corr. pic/V rallumage "
                    f"{np.corrcoef(von, pic)[0, 1]:+.2f})", fontsize=10)
        print(f"{nom:36s} pic {pic.min():.2f}-{pic.max():.2f} V  "
              f"echantillon sigma {shk.std()*1e3:.2f} mV  D sigma "
              f"{dk.std():.4f}  D moy {dk.mean():.4f}")
    for a in ax.flat:
        a.grid(alpha=0.25)
        a.grid(alpha=0.1, which="minor")
        a.xaxis.set_minor_locator(AutoMinorLocator())
    fig.tight_layout()
    out = ICI / "r2_dcm_mlcc.png"
    fig.savefig(out, dpi=120)
    for f in fs:
        f.with_suffix(".raw").unlink()
    print(f"figure : {out}")


if __name__ == "__main__":
    main()
