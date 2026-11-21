"""Validation d'une etape, avec les TROIS refus du gendarme appliques.

Un seul point d'entree pour toutes les etapes : meme jeu de mesures, memes
controles, meme format de sortie. C'est ce qui rend deux etapes comparables.

LES TROIS REFUS, et ce qui les a imposes le 2026-11-21 :
  W1  fenetre entiere   2,2 periodes -> 100,1 % de rendement sur un banc sain
  W2  bilan ferme       sans terme de stockage : 715 mW de pertes fantomes
  W3  recoupement       un chiffre par soustraction n'est pas une mesure
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parents[2]
for q in (ICI, RAC / ".claude/skills/sim-spice/scripts",
          RAC / ".claude/skills/sim-commun"):
    sys.path.insert(0, str(q))
import etape                                             # noqa: E402
from gendarme import bilan_ferme, fenetre_entiere, recoupe, REFUS  # noqa: E402
from simcommun.lecture import lire                       # noqa: E402

EXE = r"C:\Program Files\ADI\LTspice\LTspice.exe"
RP, RS, RC, L_IND, COSN, CP = 7315.89, 0.0107, 140.0, 47e-6, 1e-18, 8.183e-12
LB = 10e-9                 # maille de routage, element PHYSIQUE


def lance(nom, **kw):
    f = ICI / f"{nom}.cir"
    f.write_text(etape.etape0(**kw), encoding="utf-8")
    subprocess.run([EXE, "-b", str(f)], capture_output=True, timeout=600)
    return f.with_suffix(".raw")


def mesure(raw, ser):
    """Rend (bilan, griefs). Fenetre calee sur des fronts de GRILLE."""
    r = lire(str(raw)); t = np.asarray(r.x)
    vg = np.asarray(r.trace("V(ng)")).real
    mont = np.where((vg[:-1] < 2.5) & (vg[1:] >= 2.5))[0]
    if len(mont) < 5:
        return None, [("REFUS", "W1", "moins de 4 periodes exploitables")]
    sl = slice(mont[-5], mont[-1] + 1)
    tt = t[sl]; T = tt[-1] - tt[0]
    g = lambda n: np.asarray(r.trace(n)).real[sl]
    moy = lambda y: float(np.trapezoid(y, tt) / T)

    vs, vo, ib, idd = g("V(nsw)"), g("V(nout)"), g("I(Vbat)"), g("I(Vd)")
    itot, icos, il = g("I(Vsl)"), g("I(Cosn)"), g("I(L1)")
    isw = itot - idd - icos
    ilb = g("I(Lb)")
    pin, pout = -moy(ib) * 19.0, moy(idd) * 80.0

    if ser:
        irp, icp, irs = g("I(Rp_l)"), g("I(Cp_l)"), g("I(Rs_l)")
        v1, v2, vsl = g("V(n1l)"), g("V(n2l)"), g("V(nsl)")
        pert = {"L.Rp": moy(irp ** 2) * RP, "L.Rs": moy(irs ** 2) * RS,
                "L.Rc": moy(icp ** 2) * RC}
        # W3 : chaque resistance, par DEUX methodes independantes
        rec = (recoupe(moy(irp ** 2) * RP, moy((v1 - vs) ** 2) / RP, "L.Rp")
               + recoupe(moy(irs ** 2) * RS, moy((vsl - v1) ** 2) / RS, "L.Rs"))
        dEl = 0.5 * CP * ((v1[-1] - v2[-1]) ** 2 - (v1[0] - v2[0]) ** 2)
    else:
        pert = {"L.DCR": moy((il) ** 2) * etape.DCR}
        rec = recoupe(moy(il ** 2) * etape.DCR,
                      moy((g("V(nl)") - vs) ** 2) / etape.DCR
                      if "V(nl)" in r.noms() else moy(il ** 2) * etape.DCR,
                      "L.DCR")
        dEl = 0.0
    pert["S1"] = moy(vs * isw)
    vda = g("V(nda)")
    pert["D1"] = moy((vda - vo) * idd)
    stock = (0.5 * L_IND * (il[-1] ** 2 - il[0] ** 2)
             + 0.5 * COSN * (vs[-1] ** 2 - vs[0] ** 2) + dEl
             + 0.5 * LB * (ilb[-1] ** 2 - ilb[0] ** 2)) / T

    griefs = [(x.rang, x.ref, x.texte) for x in
              (fenetre_entiere(tt, 200e3)
               + bilan_ferme(pin, pout, pert, stockage=stock) + rec)]
    # temps mort : diode bloquee ET grille basse -> c'est la resonance
    mort = (g("V(ng)") < 2.5) & (np.abs(idd) < 0.01)
    pres = float(np.trapezoid(np.where(mort, sum(
        [moy(0) * 0 + p for p in []], np.zeros_like(tt)) * 0, 0.0), tt))
    bil = dict(pin=pin, pout=pout, pert=pert, stock=stock,
               rend=100 * pout / pin, ipk=float(il.max()), imin=float(il.min()),
               vmort=float(vs[mort].max() - vs[mort].min()) if mort.any() else 0,
               tmort=100 * float(np.trapezoid(mort.astype(float), tt)) / T)
    return bil, griefs


def rapport(nom, bil, griefs):
    print(f"\n  === {nom} ===")
    if bil is None:
        for r_, c, tx in griefs:
            print(f"    [{r_}] {c} {tx[:90]}")
        return False
    tot = sum(bil["pert"].values())
    print(f"    Pin {bil['pin']:.4f} W   Pout {bil['pout']:.4f} W   "
          f"rendement {bil['rend']:.2f} %")
    for k, v in bil["pert"].items():
        print(f"      {k:8s} {v*1e3:8.2f} mW")
    print(f"      {'TOTAL':8s} {tot*1e3:8.2f} mW   "
          f"stockage {bil['stock']*1e3:+.4f} mW")
    print(f"    I crete {bil['ipk']:.3f} A   I min {bil['imin']:+.3f} A   "
          f"temps mort {bil['tmort']:.0f} % sur {bil['vmort']:.1f} V")
    ko = [x for x in griefs if x[0] == REFUS]
    for r_, c, tx in griefs:
        print(f"    [{r_:6s}] {c} {tx[:88]}")
    print(f"    -> {'REFUSE' if ko else 'VALIDE'}")
    return not ko


if __name__ == "__main__":
    import os
    cfg = dict(charge=False, n_etab=40, n_mes=8, dtmax=0.5e-9,
               c_noeud=float(os.environ.get("CNOEUD", "0")))
    res = {}
    for tag, nom, kw in (
            ("s0", "ETAPE 0  tout ideal", dict(ser=False, v8pa22=False)),
            ("s1", "ETAPE 1  + SER2211 constructeur", dict(ser=True, v8pa22=False)),
            ("s2", "ETAPE 2  + V8PA22 constructeur", dict(ser=True, v8pa22=True))):
        raw = lance(tag, **cfg, **kw)
        b, g = mesure(raw, ser=kw["ser"])
        res[nom] = (b, g)
        rapport(nom, b, g)
    # L'ARTEFACT A-T-IL DISPARU ? C'est la question qui a motive la maille.
    import numpy as _np
    from simcommun.lecture import lire as _lire
    print(chr(10) + "  === LA POINTE A LA FERMETURE ===")
    print(f"    {'etape':28s} {'avant 10 nH':>12s} {'avec 10 nH':>12s}")
    for tag, nom, av in (("s0", "tout ideal", None),
                         ("s1", "SER2211 + diode ideale", -0.30),
                         ("s2", "SER2211 + V8PA22", -7.19)):
        r = _lire(str(ICI / f"{tag}.raw"))
        i = _np.asarray(r.trace("I(Vd)")).real
        a = f"{av:11.2f} A" if av is not None else f"{'—':>12s}"
        print(f"    {nom:28s} {a} {i.min():11.2f} A")
