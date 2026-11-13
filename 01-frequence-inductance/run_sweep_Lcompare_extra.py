"""Complement a run_sweep_Lcompare.py : ajoute SER2211-822 (8,2uH, le
plus proche de 10uH -- SER2211 n'a pas de valeur exacte a 10uH) et
SER2211-273 (27uH, le plus proche de 22uH) a un Lcompare_<fsw>khz.csv
deja existant, memes 5 points (nominal x4 puissances + coin dur a 40W),
meme format de ligne que run_sweep_Lcompare.py. Usage :
    python run_sweep_Lcompare_extra.py <fsw_Hz>
"""
import csv
import sys

sys.path.insert(0, ".")
from find_duty1 import find_duty
from run_point1 import run as run_final

NOMINAL_PAIR = ("20V_80V", 20.0, 80.0)
HARDEST_PAIR = ("24V_100V", 24.0, 100.0)
POWERS = [5.0, 10.0, 20.0, 40.0]

# ser2211.pdf, doc Coilcraft 1084-1 -- valeurs les plus proches de
# 10/22uH dans la serie reelle (pas de valeur exacte a ces deux points).
EXTRA_PARTS = [
    ("SER2211-822", 8.2e-6, 2.30e-3, 13.4, 15.0, 15.8, 18.5),
    ("SER2211-273", 27.0e-6, 6.84e-3, 7.7, 8.5, 8.9, 13.1),
]

FIELDS = ["fsw_khz", "part", "l_uH", "dcr_ohm", "isat_10pct_A", "irms_40C_A",
          "pair", "vin", "vout_target", "pout_target", "d",
          "vout_avg", "pout_avg", "pin_avg", "eta_pct",
          "ploss_switch", "ploss_diode", "ploss_l_dcr",
          "vds_switch_max", "ipk_l", "irms_l", "il_end_of_period",
          "mode_measured", "isat_margin", "irms_margin"]


def run_extra(fsw):
    rows = []
    for part, l_h, dcr, isat10, isat20, isat30, irms40 in EXTRA_PARTS:
        points = [(NOMINAL_PAIR[0], NOMINAL_PAIR[1], NOMINAL_PAIR[2], p) for p in POWERS]
        points.append((HARDEST_PAIR[0], HARDEST_PAIR[1], HARDEST_PAIR[2], 40.0))
        for label, vin, vout, pout in points:
            print(f"=== fsw={fsw/1e3:.0f}kHz {part} ({l_h*1e6:.1f}uH) "
                  f"{label} Pout={pout}W ===")
            d_ideal = 1 - vin / vout
            d, r = find_duty(
                vin, vout, pout, fsw, l_h, dcr,
                d_lo=max(0.05, d_ideal * 0.5), d_hi=min(0.97, d_ideal * 1.2),
                tol=0.02, max_iter=8, settle_periods=1500)
            if r is None or "vout_avg" not in r:
                print(f"  ECHEC pour {part}/{label}/{pout}W")
                continue
            rf = run_final(vin, vout, pout, d, fsw, l_h, dcr,
                            out=f"results/ptL_{int(fsw/1e3)}k_{part}_{label}_{int(pout)}W.asc",
                            settle_periods=4000)
            if "vout_avg" not in rf:
                rf = r
            il_end = rf.get("il_end_of_period", 0.0)
            ipk = rf.get("ipk_l", 1.0)
            mode = "CCM" if abs(il_end) > 0.03 * ipk else "DCM"
            row = {
                "fsw_khz": fsw / 1e3, "part": part, "l_uH": l_h * 1e6,
                "dcr_ohm": dcr, "isat_10pct_A": isat10, "irms_40C_A": irms40,
                "pair": label, "vin": vin, "vout_target": vout,
                "pout_target": pout, "d": round(d, 4),
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
                "isat_margin": round(isat10 / max(rf.get("ipk_l", 1e-9), 1e-9), 3),
                "irms_margin": round(irms40 / max(rf.get("irms_l", 1e-9), 1e-9), 3),
            }
            rows.append(row)
            print(f"  -> Vout={row['vout_avg']}V eta={row['eta_pct']}% "
                  f"mode={mode} Ipk={row['ipk_l']}A (marge Isat x{row['isat_margin']}) "
                  f"Irms={row['irms_l']}A (marge x{row['irms_margin']})")
    return rows


if __name__ == "__main__":
    fsw = float(sys.argv[1])
    csv_path = f"results/Lcompare_{int(fsw/1e3)}khz.csv"
    with open(csv_path, newline="", encoding="utf-8") as f:
        existing = list(csv.DictReader(f))
    new_rows = run_extra(fsw)
    all_rows = existing + new_rows
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(all_rows)
    print(f"\n{csv_path} : {len(existing)} + {len(new_rows)} = {len(all_rows)} lignes")
