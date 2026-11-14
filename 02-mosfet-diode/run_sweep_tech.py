"""Chapitre 2 -- balaye la grille allegee : 4 combinaisons
switch x diode, 4 frequences, 3 valeurs L (SER2211, meme boitier gagnant
du chapitre 1), grille electrique allegee (point nominal 20V->80V aux 4
puissances + coin le plus dur 24V->100V a 40W seulement) = 4x4x3x5 = 240
points. Ecrit results/stage1_tech_sweep.csv.

Usage : python run_sweep_tech.py [out_csv]
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from find_duty2 import find_duty
from inductor_sizing import crossover_power
from switch_diode_models import DIODES, SWITCHES, diode_vf_at

FREQS_HZ = [100e3, 200e3, 300e3, 400e3]

# SER2211 -- 3 valeurs, Coilcraft doc 1084-1 (meme feuille que le ch.1,
# DCR typ) -- PAS de melange de famille (verdict ch.1 : SER2211 domine
# MSS1583/MSS1514V a L egale).
L_CANDIDATES = [
    ("SER2211-123MED", 12.0e-6, 3.15e-3),
    ("SER2211-273MED", 27.0e-6, 6.84e-3),
    ("SER2211-473MED", 47.0e-6, 8.95e-3),
]

NOMINAL = ("20V_80V", 20.0, 80.0)
HARDEST = ("24V_100V", 24.0, 100.0)
NOMINAL_POWERS = [5.0, 10.0, 20.0, 40.0]
HARDEST_POWERS = [40.0]

SWITCH_TECHS = list(SWITCHES.keys())
DIODE_TECHS = list(DIODES.keys())

FIELDS = [
    "switch_tech", "switch_part", "diode_tech", "diode_part",
    "fsw_khz", "l_name", "l_uh", "dcr_ohm", "pair", "vin", "vout_target",
    "pout_target", "duty_ideal", "duty_used", "crossover_w",
    "mode_predicted", "mode_measured",
    "vout_avg", "pout_avg", "pin_avg", "eta_pct",
    "ploss_switch_total", "irms_switch", "ploss_switch_cond_est",
    "ploss_switch_sw_est",
    "ploss_diode_total", "ploss_diode_cond_est", "ploss_diode_recovery_est",
    "ploss_l_dcr", "vds_switch_max", "vds_overshoot_v",
    "ipk_l", "irms_l", "il_end_of_period",
]


def electrical_points():
    pts = []
    label, vin, vout = NOMINAL
    for p in NOMINAL_POWERS:
        pts.append((label, vin, vout, p))
    label, vin, vout = HARDEST
    for p in HARDEST_POWERS:
        pts.append((label, vin, vout, p))
    return pts


def run_all(out_csv="results/stage1_tech_sweep.csv"):
    os.makedirs("results", exist_ok=True)
    rows = []
    points = electrical_points()
    total = (len(SWITCH_TECHS) * len(DIODE_TECHS) * len(FREQS_HZ)
             * len(L_CANDIDATES) * len(points))
    n = 0
    for switch_tech in SWITCH_TECHS:
        rd = SWITCHES[switch_tech]["rd_ohm"]
        for diode_tech in DIODE_TECHS:
            for fsw in FREQS_HZ:
                for l_name, l_h, dcr in L_CANDIDATES:
                    for label, vin, vout, pout in points:
                        n += 1
                        d_ideal = 1 - vin / vout
                        pc = crossover_power(vin, vout, l_h, fsw)
                        mode_pred = "CCM" if pout >= pc else "DCM"
                        print(f"[{n}/{total}] {switch_tech}+{diode_tech} "
                              f"{fsw/1e3:.0f}kHz {l_name} {label} {pout}W "
                              f"(pred {mode_pred})")
                        tmp_out = (f"results/pt2_{int(fsw/1e3)}k_"
                                   f"{switch_tech}_{diode_tech}_{l_name}_"
                                   f"{label}_{int(pout)}W.asc")
                        d, r = find_duty(
                            vin, vout, pout, fsw, l_h, dcr, switch_tech,
                            diode_tech,
                            d_lo=max(0.05, d_ideal * 0.5),
                            d_hi=min(0.97, d_ideal * 1.15),
                            tol=0.02, max_iter=8, tmp_out=tmp_out)
                        if r is None or r.get("vout_avg") is None:
                            print(f"  ECHEC pour ce point, ligne ignoree")
                            continue
                        row = dict(
                            switch_tech=switch_tech,
                            switch_part=SWITCHES[switch_tech]["part"],
                            diode_tech=diode_tech,
                            diode_part=DIODES[diode_tech]["part"],
                            fsw_khz=fsw / 1e3, l_name=l_name,
                            l_uh=round(l_h * 1e6, 4), dcr_ohm=dcr,
                            pair=label, vin=vin, vout_target=vout,
                            pout_target=pout,
                            duty_ideal=round(d_ideal, 4),
                            duty_used=round(d, 4),
                            crossover_w=round(pc, 4),
                            mode_predicted=mode_pred,
                        )
                        for k in ("vout_avg", "pout_avg", "pin_avg",
                                  "ploss_switch_total", "irms_switch",
                                  "ploss_diode_total", "ploss_l_dcr",
                                  "vds_switch_max", "ipk_l", "irms_l",
                                  "il_end_of_period"):
                            v = r.get(k)
                            row[k] = round(v, 6) if v is not None else None

                        row["eta_pct"] = (
                            round(100 * row["pout_avg"] / row["pin_avg"], 3)
                            if row["pout_avg"] is not None and row["pin_avg"]
                            else None)
                        row["vds_overshoot_v"] = (
                            round(row["vds_switch_max"] - row["vout_avg"], 4)
                            if row["vds_switch_max"] is not None
                            and row["vout_avg"] is not None else None)

                        if row["irms_switch"] is not None:
                            cond = row["irms_switch"] ** 2 * rd
                            row["ploss_switch_cond_est"] = round(cond, 6)
                            row["ploss_switch_sw_est"] = (
                                round(row["ploss_switch_total"] - cond, 6)
                                if row["ploss_switch_total"] is not None
                                else None)
                        else:
                            row["ploss_switch_cond_est"] = None
                            row["ploss_switch_sw_est"] = None

                        iout_avg = r.get("iout_avg")
                        if iout_avg is not None:
                            vf_est = diode_vf_at(diode_tech, iout_avg)
                            cond_d = vf_est * iout_avg
                            row["ploss_diode_cond_est"] = round(cond_d, 6)
                            row["ploss_diode_recovery_est"] = (
                                round(row["ploss_diode_total"] - cond_d, 6)
                                if row["ploss_diode_total"] is not None
                                else None)
                        else:
                            row["ploss_diode_cond_est"] = None
                            row["ploss_diode_recovery_est"] = None

                        il_end = row.get("il_end_of_period") or 0.0
                        ipk = row.get("ipk_l") or 1.0
                        row["mode_measured"] = (
                            "CCM" if abs(il_end) > 0.03 * ipk else "DCM")

                        rows.append(row)
                        print(f"  -> Vout={row['vout_avg']}V "
                              f"eta={row['eta_pct']}% mode={row['mode_measured']} "
                              f"Psw={row['ploss_switch_total']}W "
                              f"Pd={row['ploss_diode_total']}W "
                              f"Vds_os={row['vds_overshoot_v']}V")

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"\nEcrit {out_csv} ({len(rows)} lignes / {total} attendues)")
    return rows


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "results/stage1_tech_sweep.csv"
    run_all(out)
