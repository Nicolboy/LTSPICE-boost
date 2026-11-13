"""Balayage etage1 : pour une frequence donnee et L=47uH fixe (SER2211-473,
contrainte boitier utilisateur -- pas de piece plus grosse pour cet
etage), les 3 couples (Vin,Vout) x 4 puissances (5/10/20/40W). D resolu
par bissection (find_duty1), mesures completes via run_point1.
Usage: python run_sweep_stage1.py <fsw_Hz> [out_csv]
"""
import csv
import sys

sys.path.insert(0, ".")
from find_duty1 import find_duty

PAIRS = [
    ("12V_60V", 12.0, 60.0),
    ("20V_80V", 20.0, 80.0),
    ("24V_100V", 24.0, 100.0),
]
POWERS = [5.0, 10.0, 20.0, 40.0]
L_H = 47e-6
DCR_OHM = 8.95e-3  # SER2211-473 typ, doc Coilcraft 1084-1

FIELDS = ["fsw_khz", "pair", "vin", "vout_target", "pout_target", "d",
          "vout_avg", "pout_avg", "pin_avg", "eta_pct",
          "ploss_switch", "ploss_diode", "ploss_l_dcr",
          "vds_switch_max", "ipk_l", "irms_l", "il_end_of_period",
          "mode_measured"]


def run_sweep(fsw):
    rows = []
    for label, vin, vout in PAIRS:
        for pout in POWERS:
            print(f"=== fsw={fsw/1e3:.0f}kHz {label} Pout={pout}W ===")
            d_ideal = 1 - vin / vout
            d, r = find_duty(
                vin, vout, pout, fsw, L_H, DCR_OHM,
                d_lo=max(0.05, d_ideal * 0.5), d_hi=min(0.97, d_ideal * 1.15),
                tol=0.02, max_iter=8, settle_periods=1500)
            if r is None or "vout_avg" not in r:
                print(f"  ECHEC pour {label}/{pout}W")
                continue
            # run final de mesure a pleine precision (settle_periods=4000)
            from run_point1 import run as run_final
            rf = run_final(vin, vout, pout, d, fsw, L_H, DCR_OHM,
                            out=f"results/pt_stage1_{int(fsw/1e3)}k_{label}_{int(pout)}W.asc",
                            settle_periods=4000)
            if "vout_avg" not in rf:
                print(f"  ECHEC run final pour {label}/{pout}W, garde le resultat de recherche")
                rf = r
            il_end = rf.get("il_end_of_period", 0.0)
            ipk = rf.get("ipk_l", 1.0)
            mode = "CCM" if abs(il_end) > 0.03 * ipk else "DCM"
            row = {
                "fsw_khz": fsw / 1e3, "pair": label, "vin": vin,
                "vout_target": vout, "pout_target": pout, "d": round(d, 4),
                "vout_avg": round(rf.get("vout_avg", 0.0), 4),
                "pout_avg": round(rf.get("pout_avg", 0.0), 4),
                "pin_avg": round(rf.get("pin_avg", 0.0), 4),
                "eta_pct": round(100 * rf["pout_avg"] / rf["pin_avg"], 3),
                "ploss_switch": round(rf.get("ploss_switch", 0.0), 5),
                "ploss_diode": round(rf.get("ploss_diode", 0.0), 5),
                "ploss_l_dcr": round(rf.get("ploss_l_dcr", 0.0), 5),
                "vds_switch_max": round(rf.get("vds_switch_max", 0.0), 3),
                "ipk_l": round(rf.get("ipk_l", 0.0), 4),
                "irms_l": round(rf.get("irms_l", 0.0), 4),
                "il_end_of_period": round(il_end, 4),
                "mode_measured": mode,
            }
            rows.append(row)
            print(f"  -> Vout={row['vout_avg']}V eta={row['eta_pct']}% "
                  f"mode={mode} Ipk={row['ipk_l']}A Irms={row['irms_l']}A "
                  f"Vds_max={row['vds_switch_max']}V")
    return rows


if __name__ == "__main__":
    fsw = float(sys.argv[1])
    out_csv = sys.argv[2] if len(sys.argv) > 2 else f"results/stage1_{int(fsw/1e3)}khz.csv"
    rows = run_sweep(fsw)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"\nEcrit {out_csv} ({len(rows)} points)")
