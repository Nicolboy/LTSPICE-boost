"""R2 -- recoupement des limites du P par injection MULTI-TONS (boucle ouverte).

L'identification par echelon (r2_identif_arx.py) n'a pas tranche : un
echelon met son energie en basse frequence, et la limite depend de ce que
fait le plant vers 5 kHz (CCM) et 30 kHz (DCM). Ici on mesure H(e^j.theta)
DIRECTEMENT a ces frequences, comme le Bode de R1.

Banc : boucle ouverte au point d'apres l'echelon (CCM 30 W, DCM 10 W),
meme chaine de mesure (filtre 1 us, echantillon a 0,998 T), MLCC HF,
FDD770, Wurth. D = D0 + somme de sinusoides, chaque ton faisant un nombre
ENTIER de cycles sur la fenetre d'analyse (pas de fuite entre tons).

Sequences echantillonnees, une valeur par periode n :
  d[n] = V(nctrl) a l'instant du blocage (n.T + D0.T) -- la commande
         reellement appliquee dans la periode n ;
  s[n] = valeur figee a la fin de la periode n.
H(theta_k) = S(theta_k) / Dd(theta_k), DFT sur la fenetre, tendance
lineaire retiree. Boucle du banc : d[n] = -Kp.s[n-2], donc
L = Kp.e^(-2j.theta).H : limite ou arg(e^-2j.theta H) = -180 deg,
Kp_lim = 1/|H| a cette frequence (interpolation entre tons).
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
import r2_identif as idf                                     # noqa: E402
import etape                                                 # noqa: E402
import ltspice_run                                           # noqa: E402
sys.path.insert(0, str(ICI.parent.parent / ".claude/skills/sim-commun"))
from simcommun.lecture import lire                           # noqa: E402

FSW, T = z.FSW, 1.0 / z.FSW
N_ETAB, N_FEN = 600, 1600            # 3 ms d'etablissement, 8 ms analyses
DF = FSW / N_FEN                     # 125 Hz : resolution, tons sur ce pas
TONS = {
    "ccm": dict(f=np.arange(3000, 7001, 500), amp=0.0005),
    "dcm": dict(f=np.arange(15000, 45001, 2500), amp=0.003),
}
REF = {"ccm": (0.0207, 4.85e3), "dcm": (1.345, 30.6e3)}


def expr_tons(mode, d0):
    rng = np.random.default_rng(1)
    t = TONS[mode]
    termes = [f"{t['amp']:.6f}*sin({2*np.pi*f:.6e}*time+{ph:.4f})"
              for f, ph in zip(t["f"], rng.uniform(0, 2 * np.pi, len(t["f"])))]
    return f"V={d0:.6f} + " + " + ".join(termes)


def prepare(mode, n_mes):
    m = idf.MODES[mode]
    kp, d0, src = idf.d_etabli(*m["src"])
    m["d0"] = d0
    n = etape.etape0(p=m["p"], vin=z.VIN, charge=True, rl=m["rl"], cout=z.COUT,
                     ser=True, v8pa22=True, mos=z.MOS, n_etab=0, n_mes=n_mes,
                     dtmax=200e-9, duty=d0, pwm=expr_tons(mode, d0),
                     vref=z.VREF, sobre=True, cout_we=z.COUT_WE,
                     tau_mes=z.TAU_MES, echant=z.ECHANT, cout_hf=True,
                     force_ic=True)
    f = ICI / f"zm_{mode}.cir"
    f.write_text(n, encoding="utf-8")
    return f


def sequences(f, mode, n_tot):
    x = lire(str(f.with_suffix(".raw")))
    t = np.asarray(x.x)
    sh = np.asarray(x.trace("V(nsh)")).real
    nc = np.asarray(x.trace("V(nctrl)")).real
    d0 = idf.MODES[mode]["d0"]
    n = np.arange(n_tot - 1)
    d = np.interp((n + d0) * T, t, nc)               # commande au blocage
    s = np.interp((n + 1 + 0.5) * T, t, sh)          # fin de periode n
    return d, s


def analyse(mode, d, s):
    sel = slice(N_ETAB, N_ETAB + N_FEN)
    dd, ss = d[sel], s[sel]
    k = np.arange(N_FEN)
    dd = dd - np.polyval(np.polyfit(k, dd, 1), k)
    ss = ss - np.polyval(np.polyfit(k, ss, 1), k)
    Dk, Sk = np.fft.rfft(dd), np.fft.rfft(ss)
    rows = []
    for f in TONS[mode]["f"]:
        i = int(round(f / DF))
        th = 2 * np.pi * i / N_FEN
        H = Sk[i] / Dk[i]
        L = np.exp(-2j * th) * H
        # qualite : energie du ton contre bins voisins (hors tons)
        voisins = np.abs(Sk[[i - 2, i + 2]]).mean()
        rows.append((f, abs(H), np.degrees(np.angle(H)),
                     np.degrees(np.angle(L)), abs(Sk[i]) / max(voisins, 1e-30)))
    return rows


def lecture(mode, rows):
    f = np.array([r[0] for r in rows])
    mag = np.array([r[1] for r in rows])
    phL = np.unwrap(np.radians([r[3] for r in rows]))
    phL_deg = np.degrees(phL)
    print(f"  {mode.upper()}   f [kHz]   |H| [V/unite D]  arg H   arg(z^-2 H)  ton/voisins")
    for r, p in zip(rows, phL_deg):
        print(f"        {r[0]/1e3:6.2f}   {r[1]:10.3f}   {r[2]:+7.1f}   {p:+8.1f}"
              f"   {r[4]:8.0f}")
    # passage a -180 deg : interpolation lineaire en frequence
    c = np.where(np.diff(np.sign(phL_deg + 180)) != 0)[0]
    if len(c) == 0:
        print("     pas de passage a -180 deg dans la bande injectee\n")
        return None
    i = c[0]
    u = (-180 - phL_deg[i]) / (phL_deg[i + 1] - phL_deg[i])
    fc = f[i] + u * (f[i + 1] - f[i])
    m = np.exp(np.log(mag[i]) + u * (np.log(mag[i + 1]) - np.log(mag[i])))
    kr, fr = REF[mode]
    print(f"     passage a -180 deg a {fc/1e3:.2f} kHz, |H| = {m:.3f} -> "
          f"Kp limite {1/m:.4g}")
    print(f"     k-section : Kp {kr} a {fr/1e3:.2f} kHz   "
          f"(ecart Kp {100*(1/m/kr-1):+.0f} %, f {100*(fc/fr-1):+.0f} %)\n")
    return fc, 1 / m


def blanc() -> int:
    print("  TEST A BLANC multi-tons -- 30 us par mode")
    fs = [prepare(m, 6) for m in TONS]
    t0 = time.monotonic()
    res = ltspice_run.lance_lot(fs, procs=2)
    print(f"     {time.monotonic()-t0:.0f} s")
    for mode, f in zip(TONS, fs):
        r = res[f.stem]
        print(f"     {mode} : {'OK' if r['ok'] else 'ECHEC'}  {r['diagnostic'][:90]}")
        if r["ok"]:
            x = lire(str(f.with_suffix(".raw")))
            nc = np.asarray(x.trace("V(nctrl)")).real
            print(f"        D min {nc.min():.4f} max {nc.max():.4f}  "
                  f"(D0 {idf.MODES[mode]['d0']:.4f})")
            f.with_suffix(".raw").unlink()
    return 0 if all(res[f.stem]["ok"] for f in fs) else 1


def main() -> int:
    n_tot = N_ETAB + N_FEN + 2
    fs = [prepare(m, n_tot) for m in TONS]
    t0 = time.monotonic()
    res = ltspice_run.lance_lot(fs, procs=2)
    print(f"  2 cas ({n_tot} periodes) : {time.monotonic()-t0:.0f} s\n")
    out = {}
    for mode, f in zip(TONS, fs):
        if not res[f.stem]["ok"]:
            print(f"  {mode} ECHEC {res[f.stem]['diagnostic'][:90]}")
            continue
        d, s = sequences(f, mode, n_tot)
        np.savez(ICI / f"zm_{mode}.npz", d=d, s=s)
        f.with_suffix(".raw").unlink()
        rows = analyse(mode, d, s)
        out[mode] = dict(rows=rows, lim=lecture(mode, rows))
    np.save(ICI / "r2_multitons_resultats.npy", out, allow_pickle=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "complet":
        raise SystemExit(main())
    raise SystemExit(blanc())
