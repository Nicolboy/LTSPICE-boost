"""Contrainte sur la diode : Si 200 V contre SiC 650 V, modeles constructeur.

La V8PA22 est une Si 200 V : son claquage ECRETE le pic de commutation, d'ou
les ~700 mW d'avalanche releves au chapitre 3. La C6D04065A est la SiC 650 V
du prototype de juillet-aout -- modele Wolfspeed complet, avec reseau
thermique et claquage modelise vers 768 V.

CE QUE TROIS BALAYAGES ONT DEJA ETABLI, et qui motive ce banc : le pic de
~360-377 V ne vient PAS de la diode. Le faire varier d'un facteur 34 en
capacite de jonction, de 20 en inductance de maille, ou le priver de toute
charge stockee, ne le deplace que de quelques pour cent. Ce qui change tout,
c'est le niveau de claquage : a 220 V le pic est tronque et dissipe, a 650 V
il passe. L'utilisateur n'a constate aucune surtension sur prototype parce
qu'avec une SiC il n'y a rien a constater.

TOUS LES CAS PARTENT EN PARALLELE (`exige_lot`). Un transitoire SPICE est
sequentiel dans le temps, donc aucun moteur ne le repartit sur plusieurs
coeurs ; le seul parallelisme disponible est entre les cas. Les lancer en
serie laissait LTspice a 6 % d'un 16 coeurs.
"""
import sys
from pathlib import Path

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
RES.mkdir(exist_ok=True)

CAS = [("22u_si",  "22u", "si",  "22 µH CCM + V8PA22 (Si 200 V)",   220.0),
       ("22u_sic", "22u", "sic", "22 µH CCM + C6D04065A (SiC 650)", 768.0),
       ("47u_sic", "47u", "sic", "47 µH CCM + C6D04065A (SiC 650)", 768.0),
       ("4u7_sic", "4u7", "sic", "4,7 µH DCM + C6D04065A",          768.0)]


def main():
    cirs = []
    for nom, ind, dio, _, _ in CAS:
        c = RES / f"diode_{nom}.cir"
        c.write_text(g.netlist(cin=g.VARIANTES["complet"], ind=ind, diode=dio),
                     encoding="utf-8")
        cirs.append(c)
    print(f"{len(cirs)} cas lances EN PARALLELE...")
    res = lance_lot(cirs)

    print(f"\n{'cas':>34s} {'V inv crête':>12s} {'marge':>9s} "
          f"{'avalanche':>10s} {'Tj max':>8s}")
    for nom, _, dio, lib, vbr in CAS:
        r = res.get(f"diode_{nom}")
        if not r or not r["ok"]:
            print(f"{lib:>34s}   ÉCHEC : {(r or {}).get('diagnostic','?')[:60]}")
            continue
        raw = lire(r["raw"])
        t = np.asarray(raw.x)
        m = (t >= 60e-6) & (t <= 100e-6)
        t = t[m]
        vd = np.asarray(raw.trace("V(nda)")).real[m] - 80.0
        idio = np.asarray(raw.trace("I(Vd)")).real[m]
        pav = np.trapezoid(np.where(vd < -(vbr - 5), -vd * np.abs(idio), 0.0),
                           t) / (t[-1] - t[0])
        try:
            tj = f"{np.asarray(raw.trace('V(ntj)')).real[m].max():6.1f} °C"
        except Exception:
            tj = "   n/a"
        print(f"{lib:>34s} {-vd.min():10.1f} V {vbr + vd.min():7.1f} V"
              f" {pav*1e3:8.1f} mW {tj:>8s}")


if __name__ == "__main__":
    main()
