"""Surface complete de la surtension : dV = f(Rg, L_boucle).

POURQUOI UNE SURFACE ET NON DEUX COURBES. Les deux balayages precedents
etaient des COUPES : l'un figeait L_boucle a 20 nH, l'autre Rg a 10 ohms.
Ils ne disent rien des COINS -- par exemple « Schottky silicium avec
L_boucle < 4 nH et Rg = 22 ohms », qui est precisement l'hypothese a
evaluer. Deux coupes ne font pas une surface des qu'il y a interaction, et
il y en a une : L_boucle modifie le di/dt, donc deplace l'effet de Rg.

GRILLE : 6 valeurs de Rg x 5 de L_boucle = 30 points, pour QUATRE
combinaisons -- deux diodes x deux modes de conduction.

    DCM   SER1360-472, 4,7 uH    frontiere a 71 W, donc DCM a 47 W
    CCM   SER2211-473,  47 uH    frontiere a 7,1 W, donc CCM a 47 W

    SiC   C6D04065A  650 V, modele Wolfspeed
    Si    V8PA22     200 V, modele Vishay (Schottky silicium)

Lance par `campagne()`, qui chronometre un temoin, controle son point de
fonctionnement et refuse si le compte n'y est pas.
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

import gen_emi_dm as g                                    # noqa: E402
from ltspice_run import campagne                          # noqa: E402
from simcommun.lecture import lire                        # noqa: E402

RES = ICI / "results" / "surface"
RES.mkdir(parents=True, exist_ok=True)

RG = (1.0, 2.2, 4.7, 10.0, 22.0, 47.0)
LB = (2e-9, 5e-9, 10e-9, 20e-9, 40e-9)
# La SiC est l'INFINEON, pas la Wolfspeed. Meme technologie, meme calibre,
# meme fonction -- mais le modele Wolfspeed place un `ddt()` a l'interieur
# d'un `if` discontinu, et ne converge PAS en DCM : 180 s d'abandon contre
# 2,8 s pour l'Infineon sur le meme circuit. Un modele constructeur n'est
# pas interchangeable avec un autre du meme composant.
COMB = (("4u7", "si",  "DCM · Schottky Si 200 V", 220.0),
        ("4u7", "inf", "DCM · SiC 650 V",         650.0),
        ("47u", "si",  "CCM · Schottky Si 200 V", 220.0),
        ("47u", "inf", "CCM · SiC 650 V",         650.0))


def extrait(raw, vbr):
    r = lire(raw)
    t = np.asarray(r.x)
    m = (t >= 20e-6) & (t <= 25e-6)
    t = t[m]
    vda = np.asarray(r.trace("V(nda)")).real[m]
    idio = np.asarray(r.trace("I(Vd)")).real[m]
    vd = vda - 80.0
    pav = np.trapezoid(np.where(vd < -(vbr - 5), -vd * np.abs(idio), 0.0),
                       t) / (t[-1] - t[0]) * 1e3
    dt = np.diff(t)
    b = dt > 0
    return dict(dv=float(-vd.min() - 80.0), av=float(pav),
                didt=float(np.abs(np.diff(idio)[b] / dt[b]).max() / 1e9),
                dvdt=float(np.abs(np.diff(vda)[b] / dt[b]).max() / 1e9),
                ecrete=bool((-vd.min()) >= vbr - 1.0))


def main():
    cirs, cles = [], []
    for ind, dio, _, _ in COMB:
        for rg in RG:
            for lb in LB:
                nom = f"s_{ind}_{dio}_{rg:g}_{lb*1e9:.0f}n"
                c = RES / f"{nom}.cir"
                c.write_text(g.netlist(ind=ind, diode=dio, rg=rg, lb=lb,
                                       n_etab=8, n_mes=2), encoding="utf-8")
                cirs.append(c)
                cles.append((ind, dio, rg, lb))

    print(f"{len(cirs)} points de grille")
    # DELAI COURT, ET C'EST DELIBERE. Un cas qui converge prend 3 a 6 s ;
    # 90 s est donc deja dix fois la marge. Le seul groupe qui depasse est
    # DCM + SiC, dont on SAIT qu'il ne converge pas : la capacite de jonction
    # du modele Wolfspeed est derriere un `if` discontinu sur le signe de la
    # tension, et en DCM la diode sejourne precisement au voisinage de zero
    # pendant tout le temps mort. Avec le delai par defaut de 900 s, ces 24
    # cas couteraient trois quarts d'heure pour ne rien produire.
    #
    # Ces mailles resteront des TROUS dans la surface, marques au sol. C'est
    # un resultat : ce modele de diode n'est pas utilisable en DCM.
    r = campagne(cirs, attendu={"V(nin)": (17.0, 21.0)}, budget_s=900,
                 delai=90.0)
    if not r["ok"]:
        raise SystemExit(r["diagnostic"])
    print(r["diagnostic"])

    out, manques = {}, 0
    for (ind, dio, rg, lb), c in zip(cles, cirs):
        res = r["resultats"].get(c.stem)
        vbr = dict((x[0] + x[1], x[3]) for x in COMB)[ind + dio]
        if not res or not res["ok"]:
            manques += 1
            continue
        out[f"{ind}|{dio}|{rg}|{lb}"] = extrait(res["raw"], vbr)
    (RES / "surface.json").write_text(json.dumps(out, indent=1),
                                      encoding="utf-8")
    print(f"{len(out)} points exploitables, {manques} manquants"
          f"  ->  {RES / 'surface.json'}")


if __name__ == "__main__":
    main()
