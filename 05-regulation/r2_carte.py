"""R2 -- carte de stabilite du P pur sur un echelon de charge 5 -> 10 W.

Demande du concepteur (2026-11-22) :
    Cout = 10 uF, Vin = 20 V, Vout = 80 V, echelon 5 W -> 10 W.
    x : Kp     y : facteur d'amortissement ou d'amplification
    z : frequence d'oscillation
    classes : stable (aperiodique) / amorti / entretenu / divergent

LES DEUX POINTS SONT EN DCM. Frontiere 15,3 W a 20 V avec 47 uH : 5 et
10 W sont dessous. Le plant moyen y est du PREMIER ordre, sans zero RHP
-- un P n'y oscille pas par le plant moyen. S'il oscille, ce sera par ce
que la moyenne ignore : l'echantillonnage du modulateur (sous-harmonique
a fsw/2 = 100 kHz) ou l'entree en CCM. D'ou une lecture en DEUX temps :
la moyenne par periode (basse frequence) ET le rapport cyclique cycle a
cycle (alternance pair/impair, que la moyenne glissante efface).

Ce fichier ne contient pour l'instant que le TEST A BLANC : un cas,
chronometre, lu, controle contre un attendu. La carte sera lancee apres
discussion du cout.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parent
for q in (str(RAC / "04-emi/etapes"),
          str(RAC.parent / ".claude/skills/sim-spice/scripts"),
          str(RAC.parent / ".claude/skills/sim-commun")):
    sys.path.insert(0, q)
import etape                                                 # noqa: E402
import ltspice_run                                           # noqa: E402
from simcommun.lecture import lire                           # noqa: E402

FSW, VIN, VREF, COUT, L = 200e3, 20.0, 80.0, 10e-6, 47e-6
P1, P2 = 5.0, 10.0
MOS = False          # interrupteur IDEAL : voir le test a blanc du 2026-11-22
R1 = VREF ** 2 / P1                 # 1280 ohms
R2 = 1.0 / (1.0 / (VREF ** 2 / P2) - 1.0 / R1)   # ajout en parallele : 1280


def dcm(p):
    """Formule fermee DCM, charge R : rapport cyclique et gain dVout/dD."""
    r = VREF ** 2 / p
    k = 2 * L * FSW / r
    d = math.sqrt((VREF / VIN) * (VREF / VIN - 1) * k)
    m = VREF / VIN
    g = VIN * 2 * m * (m - 1) / (d * (2 * m - 1))
    tau = r * COUT * (m - 1) / (2 * m - 1)        # pole unique du plant
    return d, g, tau


def prepare(tag, kp, n_avant, n_apres):
    t_step = n_avant / FSW
    n = etape.etape0(p=P1, vin=VIN, charge=True, rl=R1, cout=COUT,
                     ser=True, v8pa22=True, mos=MOS, n_etab=0,
                     n_mes=n_avant + n_apres, dtmax=200e-9, kp=kp,
                     vref=VREF, echelon=(R2, t_step), sobre=True)
    f = ICI / f"{tag}.cir"
    f.write_text(n, encoding="utf-8")
    return f, t_step


def lecture(f, t_step):
    """Moyenne par periode (grille uniforme) et rapport cyclique par cycle."""
    r = lire(str(Path(f).with_suffix(".raw")))
    t = np.asarray(r.x)
    np_ = 256
    n = int(round((t[-1] - t[0]) * FSW)) * np_
    tu = np.linspace(t[0], t[-1], n, endpoint=False)
    vu = np.interp(tu, t, np.asarray(r.trace("V(nout)")).real)
    du = np.interp(tu, t, np.asarray(r.trace("V(nctrl)")).real)
    iu = np.interp(tu, t, np.asarray(r.trace("I(L1)")).real)
    # une valeur PAR PERIODE (blocs disjoints) : la moyenne et le min de
    # courant -- le second dit si le DCM tient
    nb = len(tu) // np_
    vb = vu[:nb * np_].reshape(nb, np_).mean(1)
    db = du[:nb * np_].reshape(nb, np_).mean(1)
    imin = iu[:nb * np_].reshape(nb, np_).min(1)
    tb = (np.arange(nb) + 0.5) / FSW + t[0]
    return tb, vb, db, imin, len(t)


def blanc(kp=0.01, n_avant=200, n_apres=600) -> int:
    d1, g1, tau1 = dcm(P1)
    d2, g2, tau2 = dcm(P2)
    print("  TEST A BLANC -- carte de stabilite R2, echelon 5 -> 10 W\n")
    print(f"  Formule fermee DCM, Vin {VIN:.0f} V, L {L*1e6:.0f} uH, "
          f"Cout {COUT*1e6:.0f} uF :")
    print(f"     5 W  R {R1:6.0f} ohms  D {d1:.4f}  G {g1:6.1f} V  "
          f"tau plant {tau1*1e3:.2f} ms")
    print(f"     10 W R {VREF**2/P2:6.0f} ohms  D {d2:.4f}  G {g2:6.1f} V  "
          f"tau plant {tau2*1e3:.2f} ms")
    v_stat = VREF - (d2 - d1) / kp          # P seul : ecart statique (lineaire)
    print(f"\n  Kp {kp}   Kp.G {kp*g1:.2f} -> {kp*g2:.2f}")
    print(f"     erreur statique attendue apres echelon ~ (D2-D1)/Kp = "
          f"{(d2-d1)/kp:.1f} V, a corriger du gain fini -> Vout ~ "
          f"{VREF - (d2-d1)/kp/(1+1/(kp*g2)) if kp*g2 > 0 else v_stat:.1f} V")
    print(f"     constante de temps boucle fermee ~ tau/(1+Kp.G) = "
          f"{tau2/(1+kp*g2)*1e3:.2f} ms")
    f, t_step = prepare("c_blanc", kp, n_avant, n_apres)
    print(f"\n  fenetre : {n_avant} periodes avant l'echelon, {n_apres} apres "
          f"({(n_avant+n_apres)/FSW*1e3:.1f} ms simules)")
    t0 = time.monotonic()
    r = ltspice_run.lance(f)
    ts = time.monotonic() - t0
    print(f"  lance() : {'OK' if r['ok'] else 'REFUS'} en {ts:.1f} s -- "
          f"{r['diagnostic'][:120]}")
    if not r["ok"]:
        return 1
    raw = f.with_suffix(".raw")
    t0 = time.monotonic()
    tb, vb, db, imin, npts = lecture(f, t_step)
    tl = time.monotonic() - t0
    print(f"  .raw {raw.stat().st_size/1e6:.1f} Mo, {npts} points, "
          f"lu en {tl:.1f} s")
    print(f"  cout : {ts/(n_avant+n_apres)*1e3:.1f} ms de simulation par "
          f"periode, {tl/(n_avant+n_apres)*1e3:.1f} ms de lecture\n")
    av = (tb > 0.5 * t_step) & (tb < t_step)
    ap = tb > t_step + 0.7 * (tb[-1] - t_step)
    print(f"  avant echelon : Vout {vb[av].mean():7.2f} V   D {db[av].mean():.4f}"
          f"   I min/periode {imin[av].max():+.3f} A (DCM si ~0)")
    print(f"  fin           : Vout {vb[ap].mean():7.2f} V   D {db[ap].mean():.4f}"
          f"   I min/periode {imin[ap].max():+.3f} A")
    # alternance cycle a cycle : signature d'une sous-harmonique fsw/2
    alt = np.abs(np.diff(db[ap]))
    print(f"  alternance du rapport cyclique cycle a cycle : max {alt.max():.4f}")
    print("\n  Trace par periode autour de l'echelon (1 ligne / 20 periodes) :")
    k0 = int(np.searchsorted(tb, t_step)) - 40
    for k in range(max(k0, 0), len(tb), 20):
        print(f"     {tb[k]*1e3:6.3f} ms  Vout {vb[k]:7.2f}  D {db[k]:.4f}"
              f"  Imin {imin[k]:+.3f}")
    return 0


# =====================================================================
# LA CARTE
# =====================================================================
KPS = np.logspace(-3, 1, 17)          # 4 points par decade, 0,001 a 10
N_AVANT = 200


def fenetre(kp):
    """Periodes apres l'echelon : 6 constantes de temps boucle fermee
    (plant DCM premier ordre, tau/(1+Kp.G) a 10 W), 300 au minimum pour
    qu'une oscillation rapide ait de quoi se lire."""
    _, g2, tau2 = dcm(P2)
    return int(max(6 * tau2 / (1 + kp * g2) * FSW, 300))


