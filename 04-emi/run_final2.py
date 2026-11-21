"""Matrice complete : 4 puissances x 3 inductances x 4 diodes.

Deux corrections par rapport a run_diodes_final :

  1. CINQ passes de correction du rapport cyclique au lieu de deux. En
     CCM, R_eff depend du point de fonctionnement -- une diode n'est pas
     une resistance -- donc la resolution est un POINT FIXE, pas une
     formule directe. Elle converge, mais pas en deux coups.

  2. Capacite de conditionnement ESCALADEE par cas : 50 pF, puis 150, puis
     300 si le modele refuse de converger. Elle ne touche pas la mesure de
     diode (elle se decharge dans l'interrupteur), mais elle entre dans le
     bilan -- donc on la rend avec le resultat.
"""
import json, math, sys
from pathlib import Path
import numpy as np
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parents[1]
for q in (ICI, RAC/".claude/skills/sim-spice/scripts", RAC/".claude/skills/sim-commun"):
    sys.path.insert(0, str(q))
import gen_diode_dpt as gd
from ltspice_run import lance_lot
from run_diodes_final import duty_dcm, duty_ccm, est_dcm, mesure, VIN, VOUT, NOM

RES = ICI/"results"/"final2"; RES.mkdir(parents=True, exist_ok=True)
PUISS = (5., 10., 20., 40.); INDS = ("4u7","10u","47u"); DIOS = ("si","c6d","c3d","inf")
COSN = (50e-12, 150e-12, 300e-12)

def lot(trav, etiq):
    """trav : {cle: (duty, cosn)}. Rend {cle: mesure}."""
    cirs, cles = [], []
    for k, (d, c) in trav.items():
        f = RES/f"{etiq}_{k[0]}_{k[1]}_{k[2]:.0f}.cir"
        f.write_text(gd.netlist(k[0], k[1], k[2], duty=d, cosn=c), encoding="utf-8")
        cirs.append(f); cles.append(k)
    res = lance_lot(cirs, delai=70.0, procs=2)
    out = {}
    for k, f in zip(cles, cirs):
        r = res.get(f.stem)
        if r and r["ok"]:
            try:
                e = mesure(r["raw"]); e["duty"], e["cosn"] = trav[k]
                out[k] = e
            except Exception:
                pass
    return out

def main():
    cas = [(i,d,p) for i in INDS for d in DIOS for p in PUISS]
    etat = {k: dict(duty=(duty_dcm(gd.L_VAL[k[0]], k[2]) if est_dcm(gd.L_VAL[k[0]], k[2])
                          else (duty_ccm(k[2], 0.05) or 0.75)),
                    icosn=0, best=None) for k in cas}
    for it in range(5):
        trav = {k: (v["duty"], COSN[v["icosn"]]) for k, v in etat.items()}
        r = lot(trav, f"i{it}")
        n_ok = 0
        for k, v in etat.items():
            e = r.get(k)
            if e is None:                       # pas converge -> plus de Cosn
                v["icosn"] = min(v["icosn"]+1, len(COSN)-1); continue
            err = abs(e["pout"]-k[2])/k[2]
            if v["best"] is None or err < v["best"]["err"]:
                v["best"] = dict(e, err=err)
            if err <= 0.05: n_ok += 1; continue
            l_h = gd.L_VAL[k[0]]
            if est_dcm(l_h, k[2]) and e["pout"] > 0.1:
                v["duty"] = e["duty"]*math.sqrt(k[2]/e["pout"])
            elif e["il_moy"] > 1e-3:
                reff = (VIN - VOUT*(1-e["duty"]))/e["il_moy"]
                d = duty_ccm(k[2], max(reff, 1e-4))
                # amorti : R_eff bouge avec le point, un pas entier oscille
                v["duty"] = 0.5*(e["duty"] + d) if d else e["duty"]
            v["duty"] = min(max(v["duty"], 0.02), 0.94)
        print(f"  passe {it+1} : {len(r)} aboutis, {n_ok} a moins de 5 %")

    bons = {}
    for k, v in etat.items():
        e = v["best"]
        if not e or e["err"] > 0.08 or e["pdio"] <= 0: continue
        e["approx"] = e["vf"]*e["id_moy"]
        e["ecart_c"] = abs(e["approx"]-e["pdio"])/max(e["pdio"],1e-9)
        e["pdcr"] = e["irms"]**2*gd.DCR[k[0]]
        e["pcn"] = 0.5*e["cosn"]*VOUT**2*400e3
        e["psw"] = e["pin"]-e["pout"]-e["pdio"]-e["pdcr"]-e["pcn"]
        if e["ecart_c"] <= 0.45: bons[k] = e
    json.dump({f"{a}|{b}|{c:.0f}": {x: float(y) for x, y in v.items()
               if isinstance(y,(int,float))} for (a,b,c),v in bons.items()},
              open(RES/"pertes.json","w",encoding="utf-8"), indent=1)

    print(f"\n{len(bons)} / {len(cas)} cas verifies")
    print(f"\n  verification croisee Vf x Imoy : ecart max "
          f"{100*max(e['ecart_c'] for e in bons.values()):.1f} %, "
          f"median {100*float(np.median([e['ecart_c'] for e in bons.values()])):.1f} %")
    print("\n" + "="*78)
    print("PERTES DIODE -- 20 V -> 80 V, 400 kHz. Seule la diode est reelle.")
    print("="*78)
    for ind, lh in (("4u7","4,7 uH"),("10u","10 uH"),("47u","47 uH")):
        print(f"\n  {lh}")
        print(f"    {'':>7s} " + " ".join(f"{NOM[d]:>17s}" for d in DIOS))
        for p in PUISS:
            l = f"    {p:4.0f} W "
            for d in DIOS:
                e = bons.get((ind,d,p))
                l += (f"{e['pdio']*1e3:7.0f} mW {'DCM' if est_dcm(gd.L_VAL[ind],p) else 'CCM'}"
                      if e else f"{'—':>17s}") + " "
            print(l)

if __name__ == "__main__":
    main()
