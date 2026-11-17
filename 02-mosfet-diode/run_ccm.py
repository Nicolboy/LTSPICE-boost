"""Lance l'architecture 2 : pour chaque courant vise, affine le rapport
cyclique jusqu'a annuler la derive, puis sort le bilan par elements.

POURQUOI UNE ITERATION SUR LE RAPPORT CYCLIQUE
----------------------------------------------
Les deux tensions etant imposees, dI/dD vaut environ 860 A par unite de
rapport cyclique : une erreur de 1e-3 sur D fait deriver le courant de
plusieurs A/ms. Tant qu'il derive, l'inductance stocke ou restitue
0,5*L*d(i^2)/dt, terme qui se confond avec une perte dans Pin-Pout -- il
pesait 0,83 W sur 2,42 W au premier essai. On le mesure et on le soustrait,
ET on corrige D pour le rendre negligeable :

    d(di/dt)/dD = Vout/L   =>   dD = -(di/dt) * L / Vout

Un pas de Newton suffit en general, deux par securite.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import gen_ccm_ltspice as g
from gen_dcm_ltspice import lit_log

ICI = Path(__file__).resolve().parent
TRAVAIL = ICI / "results" / "ccm"
LTSPICE = Path(r"C:/Program Files/ADI/LTspice/LTspice.exe")

POSTES = [("MOSFET", "pmos"), ("diode", "pdio"), ("cuivre L", "pcu"),
          ("grille Rg ext", "prge")]


def lance(nom: str, texte: str) -> dict:
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    cir = TRAVAIL / f"{nom}.cir"
    cir.write_text(texte, encoding="ascii")
    log, raw = cir.with_suffix(".log"), cir.with_suffix(".raw")
    for f in (log, raw):
        if f.exists():
            f.unlink()
    subprocess.run([str(LTSPICE), "-b", str(cir)], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=False)
    if not log.exists():
        raise RuntimeError(f"{nom} : pas de log")
    txt = log.read_text(errors="replace")
    for m in ("Simulation Failed", "Iteration limit reached",
              "Time step too small", "Fatal Error", "Voltage not found"):
        if m in txt:
            raise RuntimeError(f"{nom} : {next(l.strip() for l in txt.splitlines() if m in l)}")
    return lit_log(log)[0]


def fenetre(r: dict) -> float:
    return g.N_MES / g.FSW


def stockage(r: dict) -> float:
    """Puissance absorbee par l'inductance du fait de la derive du courant."""
    return 0.5 * g.L_H * (r["il1"] ** 2 - r["il0"] ** 2) / fenetre(r)


def point(i_l: float, temp: float, n_iter: int = 2) -> dict:
    d = g.duty_ccm(i_l)
    r = {}
    for k in range(n_iter + 1):
        r = lance(f"ccm_{temp:.0f}_{i_l:.3f}", g.netlist((d,), i_l, temp=temp))
        didt = (r["il1"] - r["il0"]) / fenetre(r)
        r["duty"], r["didt"] = d, didt
        if k == n_iter:
            break
        d -= didt * g.L_H / g.VOUT
    return r


def bilan(r: dict, titre: str) -> None:
    stock = stockage(r)
    pertes = r["pin"] - r["pout"] - stock
    total = sum(r[k] for _, k in POSTES)
    print(f"\n{titre}")
    print(f"  IL {r['il']:.3f} A ({r['imin']:.2f}-{r['ipk']:.2f})"
          f"   Vpk {r['vpk']:.1f} V   derive {r['didt']:+.0f} A/s")
    print(f"  Pin {r['pin']:.3f} W   Pout {r['pout']:.3f} W"
          f"   stockage L {stock*1e3:+.0f} mW")
    print(f"  rendement {100*r['pout']/(r['pin']-stock):.2f} %")
    for nom, k in POSTES:
        print(f"    {nom:<16}{r[k]*1e3:>8.1f} mW")
    print(f"    {'-'*24}")
    print(f"    {'total mesure':<16}{total*1e3:>8.1f} mW")
    print(f"    {'bouclage':<16}{(pertes-total)*1e3:>8.1f} mW"
          f"   ({100*(pertes-total)/pertes:+.1f} % des pertes)")


def main() -> int:
    for i_l in (2.632, 1.0):
        try:
            r = point(i_l, 25.0)
        except RuntimeError as exc:
            print(f"  !! {i_l} A : {exc}")
            continue
        bilan(r, f"ARCHI 2 -- CCM 400 kHz, 25 degC, consigne {i_l:.2f} A"
                 f" -> {r['pout']:.2f} W")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
