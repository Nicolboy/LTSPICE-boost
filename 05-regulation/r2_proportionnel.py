"""R2 — le correcteur PROPORTIONNEL. Le plus simple, et le premier.

POURQUOI IL VIENT AVANT L'INTEGRATEUR

Un P n'ajoute AUCUNE phase. C'est le correcteur le plus docile du lot, et
il ne peut pas saturer puisqu'il n'integre pas. J'avais commence par
l'integrateur -- qui ajoute -90 degres PARTOUT, le plus contraignant --
en pretendant suivre "le plus simple d'abord". Le concepteur a redresse.

DEUX CHOSES QU'IL MESURE, et qu'aucun autre ne mesure aussi proprement

  1. LE GAIN DE BOUCLE, par son erreur residuelle. Avec
         Vout = (Vout_ouvert + Kp.G.Vref) / (1 + Kp.G)
     l'ecart a la consigne donne Kp.G directement. Pas de modele, pas
     d'hypothese : une division.

  2. LA LIMITE DE STABILITE SANS AUCUN DEPHASAGE AJOUTE. Si un P pur ne
     peut deja pas monter, c'est que le PLANT est en cause -- son pic de
     resonance -- et non le correcteur. C'est ce que R3 a suggere sans
     pouvoir le prouver, l'integrateur melangeant les deux effets.

CE QUE R3 A DEJA ETABLI (integrateur pur)
  erreur statique annulee exactement a 10, 20 et 40 W : 80,000 V
  plafond a 790 Hz, fixe par le PIC DE RESONANCE et non par la phase au
  croisement -- |T| repasse au-dessus de 1 a 4 kHz ou la phase vaut -204
  echec a 5 W, cause NON ETABLIE : deux hypotheses refutees, la
  non-linearite du plant (gain local constant a 163 V) et la saturation
  au demarrage (partir du bon rapport cyclique ne change rien)

C'est ce dernier point que le P doit trancher : s'il tient a 5 W, le
probleme est dans l'integration ; s'il echoue aussi, il est ailleurs.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parent
for q in (str(RAC / "04-emi/etapes"),
          str(RAC.parent / ".claude/skills/sim-commun")):
    sys.path.insert(0, q)
import etape                                                 # noqa: E402
from simcommun.lecture import lire                           # noqa: E402

EXE = r"C:\Program Files\ADI\LTspice\LTspice.exe"
FSW, VIN, VREF, COUT, DUTY0 = 200e3, 20.0, 80.0, 2.2e-6, 0.750929


def prepare(tag, kp, rl, n_etab=400, n_mes=500):
    n = etape.etape0(p=40.0, vin=VIN, charge=True, rl=rl, cout=COUT,
                     ser=True, v8pa22=True, mos="ipd530", n_etab=n_etab,
                     n_mes=n_mes, dtmax=200e-9, duty=DUTY0, kp=kp, vref=VREF)
    n = n.replace(".options plotwinsize=0",
                  ".options plotwinsize=256" + chr(10)
                  + ".options cshunt=1e-15")
    n = re.sub(r"(?m)^\.save .*$", "", n).replace(chr(10) * 3, chr(10) * 2)
    n = n.replace(".end", ".save V(nout) V(nctrl)" + chr(10) + ".end")
    f = ICI / f"{tag}.cir"
    f.write_text(n, encoding="utf-8")
    return f


def en_parallele(fs):
    t0 = time.monotonic()
    pr = [subprocess.Popen([EXE, "-b", str(f)], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) for f in fs]
    for p in pr:
        p.wait(timeout=7200)
    return time.monotonic() - t0


def lis(f):
    """Rend (Vout moyen, ondulation BF, duty min, duty max) en O(n)."""
    r = lire(str(Path(f).with_suffix(".raw")))
    t = np.asarray(r.x)
    np_ = max(int(round((1 / FSW) / np.median(np.diff(t)))), 3)

    def gliss(y):
        c = np.concatenate(([0.0], np.cumsum(y)))
        return (c[np_:] - c[:-np_]) / np_

    vm, dm = gliss(np.asarray(r.trace("V(nout)")).real), \
        gliss(np.asarray(r.trace("V(nctrl)")).real)
    tm = t[np_ // 2: np_ // 2 + len(vm)]
    m = tm > tm[0] + 0.7 * (tm[-1] - tm[0])
    return (float(np.mean(vm[m])), float(vm[m].max() - vm[m].min()),
            float(dm.min()), float(dm.max()))


def main() -> int:
    # Vout en boucle OUVERTE au rapport cyclique de reference, par charge.
    # C'est le point de depart contre lequel le P se mesure.
    OUV = {1280.0: 134.3, 640.0: 103.0, 320.0: 80.0, 160.0: 79.90}

    print("  1. LA LIMITE DE STABILITE D'UN P PUR, a 40 W\n")
    kps = (0.002, 0.005, 0.01, 0.02, 0.05, 0.1)
    fs = [prepare(f"p{int(k*10000)}", k, 160.0) for k in kps]
    print(f"     {len(fs)} cas en parallele : {en_parallele(fs):.0f} s\n")
    print(f"     {'Kp':>7s} {'Kp.G attendu':>13s} {'Vout':>9s} "
          f"{'erreur':>9s} {'Kp.G mesure':>12s} {'ondul.':>8s} {'verdict':>10s}")
    print("     " + "-" * 76)
    for kp, f in zip(kps, fs):
        v, osc, dmin, dmax = lis(f)
        err = VREF - v
        # Vout = (Vouv + T.Vref)/(1+T)  =>  T = (Vouv - Vout)/(Vout - Vref)
        t_mes = ((OUV[160.0] - v) / (v - VREF)) if abs(v - VREF) > 1e-6 else np.inf
        verdict = ("stable" if osc < 0.3 else
                   "sonne" if osc < 3 else "INSTABLE")
        print(f"     {kp:7.4f} {kp*321:12.1f} {v:7.3f} V {err:+8.3f} V "
              f"{t_mes:11.1f} {osc:7.3f} V {verdict:>10s}")

    print("\n  2. L'ERREUR RESIDUELLE A CHAQUE CHARGE, au Kp le plus eleve "
          "qui tienne\n")
    kp = 0.01
    chg = ((1280.0, "5 W   DCM"), (640.0, "10 W  DCM"),
           (320.0, "20 W  CCM"), (160.0, "40 W  CCM"))
    fs = [prepare(f"q{int(rl)}", kp, rl, 600, 600) for rl, _ in chg]
    print(f"     {len(fs)} cas en parallele : {en_parallele(fs):.0f} s\n")
    print(f"     Kp = {kp:.4f}\n")
    print(f"     {'point':11s} {'boucle ouverte':>15s} {'avec P':>10s} "
          f"{'erreur':>9s} {'ondul.':>8s} {'ecretage':>10s}")
    print("     " + "-" * 68)
    for (rl, lib), f in zip(chg, fs):
        v, osc, dmin, dmax = lis(f)
        ecr = "ATTEINT" if dmin < 0.06 or dmax > 0.94 else "non"
        print(f"     {lib:11s} {OUV[rl]:12.2f} V {v:7.2f} V "
              f"{VREF-v:+8.2f} V {osc:7.3f} V {ecr:>10s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
