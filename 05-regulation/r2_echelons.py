"""R2 -- six echelons de charge, les deux PI, banc complet.

Echelons (Vin 20 V, Vout 80 V, frontiere DCM/CCM 15,3 W) :
  croissants   5 -> 15 W  DCM/DCM (15 W a la frontiere)
              10 -> 30 W  DCM/CCM
              25 -> 50 W  CCM/CCM
  decroissants 40 -> 20 W  CCM/CCM
              25 -> 15 W  CCM/DCM
              10 ->  5 W  DCM/DCM
Deux reglages, appliques chacun SEUL (aucun basculement modelise) :
  PI CCM  Kp 0,00932  Ki 12    (0,45 Ku_CCM, limite Ki ~30)
  PI DCM  Kp 0,61     Ki 785   (0,45 Ku_DCM, meme zero d'integrale)
Banc : FDD770, Wurth 10 uF + MLCC HF, mesure filtree 1 us, echantillon a
0,998 T, retard d'une periode, .ic L1 et integrale au point de repos.
Charge : R finale toujours branchee ; une seconde R branchee (croissant)
ou ouverte (decroissant) a t_step, comme les k-sections.
D0 : CCM 0,752 (releve) ; DCM formule sans pertes x 1,048 (rapport
releve a 5 et 10 W : 0,4402/0,4198 et 0,6216/0,5937), plafonne au CCM.
"""
from __future__ import annotations

import math
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

VIN, VOUT, L, FSW = 20.0, 80.0, 47e-6, 200e3
T = 1 / FSW
N_AVANT, N_APRES = 600, 1400
P_FRONT = 15.3
ECHELONS = [(5, 15), (10, 30), (25, 50), (40, 20), (25, 15), (10, 5)]
PI = {"ccm": (0.00932, 12.0), "dcm": (0.61, 785.0)}


def d0(p):
    r = VOUT ** 2 / p
    d_dcm = math.sqrt((VOUT ** 2 - VIN * VOUT) * 2 * L * FSW / (r * VIN ** 2))
    return min(1.048 * d_dcm, 0.752) if p < P_FRONT else 0.752


def mode(p):
    return "DCM" if p < P_FRONT else "CCM"


def prepare(p1, p2, pi, n_mes=None):
    kp, ki = PI[pi]
    r1, r2 = VOUT ** 2 / p1, VOUT ** 2 / p2
    if p2 > p1:          # croissant : R1 branchee, R ajoutee en parallele
        rl, ech = r1, (1 / (1 / r2 - 1 / r1), N_AVANT * T)
    else:                # decroissant : R2 branchee, R ouverte a t_step
        rl, ech = r2, (1 / (1 / r1 - 1 / r2), N_AVANT * T, "-")
    n = etape.etape0(p=p1, vin=VIN, charge=True, rl=rl, cout=z.COUT,
                     ser=True, v8pa22=True, mos=z.MOS, n_etab=0,
                     n_mes=n_mes or (N_AVANT + N_APRES), dtmax=200e-9,
                     duty=d0(p1), kp=kp, ki=ki, vref=VOUT, echelon=ech,
                     sobre=True, cout_we=z.COUT_WE, tau_mes=z.TAU_MES,
                     echant=z.ECHANT, retard=z.RETARD, cout_hf=z.COUT_HF)
    f = ICI / f"ze_{p1}_{p2}_{pi}.cir"
    f.write_text(n, encoding="utf-8")
    return f


def blanc() -> int:
    print("  TEST A BLANC -- 30 us, cas les plus risques")
    fs = [prepare(25, 50, "dcm", 6), prepare(5, 15, "ccm", 6),
          prepare(40, 20, "dcm", 6), prepare(10, 30, "ccm", 6)]
    t0 = time.monotonic()
    res = ltspice_run.lance_lot(fs, procs=4)
    print(f"     {time.monotonic()-t0:.0f} s")
    for f in fs:
        r = res[f.stem]
        log = f.with_suffix(".log").read_text(encoding="utf-8",
                                              errors="replace").replace("\0", "")
        ilmx = [l.split("=")[1].split()[0] for l in log.splitlines()
                if l.startswith("ilmx")]
        print(f"     {f.stem:16s} {'OK' if r['ok'] else 'ECHEC'}  Newton "
              f"{'reussi' if 'Direct Newton iteration succeeded' in log else 'ECHOUE'}"
              f"  I(L1) max {ilmx[0] if ilmx else '?'} A  {r['diagnostic'][:60]}")
        if r["ok"]:
            f.with_suffix(".raw").unlink()
    return 0


def main() -> int:
    fs = [prepare(p1, p2, pi) for p1, p2 in ECHELONS for pi in PI]
    t0 = time.monotonic()
    res = ltspice_run.lance_lot(fs, procs=4)
    print(f"  {len(fs)} cas ({N_AVANT}+{N_APRES} periodes) : "
          f"{time.monotonic()-t0:.0f} s\n")
    for f in fs:
        r = res[f.stem]
        if not r["ok"]:
            print(f"  {f.stem:16s} ECHEC  {r['diagnostic'][:90]}")
            continue
        D = z.par_periode(f)
        np.savez(f.with_suffix(".npz"), **D)
        f.with_suffix(".raw").unlink()
        print(f"  {f.stem:16s} extrait")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "complet":
        raise SystemExit(main())
    raise SystemExit(blanc())
