"""Matrice de pertes : 4 puissances x 3 inductances x 4 diodes.

Points demandes : 5 / 10 / 20 / 40 W, Vin 20 V, Vout 80 V,
inductances 4,7 / 10 / 47 uH.

LE RAPPORT CYCLIQUE EST ASSERVI. La sortie est une source de tension raide
-- seule initialisation que tous les modeles encapsules supportent -- donc
la puissance n'est pas fixee par la charge mais par l'equilibre que les
resistances parasites imposent au rapport cyclique. On le CHERCHE, par
secante, jusqu'a tomber a 2 % de la cible.

Sans cet asservissement il n'y a pas de comparaison possible : les premiers
essais sont sortis entre 16,2 et 46,9 W pour une meme consigne, et comparer
des rendements a des puissances qui varient d'un facteur 3 n'a aucun sens.

LES ITERATIONS SONT MENEES EN LOCKSTEP : tous les points avancent d'un pas
ensemble, et chaque pas est un lot parallele. Chercher point par point
serait sequentiel.

CONVERGENCE DES MODELES, relevee et non supposee :
    Infineon CoolSiC G6   DCM et CCM
    Vishay V8PA22         DCM et CCM
    Wolfspeed C6D         CCM seulement
    Wolfspeed C3D         CCM seulement
Les deux Wolfspeed echouent en DCM sur leur capacite de jonction. Leurs
mailles DCM restent donc vides -- c'est un resultat, pas une lacune.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
for q in (ICI, RACINE / ".claude/skills/sim-spice/scripts",
          RACINE / ".claude/skills/sim-commun"):
    sys.path.insert(0, str(q))

import gen_pertes as gp                                   # noqa: E402
from ltspice_run import lance_lot                         # noqa: E402
from simcommun.lecture import lire                        # noqa: E402

RES = ICI / "results" / "matrice"
RES.mkdir(parents=True, exist_ok=True)
VIN = 20.0
PUISSANCES = (5.0, 10.0, 20.0, 40.0)
INDUCTANCES = ("4u7", "10u", "47u")
DIODES = ("inf", "si", "c6d", "c3d")
TOL = 0.02          # 2 % sur la puissance
N_ITER = 4


def bilan(raw, vbr, ind):
    """Bilan de pertes. p = moyenne(v*i), JAMAIS moyenne(|v*i|)."""
    r = lire(raw)
    t = np.asarray(r.x)
    m = (t >= 30e-6) & (t <= 50e-6)
    t = t[m]
    T = t[-1] - t[0]
    moy = lambda y: float(np.trapezoid(y, t) / T)

    vda = np.asarray(r.trace("V(nda)")).real[m]
    vsw = np.asarray(r.trace("V(nsw)")).real[m]
    isw = np.asarray(r.trace("I(Vs)")).real[m]
    io = np.asarray(r.trace("I(Vo)")).real[m]
    il = np.asarray(r.trace("I(Vl)")).real[m]

    pout = abs(moy(gp.VOUT * io))
    pin = moy(VIN * il)
    # diode : (V_anode - V_cathode) x courant, le courant de sortie passant
    # par elle en conduction
    pdio = moy((vda - gp.VOUT) * io)
    pav = moy(np.where(vda - gp.VOUT < -(vbr - 5),
                       -(vda - gp.VOUT) * np.abs(io), 0.0))
    ptr = moy(vsw * isw)
    irms = float(np.sqrt(moy(il ** 2)))
    pcu = irms ** 2 * gp.g.INDUCTANCES[ind][2]
    return dict(pout=pout, pin=pin, pdio=pdio * 1e3, pav=pav * 1e3,
                ptr=ptr * 1e3, pcu=pcu * 1e3, irms=irms,
                vinv=float(gp.VOUT - vda.min()),
                rend=100.0 * pout / pin if pin > 0 else float("nan"))


def main():
    # etat de chaque point : duty courant, et les deux derniers essais
    pts = {}
    for ind in INDUCTANCES:
        for p in PUISSANCES:
            m, d0 = gp.mode(gp.g.INDUCTANCES[ind][1], p, VIN)
            for dio in DIODES:
                pts[(ind, p, dio)] = dict(mode=m, duty=d0, hist=[], fini=False,
                                          res=None)

    for it in range(N_ITER):
        actifs = [k for k, v in pts.items() if not v["fini"]]
        if not actifs:
            break
        cirs = []
        for k in actifs:
            ind, p, dio = k
            c = RES / f"m_{ind}_{p:.0f}_{dio}_{it}.cir"
            c.write_text(gp.netlist(ind, dio, p, vin=VIN,
                                    duty=pts[k]["duty"]), encoding="utf-8")
            cirs.append(c)
        print(f"itération {it + 1} : {len(cirs)} points")
        res = lance_lot(cirs, delai=90.0, procs=2)

        for k, c in zip(actifs, cirs):
            ind, p, dio = k
            r = res.get(c.stem)
            if not r or not r["ok"]:
                pts[k]["fini"] = True          # ne converge pas, on abandonne
                continue
            vbr = gp.DIODES[dio][3]
            b = bilan(r["raw"], vbr, ind)
            pts[k]["res"] = b
            ecart = (b["pout"] - p) / p
            pts[k]["hist"].append((pts[k]["duty"], b["pout"]))
            if abs(ecart) <= TOL:
                pts[k]["fini"] = True
                continue
            h = pts[k]["hist"]
            if len(h) >= 2 and abs(h[-1][1] - h[-2][1]) > 1e-9:
                # secante : la puissance est monotone en duty au voisinage
                d = h[-1][0] + (p - h[-1][1]) * (h[-1][0] - h[-2][0]) \
                    / (h[-1][1] - h[-2][1])
            else:
                # premier pas : en DCM la puissance va en duty^2
                d = pts[k]["duty"] * (p / max(b["pout"], 1e-6)) ** (
                    0.5 if pts[k]["mode"] == "DCM" else 0.08)
            pts[k]["duty"] = float(min(max(d, 0.02), 0.95))

    out = {}
    for (ind, p, dio), v in pts.items():
        if v["res"]:
            out[f"{ind}|{p:.0f}|{dio}"] = dict(v["res"], mode=v["mode"],
                                               duty=v["duty"])
    (RES / "matrice.json").write_text(json.dumps(out, indent=1),
                                      encoding="utf-8")
    print(f"\n{len(out)} points sur {len(pts)} -> {RES / 'matrice.json'}")

    print(f"\n{'L':>5s} {'P vis':>6s} {'mode':>4s} {'diode':>5s} {'P réel':>7s} "
          f"{'rend':>7s} {'diode':>8s} {'aval.':>8s} {'transi':>8s} {'V inv':>7s}")
    for ind in INDUCTANCES:
        for p in PUISSANCES:
            for dio in DIODES:
                e = out.get(f"{ind}|{p:.0f}|{dio}")
                if not e:
                    continue
                print(f"{ind:>5s} {p:5.0f}W {e['mode']:>4s} {dio:>5s} "
                      f"{e['pout']:6.2f}W {e['rend']:6.2f}% "
                      f"{e['pdio']:6.0f}mW {e['pav']:6.0f}mW "
                      f"{e['ptr']:6.0f}mW {e['vinv']:6.1f}V")


if __name__ == "__main__":
    main()
