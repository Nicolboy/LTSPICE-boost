"""Chapitre 2 -- trouve par bissection le duty cycle donnant Vout_cible,
memes principes que find_duty1.py (chapitre 1), mais via run_point2 (qui
ajoute switch_tech/diode_tech). Robuste CCM/DCM : bissecte sur le Vout
SIMULE, jamais sur la formule ideale D=1-Vin/Vout.

Recherche en DEUX temps pour rester praticable malgre le dtmax resserre
du chapitre 2 (1ns, necessaire pour resoudre l'anneau LC/le recouvrement
diode -- voir gen_boost2_tech.py) : la bissection elle-meme tourne avec
un dtmax GROSSIER et une fenetre de reglage COURTE (Vout approximatif
suffit pour converger en direction -- la bissection s'auto-corrige meme
avec une mesure bruitee), puis UNE seule simulation finale, precise
(dtmax fin, fenetre de reglage complete), est relancee au D retenu --
c'est cette derniere qui fournit les mesures de commutation/overshoot
reellement exploitees en aval."""
import sys

sys.path.insert(0, ".")
from run_point2 import run

SEARCH_DTMAX_S = 10e-9
SEARCH_SETTLE_PERIODS = 150


def find_duty(vin, vout_target, pout, fsw, l_henries, dcr_ohm, switch_tech,
              diode_tech, d_lo=0.1, d_hi=0.95, tol=0.01, max_iter=14,
              settle_periods=None, tmp_out=None):
    r = None
    d = (d_lo + d_hi) / 2
    if tmp_out is None:
        tmp_out = f"_find_tmp2_{int(fsw)}_{switch_tech}_{diode_tech}.asc"
    for i in range(max_iter):
        d = (d_lo + d_hi) / 2
        r = run(vin, vout_target, pout, d, fsw, l_henries, dcr_ohm,
                switch_tech, diode_tech, out=tmp_out,
                settle_periods=SEARCH_SETTLE_PERIODS,
                dtmax_s=SEARCH_DTMAX_S)
        vout = r.get("vout_avg")
        if vout is None:
            print(f"  iter {i}: D={d:.4f} -> ECHEC (recherche)")
            d_hi = d
            continue
        print(f"  iter {i}: D={d:.4f} -> Vout={vout:.4f}V (cible {vout_target}V, recherche grossiere)")
        if abs(vout - vout_target) / vout_target < tol:
            break
        if vout < vout_target:
            d_lo = d
        else:
            d_hi = d

    # Point final, precis (dtmax fin + fenetre de reglage complete,
    # valeurs par defaut de build()) -- c'est CE resultat qui est retenu,
    # pas celui de la derniere iteration grossiere ci-dessus.
    r_final = run(vin, vout_target, pout, d, fsw, l_henries, dcr_ohm,
                  switch_tech, diode_tech, out=tmp_out,
                  settle_periods=settle_periods)
    vout_final = r_final.get("vout_avg")
    if vout_final is not None:
        print(f"  FINAL (precis) : D={d:.4f} -> Vout={vout_final:.4f}V "
              f"(cible {vout_target}V)")
        return d, r_final
    print("  FINAL (precis) : ECHEC -- on retombe sur le dernier resultat "
          "de recherche (grossier, moins fiable)")
    return d, r


if __name__ == "__main__":
    vin = float(sys.argv[1])
    vout_t = float(sys.argv[2])
    pout = float(sys.argv[3])
    fsw = float(sys.argv[4])
    l_h = float(sys.argv[5])
    dcr = float(sys.argv[6])
    switch_tech = sys.argv[7]
    diode_tech = sys.argv[8]
    d, r = find_duty(vin, vout_t, pout, fsw, l_h, dcr, switch_tech, diode_tech)
    print(f"FINAL: D={d:.4f} Vout={r.get('vout_avg'):.4f}V "
          f"Pout={r.get('pout_avg'):.4f}W "
          f"eta={100*r.get('pout_avg')/r.get('pin_avg'):.1f}%")
