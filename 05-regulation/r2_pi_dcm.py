"""R2 -> deux PI en DCM, comparaison HOMOGENE (verdict du gendarme).

Banc complet (FDD770, Wurth 10 uF + MLCC, mesure filtree, echantillon a
0,998 T, retard d'une periode). Echelon de charge 5 -> 10 W, DCM.

  PI CCM : Kp 0,00932 (0,45 Ku_CCM), Ki 12      -- reglage unique, CCM-sur
  PI DCM : Kp 0,61    (0,45 Ku_DCM), Ki 785     -- MEME proportion de sa
           limite (Ku_DCM ~ 1,35) et MEME zero d'integrale (Ki/Kp ~ 1290 /s)

Corrections apres le verdict :
  - l'integrale est tenue a D0 pendant le point de repos (.ic V(nint),
    etape.py) : avant, Newton/Gmin/source stepping echouaient et tous les
    cas PI demarraient a 127 A dans L1 ;
  - D0 = D REEL a 5 W relu dans les regimes etablis (0,4402), et non la
    formule sans pertes (0,4198) : le pre-echelon part du voisinage de
    l'equilibre au lieu de traîner la convergence de l'integrale.
Mesures : creux depuis l'etat PRE-ECHELON, retour a +-0,1 V, erreur
finale sur l'echantillon et sur la moyenne.
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
import r2_ziegler_dcm as d                                   # noqa: E402
import etape                                                 # noqa: E402
import ltspice_run                                           # noqa: E402
sys.path.insert(0, str(ICI.parent.parent / ".claude/skills/sim-commun"))
from simcommun.lecture import lire                           # noqa: E402

T = 1 / z.FSW
D0_5W = 0.4402
N_AVANT, N_APRES = 600, 1400
PI = {"pi_ccm": (0.00932, 12.0), "pi_dcm": (0.61, 785.0)}


def prepare(tag, kp, ki, n_mes=None):
    n = etape.etape0(p=d.P1, vin=z.VIN, charge=True, rl=d.R1, cout=z.COUT,
                     ser=True, v8pa22=True, mos=z.MOS, n_etab=0,
                     n_mes=n_mes or (N_AVANT + N_APRES), dtmax=200e-9,
                     duty=D0_5W, kp=kp, ki=ki, vref=z.VREF,
                     echelon=(d.R_AJ, N_AVANT * T), sobre=True,
                     cout_we=z.COUT_WE, tau_mes=z.TAU_MES, echant=z.ECHANT,
                     retard=z.RETARD, cout_hf=z.COUT_HF)
    f = ICI / f"{tag}.cir"
    f.write_text(n, encoding="utf-8")
    return f


def journal(f):
    t = f.with_suffix(".log").read_text(encoding="utf-8", errors="replace")
    t = t.replace("\0", "")
    ok = "Direct Newton iteration succeeded" in t
    ilmx = [l for l in t.splitlines() if l.startswith("ilmx")]
    return ok, (ilmx[0].split("=")[1].split()[0] if ilmx else "?")


def blanc() -> int:
    print("  TEST A BLANC -- 30 us, verification du point de repos")
    fs = [prepare(f"zpd_blanc_{k}", *v, n_mes=6) for k, v in PI.items()]
    # temoin CCM : le PI CCM a son propre point (40 W), la ou les 127 A
    # avaient ete releves
    import r2_ki
    fs.append(r2_ki.prepare("zki_blanc_fix", 12.164, n_mes=6))
    t0 = time.monotonic()
    res = ltspice_run.lance_lot(fs, procs=3)
    print(f"     {time.monotonic()-t0:.0f} s")
    for f in fs:
        r = res[f.stem]
        newton, ilmx = journal(f) if r["ok"] else (False, "?")
        print(f"     {f.stem:18s} {'OK' if r['ok'] else 'ECHEC'}  Newton direct "
              f"{'reussi' if newton else 'ECHOUE'}  I(L1) max {ilmx} A")
        if r["ok"]:
            f.with_suffix(".raw").unlink()
    return 0


def mesure(tag, D):
    tb, vb, db, im, sh = D["tb"], D["vb"], D["db"], D["imin"], D["sh2"]
    ts = N_AVANT * T
    av = (tb > ts - 0.5e-3) & (tb < ts)
    ap = tb > ts
    fin = tb > tb[-1] - 1e-3
    v_av, vfin = float(vb[av].mean()), float(vb[fin].mean())
    creux = float(vb[ap].min())
    hors = np.where(np.abs(vb[ap] - vfin) > 0.1)[0]
    t_ret = float(tb[ap][hors[-1]] - ts) if len(hors) else 0.0
    print(f"  {tag}  pre-echelon Vout {v_av:.3f} V (echantillon "
          f"{sh[av].mean():.3f}, D {db[av].mean():.4f})")
    print(f"     creux {creux:.3f} V, soit {creux - v_av:+.2f} V depuis le "
          f"pre-echelon ; retour a +-0,1 V en {t_ret*1e3:.2f} ms")
    print(f"     fin : Vout moyen {vfin:.3f} V, echantillon "
          f"{sh[fin].mean():.3f} V, D {db[fin].mean():.4f}, D efficace AC "
          f"{np.std(db[fin]):.5f}, CCM {np.mean(im[ap] > 0.02)*100:.1f} %")


def main() -> int:
    fs = [prepare(k, *v) for k, v in PI.items()]
    t0 = time.monotonic()
    res = ltspice_run.lance_lot(fs, procs=2)
    print(f"  2 cas ({N_AVANT}+{N_APRES} periodes) : {time.monotonic()-t0:.0f} s\n")
    for f in fs:
        r = res[f.stem]
        if not r["ok"]:
            print(f"  {f.stem} ECHEC {r['diagnostic'][:100]}")
            continue
        newton, ilmx = journal(f)
        D = z.par_periode(f)
        x = lire(str(f.with_suffix(".raw")))
        D["sh2"] = np.interp(D["tb"], np.asarray(x.x),
                             np.asarray(x.trace("V(nsh2)")).real)
        np.savez(f.with_suffix(".npz"), **D)
        f.with_suffix(".raw").unlink()
        print(f"  [{f.stem}] Newton direct {'reussi' if newton else 'ECHOUE'}, "
              f"I(L1) max {ilmx} A")
        mesure(f.stem, D)
        print()
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "blanc":
        raise SystemExit(blanc())
    raise SystemExit(main())
