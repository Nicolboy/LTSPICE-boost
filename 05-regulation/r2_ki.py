"""R2 -> PI en CCM : limite de Ki a Kp fixe, par k-section.

Banc complet (r2_ziegler.py) : FDD770, Wurth 10 uF + MLCC HF, mesure
filtree 1 us, echantillonnee a 0,998 T, retard d'une periode. Echelon de
charge 40 -> 30 W a 1 ms, CCM.

Pourquoi pas le PI de Ziegler-Nichols directement : il a donne un cycle
limite de 2,3 V a 3,6 kHz (r2_pi.py). Le plant est un second ordre
resonant avec zero RHP, hors hypothese de ZN, et Ki = 57 /V/s place a lui
seul un croisement d'integrale vers 2,9 kHz, au pied de la resonance.

Ici : Kp = 0,45 Ku (la part proportionnelle de ZN, Ku = 0,0207), et une
k-section sur Ki en partant des fortes valeurs. Critere : celui de la
k-section du P (enveloppe de <Vout>, plancher 0,1 V, cycle limite borne
par DCM = instable). En plus : l'ERREUR STATIQUE apres l'echelon, que
le PI doit annuler.
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

KU = 0.0207
KP = 0.45 * KU


def prepare(tag, ki, n_mes=None):
    n = etape.etape0(p=40.0, vin=z.VIN, charge=True, rl=z.R_BASE, cout=z.COUT,
                     ser=True, v8pa22=True, mos=z.MOS, n_etab=0,
                     n_mes=n_mes or (z.N_AVANT + z.N_APRES), dtmax=200e-9,
                     duty=z.DUTY0, kp=KP, ki=ki, vref=z.VREF,
                     echelon=(z.R_OUV, z.N_AVANT / z.FSW, "-"), sobre=True,
                     cout_we=z.COUT_WE, tau_mes=z.TAU_MES, echant=z.ECHANT,
                     retard=z.RETARD, cout_hf=z.COUT_HF)
    f = ICI / f"{tag}.cir"
    f.write_text(n, encoding="utf-8")
    return f


def lit(f):
    """par_periode + V(nint) n'est pas indispensable : on lit Vout et D."""
    D = z.par_periode(f)
    v = z.verdict(D)
    fin = D["tb"] > D["tb"][-1] - 1e-3
    v["vfin"] = float(D["vb"][fin].mean())
    return D, v


def montre(ki, v):
    if v is None:
        print(f"     Ki {ki:8.3f}  INDETERMINE (simulation morte)")
        return
    print(f"     Ki {ki:8.3f}  {v['cls']:40s} r {v['r']:4.2f}  sigma "
          f"{v['sig']:+6.0f}/s  f {v['f']:5.0f} Hz  env {v['app']*1e3:6.0f} mV"
          f"  DCM {v['dcm']*100:4.1f} %  Vfin {v['vfin']:.3f} V")


def blanc(ki=5.0) -> int:
    print(f"  TEST A BLANC PI -- Kp {KP:.5f}, Ki {ki}")
    f = prepare("zi_pi_blanc30", ki, n_mes=6)
    t0 = time.monotonic()
    r = ltspice_run.lance(f)
    print(f"     30 us : {'OK' if r['ok'] else 'ECHEC'} en "
          f"{time.monotonic()-t0:.1f} s  {r['diagnostic'][:80]}")
    if not r["ok"]:
        return 1
    print("     " + " | ".join(l.strip() for l in f.read_text().splitlines()
                               if l[:4] in ("Gint", "Cint", "Bctr")))
    f.with_suffix(".raw").unlink()
    f = prepare("zi_pi_blanc", ki)
    t0 = time.monotonic()
    r = ltspice_run.lance(f)
    print(f"     complet : {'OK' if r['ok'] else 'ECHEC'} en "
          f"{time.monotonic()-t0:.0f} s  {r['diagnostic'][:80]}")
    if not r["ok"]:
        return 1
    D, v = lit(f)
    np.savez(f.with_suffix(".npz"), **D)
    f.with_suffix(".raw").unlink()
    av = (D["tb"] > 0.6e-3) & (D["tb"] < 1e-3)
    print(f"     avant echelon : Vout {D['vb'][av].mean():.3f} V  "
          f"D {D['db'][av].mean():.4f}")
    montre(ki, v)
    return 0


def un_tour(kis, n_tour):
    fs = [prepare(f"zki{n_tour}_{j}", float(k)) for j, k in enumerate(kis)]
    t0 = time.monotonic()
    res = ltspice_run.lance_lot(fs, procs=len(fs))
    dt = time.monotonic() - t0
    out = []
    for k, f in zip(kis, fs):
        r = res[f.stem]
        if not r["ok"]:
            out.append((float(k), None))
            continue
        D, v = lit(f)
        np.savez(f.with_suffix(".npz"), **D)
        f.with_suffix(".raw").unlink()
        out.append((float(k), v))
    return out, dt


def ksection(lo=0.5, hi=60.0, tol=1.15, n=4) -> int:
    print(f"  K-SECTION Ki -- PI CCM, Kp {KP:.5f} (0,45 Ku), echelon 40 -> 30 W")
    print(f"  bornes [{lo} ; {hi}], {n} cas par tour, arret a hi/lo <= {tol}\n")
    tous = []
    kis = np.geomspace(hi, lo, n)
    tour = 1
    while True:
        print(f"  tour {tour} : Ki = {[round(float(k), 3) for k in kis]}")
        res, dt = un_tour(kis, tour)
        print(f"     ({dt:.0f} s)")
        for k, v in sorted(res, key=lambda r: -r[0]):
            montre(k, v)
        if any(v is None for _, v in res):
            print("\n  Cas MORT : INDETERMINE, arret.")
            return 1
        tous += res
        st = [k for k, v in tous if v["cls"] == "decroit"]
        inst = [k for k, v in tous if v["cls"] != "decroit"]
        if not st or not inst:
            print("\n  Pas d'encadrement.")
            return 1
        lo = max(st)
        hi = min([k for k in inst if k > lo] or [max(inst)])
        print(f"  -> encadrement [{lo:.3f} ; {hi:.3f}], rapport {hi/lo:.3f}\n")
        if hi / lo <= tol:
            break
        kis = np.geomspace(hi, lo, n + 2)[1:-1]
        tour += 1
    print(f"  LIMITE Ki (Kp {KP:.5f}) : entre {lo:.3f} et {hi:.3f} /V/s")
    np.save(ICI / "r2_ki_resultats.npy", dict(lo=lo, hi=hi, tous=tous),
            allow_pickle=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "ksection":
        raise SystemExit(ksection())
    raise SystemExit(blanc())
