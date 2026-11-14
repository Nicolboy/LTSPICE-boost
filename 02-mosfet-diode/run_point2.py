"""Genere un point de fonctionnement etage1 chapitre 2 (switch/diode
techno reelle), le lance dans LTspice (mode batch), affiche les
resultats .meas. Usage :
    python run_point2.py <Vin> <Vout_cible> <Pout> <D> <fsw_Hz> <L_H> <DCR_Ohm> <switch_tech> <diode_tech> [out.asc]
"""
import subprocess
import sys

sys.path.insert(0, ".")
from gen_boost2_tech import build

LTSPICE = r"C:/Program Files/ADI/LTspice/LTspice.exe"


def run(vin, vout_target, pout, d, fsw, l_henries, dcr_ohm, switch_tech,
        diode_tech, out="point2.asc", lstray_h=None, settle_periods=None,
        measure_periods=None, rload=None, dtmax_s=1e-9):
    period = 1 / fsw
    build("point", vin, vout_target, pout, d, period, out,
          l_henries=l_henries, dcr_ohm=dcr_ohm, switch_tech=switch_tech,
          diode_tech=diode_tech, lstray_h=lstray_h, rload=rload,
          settle_periods=settle_periods, measure_periods=measure_periods,
          dtmax_s=dtmax_s)
    subprocess.run([LTSPICE, "-b", out], stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
    log_path = out.replace(".asc", ".log")
    results = {}
    with open(log_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if ":" in line and "=" in line.split(":", 1)[1]:
                name, rest = line.split(":", 1)
                if not name.strip().replace("_", "").isalnum():
                    continue
                try:
                    val = float(rest.split("=")[-1].split()[0])
                    results[name.strip()] = val
                except (IndexError, ValueError):
                    pass
    return results


if __name__ == "__main__":
    vin = float(sys.argv[1])
    vout_t = float(sys.argv[2])
    pout = float(sys.argv[3])
    d = float(sys.argv[4])
    fsw = float(sys.argv[5])
    l_h = float(sys.argv[6])
    dcr = float(sys.argv[7])
    switch_tech = sys.argv[8]
    diode_tech = sys.argv[9]
    out = sys.argv[10] if len(sys.argv) > 10 else "point2.asc"
    r = run(vin, vout_t, pout, d, fsw, l_h, dcr, switch_tech, diode_tech, out)
    for k, v in r.items():
        print(f"{k} = {v:.6g}")
