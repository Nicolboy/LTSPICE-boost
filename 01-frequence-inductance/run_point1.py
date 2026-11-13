"""Genere un point de fonctionnement etage1 (boost), le lance dans
LTspice (mode batch), affiche les resultats .meas. Usage :
    python run_point1.py <Vin> <Vout_cible> <Pout> <D> <fsw_Hz> <L_H> <DCR_Ohm> [out.asc]
"""
import subprocess
import sys

sys.path.insert(0, ".")
from gen_boost1 import build

LTSPICE = r"C:/Program Files/ADI/LTspice/LTspice.exe"


def run(vin, vout_target, pout, d, fsw, l_henries, dcr_ohm, out="point.asc",
        settle_periods=4000, measure_periods=100, rload=None):
    period = 1 / fsw
    build("point", vin, vout_target, pout, d, period, out,
          l_henries=l_henries, dcr_ohm=dcr_ohm, rload=rload,
          settle_periods=settle_periods, measure_periods=measure_periods)
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
    out = sys.argv[8] if len(sys.argv) > 8 else "point.asc"
    r = run(vin, vout_t, pout, d, fsw, l_h, dcr, out)
    for k, v in r.items():
        print(f"{k} = {v:.6g}")
