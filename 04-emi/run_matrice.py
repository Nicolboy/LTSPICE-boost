"""Matrice complète des pertes diode — par BALAYAGE et INTERPOLATION.

POURQUOI PAS UNE RECHERCHE DE RAPPORT CYCLIQUE.

En CCM avec une sortie raide, le courant d'équilibre vaut
I_L = [Vin - (1-D)Vout] / R_eff : à D = 0,7500 il est nul, à D = 0,7600 il
vaut 8 A. Viser une puissance demande D à quatre décimales, et R_eff change
avec la diode ET le point de fonctionnement. Pire, la constante de temps
L/R_eff vaut 712 µs à 47 µH : une fenêtre à 75 µs n'est qu'à 11 % d'UNE
constante, et le courant y dérive encore de 1,70 à 2,16 A -- ce qui injecte
2,59 W de FAUSSE PERTE dans le bilan, soit plus que tout ce qu'on mesure.

D'OÙ CETTE MÉTHODE, qui ne demande ni condition initiale ni convergence :

  1. on BALAIE le rapport cyclique autour de l'estimée analytique ;
  2. chaque passage donne un couple (P_out réelle, P_diode) ;
  3. on CORRIGE le bilan de l'énergie stockée dans l'inductance,
     ½L(I₁²-I₀²)/T, calculable exactement sur la fenêtre ;
  4. on INTERPOLE P_diode aux puissances visées.

La perte diode est mesurée directement -- ∫v·i à ses bornes -- et ne dépend
pas de l'atteinte du régime établi : elle correspond à la puissance
RÉELLEMENT relevée sur la fenêtre, et c'est elle qu'on porte en abscisse.

Aucune condition initiale, donc aucun `uic` : tous les modèles constructeur
passent tels quels.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parents[1]
for q in (ICI, RAC / ".claude/skills/sim-spice/scripts",
          RAC / ".claude/skills/sim-commun"):
    sys.path.insert(0, str(q))
import gen_diode_dpt as gd                                  # noqa: E402
from ltspice_run import lance_lot                           # noqa: E402
from simcommun.lecture import lire                          # noqa: E402

RES = ICI / "results" / "matrice"
RES.mkdir(parents=True, exist_ok=True)
VIN, VOUT, FSW = 20.0, 80.0, 400e3
CIBLES = (5.0, 10.0, 20.0, 40.0)
INDS = ("4u7", "10u", "47u")
DIOS = ("si", "c6d", "c3d", "inf")
NOM = {"si": "V8PA22 Si 200 V", "c6d": "C6D SiC 650 V",
       "c3d": "C3D SiC 650 V", "inf": "CoolSiC G6 650 V"}
COSN = (50e-12, 150e-12, 300e-12)


def duty_dcm(l_h, p):
    """D exact en DCM. P_out = ½LI²f · Vout/(Vout-Vin) : l'entrée alimente
    AUSSI pendant la décharge, d'où le facteur que j'avais oublié."""
    return math.sqrt(2.0 * p * l_h * FSW * (VOUT - VIN) / (VIN ** 2 * VOUT))


def est_dcm(l_h, p):
    di = VIN * (1 - VIN / VOUT) / (l_h * FSW)
    return (p / VIN) < di / 2.0


def lis(raw, l_h):
    """Mesure sur une fenêtre de périodes ENTIÈRES, avec la correction
    d'énergie stockée."""
    r = lire(raw)
    t = np.asarray(r.x)
    tsw = 1.0 / FSW
    n = min(10, int((t[-1] - t[0]) / tsw))
    if n < 2:
        return None
    t0 = t[-1] - n * tsw
    m = (t >= t0)
    tt = t[m]
    T = tt[-1] - tt[0]
    moy = lambda y: float(np.trapezoid(y, tt) / T)
    g = lambda nm: np.asarray(r.trace(nm)).real[m]

    il, ivo, ivd = g("I(L1)"), g("I(Vo)"), g("I(Vd)")
    vsw, vnd = g("V(nsw)"), g("V(nd)")

    # ÉNERGIE STOCKÉE : si le courant dérive, la différence Pin-Pout en
    # contient la variation. Sans ce terme, 2,6 W de fausse perte à 47 µH.
    i0 = float(np.mean(il[:max(10, len(il) // 40)]))
    i1 = float(np.mean(il[-max(10, len(il) // 40):]))
    p_stock = 0.5 * l_h * (i1 ** 2 - i0 ** 2) / T

    pin, pout = moy(VIN * il), moy(VOUT * ivo)
    cond = ivd > 0.05
    return dict(pin=pin, pout=pout, pdio=moy((vsw - vnd) * ivd),
                p_stock=p_stock, pertes=pin - pout - p_stock,
                irms=float(np.sqrt(moy(il ** 2))), il_moy=moy(il),
                derive=i1 - i0,
                vf=float(np.median((vsw - vnd)[cond])) if cond.any() else float("nan"),
                id_moy=moy(np.where(ivd > 0, ivd, 0.0)))


def balaye(ind, dio, duties, icosn=0):
    """Un lot de rapports cycliques pour un couple (inductance, diode)."""
    l_h = gd.L_VAL[ind]
    cirs = []
    for k, d in enumerate(duties):
        c = RES / f"b_{ind}_{dio}_{k}.cir"
        c.write_text(gd.netlist(ind, dio, 20.0, duty=d, cosn=COSN[icosn]),
                     encoding="utf-8")
        cirs.append(c)
    res = lance_lot(cirs, delai=90.0, procs=2)
    pts = []
    for d, c in zip(duties, cirs):
        r = res.get(c.stem)
        if r and r["ok"]:
            e = lis(r["raw"], l_h)
            if e and e["pout"] > 0.3 and e["pdio"] > 0:
                e["duty"] = d
                pts.append(e)
    return pts


def main():
    tout, courbes = {}, {}
    for ind in INDS:
        l_h = gd.L_VAL[ind]
        # rapports cycliques : l'estimée DCM pour chaque cible, plus des
        # points intermédiaires pour que l'interpolation ait de la matière
        ds = sorted({round(duty_dcm(l_h, p), 5) for p in
                     (3., 5., 7., 10., 14., 20., 28., 40., 55.)})
        ds = [d for d in ds if 0.03 <= d <= 0.93]
        if not est_dcm(l_h, 40.0):          # la plage touche le CCM
            ds = sorted(set(ds + [0.745, 0.7495, 0.751, 0.7525, 0.755, 0.76]))
            ds = [d for d in ds if d <= 0.93]
        for dio in DIOS:
            pts = []
            for ic in range(3):
                pts = balaye(ind, dio, ds, ic)
                if len(pts) >= 4:
                    break
            if len(pts) < 2:
                print(f"  {ind:>4s} {dio:>4s} : {len(pts)} point(s), abandonné")
                continue
            pts.sort(key=lambda e: e["pout"])
            P = np.array([e["pout"] for e in pts])
            Q = np.array([e["pdio"] for e in pts])
            courbes[f"{ind}|{dio}"] = [[float(a), float(b * 1e3)]
                                       for a, b in zip(P, Q)]
            print(f"  {ind:>4s} {dio:>4s} : {len(pts)} points, "
                  f"P de {P.min():.1f} à {P.max():.1f} W")
            for c in CIBLES:
                if P.min() * 0.92 <= c <= P.max() * 1.08:
                    tout[f"{ind}|{dio}|{c:.0f}"] = dict(
                        pdio=float(np.interp(c, P, Q)),
                        extrap=bool(c < P.min() or c > P.max()),
                        n=len(pts))
    (RES / "matrice.json").write_text(
        json.dumps({"points": tout, "courbes": courbes}, indent=1),
        encoding="utf-8")

    print(f"\n{len(tout)} / 48 cellules\n" + "=" * 80)
    print("PERTES DIODE — Vin 20 V -> Vout 80 V, 400 kHz, par interpolation")
    print("=" * 80)
    for ind, lh in (("4u7", "4,7 µH"), ("10u", "10 µH"), ("47u", "47 µH")):
        print(f"\n  {lh}")
        print(f"    {'':>7s} " + " ".join(f"{NOM[d]:>17s}" for d in DIOS))
        for p in CIBLES:
            l = f"    {p:4.0f} W "
            for d in DIOS:
                e = tout.get(f"{ind}|{d}|{p:.0f}")
                md = "DCM" if est_dcm(gd.L_VAL[ind], p) else "CCM"
                l += (f"{e['pdio']*1e3:7.0f} mW {md}" if e
                      else f"{'—':>17s}") + " "
            print(l)
    return tout, courbes


if __name__ == "__main__":
    main()
