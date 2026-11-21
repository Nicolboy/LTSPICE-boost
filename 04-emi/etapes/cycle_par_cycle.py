"""Le bilan énergétique CYCLE PAR CYCLE, sans moyenne.

Jusqu'ici tout a été intégré sur quatre périodes entières puis divisé par
quatre. C'est juste, mais ça fait disparaître une question : les cycles
sont-ils identiques ? Une moyenne stable peut couvrir une dérive, un
battement, ou un régime qui n'est pas encore établi.

Le contrôle n'est pas décoratif. Si l'énergie reçue par la charge varie
d'un cycle au suivant alors que rien ne change dans la commande, c'est que
le point de fonctionnement n'est pas atteint -- et tout ce qui a été
conclu sur la moyenne est à reprendre.

TROIS CHOSES VÉRIFIÉES ICI
  1. la dispersion de E_in et E_out d'un cycle a l'autre
  2. le terme de stockage par cycle, qui doit etre nul en regime etabli
     puisque le DCM ramene le courant a zero a chaque fois
  3. l'absence de DERIVE : une regression lineaire sur les huit cycles,
     dont la pente doit etre indiscernable de zero
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parents[2]
for q in (ICI, RAC / ".claude/skills/sim-spice/scripts",
          RAC / ".claude/skills/sim-commun"):
    sys.path.insert(0, str(q))
from simcommun.lecture import lire                            # noqa: E402

FSW, VIN, L_H = 200e3, 19.0, 47e-6
CAS = (("s0", "ÉTAPE 0  tout idéal"),
       ("s1", "ÉTAPE 1  + SER2211"),
       ("s2", "ÉTAPE 2  + V8PA22"),
       ("s3", "ÉTAPE 3  + IPD530N15N3"))


def main() -> int:
    for f, lib in CAS:
        r = lire(str(ICI / f"{f}.raw"))
        t = np.asarray(r.x)
        vg = np.asarray(r.trace("V(ng)")).real
        # chaque cycle va d'un front MONTANT de grille au suivant : c'est
        # le seul decoupage qui ne depende pas du point de fonctionnement
        mo = np.where((vg[:-1] < 2.5) & (vg[1:] >= 2.5))[0]
        g = lambda n: np.asarray(r.trace(n)).real
        il, idd, ib, vo = g("I(L1)"), g("I(Vd)"), g("I(Vbat)"), g("V(nout)")

        print(f"\n  === {lib} ===")
        print(f"    {'cycle':>5s} {'durée':>9s} {'E entrée':>11s} "
              f"{'E sortie':>11s} {'pertes':>10s} {'rendement':>11s} "
              f"{'I crête':>9s} {'stockage':>11s}")
        print("    " + "-" * 82)
        lig = []
        for k in range(len(mo) - 1):
            a, b = mo[k], mo[k + 1] + 1
            tt = t[a:b]
            ein = float(np.trapezoid(-ib[a:b] * VIN, tt))
            eout = float(np.trapezoid(vo[a:b] * idd[a:b], tt))
            st = 0.5 * L_H * (il[b - 1] ** 2 - il[a] ** 2)
            lig.append((tt[-1] - tt[0], ein, eout, st))
        for k, (d, ein, eout, st) in enumerate(lig):
            print(f"    {k+1:5d} {d*1e6:7.3f} µs {ein*1e6:8.3f} µJ "
                  f"{eout*1e6:8.3f} µJ {(ein-eout)*1e6:7.3f} µJ "
                  f"{100*eout/ein:9.3f} % {il[mo[k]:mo[k+1]].max():6.3f} A "
                  f"{st*1e9:8.2f} nJ")
        A = np.array(lig)
        print("    " + "-" * 82)
        for nom, j in (("E entrée", 1), ("E sortie", 2)):
            c = A[:, j]
            # derive : pente d'une regression lineaire, rapportee a la
            # moyenne. Une pente non nulle = regime pas encore etabli.
            p = np.polyfit(np.arange(len(c)), c, 1)[0]
            print(f"    {nom:10s} moyenne {c.mean()*1e6:7.3f} µJ   "
                  f"écart-type {100*c.std()/c.mean():6.3f} %   "
                  f"étendue {100*(c.max()-c.min())/c.mean():6.3f} %   "
                  f"dérive {100*p*len(c)/c.mean():+6.3f} % sur {len(c)} cycles")
        st = A[:, 3]
        print(f"    {'stockage':10s} max {np.abs(st).max()*1e9:7.3f} nJ, "
              f"soit {100*np.abs(st).max()/A[:, 2].mean():.4f} % de E sortie "
              f"-- le DCM ramène le courant à zéro à chaque cycle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
