"""R2 — l'intégrateur pur. Un seul paramètre : le gain.

OBJET DE L'ÉTAPE. Pas de faire fonctionner le produit : d'établir, par la
mesure, le PLAFOND d'un intégrateur seul. C'est contre ce plafond que le
zéro de R3 se justifiera — ou ne se justifiera pas.

CE QUE LA PHASE MESURÉE EN R1 ANNONCE, l'intégrateur ajoutant −90°
partout :

    croisement    phase plant    marge
      500 Hz        −1,4°        88,6°    confortable
     1000 Hz        −5,5°        84,5°    confortable
     2000 Hz       −12,8°        77,2°    confortable
     3000 Hz       −63,5°        26,5°    au bord
     4000 Hz      −114,3°       −24,3°    INSTABLE

Le réglage : boucle ouverte = Ki/s × G(s), croisement quand
Ki·G0/(2πfc) = 1, donc Ki = 2πfc/G0 avec G0 = 321 V mesuré en R1.

DEUX CHOSES À VÉRIFIER, et la seconde est la vraie question

  1. L'erreur statique est-elle annulée ? Un intégrateur le fait par
     construction, mais il faut le CONSTATER -- et le constater à
     plusieurs charges, puisque c'est là que la boucle ouverte échouait.

  2. Où se situe la limite ? On monte le gain jusqu'à ce que ça sonne,
     et on compare à ce que la phase mesurée annonçait.

L'INTÉGRATEUR est un condensateur de 1 F chargé par une source de courant
commandée : dV/dt = I, donc V = l'intégrale. Exact, sans pôle parasite.
`ic=` le fait partir du bon rapport cyclique, sans quoi l'établissement
coûterait les mêmes 600 périodes qu'en boucle ouverte.
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
FSW, VIN, VREF, COUT, G0 = 200e3, 20.0, 80.0, 2.2e-6, 321.0
DUTY0 = 0.750929
FCS = (500.0, 1000.0, 2000.0, 3000.0, 4000.0)


def prepare(tag, ki, rl, n_etab, n_mes):
    n = etape.etape0(p=40.0, vin=VIN, charge=True, rl=rl, cout=COUT,
                     ser=True, v8pa22=True, mos="ipd530", n_etab=n_etab,
                     n_mes=n_mes, dtmax=200e-9, duty=DUTY0, ki=ki, vref=VREF)
    n = n.replace(".options plotwinsize=0",
                  ".options plotwinsize=256" + chr(10)
                  + ".options cshunt=1e-15")
    n = re.sub(r"(?m)^\.save .*$", "", n).replace(chr(10) * 3, chr(10) * 2)
    n = n.replace(".end", ".save V(nout) V(nint) I(L1)" + chr(10) + ".end")
    f = ICI / f"{tag}.cir"
    f.write_text(n, encoding="utf-8")
    return f


def en_parallele(fs):
    """Les CAS se parallelisent ; un transitoire, non."""
    t0 = time.monotonic()
    pr = [subprocess.Popen([EXE, "-b", str(f)], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) for f in fs]
    for p in pr:
        p.wait(timeout=7200)
    return time.monotonic() - t0


def lent(t, y):
    """Composante lente : moyenne glissante sur une periode, en O(n).

    Somme cumulee, surtout pas `np.convolve` : avec des millions de
    points et un noyau d'une periode, la convolution directe est en
    O(n.m) et prend des heures.
    """
    np_ = max(int(round((1 / FSW) / np.median(np.diff(t)))), 3)
    cum = np.concatenate(([0.0], np.cumsum(y)))
    return t[np_ // 2: np_ // 2 + len(cum) - np_ - 1], \
        (cum[np_:] - cum[:-np_])[:len(cum) - np_ - 1] / np_


def main() -> int:
    print("  BOUCLE FERMEE, INTEGRATEUR PUR, charge 160 ohms (40 W)\n")
    fs, kis = [], []
    for fc in FCS:
        ki = 2 * np.pi * fc / G0
        kis.append(ki)
        fs.append(prepare(f"k{int(fc)}", ki, 160.0, 300, 500))
    print(f"  {len(fs)} cas en parallele : {en_parallele(fs):.0f} s\n")
    print(f"  {'croisement':>11s} {'Ki':>8s} {'Vout moyen':>12s} "
          f"{'erreur':>9s} {'ondulation BF':>14s} {'verdict':>12s}")
    print("  " + "-" * 72)
    for fc, ki in zip(FCS, kis):
        r = lire(str(ICI / f"k{int(fc)}.raw"))
        t = np.asarray(r.x)
        tm, vm = lent(t, np.asarray(r.trace("V(nout)")).real)
        m = tm > tm[0] + 0.6 * (tm[-1] - tm[0])      # dernier 40 %
        moy = float(np.mean(vm[m]))
        osc = float(vm[m].max() - vm[m].min())
        v = ("stable" if osc < 0.3 else
             ("sonne" if osc < 3 else "INSTABLE"))
        print(f"  {fc:8.0f} Hz {ki:7.2f} {moy:9.3f} V "
              f"{moy-VREF:+8.3f} V {osc:11.3f} V {v:>12s}")
    print()
    print("  L'ERREUR STATIQUE EST-ELLE ANNULEE A TOUTE CHARGE ?")
    print("  C'est la ou la boucle ouverte echouait : 74 V a 5 W, 64 a 10 W.\n")
    ki = 2 * np.pi * 1000.0 / G0
    chg = ((1280.0, "5 W   DCM"), (640.0, "10 W  DCM"),
           (320.0, "20 W  CCM"), (160.0, "40 W  CCM"))
    fs = [prepare(f"c{int(rl)}", ki, rl, 400, 500) for rl, _ in chg]
    print(f"  {len(fs)} cas en parallele : {en_parallele(fs):.0f} s\n")
    print(f"  {'point':12s} {'R':>7s} {'Vout boucle OUVERTE':>21s} "
          f"{'Vout boucle FERMEE':>20s} {'erreur':>9s}")
    print("  " + "-" * 74)
    ouvert = {1280.0: 73.92, 640.0: 64.00, 320.0: 80.00, 160.0: 79.90}
    for rl, lib in chg:
        r = lire(str(ICI / f"c{int(rl)}.raw"))
        t = np.asarray(r.x)
        tm, vm = lent(t, np.asarray(r.trace("V(nout)")).real)
        moy = float(np.mean(vm[tm > tm[0] + 0.6 * (tm[-1] - tm[0])]))
        print(f"  {lib:12s} {rl:6.0f} oh {ouvert[rl]:18.2f} V "
              f"{moy:17.3f} V {moy-VREF:+8.3f} V")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
