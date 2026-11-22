"""R2 -- PI CCM au pire point : 50 W.

Le PI CCM (Kp 0,0093 = 0,45 Ku(30 W), Ki 12) OSCILLE a 50 W (r2_echelons :
+-1 V a 3,5 kHz). Le plant CCM change avec la charge (zero RHP plus bas a
50 W), donc Ku et la limite de Ki se re-mesurent au point le plus dur.

Echelon 40 -> 50 W (CCM/CCM), banc complet (FDD770, Wurth 10 uF + MLCC,
mesure filtree, echantillon 0,998 T, retard d'une periode). Meme critere
que r2_ziegler.verdict (enveloppe de <Vout>, plancher 0,1 V).
  etape 1 : k-section du P   -> Ku(50 W), Tu(50 W)
  etape 2 : k-section de Ki a Kp = 0,45 Ku(50 W)
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

P1, P2 = 40.0, 50.0
R_BASE = z.VREF ** 2 / P1                    # 160 ohms
R_AJ = 1 / (1 / (z.VREF ** 2 / P2) - 1 / R_BASE)    # 640 ohms ajoutes
N_AV, N_AP = 200, 1200


def prepare(tag, kp, ki=None, n_mes=None):
    n = etape.etape0(p=P1, vin=z.VIN, charge=True, rl=R_BASE, cout=z.COUT,
                     ser=True, v8pa22=True, mos=z.MOS, n_etab=0,
                     n_mes=n_mes or (N_AV + N_AP), dtmax=200e-9,
                     duty=0.752, kp=kp, ki=ki, vref=z.VREF,
                     echelon=(R_AJ, N_AV / z.FSW), sobre=True,
                     cout_we=z.COUT_WE, tau_mes=z.TAU_MES, echant=z.ECHANT,
                     retard=z.RETARD, cout_hf=z.COUT_HF)
    f = ICI / f"{tag}.cir"
    f.write_text(n, encoding="utf-8")
    return f


def lit(f):
    D = z.par_periode(f)
    np.savez(f.with_suffix(".npz"), **D)
    f.with_suffix(".raw").unlink()
    v = z.verdict(D)
    v["vfin"] = float(D["vb"][D["tb"] > D["tb"][-1] - 1e-3].mean())
    return v


def ligne(nom, x, v):
    if v is None:
        return f"     {nom} {x:9.5f}  INDETERMINE (simulation morte)"
    return (f"     {nom} {x:9.5f}  {v['cls']:40s} r {v['r']:4.2f} sigma "
            f"{v['sig']:+6.0f}/s f {v['f']:5.0f} Hz env {v['app']*1e3:5.0f} mV "
            f"DCM {v['dcm']*100:4.1f} % Vfin {v['vfin']:.3f}")


def blanc() -> int:
    print("  TEST A BLANC 50 W -- 30 us, P et PI")
    fs = [prepare("z50_blanc_p", 0.01, n_mes=6),
          prepare("z50_blanc_pi", 0.00932, 12.0, n_mes=6)]
    t0 = time.monotonic()
    res = ltspice_run.lance_lot(fs, procs=2)
    print(f"     {time.monotonic()-t0:.0f} s")
    for f in fs:
        r = res[f.stem]
        log = f.with_suffix(".log").read_text(encoding="utf-8",
                                              errors="replace").replace("\0", "")
        im = [l.split("=")[1].split()[0] for l in log.splitlines()
              if l.startswith("ilmx")]
        print(f"     {f.stem:14s} {'OK' if r['ok'] else 'ECHEC'}  Newton "
              f"{'reussi' if 'Direct Newton iteration succeeded' in log else 'ECHOUE'}"
              f"  I(L1) max {im[0] if im else '?'} A")
        if r["ok"]:
            f.with_suffix(".raw").unlink()
    return 0


def ksection(nom, gen, lo, hi, tol=1.1, n=4):
    """gen(tag, x) -> netlist ; stable = verdict 'decroit'."""
    tous, tour = [], 1
    xs = np.geomspace(hi, lo, n)
    while True:
        print(f"  tour {tour} : {nom} = {[round(float(x), 5) for x in xs]}")
        fs = [gen(f"z50{nom}{tour}_{j}", float(x)) for j, x in enumerate(xs)]
        t0 = time.monotonic()
        res = ltspice_run.lance_lot(fs, procs=len(fs))
        print(f"     ({time.monotonic()-t0:.0f} s)")
        out = [(float(x), lit(f) if res[f.stem]["ok"] else None)
               for x, f in zip(xs, fs)]
        for x, v in sorted(out, key=lambda o: -o[0]):
            print(ligne(nom, x, v))
        if any(v is None for _, v in out):
            print("  cas MORT : arret")
            return None
        tous += out
        st = [x for x, v in tous if v["cls"] == "decroit"]
        inst = [x for x, v in tous if v["cls"] != "decroit"]
        if not st or not inst:
            print("  pas d'encadrement")
            return None
        lo = max(st)
        hi = min([x for x in inst if x > lo] or [max(inst)])
        print(f"  -> encadrement [{lo:.5f} ; {hi:.5f}], rapport {hi/lo:.3f}\n")
        if hi / lo <= tol:
            return lo, hi, tous
        xs = np.geomspace(hi, lo, n + 2)[1:-1]
        tour += 1


def main() -> int:
    print("  ETAPE 1 -- k-section du P a 50 W (echelon 40 -> 50 W)\n")
    r = ksection("Kp", lambda t, x: prepare(t, x), 0.001, 0.03)
    if r is None:
        return 1
    lo, hi, tous = r
    # sigma sur les cas CCM purs (DCM = 0) encadrant la limite, comme au 30 W
    pur = sorted([(x, v) for x, v in tous if v["dcm"] == 0], key=lambda a: a[0])
    print(f"  LIMITE P 50 W : [{lo:.5f} ; {hi:.5f}]")
    for x, v in pur[-3:]:
        print(f"     CCM pur : Kp {x:.5f} sigma {v['sig']:+.0f}/s f {v['f']:.0f} Hz")
    ku = 0.5 * (lo + hi)
    kp = 0.45 * ku
    print(f"\n  ETAPE 2 -- k-section de Ki a Kp = 0,45 x {ku:.5f} = {kp:.5f}\n")
    r2 = ksection("Ki", lambda t, x: prepare(t, kp, x), 0.5, 60.0, tol=1.15)
    if r2 is None:
        return 1
    print(f"  LIMITE Ki 50 W (Kp {kp:.5f}) : [{r2[0]:.3f} ; {r2[1]:.3f}]")
    np.save(ICI / "r2_k50_resultats.npy",
            dict(ku=(lo, hi), kp=kp, ki=(r2[0], r2[1])), allow_pickle=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "complet":
        raise SystemExit(main())
    raise SystemExit(blanc())
