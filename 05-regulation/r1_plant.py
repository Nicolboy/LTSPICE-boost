"""R1 — mesurer le plant, rapport cyclique vers tension de sortie.

On ne l'ecrit pas, on le MESURE. C'est l'equivalent de l'etape 0 sur les
composants : valider ce que le banc rend avant toute question de
correcteur. Si la mesure ne retrouve pas le zero RHP et le pole que la
formule fermee annonce, rien de ce qui suit n'a de sens.

    f_RHP  = R.(1-D)^2 / (2.pi.L)          33,9 kHz a 40 W
    f_pole = (1-D) / (2.pi.sqrt(L.Cout))   3,91 kHz avec Cout = 2,2 uF

METHODE : INJECTION MULTI-TONS, et non un balayage frequence par
frequence. L'etablissement coute 600 periodes ; le payer dix fois serait
absurde. On s'etablit une fois, on injecte tous les tons ensemble, et une
seule transformee les separe.

TROIS CONTRAINTES, et chacune vient d'une faute possible.

  1. Chaque ton doit tenir un nombre ENTIER de periodes dans la fenetre,
     sinon il fuit dans ses voisins. On prend donc f = f_sw / k avec k
     divisant la longueur de fenetre.

  2. La fenetre doit faire un nombre entier de periodes de DECOUPAGE,
     sinon l'ondulation de commutation fuit dans les raies de mesure.
     C'est automatique si on compte la fenetre en periodes.

  3. L'amplitude doit rester petite -- c'est une mesure PETIT SIGNAL --
     mais assez grande pour sortir de l'ondulation. On le verifie en
     doublant l'amplitude : si le plant mesure bouge, on n'est plus dans
     le lineaire.

ET LE MODULATEUR SE CALIBRE. La dent de scie ne monte pas sur exactement
une periode (LTspice refuse un front de descente nul), donc le rapport
cyclique produit n'est pas la tension de commande. Mesure : 0,999 de
rapport, soit -0,24 V sur Vout. On ne compense pas par un facteur suppose,
on releve la courbe reelle.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parent
ET = RAC / "04-emi/etapes"
for q in (str(ET), str(RAC.parent / ".claude/skills/sim-commun")):
    sys.path.insert(0, q)
import etape                                                 # noqa: E402
from simcommun.lecture import lire                           # noqa: E402

EXE = r"C:\Program Files\ADI\LTspice\LTspice.exe"
FSW, VIN, VOUT, L = 200e3, 20.0, 80.0, 47e-6
RL, COUT, DUTY = 160.0, 2.2e-6, 0.750929
M = 1600                      # longueur de fenetre, en periodes
KS = (1600, 800, 400, 200, 100, 50, 25, 16, 8, 4)


def lance(tag: str, pwm: str, n_etab: int, n_mes: int, dt: float = 20e-9):
    n = etape.etape0(p=40.0, vin=VIN, charge=True, rl=RL, cout=COUT,
                     ser=True, v8pa22=True, mos="ipd530", n_etab=n_etab,
                     n_mes=n_mes, dtmax=dt, duty=DUTY, pwm=pwm)
    n = n.replace(".options plotwinsize=0",
                  ".options plotwinsize=0" + chr(10) + ".options cshunt=1e-15")
    # on remplace les deux lignes `.save` par la seule paire utile
    n = re.sub(r"(?m)^\.save .*$", "", n).replace(chr(10)*3, chr(10)*2)
    n = n.replace(".end", ".save V(nout) V(nctrl) V(ng)" + chr(10) + ".end")
    f = ICI / f"{tag}.cir"
    f.write_text(n, encoding="utf-8")
    t0 = time.monotonic()
    subprocess.run([EXE, "-b", str(f)], capture_output=True, timeout=7200)
    return f.with_suffix(".raw"), time.monotonic() - t0


def duty_reel(raw) -> float:
    """Rapport cyclique REELLEMENT produit, lu sur la grille."""
    r = lire(str(raw))
    t = np.asarray(r.x)
    vg = np.asarray(r.trace("V(ng)")).real
    return float(np.trapezoid((vg > 5.0).astype(float), t) / (t[-1] - t[0]))


def calibre() -> tuple[float, float]:
    """Pente et decalage de commande -> rapport cyclique, MESURES."""
    print("  CALIBRATION DU MODULATEUR -- on releve, on ne suppose pas\n")
    print(f"    {'V commande':>12s} {'duty mesure':>13s}")
    print("    " + "-" * 28)
    pts = []
    for vc in (0.70, 0.75, 0.80):
        raw, _ = lance(f"cal{int(vc*100)}", f"DC {vc:.6f}", 20, 8)
        d = duty_reel(raw)
        pts.append((vc, d))
        print(f"    {vc:10.4f} V {d:12.6f}")
        for e in ("cir", "raw", "log", "op.raw"):
            (ICI / f"cal{int(vc*100)}.{e}").unlink(missing_ok=True)
    a, b = np.polyfit([p[0] for p in pts], [p[1] for p in pts], 1)
    print(f"\n    duty = {a:.6f} x Vcmd {b:+.6f}")
    print(f"    -> pour duty = {DUTY:.6f}, commander "
          f"{(DUTY - b) / a:.6f} V\n")
    return float(a), float(b)


def main() -> int:
    a, b = calibre()
    vc0 = (DUTY - b) / a
    freqs = np.array([FSW / k for k in KS])

    print("  INJECTION MULTI-TONS\n")
    print(f"    fenetre {M} periodes = {M/FSW*1e3:.1f} ms")
    print(f"    tons    {len(KS)} de {freqs.min():.0f} a {freqs.max()/1e3:.0f} kHz")
    amp = 0.004                      # 0,4 % de rapport cyclique par ton
    print(f"    amplitude {amp:.4f} V par ton, soit {100*amp*a/DUTY:.2f} % "
          f"de rapport cyclique\n")
    src = f"DC {vc0:.6f}" + "".join(
        f" SIN(0 {amp:.6f} {f:.6f} 0 0 0)" if i == 0 else ""
        for i, f in enumerate(freqs))
    # LTspice n'empile pas plusieurs SIN sur une source : on ecrit la
    # somme dans une source COMPORTEMENTALE.
    somme = " + ".join(f"{amp:.6f}*sin(2*pi*{f:.4f}*time)" for f in freqs)
    src = f"V = {vc0:.6f} + {somme}"
    raw, dur = lance("r1", src, 600, M)
    print(f"    simulation {dur:.0f} s")
    r = lire(str(raw))
    t = np.asarray(r.x)
    vo = np.asarray(r.trace("V(nout)")).real
    vc = np.asarray(r.trace("V(nctrl)")).real
    # fenetre = un nombre ENTIER de periodes de decoupage, calee sur la fin
    t1 = t[-1]
    t0 = t1 - M / FSW
    m = t >= t0
    tt, vv, cc = t[m] - t0, vo[m], vc[m]
    print(f"    fenetre retenue {(tt[-1]-tt[0])*1e3:.3f} ms, {m.sum()} points\n")

    # LOCK-IN sur chaque ton : correlation avec sin et cos.
    print(f"  {'f':>9s} {'|G|':>10s} {'dB':>8s} {'phase':>9s} "
          f"{'formule fermee':>18s}")
    print("  " + "-" * 60)
    frhp = RL * (1 - DUTY) ** 2 / (2 * np.pi * L)
    fpol = (1 - DUTY) / (2 * np.pi * np.sqrt(L * COUT))
    res = []
    for f in freqs:
        w = 2 * np.pi * f
        n_ = np.trapezoid(np.ones_like(tt), tt)
        cs = 2 * np.trapezoid(vv * np.cos(w * tt), tt) / n_
        sn = 2 * np.trapezoid(vv * np.sin(w * tt), tt) / n_
        cc_ = 2 * np.trapezoid(cc * np.cos(w * tt), tt) / n_
        ss_ = 2 * np.trapezoid(cc * np.sin(w * tt), tt) / n_
        num, den = complex(cs, sn), complex(cc_, ss_)
        g = num / den if abs(den) > 1e-12 else complex(np.nan)
        rep = ""
        if abs(f - fpol) / fpol < .35:
            rep = f"<- pole {fpol/1e3:.2f} kHz"
        if abs(f - frhp) / frhp < .35:
            rep = f"<- zero RHP {frhp/1e3:.1f} kHz"
        res.append((f, abs(g), np.degrees(np.angle(g))))
        print(f"  {f:8.0f} {abs(g):9.2f} {20*np.log10(max(abs(g),1e-9)):7.1f} "
              f"{np.degrees(np.angle(g)):8.1f} deg {rep:>18s}")
    np.savetxt(ICI / "r1_plant.csv", np.array(res), delimiter=",",
               header="f_Hz,gain,phase_deg", comments="")
    print(f"\n  attendu : pole {fpol/1e3:.2f} kHz, zero RHP {frhp/1e3:.1f} kHz")
    print(f"  gain continu theorique Vout/(1-D) = {VOUT/(1-DUTY):.0f} "
          f"(soit {20*np.log10(VOUT/(1-DUTY)):.1f} dB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
