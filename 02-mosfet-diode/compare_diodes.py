"""Compare les candidates diode dans l'architecture 2 reelle.

BV porte a 400 V : on ne veut PAS d'ecretage, on veut voir ou la
resonance monte vraiment, pour la confronter ensuite au calibre.
"""
import numpy as np, gen_ccm_ltspice as g, run_ccm as rc
from spicelib.raw.raw_read import RawRead

MODELES = {
 "V8PA15 150V": "IS=7.86e-08 N=1.05 RS=0.0753 CJO=872p VJ=4.90 M=0.9",
 "V8PA22 200V": "IS=1.08e-11 N=1.05 RS=0.0128 CJO=811p VJ=3.36 M=0.9",
 "V5N3202 200V": "IS=2.05e-11 N=1.05 RS=0.0165 CJO=652p VJ=3.77 M=0.9",
 "V3N22  200V": "IS=4.04e-12 N=1.05 RS=0.0275 CJO=281p VJ=3.96 M=0.9",
}
QUEUE = " FC=0.5 TT=0 EG=0.69 XTI=2 BV=400 IBV=1e-4"

def essai(nom, params, lb):
    d = g.duty_ccm(2.632)
    for k in range(3):
        base = g.netlist((d,), 2.632, l_boucle=lb)
        txt = base.replace(g.DIODE[1], f"D({params}{QUEUE})")
        r = rc.lance(f"dio_{nom.split()[0]}_{lb*1e9:.0f}", txt)
        if k < 2:
            d -= (r["il1"]-r["il0"])/rc.fenetre(r) * g.L_H / g.VOUT
    raw = RawRead(f"results/ccm/dio_{nom.split()[0]}_{lb*1e9:.0f}.raw")
    vd = (np.asarray(raw.get_trace('V(nda)').get_wave(), dtype=float).real
          - np.asarray(raw.get_trace('V(nd)').get_wave(), dtype=float).real)
    return r, abs(vd.min())

for lb in (20e-9, 5e-9):
    print(f"\nInductance de maille {lb*1e9:.0f} nH"
          f"   (calibre a comparer : 150 ou 200 V)")
    print(f"{'diode':<14}{'V inv crete':>12}{'marge':>9}{'MOSFET':>9}"
          f"{'diode':>9}{'total':>9}{'rend':>8}")
    for nom, p in MODELES.items():
        calibre = 150.0 if "150" in nom else 200.0
        r, vpk = essai(nom, p, lb)
        tot = (r['pmos']+r['pdio']+r['pcu']+r['prp']+r['prge'])*1e3
        print(f"{nom:<14}{vpk:>11.0f}V{(calibre-vpk)/calibre*100:>8.0f}%"
              f"{r['pmos']*1e3:>9.0f}{r['pdio']*1e3:>9.0f}{tot:>9.0f}"
              f"{100*r['pout']/r['pin']:>8.2f}")
