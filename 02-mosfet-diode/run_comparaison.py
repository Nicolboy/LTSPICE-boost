"""Compare les deux architectures sur le MEME banc.

Les deux generateurs ont ete alignes au prealable : meme tension d'entree
(19 V, le point dimensionnant), meme diode (V8PA22 200 V), meme
temperature, et plus aucune resistance parallele d'inductance d'un cote
sans homologue de l'autre. Les pertes fer ne sortent pas de SPICE : elles
viennent des calculateurs constructeur, ajoutees apres coup des deux
cotes.

Usage :  python run_comparaison.py fumee    (rapide, valide la chaine)
         python run_comparaison.py          (complet)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                       / ".claude/skills/sim-spice/scripts"))

import gen_ccm_ltspice as c2
import gen_dcm_ltspice as d1
import run_ccm
from ltspice_run import lance

TRAVAIL = Path(__file__).resolve().parent / "results" / "comparaison"

# Pertes fer, hors SPICE, de chaque calculateur constructeur a 50 W.
# SER1360-472 : ajustement Steinmetz du chapitre inductances (849 mW
# TOTAL, dont le cuivre que SPICE calcule par ailleurs).
# WE-HCF 100 uH : REDEXPERT, AC 16,7 mW au point nominal.
FER = {"archi1": None, "archi2": 16.7e-3}      # archi1 : calcule plus bas


def archi1(duty, dtmax, n_etab):
    d1.N_ETAB = n_etab
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    cir = TRAVAIL / f"dcm_{duty:.4f}.cir"
    cir.write_text(d1.netlist((duty,), dtmax=dtmax), encoding="ascii")
    r = lance(cir)
    if not r["ok"]:
        raise RuntimeError("ARCHI 1 : " + r["diagnostic"])
    m = r["meas"]
    m["pgan"] = m["pcanal"] + m["prd"] + m["prs"]
    return m


def archi2(i_l, dtmax, n_etab):
    c2.N_ETAB = n_etab
    d = c2.duty_ccm(i_l)
    for k in range(3):
        TRAVAIL.mkdir(parents=True, exist_ok=True)
        cir = TRAVAIL / f"ccm_{i_l:.3f}.cir"
        cir.write_text(c2.netlist((d,), i_l, dtmax=dtmax), encoding="ascii")
        r = lance(cir)
        if not r["ok"]:
            raise RuntimeError("ARCHI 2 : " + r["diagnostic"])
        m = r["meas"]
        didt = (m["il1"] - m["il0"]) / (c2.N_MES / c2.FSW)
        if k < 2:
            d -= didt * c2.L_H / c2.VOUT
    m["stock"] = 0.5 * c2.L_H * (m["il1"]**2 - m["il0"]**2) / (c2.N_MES/c2.FSW)
    return m


def montre(nom, m, postes, stock=0.0):
    pertes = m["pin"] - m["pout"] - stock
    total = sum(m[k] for _, k in postes)
    print(f"\n{nom}   Pout {m['pout']:.2f} W   rendement "
          f"{100*m['pout']/(m['pin']-stock):.2f} %")
    for lib, k in postes:
        print(f"    {lib:<18}{m[k]*1e3:>8.1f} mW")
    print(f"    {'-'*26}\n    {'total':<18}{total*1e3:>8.1f} mW"
          f"   bouclage {100*(pertes-total)/pertes:+.1f} %")
    print(f"    tension inverse diode : {m['vdrev']:.0f} V")
    return total


if __name__ == "__main__":
    fumee = "fumee" in sys.argv
    # Pas de temps DIFFERENT par architecture, et c'est voulu : le GaN
    # commute en moins d'une nanoseconde, le MOSFET Si en une dizaine.
    # Imposer le meme chiffre aux deux serait soit ruineux, soit faux.
    # Ce qui doit etre identique, c'est le CRITERE : une mesure n'est
    # acquise que si elle ne bouge plus quand on divise le pas par deux.
    if fumee:
        cas = [("fumee", 1e-9, 1e-9, 6, 3)]
    else:
        cas = [("nominal", 0.1e-9, 0.25e-9, 20, 6),
               ("pas / 2", 0.05e-9, 0.125e-9, 20, 6)]

    hist = {}
    for nom, dt1, dt2, n1, n2 in cas:
        print(f"\n{'='*64}\n{nom.upper()}  (archi1 {dt1*1e12:.0f} ps, "
              f"archi2 {dt2*1e12:.0f} ps)\n{'='*64}")
        m1 = archi1(d1.duty_dcm(50.0), dt1, n1)
        t1 = montre("ARCHI 1 -- DCM, GaN EPC2207 + V8PA22",
                    m1, [("GaN", "pgan"), ("diode", "pdio"),
                         ("cuivre L", "pcu"), ("grille Rg ext", "prge")])
        m2 = archi2(2.632, dt2, n2)
        t2 = montre("ARCHI 2 -- CCM, BSC360N15NS3 + V8PA22",
                    m2, [("MOSFET", "pmos"), ("diode", "pdio"),
                         ("cuivre L", "pcu"), ("grille Rg ext", "prge")],
                    stock=m2["stock"])
        hist[nom] = (t1, t2, m1, m2)

    if len(hist) > 1:
        (a1, a2, _, _), (b1, b2, _, _) = hist["nominal"], hist["pas / 2"]
        print(f"\n{'='*64}\nCONVERGENCE (ecart nominal -> pas/2)")
        for nom, x, y in (("archi 1", a1, b1), ("archi 2", a2, b2)):
            e = 100*(y-x)/x
            print(f"  {nom} : {x*1e3:.1f} -> {y*1e3:.1f} mW  ({e:+.2f} %)"
                  f"   {'converge' if abs(e) < 1.0 else 'NON CONVERGE'}")
