"""R2 -> PI : reglage Ziegler-Nichols injecte et teste.

Banc identique a la k-section retenue (r2_ziegler.py) : echelon 40 -> 30 W
a 1 ms, CCM, Vin 20 V, Vref 80 V, FDD770N15A, Wurth 860130874006
(10 uF / 100 V), mesure de Vout filtree RC 1 us.

Ku ~ 0,021 et Tu ~ 0,20 ms (k-section du 2026-11-22, approximatifs).
PI de Ziegler-Nichols :  Kp = 0,45 Ku   Ti = Tu / 1,2   Ki = Kp / Ti

Ce qu'on verifie :
  - erreur statique ANNULEE (le P seul laissait 0,3 a 0,5 V) ;
  - amortissement de la reponse : ZN vise ~1/4 de decroissance par
    periode d'oscillation, agressif -- avec le zero RHP on attend
    20 a 40 % de depassement et quelques alternances.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import r2_ziegler as z                                       # noqa: E402
import etape                                                 # noqa: E402
import ltspice_run                                           # noqa: E402

KU, TU = 0.021, 0.20e-3
KP = 0.45 * KU
TI = TU / 1.2
KI = KP / TI


def prepare(tag, n_mes=None, kp=KP, ki=KI):
    n = etape.etape0(p=40.0, vin=z.VIN, charge=True, rl=z.R_BASE,
                     cout=z.COUT, ser=True, v8pa22=True, mos=z.MOS, n_etab=0,
                     n_mes=n_mes or (z.N_AVANT + z.N_APRES), dtmax=200e-9,
                     duty=z.DUTY0, kp=kp, ki=ki, vref=z.VREF,
                     echelon=(z.R_OUV, z.N_AVANT / z.FSW, "-"), sobre=True,
                     cout_we=z.COUT_WE, tau_mes=z.TAU_MES)
    f = ICI / f"{tag}.cir"
    f.write_text(n, encoding="utf-8")
    return f


def mesures(d):
    """Apres l'echelon : erreur statique, depassement, oscillation."""
    ts = z.N_AVANT / z.FSW
    tb, vb = d["tb"], d["vb"]
    av = (tb > ts - 100 / z.FSW) & (tb < ts)
    ap = tb > ts
    fin = tb > tb[-1] - 1e-3
    vfin = float(vb[fin].mean())
    x = vb[ap]
    dep = float(x.max() - vfin)                  # la charge BAISSE : Vout monte
    v = z.verdict(d)
    # temps d'etablissement a +-0,1 V
    hors = np.where(np.abs(x - vfin) > 0.1)[0]
    t_etab = float(tb[ap][hors[-1]] - ts) if len(hors) else 0.0
    return dict(v_avant=float(vb[av].mean()), vfin=vfin, err=80.0 - vfin,
                dep=dep, t_etab=t_etab, verdict=v)


def main() -> int:
    print(f"  PI Ziegler-Nichols : Ku {KU}  Tu {TU*1e3:.2f} ms")
    print(f"     Kp = 0,45 Ku = {KP:.5f}   Ti = Tu/1,2 = {TI*1e3:.4f} ms"
          f"   Ki = {KI:.1f} /V/s\n")
    # 1. test a blanc : 30 us, franchir les premiers blocages
    f = prepare("pi_blanc", n_mes=6)
    t0 = time.monotonic()
    r = ltspice_run.lance(f)
    print(f"  test a blanc 30 us : {'OK' if r['ok'] else 'ECHEC'} en "
          f"{time.monotonic()-t0:.0f} s  {r['diagnostic'][:100]}")
    if not r["ok"]:
        return 1
    # 2. cas complet
    f = prepare("pi_zn")
    t0 = time.monotonic()
    r = ltspice_run.lance(f)
    print(f"  cas complet : {'OK' if r['ok'] else 'ECHEC'} en "
          f"{time.monotonic()-t0:.0f} s  {r['diagnostic'][:100]}")
    if not r["ok"]:
        return 1
    d = z.par_periode(f)
    np.savez(f.with_suffix(".npz"), **d)
    f.with_suffix(".raw").unlink()
    m = mesures(d)
    v = m["verdict"]
    print(f"\n  avant echelon : Vout {m['v_avant']:.3f} V")
    print(f"  apres         : Vout final {m['vfin']:.3f} V  "
          f"(erreur statique {m['err']*1e3:+.0f} mV)")
    print(f"                  depassement {m['dep']*1e3:.0f} mV, "
          f"etabli a +-0,1 V en {m['t_etab']*1e3:.2f} ms")
    print(f"  oscillation   : {v['cls']}  r {v['r']:.2f}  sigma "
          f"{v['sig']:+.0f} /s  f {v['f']:.0f} Hz  env fin "
          f"{v['app']*1e3:.0f} mV  DCM {v['dcm']*100:.1f} %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
