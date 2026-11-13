"""Trouve par bissection le duty cycle donnant Vout_cible a
Vin/Pout/fsw/L/DCR fixes (Vout(D) suppose monotone croissant pour un
boost). Robuste que le point tombe en CCM ou en DCM : on bissecte sur
le Vout SIMULE, jamais sur la formule ideale D=1-Vin/Vout (qui ne vaut
que pour le CCM)."""
import sys

sys.path.insert(0, ".")
from run_point1 import run


def find_duty(vin, vout_target, pout, fsw, l_henries, dcr_ohm,
              d_lo=0.1, d_hi=0.95, tol=0.01, max_iter=14,
              settle_periods=2000, tmp_out=None):
    r = None
    if tmp_out is None:
        tmp_out = f"_find_tmp_{int(fsw)}.asc"
    for i in range(max_iter):
        d = (d_lo + d_hi) / 2
        r = run(vin, vout_target, pout, d, fsw, l_henries, dcr_ohm,
                out=tmp_out, settle_periods=settle_periods)
        vout = r.get("vout_avg")
        if vout is None:
            print(f"  iter {i}: D={d:.4f} -> ECHEC")
            d_hi = d
            continue
        print(f"  iter {i}: D={d:.4f} -> Vout={vout:.4f}V (cible {vout_target}V)")
        if abs(vout - vout_target) / vout_target < tol:
            return d, r
        if vout < vout_target:
            d_lo = d
        else:
            d_hi = d
    return d, r


if __name__ == "__main__":
    vin = float(sys.argv[1])
    vout_t = float(sys.argv[2])
    pout = float(sys.argv[3])
    fsw = float(sys.argv[4])
    l_h = float(sys.argv[5])
    dcr = float(sys.argv[6])
    d, r = find_duty(vin, vout_t, pout, fsw, l_h, dcr)
    print(f"FINAL: D={d:.4f} Vout={r.get('vout_avg'):.4f}V "
          f"Pout={r.get('pout_avg'):.4f}W "
          f"eta={100*r.get('pout_avg')/r.get('pin_avg'):.1f}%")
