"""Volet EMI/resonance (README S9) -- frequence et amplitude de
resonance de la boucle chaude (Lstray estimee par placement, voir
estimate_loop_parasitics.py) pour les 9 combinaisons switch x diode
reelles (REAL_SWITCHES x REAL_DIODES), au point nominal (20V->80V/40W,
200kHz, L=47uH), DEUX verifications croisees :

  1. Calcul a la main :
       f0   = 1 / (2*pi*sqrt(Lboucle * (Coss_switch + Cj_diode)))
       Vpic = Vout + Ipk_L * sqrt(Lboucle / (Coss_switch + Cj_diode))
     (impedance caracteristique du reseau LC excite par le courant
     inductance a l'instant de commutation -- Ipk_L deja mesure pour
     switch=Si/diode=Schottky generiques, reutilise tel quel : le
     courant de maille ne depend pas de la techno switch/diode reelle
     simulee ensuite.)
  2. Confirmation SPICE : gen_boost2_tech.build() avec Lstray=estimation
     de estimate_loop_parasitics.py (PAS une valeur devinee arbitraire)
     + Cj_DIODE ajoutee (voir gen_boost2_tech.py) -- compare
     Vds_switch_max mesure au Vpic calcule.

Lstray : deux scenarios (voir estimate_loop_parasitics.py) -- "etat
actuel" (pas de plan de masse rapproche, carte seulement placee) utilise
par defaut ici ; "cible routage" en complement pour voir la sensibilite.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from estimate_loop_parasitics import (NH_PER_CM_NO_PLANE,
                                       NH_PER_CM_WITH_RETURN, main as
                                       loop_main)
from run_point2 import run
from switch_diode_models import DIODES, REAL_DIODES, REAL_SWITCHES

VIN, VOUT_T, POUT, FSW = 20.0, 80.0, 40.0, 200e3
L_H, DCR_OHM, DUTY = 47e-6, 8.95e-3, 0.7482
IPK_L_REF = 2.775435  # A, deja mesure (Si/Schottky, meme point)


def hand_calc(l_stray_h, coss_f, cj_f, vout, ipk_l):
    c_tot = coss_f + cj_f
    f0 = 1 / (2 * math.pi * math.sqrt(l_stray_h * c_tot))
    z0 = math.sqrt(l_stray_h / c_tot)
    v_pic = vout + ipk_l * z0
    return f0, v_pic


def main():
    perimeter_cm = loop_main()
    l_stray_actuel = perimeter_cm * sum(NH_PER_CM_NO_PLANE) / 2 * 1e-9
    l_stray_cible = perimeter_cm * sum(NH_PER_CM_WITH_RETURN) / 2 * 1e-9
    print(f"\nLstray retenue pour ce balayage : {l_stray_actuel*1e9:.1f}nH "
          f"(etat actuel, milieu de fourchette) -- "
          f"{l_stray_cible*1e9:.1f}nH (cible routage) en complement\n")

    print(f"{'switch':<14}{'diode':<16}{'Coss(pF)':>9}{'Cj(pF)':>8}"
          f"{'f0_calc':>10}{'Vpic_calc':>11}{'Vds_sim':>9}{'ecart':>8}")
    rows = []
    for sw_name in REAL_SWITCHES:
        coss_f = REAL_SWITCHES[sw_name]["coss_f"]
        for di_name in REAL_DIODES:
            cj_f = REAL_DIODES[di_name]["cj_pf"] * 1e-12
            f0, v_pic = hand_calc(l_stray_actuel, coss_f, cj_f, VOUT_T,
                                   IPK_L_REF)

            out = f"_res_{sw_name}_{di_name}.asc"
            try:
                r = run(VIN, VOUT_T, POUT, DUTY, FSW, L_H, DCR_OHM,
                        sw_name, di_name, out=out, lstray_h=l_stray_actuel)
                vds_sim = r.get("vds_switch_max")
            except Exception:
                vds_sim = None
            ecart = (f"{(vds_sim - v_pic) / v_pic * 100:+.0f}%"
                     if vds_sim else "?")
            print(f"{sw_name:<14}{di_name:<16}{coss_f*1e12:>9.0f}"
                  f"{cj_f*1e12:>8.0f}{f0/1e6:>9.2f}M{v_pic:>10.1f}V"
                  f"{vds_sim if vds_sim else float('nan'):>9.1f}{ecart:>8}")
            rows.append(dict(switch=sw_name, diode=di_name, f0=f0,
                              v_pic_calc=v_pic, vds_sim=vds_sim))
    return rows


if __name__ == "__main__":
    main()
