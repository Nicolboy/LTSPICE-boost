"""Modele de pertes fer de la SER1360-472, cale sur les exports Coilcraft.

SOURCE : deux balayages du simulateur de pertes Coilcraft pour la
SER1360-472, archives dans donnees/ :
  - vs frequence   : 400 -> 800 kHz, a dI = 2 A, IDC = 2 A, 25 degC
  - vs ondulation  : dI = 1 -> 3 A, a 400 kHz, IDC = 2 A, 25 degC

METHODE. L'export donne la perte TOTALE, cuivre inclus. On retire le
cuivre -- I_rms^2 * DCR avec I_rms^2 = IDC^2 + dI^2/12 pour une
ondulation triangulaire -- et on ajuste le reste par une loi de type
Steinmetz P_fer = k * f^a * dI^b, par moindres carres sur les
logarithmes des 22 points des deux balayages a la fois.

Le point (400 kHz, 2 A) est COMMUN aux deux balayages : il sert de
controle de coherence entre eux.

LIMITE A CONNAITRE -- et elle est importante ici. Les deux balayages sont
menes a IDC = 2 A avec une ondulation de 1 a 3 A, c'est-a-dire en regime
de type CCM : un courant continu portant une petite ondulation. Or
l'architecture 1 fonctionne en DCM PERMANENT : le courant part de zero,
monte a I_pk, redescend a zero, puis le noyau reste au repos pendant le
temps mort. L'excursion dI vaut alors I_pk tout entier -- jusqu'a 5,5 A
a 40 W, donc HORS de la plage ajustee (1 a 3 A).

Deux ecarts en decoulent, tous deux declares plutot que corriges :
  1. extrapolation de dI au-dela du domaine d'ajustement ;
  2. la forme d'onde DCM n'est ni sinusoidale ni triangulaire
     symetrique, son contenu harmonique differe, et une loi de Steinmetz
     classique ne le rend pas (il faudrait une iGSE, qui demande les
     coefficients du materiau -- non publies par Coilcraft).

La perte fer en DCM donnee ici est donc un ORDRE DE GRANDEUR appuye sur
des donnees constructeur, pas une valeur garantie. Elle est affichee
separement dans le budget pour qu'on puisse la lire comme telle.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

DCR = 5.50e-3          # Ohm, SER1360-472KL, doc Coilcraft 290-1
IDC_REF = 2.0          # A, courant continu des deux balayages
ICI = Path(__file__).resolve().parent


def _nombre(s: str) -> float:
    """Les exports Coilcraft sortent en virgule decimale francaise."""
    return float(s.strip().replace(",", "."))


def _lit(nom: str) -> tuple[list[float], list[float]]:
    """Renvoie (abscisses, pertes totales en mW) d'un export."""
    # cp1252 : l'export Coilcraft ecrit le degre en 0xB0, pas en UTF-8
    lignes = list(csv.reader((ICI / "donnees" / nom).open(encoding="cp1252")))
    x = y = None
    for ligne in lignes:
        if not ligne:
            continue
        if ligne[0] in ("Frequency", "Ripple Current") and len(ligne) > 3 \
                and ligne[1] and ligne[1][0].isdigit():
            x = [_nombre(v) for v in ligne[1:] if v.strip()]
        elif ligne[0] == "Total Losses":
            y = [_nombre(v) for v in ligne[1:] if v.strip()]
    assert x and y and len(x) == len(y), f"{nom} : lecture impossible"
    return x, y


def _cuivre_mw(di: float, idc: float = IDC_REF) -> float:
    """Perte cuivre en mW pour une ondulation triangulaire crete-a-crete."""
    return (idc**2 + di**2 / 12.0) * DCR * 1e3


def ajuste(verbeux: bool = False) -> dict:
    """Moindres carres de log(P_fer) = log k + a log f + b log dI."""
    f_hz, p_f = _lit("ser1360-472_pertes_vs_frequence.csv")
    di_a, p_di = _lit("ser1360-472_pertes_vs_ondulation.csv")

    pts = [(f * 1e3, 2.0, p) for f, p in zip(f_hz, p_f)] \
        + [(400e3, di, p) for di, p in zip(di_a, p_di)]

    A, y = [], []
    for f, di, p_tot in pts:
        p_fer = p_tot - _cuivre_mw(di)
        assert p_fer > 0, f"cuivre > total a f={f}, dI={di}"
        A.append([1.0, np.log(f), np.log(di)])
        y.append(np.log(p_fer))
    sol, *_ = np.linalg.lstsq(np.array(A), np.array(y), rcond=None)
    k, a, b = float(np.exp(sol[0])), float(sol[1]), float(sol[2])

    # residus : le modele doit reproduire les 22 points d'origine
    res = []
    for f, di, p_tot in pts:
        attendu = p_tot - _cuivre_mw(di)
        res.append(100.0 * (k * f**a * di**b / attendu - 1.0))
    res = np.array(res)

    # controle de coherence : le point commun aux deux balayages
    i_commun = [i for i, (f, di, _) in enumerate(pts)
                if abs(f - 400e3) < 1 and abs(di - 2.0) < 1e-9]
    coherence = [pts[i][2] for i in i_commun]

    m = dict(k=k, a=a, b=b, n_pts=len(pts),
             res_max=float(np.abs(res).max()), res_rms=float(np.sqrt((res**2).mean())),
             point_commun=coherence)
    if verbeux:
        print(f"P_fer [mW] = {k:.4e} * f[Hz]^{a:.4f} * dI[A]^{b:.4f}")
        print(f"  {len(pts)} points, residu RMS {m['res_rms']:.2f} %, "
              f"max {m['res_max']:.2f} %")
        print(f"  point commun aux deux balayages (400 kHz, 2 A) : "
              f"{coherence} mW -> {'coherent' if len(set(coherence)) == 1 else 'DIVERGENT'}")
        print(f"  exposants : a={a:.3f} (f), b={b:.3f} (dI) -- une loi de"
              f" Steinmetz classique donne a~1,1-1,6 et b~2,0-2,6")
    return m


_FIT: dict | None = None


def p_fer_mw(fsw: float, di: float) -> float:
    """Perte fer en mW. ATTENTION : extrapolation si dI > 3 A, cf. docstring."""
    global _FIT
    if _FIT is None:
        _FIT = ajuste()
    return _FIT["k"] * fsw**_FIT["a"] * di**_FIT["b"]


def hors_domaine(di: float) -> bool:
    """Vrai si l'ondulation sort de la plage ajustee (1 a 3 A)."""
    return not (1.0 <= di <= 3.0)


if __name__ == "__main__":
    m = ajuste(verbeux=True)
    print("\n--- controle sur un point INDEPENDANT du couple (a, b) ---")
    # 600 kHz / 2 A figure dans le balayage en frequence : 146 mW total
    att = 146.0 - _cuivre_mw(2.0)
    calc = p_fer_mw(600e3, 2.0)
    print(f"600 kHz, dI=2 A : modele {calc:.1f} mW, Coilcraft {att:.1f} mW "
          f"-> {100*(calc/att-1):+.1f} %")

    print("\n--- ce que donne le DCM de l'architecture 1 (EXTRAPOLE) ---")
    print(f"{'Pout':>6} {'dI=I_pk':>9} {'P_fer':>8}  domaine")
    for pout, ipk in ((5, 2.17), (20, 4.15), (40, 5.50), (50, 6.15)):
        hd = "EXTRAPOLE (dI > 3 A)" if hors_domaine(ipk) else "ajuste"
        print(f"{pout:5.0f} W {ipk:8.2f} A {p_fer_mw(400e3, ipk):7.1f} mW  {hd}")
