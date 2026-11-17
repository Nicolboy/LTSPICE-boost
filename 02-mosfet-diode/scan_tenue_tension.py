"""Tenue en tension de l'architecture 1 : le dimensionnement tient-il ?

Le balayage de l'inductance de maille a montre que celle-ci ne coute
presque rien en rendement (+12 mW au pire) mais beaucoup en TENSION. Ce
script etablit le pire cas et le confronte aux calibres des composants.

POURQUOI BV RESTE A 150 V DANS LE MODELE alors que l'EPC2007C est un
100 V : mettre BV=100 ferait ecreter la jonction a 100 V dans SPICE, et
la simulation renverrait un depassement « sain » de 100 V pile -- en
masquant le probleme. Un GaN HEMT ne tient d'ailleurs pas l'avalanche
comme un silicium : au-dela de son BVDSS il ne conduit pas, il casse.
Le modele doit donc laisser le depassement se developper librement, et
c'est la COMPARAISON au calibre, faite ici, qui rend le verdict.

Calibres confrontes :
  EPC2007C : 100 V, maximum absolu continu (p.1 tbl Maximum Ratings) --
             et BVDSS minimum garanti 100 V lui aussi, donc AUCUNE marge
             entre les deux.
  V6PW12C  : 120 V (le « 12 » de la reference). La diode n'est stressee
             en inverse que pendant la conduction du canal ; pendant le
             depassement du noeud elle est passante, donc non stressee.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI)]

import gen_dcm_gan as g                        # noqa: E402
from make_waveforms_dcm import TRAVAIL, trim   # noqa: E402

VDS_MAX_GAN = 100.0      # V, EPC2007C p.1 Maximum Ratings, absolu continu
VRRM_DIODE = 120.0       # V, V6PW12C
DERATING = 0.80          # 20 % de marge, usage courant en production

MAILLES = (5e-9, 10e-9, 20e-9, 40e-9)
PUISSANCES = (20.0, 40.0, 50.0)


def verdict(v_pk: float) -> str:
    if v_pk > VDS_MAX_GAN:
        return "DETRUIT"
    if v_pk > VDS_MAX_GAN * DERATING:
        return "hors derating"
    return "ok"


if __name__ == "__main__":
    print(f"EPC2007C : {VDS_MAX_GAN:.0f} V absolu, "
          f"{VDS_MAX_GAN*DERATING:.0f} V avec {100*(1-DERATING):.0f} % de marge\n")
    print(f"{'maille':>7} {'Pout':>6} {'I_pk':>6} {'V_pk noeud':>11} "
          f"{'depass.':>8} {'V_inv diode':>12}  verdict")
    lignes = []
    for lb in MAILLES:
        for pw in PUISSANCES:
            d, x, m = trim(pw, TRAVAIL / f"tv{lb*1e9:.0f}_{pw:.0f}", l_boucle=lb)
            if x is None:
                print(f"{lb*1e9:6.0f}n {pw:5.0f}W  ECHEC")
                continue
            assert x["ecart"] < 0.03, f"bilan non ferme : {x['ecart']:.1%}"
            v_inv = float((m["V(nd)"] - m["V(nda)"]).max())
            vd = verdict(x["v_pk"])
            print(f"{lb*1e9:6.0f}n {pw:5.0f}W {x['i_pk']:5.2f}A "
                  f"{x['v_pk']:10.1f}V {x['v_pk']-80:7.1f}V {v_inv:11.1f}V"
                  f"  {vd}")
            lignes.append(dict(lb=lb, pout=pw, i_pk=x["i_pk"], v_pk=x["v_pk"],
                               v_inv=v_inv, verdict=vd))

    print("\n--- calibre minimal requis, 20 % de marge, au pire cas ---")
    for lb in MAILLES:
        pires = [r["v_pk"] for r in lignes if r["lb"] == lb]
        if not pires:
            continue
        v = max(pires)
        print(f"  maille {lb*1e9:3.0f} nH : V_pk {v:6.1f} V "
              f"-> composant >= {v/DERATING:5.0f} V")
    if lignes:
        vi = max(r["v_inv"] for r in lignes)
        print(f"\n  diode : V_inverse max {vi:.1f} V sur {VRRM_DIODE:.0f} V "
              f"-> {'ok' if vi < VRRM_DIODE*DERATING else 'A VERIFIER'}")
