"""Spectre conduit de la configuration ARRETEE le 2026-11-21.

CE QUI CHANGE PAR RAPPORT AU CHAPITRE 4, et pourquoi ses chiffres sont
perimes :

    frequence     400 kHz  ->  200 kHz    le peigne descend d'une octave
    inductance    4,7 uH   ->  47 uH      DCM -> CCM, 17-20 dB au chapitre 4
    transistor    EPC2207  ->  IPD530N15N3
    V_grille      5 V      ->  10 V       propre a la piece
    R_grille      1 ohm    ->  10 ohms    385 V/ns -> 73 V/ns
    bulk          220 uF POSE -> hybride Panasonic, ESR de fiche
    MLCC          1 uF nu  ->  1 uF + 0,2 ohm

Les +24,7 dB de depassement en moyennes ondes ont ete releves AVANT ces
sept changements, dont quatre vont dans le sens favorable. On ne peut donc
pas dimensionner un filtre sur eux.

DEUX POINTS DE CHARGE : 8 W, l'emploi reel, et 50 W, le nominal.
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
import gen_emi_dm as g                                   # noqa: E402
from ltspice_run import campagne                         # noqa: E402
from simcommun.lecture import lire                       # noqa: E402

RES = ICI / "results" / "emi_final"
RES.mkdir(parents=True, exist_ok=True)

# CISPR 25 classe 3, conduit, mesure en tension sur LISN — crete, dBuV
# Bandes DISCONTINUES : ce sont des bandes de service, pas un continuum.
# Le fondamental a 200 kHz tombe dans la bande 0,15-0,30 MHz, contrairement
# aux 400 kHz qui tombaient dans le TROU 0,30-0,53 MHz.
GABARIT = [(0.15e6, 0.30e6, 86.0, "ondes longues"),
           (0.53e6, 1.80e6, 70.0, "moyennes ondes"),
           (5.90e6, 6.20e6, 64.0, "ondes courtes"),
           (26.0e6, 41.0e6, 64.0, "bande 11 m / CB"),
           (41.0e6, 88.0e6, 56.0, "bande VHF basse"),
           (88.0e6, 108e6, 56.0, "radio FM")]


def spectre(raw, fsw):
    r = lire(raw)
    t = np.asarray(r.x)
    v = np.asarray(r.trace("V(mp)")).real
    # fenetre de periodes ENTIERES : un nombre non entier etale chaque raie
    n = int((t[-1] - t[0]) * fsw)
    t0 = t[-1] - n / fsw
    m = t >= t0
    tt, vv = t[m], v[m]
    # reechantillonnage uniforme, impose par la FFT
    nn = 1 << 17
    tu = np.linspace(tt[0], tt[-1], nn)
    vu = np.interp(tu, tt, vv)
    sp = np.fft.rfft(vu * np.hanning(nn)) * 4.0 / nn
    f = np.fft.rfftfreq(nn, tu[1] - tu[0])
    dbuv = 20 * np.log10(np.maximum(np.abs(sp), 1e-12) * 1e6)
    return f, dbuv


def main():
    cas = [("8W", 8.0), ("50W", 50.0)]
    cirs, cles = [], []
    for nom, p in cas:
        for var in ("final", "final_nu"):
            g.P_VISEE = p
            c = RES / f"e_{nom}_{var}.cir"
            c.write_text(g.netlist(ind="47u", cin=g.VARIANTES[var],
                                   fsw=200e3, mos="ipd530", rg=10.0,
                                   tr=2e-9, n_etab=24, n_mes=16,
                                   dtmax=1.0e-9), encoding="utf-8")
            cirs.append(c); cles.append((nom, p, var))

    r = campagne(cirs, attendu={"V(nin)": (17.0, 21.0)},
                 budget_s=1800, delai=420.0)
    if not r["ok"]:
        print(r["diagnostic"])
        return 1

    out = {}
    for (nom, p, var), c in zip(cles, cirs):
        e = r["resultats"].get(c.stem)
        if not (e and e["ok"]):
            continue
        f, d = spectre(e["raw"], 200e3)
        marges = []
        for lo, hi, lim, lib in GABARIT:
            m = (f >= lo) & (f <= hi)
            if not m.any():
                continue
            pic = float(d[m].max())
            marges.append((lib, pic, lim, pic - lim))
        out[f"{nom}|{var}"] = marges

    (RES / "emi_final.json").write_text(json.dumps(out, indent=1),
                                        encoding="utf-8")
    print(f"\n{len(out)} / {len(cirs)} cas aboutis")
    print("=" * 76)
    print("SPECTRE CONDUIT — config arretee : 200 kHz, 47 uH CCM, "
          "IPD530N15N3, Rg 10 R")
    print("CISPR 25 classe 3, crete, dBuV")
    print("=" * 76)
    for cle, marges in out.items():
        nom, var = cle.split("|")
        etiq = "avec 0,2 R" if var == "final" else "MLCC NU"
        print(f"\n  {nom} — {etiq}")
        print(f"    {'bande':20s} {'pic':>8s} {'limite':>8s} {'marge':>9s}")
        for lib, pic, lim, mar in marges:
            flag = "  DEPASSE" if mar > 0 else ""
            print(f"    {lib:20s} {pic:7.1f} {lim:7.1f} {mar:+8.1f} dB{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
