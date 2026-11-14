"""Volet EMI/resonance (README S9) -- pertes des 3 candidats switch reels
(IPD050N10N5, SUD70090E, NVD6824NL) a leur VITESSE NATIVE (pas ralentie),
pour juger si le candidat le plus rapide (IPD050N10N5) "coute" vraiment
en proportion de commutation avant d'envisager de le ralentir.

Calcul direct en Python depuis les points DEJA MESURES en SPICE au
balayage principal (results/stage1_tech_sweep.csv, switch=Si/diode=
Schottky, pair=20V_80V, pout_target=40W, L=47uH) -- AUCUNE nouvelle
simulation :
  - Irms_switch (perte Joule) : le courant au point de fonctionnement ne
    depend pas du Rds(on) du switch simule (Si generique), reutilisable
    tel quel pour les 3 candidats reels.
  - Ipk_L (I_peak a l'instant turn-off) / IL_end_of_period (I_valley a
    l'instant turn-on) : courant de maille au noeud de commutation,
    independant lui aussi de la techno switch simulee.
  - Vout_avg : approxime Vds au blocage (switch bas-cote, boost).

Methode de commutation : PAS les tr/tf publies tels quels (conditions
de test differentes d'un fabricant a l'autre -- piege deja signale
S6.2), mais recalcules depuis Qgd et le driver de grille retenu pour
cet etage (4A pic source / 6A pic puits) :
  t_sw_on  = Qgd / I_source = Qgd / 4A
  t_sw_off = Qgd / I_sink   = Qgd / 6A
  Eon  = 0,5 * Vds * I_valley * t_sw_on
  Eoff = 0,5 * Vds * I_peak   * t_sw_off
  Psw  = (Eon + Eoff) * fsw
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from switch_diode_models import REAL_SWITCHES

I_SOURCE_GATE_DRIVER = 4.0   # A, pic source -- driver de grille retenu
I_SINK_GATE_DRIVER = 6.0     # A, pic puits -- idem

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "results", "stage1_tech_sweep.csv")


def load_nominal_points():
    """Points Si/Schottky, L=47uH, pair=20V_80V, pout_target=40W, les 4
    frequences du balayage principal -- deja mesures en SPICE, pas
    reproduits ici."""
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r["switch_tech"] == "Si" and r["diode_tech"] == "Schottky"
                    and r["l_uh"] == "47.0" and r["pair"] == "20V_80V"
                    and r["pout_target"] == "40.0"):
                rows.append(dict(
                    fsw_khz=float(r["fsw_khz"]),
                    vout_avg=float(r["vout_avg"]),
                    irms_switch=float(r["irms_switch"]),
                    ipk_l=float(r["ipk_l"]),
                    il_end_of_period=float(r["il_end_of_period"]),
                ))
    rows.sort(key=lambda x: x["fsw_khz"])
    return rows


def estimate(switch_name, point):
    sw = REAL_SWITCHES[switch_name]
    fsw = point["fsw_khz"] * 1e3
    vds = point["vout_avg"]
    i_valley = max(point["il_end_of_period"], 0.0)  # CCM ici, toujours >0
    i_peak = point["ipk_l"]

    p_cond = point["irms_switch"] ** 2 * sw["rds_on_ohm"]

    qgd = sw["qgd_nc"] * 1e-9
    t_on = qgd / I_SOURCE_GATE_DRIVER
    t_off = qgd / I_SINK_GATE_DRIVER
    e_on = 0.5 * vds * i_valley * t_on
    e_off = 0.5 * vds * i_peak * t_off
    p_sw = (e_on + e_off) * fsw

    p_total = p_cond + p_sw
    return dict(fsw_khz=point["fsw_khz"], p_cond=p_cond, p_sw=p_sw,
                p_total=p_total, ratio_sw=p_sw / p_total if p_total else 0.0)


def main():
    points = load_nominal_points()
    print(f"Point nominal : 20V->80V/40W, L=47uH, driver de grille "
          f"({I_SOURCE_GATE_DRIVER:.0f}A src/{I_SINK_GATE_DRIVER:.0f}A sink)\n")
    for switch_name, sw in REAL_SWITCHES.items():
        print(f"=== {switch_name} ({sw['manufacturer']}) : "
              f"Rds(on)={sw['rds_on_ohm']*1e3:.2f}mOhm({sw['rds_on_basis']}) "
              f"Qgd={sw['qgd_nc']:.1f}nC({sw['qgd_basis']}) ===")
        print(f"{'fsw(kHz)':>10} {'P_cond(W)':>10} {'P_sw(W)':>10} "
              f"{'P_tot(W)':>10} {'Psw/Ptot':>9}")
        for p in points:
            r = estimate(switch_name, p)
            print(f"{r['fsw_khz']:>10.0f} {r['p_cond']:>10.4f} "
                  f"{r['p_sw']:>10.4f} {r['p_total']:>10.4f} "
                  f"{r['ratio_sw']*100:>8.1f}%")
        print()


if __name__ == "__main__":
    main()
