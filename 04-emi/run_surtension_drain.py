"""Campagne : surtension DRAIN contre inductance de routage, quatre pieces.

LA QUESTION. Le budget de surtension du transistor vaut
V_DS x 0,8 - V_out, soit 40 V pour un 150 V et 80 V pour un 200 V. Le
chapitre 4 n'a jamais mesure cette grandeur -- seulement celle de la diode,
qui subit un autre evenement. C'est donc la seule mesure encore susceptible
de rouvrir un choix de composant.

LE RESULTAT ATTENDU EST UNE SPECIFICATION DE PCB, pas un classement :
quelle inductance de maille maximale le routage doit tenir pour que la
piece retenue reste sous 80 % de son calibre.

Passe par `campagne()`, qui chronometre un temoin, controle son point de
fonctionnement et refuse le lot si le compte n'y est pas.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parents[1]
for q in (ICI, RAC / ".claude/skills/sim-spice/scripts",
          RAC / ".claude/skills/sim-commun"):
    sys.path.insert(0, str(q))
import gen_surtension_drain as g                        # noqa: E402
from ltspice_run import campagne                        # noqa: E402
from simcommun.lecture import lire                      # noqa: E402

RES = ICI / "results" / "drain"
RES.mkdir(parents=True, exist_ok=True)
VOUT = 80.0


def extrait(raw, vbr):
    """Rend (V_ds crete, depassement, di/dt, dV/dt, I_coupe)."""
    r = lire(raw)
    t = np.asarray(r.x)
    # LA PREMIERE COUPURE, et elle seule : c'est le seul instant ou le
    # courant vaut exactement la cible, identique pour les quatre pieces.
    # Prendre toute la fenetre melangerait la seconde impulsion, dont le
    # courant depend du temps mort et differe d'une piece a l'autre.
    ton = g.L_H * 2.6 / g.VIN
    m = (t >= ton - 50e-9) & (t <= ton + 500e-9)
    t = t[m]
    v = np.asarray(r.trace("V(nsw)")).real[m]
    i = np.asarray(r.trace("I(L1)")).real[m]
    dt = np.diff(t)
    bon = dt > 0
    return (float(v.max()), float(v.max() - VOUT),
            float(np.abs(np.diff(i)[bon] / dt[bon]).max() / 1e9),
            float(np.abs(np.diff(v)[bon] / dt[bon]).max() / 1e9),
            float(i.max()))


def main():
    cirs, cles = [], []
    for p in g.PIECES:
        for lb in g.L_PCB:
            c = RES / f"d_{p}_{lb*1e9:.0f}n.cir"
            c.write_text(g.netlist(p, lb), encoding="utf-8")
            cirs.append(c)
            cles.append((p, lb))

    # `attendu` avec le prefixe `max:` -- sur un double-pulse la MOYENNE de
    # I(L1) vaut 1,07 A pour une crete de 2,6 A (verifie analytiquement :
    # 1,08 A theorique). Controler la moyenne refusait un banc JUSTE.
    r = campagne(cirs,
                 attendu={"max:I(L1)": (2.4, 2.9), "V(nd)": (75.0, 85.0)},
                 budget_s=900, delai=180.0)
    if not r["ok"]:
        print(r["diagnostic"])
        return 1

    out = {}
    for (p, lb), c in zip(cles, cirs):
        e = r["resultats"].get(c.stem)
        if not (e and e["ok"]):
            continue
        vbr = g.PIECES[p][3]
        out[f"{p}|{lb*1e9:.0f}"] = extrait(e["raw"], vbr)

    (RES / "drain.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\n{len(out)} / {len(cirs)} cas aboutis\n" + "=" * 78)
    print("SURTENSION DRAIN — V_ds crete (V), 20 V -> 80 V, 47 uH, 200 kHz, "
          "Rg = 10 Ohm")
    print("=" * 78)
    hdr = "  ".join(f"{int(l*1e9):>5d}" for l in g.L_PCB)
    print(f"  {'piece':14s} {'boitier':9s} {'calibre':>7s} {'budget':>7s}  "
          f"L_pcb (nH) : {hdr}")
    for p in g.PIECES:
        ref, _, _, vbr, lboit, boit = g.PIECES[p]
        bud = vbr * 0.8 - VOUT
        l = f"  {ref:14s} {boit:9s} {vbr:6.0f}V {bud:6.0f}V             "
        for lb in g.L_PCB:
            e = out.get(f"{p}|{lb*1e9:.0f}")
            if not e:
                l += "     —"
                continue
            ko = "*" if e[0] > vbr * 0.8 else " "
            l += f"{e[0]:6.0f}{ko}"
        print(l)
    print("\n  * = au-dela de 80 % du calibre")
    print("\n  L_pcb MAXIMALE ADMISSIBLE, par interpolation :")
    for p in g.PIECES:
        ref, _, _, vbr, lboit, boit = g.PIECES[p]
        lim = vbr * 0.8
        pts = [(lb * 1e9, out[f"{p}|{lb*1e9:.0f}"][0]) for lb in g.L_PCB
               if f"{p}|{lb*1e9:.0f}" in out]
        if len(pts) < 2:
            continue
        xs = [a for a, _ in pts]; ys = [b for _, b in pts]
        if ys[-1] <= lim:
            print(f"    {ref:14s} > {xs[-1]:.0f} nH — tenu sur tout le balayage")
        elif ys[0] > lim:
            print(f"    {ref:14s} < {xs[0]:.0f} nH — DEJA depasse au minimum")
        else:
            print(f"    {ref:14s} {np.interp(lim, ys, xs):5.1f} nH de routage "
                  f"(+ {lboit*1e9:.2f} nH de boitier)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