def extrait(f, t_step):
    """Une ligne par PERIODE (blocs disjoints sur grille uniforme), sauvee
    en .npz : c'est tout ce que l'analyse lit. Le .raw peut ensuite partir."""
    tb, vb, db, imin, npts = lecture(f, t_step)
    np.savez(Path(f).with_suffix(".npz"), tb=tb, vb=vb, db=db, imin=imin,
             t_step=t_step, npts=npts)


def carte() -> int:
    cirs, tsteps = [], {}
    for i, kp in enumerate(KPS):
        f, ts = prepare(f"c{i:02d}", float(kp), N_AVANT, fenetre(kp))
        cirs.append(f)
        tsteps[f.stem] = ts
    i0 = int(np.argmin(np.abs(KPS - 0.01)))       # temoin = le test a blanc
    print(f"  CARTE R2 : {len(cirs)} cas, Kp de {KPS[0]} a {KPS[-1]}, "
          f"temoin c{i0:02d} (Kp {KPS[i0]:.4f})\n")
    t0 = time.monotonic()
    # attendu du temoin, lu sur le test a blanc : Vout part de ~80 V et
    # s'etablit vers ~71 V. Crete et creux, pas la moyenne -- c'est un
    # banc transitoire (et une moyenne d'echantillons est ponderee par
    # les pas, RETEX R).
    r = ltspice_run.campagne(cirs, temoin=i0, budget_s=1200.0,
                             attendu={"max:V(nout)": (78.0, 90.0),
                                      "min:V(nout)": (55.0, 78.0)})
    print(f"  campagne() : {'OK' if r['ok'] else 'REFUS'} en "
          f"{time.monotonic()-t0:.0f} s")
    print(f"     {r['diagnostic']}\n")
    for f in cirs:
        res = r["resultats"].get(f.stem)
        if res is None:
            print(f"     {f.stem} : non lance")
            continue
        if not res["ok"]:
            print(f"     {f.stem} : ECHEC -- {res['diagnostic'][:100]}")
            continue
        extrait(f, tsteps[f.stem])
        f.with_suffix(".raw").unlink()       # .npz ecrit : le .raw part
        print(f"     {f.stem} : extrait")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "carte":
        raise SystemExit(carte())
    raise SystemExit(blanc())
