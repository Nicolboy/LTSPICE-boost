"""R2 -- recoupement des limites du P par une AUTRE methode (gendarme).

Methode : identifier le plant ECHANTILLONNE en boucle ouverte, puis
calculer la limite de stabilite de la boucle P + retard sans simulation.

1. Boucle ouverte au point d'APRES l'echelon de la k-section :
     CCM 30 W (213,3 ohms)   DCM 10 W (640 ohms)
   meme banc (FDD770, Wurth 10 uF + MLCC, mesure filtree 1 us puis
   echantillonnee a 0,998 T), D FIXE relu dans le regime etabli des
   k-sections, .ic I(L1) force (force_ic).
2. DEUX cas identiques par mode : avec un petit echelon de D a la periode
   n0, et sans. La DIFFERENCE des echantillons, divisee par dD, est la
   reponse indicielle par unite de D : elle elimine la derive lente du
   point de fonctionnement et la part deterministe de l'ondulation.
   h[j] = difference premiere : reponse impulsionnelle echantillonnee,
   h[0] compris (effet dans la MEME periode, via ESR et filtre).
3. Boucle fermee du banc : d[n] = D0 - Kp.(s[n-2] - Vref) -- la periode n
   utilise l'echantillon de fin de periode n-2 (retard d'une periode).
   Equation caracteristique : 1 + Kp.z^-2.H(z) = 0. On cherche theta ou
   arg(e^-2j.theta . H(e^j.theta)) = -pi ; alors Kp_lim = 1/|H| et
   f = theta.fsw/(2.pi).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import r2_ziegler as z                                       # noqa: E402
import r2_ziegler_dcm as d                                   # noqa: E402
import etape                                                 # noqa: E402
import ltspice_run                                           # noqa: E402
sys.path.insert(0, str(ICI.parent.parent / ".claude/skills/sim-commun"))
from simcommun.lecture import lire                           # noqa: E402

FSW, T = z.FSW, 1.0 / z.FSW
N0 = 200            # periode de l'echelon de D
N_APRES = 2000      # 10 ms : CCM amorti, DCM ~3 tau (queue extrapolee)


def d_etabli(glob, kp_vise):
    """D moyen du regime etabli apres l'echelon, dans la k-section."""
    best = None
    for f in ICI.glob(glob):
        cir = f.with_suffix(".cir").read_text(encoding="utf-8")
        kp = float(cir.split("Bctrl")[1].split("+ ")[1].split("*")[0])
        if best is None or abs(np.log(kp / kp_vise)) < abs(np.log(best[0] / kp_vise)):
            D = np.load(f)
            best = (kp, float(D["db"][-200:].mean()), f.name)
    return best


MODES = {
    # mode : p (pour .ic), charge, D0 (relu), dD
    "ccm": dict(p=30.0, rl=z.VREF ** 2 / 30.0, src=("zkc[0-9]_*.npz", 0.01),
                dd=0.001),
    "dcm": dict(p=10.0, rl=z.VREF ** 2 / 10.0, src=("zr[0-9]_*.npz", 1.0),
                dd=0.005),
}


def prepare(mode, echelon_d, n_mes):
    m = MODES[mode]
    kp, d0, src = d_etabli(*m["src"])
    m["d0"], m["d0_src"] = d0, f"{src} (Kp {kp:.4g})"
    t1 = (N0 + 0.05) * T
    dd = m["dd"] if echelon_d else 0.0
    pwm = f"V={d0:.6f} + {dd:.6f}*(time > {t1:.6e})"
    n = etape.etape0(p=m["p"], vin=z.VIN, charge=True, rl=m["rl"], cout=z.COUT,
                     ser=True, v8pa22=True, mos=z.MOS, n_etab=0, n_mes=n_mes,
                     dtmax=200e-9, duty=d0, pwm=pwm, vref=z.VREF, sobre=True,
                     cout_we=z.COUT_WE, tau_mes=z.TAU_MES, echant=z.ECHANT,
                     cout_hf=True, force_ic=True)
    f = ICI / f"zi_{mode}_{'ech' if echelon_d else 'ref'}.cir"
    f.write_text(n, encoding="utf-8")
    return f


def echantillons(f, n_tot):
    """s[n] = valeur figee a la fin de la periode n (lue au debut de n+1)."""
    x = lire(str(f.with_suffix(".raw")))
    t = np.asarray(x.x)
    sh = np.asarray(x.trace("V(nsh)")).real
    tk = (np.arange(n_tot - 1) + 1 + 0.5) * T      # milieu de la periode n+1
    return np.interp(tk, t, sh)                    # indice n = periode n


