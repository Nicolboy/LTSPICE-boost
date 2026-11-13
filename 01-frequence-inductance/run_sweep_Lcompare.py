"""Comparaison des 7 valeurs de la serie Coilcraft SER2211 (meme boitier,
contrainte utilisateur deja actee -- aucune n'est plus grosse que
SER2211), a une frequence donnee. Memes 3 couples (Vin,Vout) x 4
puissances que run_sweep_stage1.py, mais L/DCR varient au lieu d'etre
fixes a 47uH. DCR/Isat typ sources : ser2211.pdf, doc Coilcraft 1084-1.
Usage: python run_sweep_Lcompare.py <fsw_Hz> [out_csv]
"""
import csv
import sys

sys.path.insert(0, ".")
from find_duty1 import find_duty
from run_point1 import run as run_final

NOMINAL_PAIR = ("20V_80V", 20.0, 80.0)
HARDEST_PAIR = ("24V_100V", 24.0, 100.0)
POWERS = [5.0, 10.0, 20.0, 40.0]

# Grille de valeurs retenue par l'utilisateur : 10/22/47/100/220/330uH
# (= exactement le catalogue MSS1583, voir plus bas) -- pas les petites
# valeurs (3/5.3/8.2uH, ecartees comme peu utiles ici). Chaque famille
# n'apparait qu'aux valeurs qu'elle propose reellement (pas d'extrapolation).

# SER2211 (11,5x11mm environ -- le boitier de reference, contrainte de
# taille actee), doc Coilcraft 1084-1 (ser2211.pdf). Seule 47uH tombe
# exactement sur la grille retenue (la serie s'arrete la de toute facon).
SER2211_PARTS = [
    ("SER2211-473", 47.0e-6, 8.95e-3, 4.4, 5.2, 5.6, 10.6),
]

# MSS1583 (14,8x14,8mm, PLUS GROS que SER2211 -- pour comparaison
# seulement, hors contrainte de boitier), doc Coilcraft 1111-1
# (mss1583.pdf) -- couvre exactement la grille 10/22/47/100/220/330uH.
MSS1583_PARTS = [
    ("MSS1583-103", 10.0e-6, 14.0e-3, 12.0, 13.6, 14.7, 7.4),
    ("MSS1583-223", 22.0e-6, 23.0e-3, 8.2, 9.1, 10.4, 5.3),
    ("MSS1583-473", 47.0e-6, 48.0e-3, 5.9, 6.7, 7.3, 3.7),
    ("MSS1583-104", 100.0e-6, 90.0e-3, 3.9, 4.4, 4.8, 2.8),
    ("MSS1583-224", 220.0e-6, 205.0e-3, 2.6, 3.0, 3.3, 1.8),
    ("MSS1583-334", 330.0e-6, 300.0e-3, 2.0, 2.3, 2.5, 1.45),
]

# MSS1514V (15,5x15,5mm, encore plus gros, 1000V max -- pour
# comparaison seulement), doc Coilcraft 1755-1 (mss1514v.pdf). Sa plage
# commence a 33uH (pas de 10/22uH) -- seules 47/100/220uH tombent sur la
# grille retenue.
MSS1514V_PARTS = [
    ("MSS1514V-473", 47.0e-6, 38.0e-3, 4.7, 5.3, 5.9, 3.9),
    ("MSS1514V-104", 100.0e-6, 64.0e-3, 3.2, 3.7, 4.0, 3.1),
    ("MSS1514V-224", 220.0e-6, 152.0e-3, 2.2, 2.5, 2.7, 2.2),
]

ALL_PARTS = SER2211_PARTS + MSS1583_PARTS + MSS1514V_PARTS

FIELDS = ["fsw_khz", "part", "l_uH", "dcr_ohm", "isat_10pct_A", "irms_40C_A",
          "pair", "vin", "vout_target", "pout_target", "d",
          "vout_avg", "pout_avg", "pin_avg", "eta_pct",
          "ploss_switch", "ploss_diode", "ploss_l_dcr",
          "vds_switch_max", "ipk_l", "irms_l", "il_end_of_period",
          "mode_measured", "isat_margin", "irms_margin"]


def run_sweep(fsw):
    rows = []
    for part, l_h, dcr, isat10, isat20, isat30, irms40 in ALL_PARTS:
        # point nominal (20V/80V) aux 4 puissances + verification CCM
        # au coin le plus dur (24V/100V) a 40W seulement -- comparaison
        # multi-familles, pas une revalidation complete par piece.
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
    out_csv = sys.argv[2] if len(sys.argv) > 2 else f"results/Lcompare_{int(fsw/1e3)}khz.csv"
    rows = run_sweep(fsw)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"\nEcrit {out_csv} ({len(rows)} points)")
