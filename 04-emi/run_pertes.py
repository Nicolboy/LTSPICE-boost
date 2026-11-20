"""Bilan de pertes : Schottky Si 200 V contre SiC 650 V, DCM et CCM.

CE QUE CE BANC PEUT DIRE, ET CE QU'IL NE PEUT PAS.

Le banc est en BOUCLE OUVERTE sur une source de tension : le rapport
cyclique est fige, la puissance de sortie n'est donc pas regulee et differe
d'un cas a l'autre. Comparer des WATTS entre deux colonnes de puissances
differentes n'a aucun sens. On publie donc la puissance de sortie de chaque
cas, et on compare des RENDEMENTS.

UNE PERTE S'INTEGRE, ELLE NE SE LIT PAS. La fenetre de 2 periodes qui
suffisait a relever une crete est trop courte pour une moyenne : on prend
8 periodes de mesure apres 12 d'etablissement.

LE PARTAGE ATTENDU, qu'il s'agit de chiffrer :
  - la Si gagne en CONDUCTION, sa tension directe est plus basse ;
  - la SiC gagne en COMMUTATION, elle n'a pas de charge recouvree ;
  - et en CCM la Si paie en plus son AVALANCHE, que la SiC n'a pas.
Reste a savoir lequel l'emporte, et dans quel mode.
"""
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
for q in (ICI, RACINE / ".claude/skills/sim-spice/scripts",
          RACINE / ".claude/skills/sim-commun"):
    sys.path.insert(0, str(q))

import gen_emi_dm as g                                    # noqa: E402
from ltspice_run import campagne                          # noqa: E402
from simcommun.lecture import lire                        # noqa: E402

RES = ICI / "results"
RG, LB = 10.0, 20e-9              # point de travail recommande
N_ETAB, N_MES = 12, 8
CAS = [("dcm_si",  "4u7", "si",  "DCM · V8PA22 Schottky Si 200 V", 220.0),
       ("dcm_sic", "4u7", "inf", "DCM · IDH04G65C6 SiC 650 V",     650.0),
       ("ccm_si",  "47u", "si",  "CCM · V8PA22 Schottky Si 200 V", 220.0),
       ("ccm_sic", "47u", "inf", "CCM · IDH04G65C6 SiC 650 V",     650.0)]


def bilan(raw, vbr, ind):
    r = lire(raw)
    t = np.asarray(r.x)
    tsw = 1.0 / g.FSW
    t0, t1 = N_ETAB * tsw, (N_ETAB + N_MES) * tsw
    m = (t >= t0) & (t <= t1)
    t = t[m]
    T = t[-1] - t[0]
    moy = lambda y: float(np.trapezoid(y, t) / T)

    vda = np.asarray(r.trace("V(nda)")).real[m]
    idio = np.asarray(r.trace("I(Vd)")).real[m]
    vsw = np.asarray(r.trace("V(nsw)")).real[m]
    isw = np.asarray(r.trace("I(Vs)")).real[m]
    ibat = np.asarray(r.trace("I(Vbat)")).real[m]
    il = np.asarray(r.trace("I(Vl)")).real[m]

    pin = moy(g.VIN * np.abs(ibat))
    pout = moy(g.VOUT * idio)
    # diode : V(nda) - V(nd), et V(nd) = Vout car Vd est une source a 0 V
    pdio = moy((vda - g.VOUT) * idio)
    # avalanche = la part dissipee au-dela du claquage
    vd = vda - g.VOUT
    pav = moy(np.where(vd < -(vbr - 5), -vd * np.abs(idio), 0.0))
    ptr = moy(np.abs(vsw * isw))
    dcr = g.INDUCTANCES[ind][2]
    pcu = float(np.sqrt(moy(il ** 2)) ** 2 * dcr)
    return dict(pin=pin, pout=pout, pdio=pdio, pav=pav, ptr=ptr, pcu=pcu,
                irms=float(np.sqrt(moy(il ** 2))),
                rend=100.0 * pout / pin if pin > 0 else float("nan"))


def main():
    cirs = []
    for nom, ind, dio, _, _ in CAS:
        c = RES / f"pertes_{nom}.cir"
        c.write_text(g.netlist(ind=ind, diode=dio, rg=RG, lb=LB,
                               n_etab=N_ETAB, n_mes=N_MES), encoding="utf-8")
        cirs.append(c)
    r = campagne(cirs, attendu={"V(nin)": (17.0, 21.0)}, budget_s=600,
                 delai=240.0)
    if not r["ok"]:
        raise SystemExit(r["diagnostic"])
    print(r["diagnostic"], "\n")

    b = {}
    for (nom, ind, dio, lib, vbr), c in zip(CAS, cirs):
        res = r["resultats"].get(c.stem)
        if not res or not res["ok"]:
            print(f"{lib:36s} ÉCHEC : {(res or {}).get('diagnostic','?')[:50]}")
            continue
        b[nom] = bilan(res["raw"], vbr, ind)

    print(f"{'cas':>34s} {'P_out':>8s} {'P_in':>8s} {'rendement':>10s}")
    for nom, _, _, lib, _ in CAS:
        if nom in b:
            e = b[nom]
            print(f"{lib:>34s} {e['pout']:6.1f} W {e['pin']:6.1f} W "
                  f"{e['rend']:8.2f} %")

    print(f"\n{'cas':>34s} {'diode':>9s} {'dont aval.':>11s} "
          f"{'transistor':>11s} {'cuivre':>8s}")
    for nom, _, _, lib, _ in CAS:
        if nom in b:
            e = b[nom]
            print(f"{lib:>34s} {e['pdio']*1e3:7.0f} mW {e['pav']*1e3:9.0f} mW "
                  f"{e['ptr']*1e3:9.0f} mW {e['pcu']*1e3:6.0f} mW")

    for mode, a, c in (("DCM", "dcm_si", "dcm_sic"), ("CCM", "ccm_si", "ccm_sic")):
        if a in b and c in b:
            print(f"\n{mode} — SiC moins Si :"
                  f"  diode {1e3*(b[c]['pdio']-b[a]['pdio']):+.0f} mW"
                  f"   transistor {1e3*(b[c]['ptr']-b[a]['ptr']):+.0f} mW"
                  f"   rendement {b[c]['rend']-b[a]['rend']:+.2f} pt"
                  f"   (P_out {b[a]['pout']:.1f} vs {b[c]['pout']:.1f} W)")


if __name__ == "__main__":
    main()