def limite(h, a_queue):
    """Kp limite et frequence pour 1 + Kp z^-2 H(z) = 0."""
    th = np.linspace(1e-4, np.pi, 200001)
    n = np.arange(len(h))
    # H(e^jth) = sum h[n] e^-jth n  + queue geometrique h[-1].a^k (k>=1)
    H = np.array([np.sum(h * np.exp(-1j * t * n)) for t in th[::200]])
    thc = th[::200]
    if a_queue is not None and 0 < a_queue < 1:
        q = h[-1] * a_queue * np.exp(-1j * thc * len(h)) / (
            1 - a_queue * np.exp(-1j * thc))
        H = H + q
    L = np.exp(-2j * thc) * H
    ph = np.unwrap(np.angle(L))
    # premier passage a -pi (ou -3pi...) : phase la plus proche d'un -pi impair
    k = np.where(np.diff(np.sign(np.sin(ph))) != 0)[0]
    out = []
    for i in k:
        if np.cos(ph[i]) < 0:                       # passage a -pi (mod 2pi)
            out.append((1.0 / abs(L[i]), thc[i] / (2 * np.pi) * FSW))
    return out, thc, L


def blanc() -> int:
    print("  TEST A BLANC identification -- 30 us par mode, boucle ouverte")
    fs = [prepare(m, True, 6) for m in MODES]
    t0 = time.monotonic()
    res = ltspice_run.lance_lot(fs, procs=2)
    print(f"     {time.monotonic()-t0:.0f} s")
    for mode, f in zip(MODES, fs):
        r = res[f.stem]
        print(f"     {mode} : {'OK' if r['ok'] else 'ECHEC'}  D0 {MODES[mode]['d0']:.4f}"
              f" (relu dans {MODES[mode]['d0_src']})  {r['diagnostic'][:80]}")
        if r["ok"]:
            x = lire(str(f.with_suffix(".raw")))
            print(f"        signaux : {sorted(x.traces)}")
            print(f"        V(nsh) fin {np.asarray(x.trace('V(nsh)')).real[-1]:.3f}"
                  f"  I(L1) max {np.asarray(x.trace('I(L1)')).real.max():.2f} A")
            f.with_suffix(".raw").unlink()
    return 0 if all(res[f.stem]["ok"] for f in fs) else 1


def main() -> int:
    n_tot = N0 + N_APRES
    fs = []
    for mode in MODES:
        fs += [prepare(mode, False, n_tot), prepare(mode, True, n_tot)]
    t0 = time.monotonic()
    res = ltspice_run.lance_lot(fs, procs=4)
    print(f"  4 cas boucle ouverte ({n_tot} periodes) : {time.monotonic()-t0:.0f} s\n")
    for f in fs:
        if not res[f.stem]["ok"]:
            print(f"  {f.stem} ECHEC {res[f.stem]['diagnostic'][:90]}")
            return 1
    ref = {"ccm": (0.0207, 4.85e3), "dcm": (1.345, 30.6e3)}
    out = {}
    for mode in MODES:
        s0 = echantillons(ICI / f"zi_{mode}_ref.cir", n_tot)
        s1 = echantillons(ICI / f"zi_{mode}_ech.cir", n_tot)
        y = (s1 - s0) / MODES[mode]["dd"]            # reponse indicielle /dD
        y = y[N0:]                                   # j = 0 : periode de l'echelon
        h = np.diff(np.concatenate(([0.0], y)))      # impulsionnelle
        # queue : rapport geometrique moyen des 200 derniers echantillons
        hq = h[-400:]
        a_q = None
        if np.all(np.abs(hq) > 0) and np.all(np.sign(hq) == np.sign(hq[0])):
            a_q = float(np.exp(np.polyfit(np.arange(len(hq)),
                                          np.log(np.abs(hq)), 1)[0]))
        lims, th, L = limite(h, a_q)
        print(f"  {mode.upper()}  D0 {MODES[mode]['d0']:.4f}  dD {MODES[mode]['dd']}"
              f"  gain statique {y[-200:].mean():.1f} V  h[0] {h[0]:+.3f}"
              f"  h[1] {h[1]:+.3f}  h[2] {h[2]:+.3f}  queue a {a_q}")
        for kp, f in lims[:3]:
            print(f"     passage a -180 deg : Kp limite {kp:.4f} a {f/1e3:.2f} kHz")
        kr, fr = ref[mode]
        print(f"     k-section : Kp {kr} a {fr/1e3:.2f} kHz\n")
        out[mode] = dict(h=h, y=y, a_q=a_q, lims=lims)
        np.savez(ICI / f"zi_{mode}.npz", s0=s0, s1=s1, h=h, y=y)
    for f in fs:
        f.with_suffix(".raw").unlink()
    np.save(ICI / "r2_identif_resultats.npy", out, allow_pickle=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "complet":
        raise SystemExit(main())
    raise SystemExit(blanc())
