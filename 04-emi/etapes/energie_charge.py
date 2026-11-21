"""L'énergie qui arrive réellement à la charge, par cycle et par régime.

Jusqu'ici la sortie n'a été vue que comme une puissance moyenne,
Pout = moy(I_diode) x 80 V. C'est exact mais ça cache deux choses.

PREMIÈRE : la part BRUTE et la part NETTE. Pendant le temps mort, la
sonnerie pousse du courant dans les deux sens à travers la branche de
diode. La moyenne peut être petite alors que les allers-retours sont
grands -- et ce sont les allers-retours qui chauffent, pas la moyenne.

SECONDE, et c'est l'idée fausse la plus répandue sur le boost :
l'inductance n'est PAS un seau qui porterait toute l'énergie. Pendant la
phase de transfert, la source alimente la charge À TRAVERS l'inductance,
en plus de ce que l'inductance restitue. Si l'énergie reçue par la charge
dépasse 1/2.L.Ipk^2, ce n'est pas une erreur de mesure.

Le banc met une SOURCE RAIDE en sortie, pas une résistance. Ce choix a été
arbitré et mesuré : en DCM il est légitime, parce que le courant crête y
vaut Vin.D.T/L et ne dépend pas de la tension de sortie. En CCM il serait
faux -- le courant y résulte d'une soustraction de grands nombres divisée
par la résistance de boucle, et 0,4 % d'écart de rapport cyclique change
le courant d'un facteur 4. La « charge » dont on parle ici est donc la
source de 80 V ; elle reçoit exactement ce qu'une charge réelle recevrait
au même point de fonctionnement.
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
from gendarme import bilan_ferme, recoupe, REFUS              # noqa: E402
from simcommun.lecture import lire                            # noqa: E402

FSW, VIN, VOUT, L_H = 200e3, 19.0, 80.0, 47e-6
CAS = (("s0", "ÉTAPE 0  tout idéal", False),
       ("s1", "ÉTAPE 1  + SER2211", True),
       ("s2", "ÉTAPE 2  + V8PA22", True))
REG = ("1 transfert", "2 temps mort", "3 conduction")


def decoupe(vg, il):
    """De chaque retombée de grille au premier zéro de I(L1) : exact en DCM."""
    on = vg > 2.5
    tr = np.zeros_like(on)
    for d in np.where(on[:-1] & ~on[1:])[0] + 1:
        k = d
        while k < len(on) and not on[k] and il[k] > 0.0:
            tr[k] = True
            k += 1
    return tr, (~on) & (~tr), on


def main() -> int:
    griefs = []
    for f, lib, ser in CAS:
        r = lire(str(ICI / f"{f}.raw"))
        t = np.asarray(r.x)
        vg = np.asarray(r.trace("V(ng)")).real
        mo = np.where((vg[:-1] < 2.5) & (vg[1:] >= 2.5))[0]
        sl = slice(mo[-5], mo[-1] + 1)
        tt = t[sl]
        T = tt[-1] - tt[0]
        n = round(T * FSW)                       # périodes entières
        g = lambda n_: np.asarray(r.trace(n_)).real[sl]
        il, idd, ib, vo = g("I(L1)"), g("I(Vd)"), g("I(Vbat)"), g("V(nout)")
        tr, mort, on = decoupe(g("V(ng)"), il)

        # l'énergie par cycle : on intègre, puis on divise par le nombre
        # de périodes -- JAMAIS par une durée approchée
        ene = lambda y, m: float(np.trapezoid(np.where(m, y, 0.0), tt)) / n
        p_out = vo * idd                         # puissance vers la sortie
        p_in = -ib * VIN

        e_out = [ene(p_out, m) for m in (tr, mort, on)]
        e_in = [ene(p_in, m) for m in (tr, mort, on)]
        # part BRUTE : tout ce qui traverse, quel que soit le sens
        e_brut = [ene(np.abs(p_out), m) for m in (tr, mort, on)]
        e_pk = 0.5 * L_H * float(il.max()) ** 2

        print(f"\n  === {lib} ===")
        print(f"    {'régime':14s} {'reçu par la charge':>20s} "
              f"{'fourni par la source':>22s} {'brut traversé':>16s}")
        print("    " + "-" * 76)
        for k in range(3):
            print(f"    {REG[k]:14s} {e_out[k]*1e6:14.2f} µJ "
                  f"{e_in[k]*1e6:19.2f} µJ {e_brut[k]*1e6:13.2f} µJ")
        print("    " + "-" * 76)
        print(f"    {'par cycle':14s} {sum(e_out)*1e6:14.2f} µJ "
              f"{sum(e_in)*1e6:19.2f} µJ {sum(e_brut)*1e6:13.2f} µJ")
        print(f"    {'soit':14s} {sum(e_out)*FSW:14.4f} W  "
              f"{sum(e_in)*FSW:19.4f} W")
        print(f"\n    rendement {100*sum(e_out)/sum(e_in):.2f} %   "
              f"pertes {(sum(e_in)-sum(e_out))*1e6:.3f} µJ/cycle "
              f"= {(sum(e_in)-sum(e_out))*FSW*1e3:.2f} mW")

        # --- CE QUE L'INDUCTANCE PORTE, ET CE QUI PASSE A TRAVERS -------
        print(f"\n    L'INDUCTANCE N'EST PAS UN SEAU")
        print(f"      1/2.L.Ipk^2 stocké au sommet    {e_pk*1e6:7.2f} µJ "
              f"(Ipk = {il.max():.3f} A)")
        print(f"      reçu par la charge par cycle    {sum(e_out)*1e6:7.2f} µJ")
        print(f"      -> la source fournit {(sum(e_out)-e_pk)*1e6:.2f} µJ "
              f"DIRECTEMENT pendant le transfert,")
        print(f"         soit {100*(sum(e_out)-e_pk)/sum(e_out):.0f} % "
              f"de ce que reçoit la charge.")

        # --- RECOUPEMENT : la formule fermée du DCM ---------------------
        # en DCM, l'energie prise a la source par cycle vaut
        #     1/2.L.Ipk^2 . Vout/(Vout-Vin)   (transfert + apport direct)
        e_th = e_pk * VOUT / (VOUT - VIN)
        gr = recoupe(sum(e_out), e_th, "énergie par cycle", tol=0.06)
        griefs += gr
        print(f"\n    RECOUPEMENT par la formule fermée du DCM")
        print(f"      1/2.L.Ipk^2 . Vout/(Vout-Vin) = {e_th*1e6:.2f} µJ")
        for x in gr:
            print(f"      [{x.rang}] {x.texte[:86]}")
        if not gr:
            print(f"      concorde a {100*abs(sum(e_out)-e_th)/e_th:.1f} % "
                  f"de la mesure directe")

        # --- LE BRUT CONTRE LE NET --------------------------------------
        ex = sum(e_brut) - sum(e_out)
        print(f"\n    BRUT CONTRE NET")
        print(f"      traversé en valeur absolue      {sum(e_brut)*1e6:7.2f} µJ")
        print(f"      net reçu                        {sum(e_out)*1e6:7.2f} µJ")
        print(f"      va-et-vient stérile             {ex*1e6:7.2f} µJ "
              f"({100*ex/sum(e_brut):.1f} %), dont "
              f"{100*(e_brut[1]-e_out[1])/max(ex, 1e-18):.0f} % en temps mort")
    return 1 if any(x.rang == REFUS for x in griefs) else 0


if __name__ == "__main__":
    raise SystemExit(main())
