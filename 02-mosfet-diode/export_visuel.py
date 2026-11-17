"""Exporte vers JSON tout ce qui doit etre TRACE : formes d'onde des neuf
points, bilans de pertes des deux architectures, courbes de pertes des
inductances candidates.

Les traces sont sous-echantillonnees a pas constant sur trois periodes,
en preservant les extrema locaux : un simple pas de N points raterait les
pointes de commutation, qui durent quelques nanosecondes et sont
precisement ce qu'on veut voir.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
DON = ICI.parents[1] / "composants-datasheets/telechargement/donne_inductances"

POINTS = [(12.0, 5.0), (12.0, 10.0), (12.0, 20.0),
          (20.0, 5.0), (20.0, 15.0), (20.0, 45.0),
          (25.0, 5.0), (25.0, 15.0), (25.0, 45.0)]
FSW = 400e3
N_PER = 3
N_OUT = 420          # points par trace apres reduction


def reduit(t, y, n=N_OUT):
    """Reduction par bacs min/max : conserve les extrema, donc les pointes."""
    if len(t) <= n:
        return t, y
    bornes = np.linspace(0, len(t), n // 2 + 1).astype(int)
    tt, yy = [], []
    for a, b in zip(bornes[:-1], bornes[1:]):
        if b <= a:
            continue
        seg = y[a:b]
        i1, i2 = a + int(np.argmin(seg)), a + int(np.argmax(seg))
        for i in sorted((i1, i2)):
            tt.append(t[i]); yy.append(y[i])
    return np.array(tt), np.array(yy)


def formes():
    from spicelib.raw.raw_read import RawRead
    out = []
    for vin, pout in POINTS:
        f = ICI / f"results/formes/a1_{vin:.0f}V_{pout:.0f}W.raw"
        if not f.exists():
            continue
        r = RawRead(str(f))
        t = np.abs(np.asarray(r.get_trace("time").get_wave(), dtype=float))
        t -= t[0]
        g = lambda n: np.asarray(r.get_trace(n).get_wave(), dtype=float).real
        m = t <= N_PER / FSW
        ts, vsw, il = t[m] * 1e6, g("V(nsw)")[m], g("I(L1)")[m]
        vd = (g("V(nda)") - g("V(nd)"))[m]
        d = dict(vin=vin, pout=pout,
                 ipk=round(float(il.max()), 2),
                 vswpk=round(float(vsw.max()), 1),
                 vdrev=round(float(vd.min()), 0),
                 mode="DCM" if il.min() < 0.05 * il.max() else "CCM")
        for nom, y in (("vsw", vsw), ("il", il), ("vd", vd)):
            tr, yr = reduit(ts, y)
            d[nom] = [[round(float(a), 4), round(float(b), 3)]
                      for a, b in zip(tr, yr)]
        out.append(d)
    return out


def pertes_inductances():
    """Courbes mesurees Coilcraft, pertes totales vs ondulation."""
    def lit(f, bloc):
        rows = list(csv.reader(open(DON / f, encoding="latin-1")))
        i = next(k for k, r in enumerate(rows)
                 if len(r) > 1 and r[1].strip() == bloc)
        num = lambda r: [float(v.replace(",", ".")) for v in r[1:] if v.strip()]
        return num(rows[i + 1]), num(rows[i + 2])
    out = {}
    for p in ("SER2915L-472", "SER2013-472"):
        di, pd = lit("4L7-Explore Loss Ripple Current.csv", p)
        out[p] = dict(di=di, pertes=pd)
    return out


BILANS = {
    "archi1": dict(
        titre="Architecture 1 — DCM", rendement=97.06, pout=47.38,
        vdrev=-99, retenue=True,
        postes=[("Pertes fer inductance", 792.0), ("Diode V8PA22", 470.2),
                ("GaN EPC2207", 151.3), ("Cuivre inductance", 18.2),
                ("Grille", 6.2)]),
    "archi2": dict(
        titre="Architecture 2 — CCM", rendement=96.60, pout=48.99,
        vdrev=-221, retenue=False,
        postes=[("Diode V8PA22", 763.0), ("MOSFET BSC360N15NS3", 622.1),
                ("Cuivre inductance", 253.3), ("Grille", 52.5),
                ("Pertes fer inductance", 17.0)]),
}

if __name__ == "__main__":
    d = dict(formes=formes(), inductances=pertes_inductances(), bilans=BILANS)
    s = json.dumps(d, separators=(",", ":"))
    (ICI / "results/visuel.json").write_text(s, encoding="ascii")
    print(f"{len(d['formes'])} points, {len(s)/1024:.0f} ko")
