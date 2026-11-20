"""Surtension inverse sur la diode : les deux leviers du concepteur.

    dV = L_maille . di/dt

L'inductance de maille et la VITESSE DE COMMUTATION. La charge recouvree Qrr
n'ajoute qu'un courant supplementaire a interrompre -- elle aggrave, elle ne
cree pas. C'est pourquoi une SiC, sans Qrr, ne supprime pas la surtension :
elle supprime seulement le surplus.

CE QUE CE BANC CORRIGE. Jusqu'ici il tournait a Rg = 1 ohm avec des fronts
de commande de 150 ps -- l'extreme physique d'un GaN, jamais justifie, qui
donnait 390 V/ns de dV/dt. Tout le contenu HF du chapitre a ete releve a
cette vitesse. On balaye donc Rg, et on porte en abscisse le di/dt REELLEMENT
MESURE, pas le reglage.

COMPOSANTS : ceux qui sont retenus.
    inductance   SER2211-473, 47 uH, modele Coilcraft (CCM des 7,1 W)
    transistor   EPC2207, GaN, modele EPC
    diode        C6D04065A, SiC 650 V Wolfspeed   <- prototype juillet-aout
                 V8PA22, Schottky Si 200 V Vishay <- choix du chapitre 3

Tous les cas partent EN PARALLELE, avec delai maximal.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
for q in (ICI, RACINE / ".claude/skills/sim-spice/scripts",
          RACINE / ".claude/skills/sim-commun"):
    sys.path.insert(0, str(q))

import gen_emi_dm as g                                    # noqa: E402
from ltspice_run import lance_lot                         # noqa: E402
from simcommun.lecture import lire                        # noqa: E402

RES = ICI / "results"
ILL = ICI / "illustrations"
for d in (RES, ILL):
    d.mkdir(exist_ok=True)

IND = "47u"
RG = (1.0, 2.2, 4.7, 10.0, 22.0, 47.0)      # ohms -- le levier reel
LB = (2e-9, 5e-9, 10e-9, 20e-9, 40e-9)      # henrys
RG_REF, LB_REF = 10.0, 20e-9                # points fixes de chaque balayage
DIODES = (("sic", "C6D04065A — SiC 650 V", 768.0, "#54d6a0"),
          ("si",  "V8PA22 — Schottky Si 200 V", 220.0, "#ff6b6b"))


def extrait(r, vbr):
    """Rend (V inverse crete, depassement, avalanche, di/dt, dV/dt)."""
    raw = lire(r["raw"])
    t = np.asarray(raw.x)
    m = (t >= 20e-6) & (t <= 25e-6)
    t = t[m]
    vda = np.asarray(raw.trace("V(nda)")).real[m]
    idio = np.asarray(raw.trace("I(Vd)")).real[m]
    vd = vda - 80.0
    pav = np.trapezoid(np.where(vd < -(vbr - 5), -vd * np.abs(idio), 0.0),
                       t) / (t[-1] - t[0])
    dt = np.diff(t)
    bon = dt > 0
    didt = np.abs(np.diff(idio)[bon] / dt[bon]).max() / 1e9      # A/ns
    dvdt = np.abs(np.diff(vda)[bon] / dt[bon]).max() / 1e9       # V/ns
    return -vd.min(), -vd.min() - 80.0, pav * 1e3, didt, dvdt


def main():
    cirs, cles = [], []
    for dio, _, _, _ in DIODES:
        for rg in RG:
            c = RES / f"sur_rg_{dio}_{rg:g}.cir"
            c.write_text(g.netlist(ind=IND, diode=dio, rg=rg, lb=LB_REF,
                                   n_etab=8, n_mes=2),
                         encoding="utf-8")
            cirs.append(c); cles.append(("rg", dio, rg))
        for lb in LB:
            c = RES / f"sur_lb_{dio}_{lb*1e9:.0f}n.cir"
            c.write_text(g.netlist(ind=IND, diode=dio, rg=RG_REF, lb=lb,
                                   n_etab=8, n_mes=2),
                         encoding="utf-8")
            cirs.append(c); cles.append(("lb", dio, lb))

    print(f"{len(cirs)} cas en parallele, delai max 1200 s")
    res = lance_lot(cirs, delai=1200.0)

    out = {}
    for (quoi, dio, val), c in zip(cles, cirs):
        r = res.get(c.stem)
        vbr = dict((d[0], d[2]) for d in DIODES)[dio]
        if not r or not r["ok"]:
            print(f"   ÉCHEC {c.stem} : {(r or {}).get('diagnostic','?')[:70]}")
            continue
        out[(quoi, dio, val)] = extrait(r, vbr)

    for quoi, lib, unite, ech in (("rg", "vitesse de commutation", "ohm", RG),
                                  ("lb", "inductance de maille", "nH", LB)):
        print(f"\n=== {lib} ===")
        for dio, nom, _, _ in DIODES:
            print(f"  {nom}")
            print(f"  {'réglage':>9s} {'di/dt':>9s} {'dV/dt':>10s} "
                  f"{'V inv':>9s} {'dépass.':>9s} {'avalanche':>10s}")
            for v in ech:
                e = out.get((quoi, dio, v))
                if not e:
                    continue
                r = f"{v:g} ohm" if quoi == "rg" else f"{v*1e9:.0f} nH"
                print(f"  {r:>9s} {e[3]:6.3f}A/ns {e[4]:7.1f}V/ns "
                      f"{e[0]:7.1f} V {e[1]:7.1f} V {e[2]:8.1f} mW")
    np.save(RES / "surtension.npy", np.array(
        [(0 if q == "rg" else 1, 0 if d == "sic" else 1, v) + tuple(e)
         for (q, d, v), e in out.items()]))
    return out


if __name__ == "__main__":
    main()
