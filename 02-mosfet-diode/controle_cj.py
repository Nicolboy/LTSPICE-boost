"""Controle de sensibilite a Cj -- le SEUL parametre non source du modele.

Cj (capacite de jonction de la diode) a ete introduite pour une raison
numerique : sans elle, ngspice diverge sur 25 des 60 cellules, une diode
purement exponentielle en serie avec une inductance n'ayant rien qui borne
son dI/dt au blocage. 100 pF est un ordre de grandeur representatif des
Schottky 100 V de ce calibre, PAS une valeur de fiche de la piece generique
simulee.

Un parametre non source qui influencerait les conclusions serait
inacceptable. On rejoue donc un sous-ensemble de cellules a 50, 100 et
200 pF -- facteur 4 au total -- et on regarde de combien bougent les
pertes mesurees. Si l'ecart reste tres inferieur aux ecarts entre pieces
que le chapitre exploite (~150 mW entre le meilleur et le pire switch a
800 kHz), la conclusion tient malgre l'incertitude sur Cj.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent.parent
sys.path[:0] = [str(ICI), str(RACINE / ".claude/skills/sim-spice/scripts"),
                str(RACINE / ".claude/skills/sim-commun")]

import gen_boost2_dpt as g                      # noqa: E402
from ngspice_run import lance_parallele          # noqa: E402
from run_sweep_dpt import mesure                 # noqa: E402

CJ_TEST = (50e-12, 100e-12, 200e-12)
# cellules temoins : les deux extremes de frequence, les deux diodes, et
# les switches aux deux bouts de l'echelle de calibre
TEMOINS = [(sw, di, f) for sw in ("Si", "FDT86113LZ", "BSC070N10NS5")
           for di in ("Schottky", "Ultrafast") for f in (200e3, 800e3)]
TRAVAIL = Path(os.environ.get("TEMP", "/tmp")) / "ch2_cj"


def main() -> int:
    cells = {(c["switch"], c["diode"], c["fsw"]): c
             for c in g.cellules(pouts=(40.0,))}
    cj_origine = g.CJO_DIODE_F
    taches, index = [], []
    for n, (sw, di, f) in enumerate(TEMOINS):
        c = cells[(sw, di, f)]
        for k, cj in enumerate(CJ_TEST):
            g.CJO_DIODE_F = cj
            d = TRAVAIL / f"t{n:02d}_{k}"
            d.mkdir(parents=True, exist_ok=True)
            fp = d / "run.cir"
            fp.write_text(g.netlist(sw, di, f, c["lh"], c["dcr"], 0.7489,
                                    40.0 / (0.99 * g.VIN)), encoding="utf-8")
            taches.append(dict(netlist=fp, dossier=d))
            index.append((n, sw, di, f, cj, c))
    g.CJO_DIODE_F = cj_origine

    print(f"{len(TEMOINS)} cellules temoins x {len(CJ_TEST)} valeurs de Cj"
          f" = {len(taches)} runs")
    res = lance_parallele(taches, n_coeurs=16)

    par = {}
    for (n, sw, di, f, cj, c), r in zip(index, res):
        if not r["ok"]:
            continue
        m = mesure(Path(r["raw"]), c, 0.7489)
        if m:
            par.setdefault((sw, di, f), {})[cj] = m

    print(f"\n{'cellule':34s} {'perte diode (mW) a Cj =':>26s}    ecart")
    print(f"{'':34s} {'50 pF':>8s} {'100 pF':>8s} {'200 pF':>8s}")
    pires = []
    for (sw, di, f), d in sorted(par.items()):
        if len(d) < len(CJ_TEST):
            continue
        v = [d[cj]["p_cond_diode"] * 1e3 for cj in CJ_TEST]
        ec = 100 * (max(v) - min(v)) / (sum(v) / len(v))
        pires.append((ec, max(v) - min(v)))
        print(f"{sw+' / '+di+' / '+str(int(f/1e3))+'k':34s}"
              f" {v[0]:8.1f} {v[1]:8.1f} {v[2]:8.1f}   {ec:5.1f} %")

    if pires:
        ec_max, abs_max = max(pires)
        print(f"\nEcart MAXIMAL sur un facteur 4 de Cj : {ec_max:.1f} %"
              f" soit {abs_max:.1f} mW.")
        print("A comparer a l'ecart entre pieces que le chapitre exploite :")
        print("  ~150 mW entre le meilleur et le pire switch a 800 kHz.")
        print("  -> " + ("CONCLUSIONS ROBUSTES : l'incertitude sur Cj est "
                         "tres inferieure aux ecarts exploites."
                         if abs_max < 40 else
                         "ATTENTION : Cj pese autant que les ecarts "
                         "exploites, il faut le sourcer sur fiche."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
