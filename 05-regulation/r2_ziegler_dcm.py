"""R2 -- limite du P en DCM, sur le banc constructeur retenu.

Meme banc que la k-section CCM (r2_ziegler.py) : FDD770N15A, sortie
Wurth 860130874006 (10 uF / 100 V, bibliotheque locale), mesure de Vout
filtree RC 1 us (entree ADC). Seul change le point : echelon de charge
5 -> 10 W (1280 ohms, puis 1280 ohms en parallele a t = 1 ms), les deux
en DCM (frontiere 15,3 W sous 20 V). D0 = formule DCM a 5 W.

CE QUI DIFFERE DU CCM, et pourquoi le critere change :
  le plant DCM moyen est du PREMIER ORDRE -- un P n'y oscille pas en
  basse frequence. Sur le banc ideal SANS filtre (r2_carte.py), la seule
  instabilite vue etait une ALTERNANCE de D cycle a cycle (fsw/2), que la
  moyenne par periode efface. Le filtre de mesure supprime justement
  l'ondulation lue par le comparateur, mecanisme suppose de cette
  alternance : la limite peut donc se deplacer fortement.

  D'ou DEUX lectures, et l'instable est l'une OU l'autre :
    BF   enveloppe de <Vout> par periode (comme en CCM) ;
    fsw/2 enveloppe de la composante ALTERNEE de D,
          d[k] - (d[k-1] + d[k+1]) / 2.
  Chacune avec un PLANCHER DE BRUIT : la k-section CCM classait
  "entretenu" le bruit constant d'une reponse deja eteinte.
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
import etape                                                 # noqa: E402
import ltspice_run                                           # noqa: E402

P1, P2 = 5.0, 10.0
R1 = z.VREF ** 2 / P1                   # 1280 ohms, toujours branchee
R_AJ = 1.0 / (1.0 / (z.VREF ** 2 / P2) - 1.0 / R1)     # 1280, ajoutee
N_AVANT, N_APRES = 200, 600             # 1 ms puis 3 ms
G10 = 115.5                             # gain DCM a 10 W (formule fermee)
SEUIL_V = 0.10                          # plancher de bruit <Vout>, V c-a-c
SEUIL_ALT = 1e-2                        # plancher de bruit alternance de D
# 1e-2 et non 1e-3 : a 1e-3, Kp 2,29 (alternance 0,0012, courbe lisse) etait
# classe instable ; le vrai decrochage saute de 0,0015 a 0,18.
# Mesure ECHANTILLONNEE une fois par periode (echantillonneur-bloqueur en
# debut de periode, comme l'ADC du C2000). Sans lui, a Kp ~ 1 le filtre
# de 1 us ne suffisait plus : 70 s pour 6 periodes, 390 relachements.
# Instant : 0,998 T, fin de la fenetre S+H du F28P551 juste avant la
# fermeture du MOSFET (r2_fig_dcm_phase.py : gigue de D 0,00054 -> 0,00010).
ECHANT = 0.998
# MLCC HF de la fiche en sortie (r2_fig_dcm_mlcc.py : pic de rallumage
# 10-24 V -> 3,7-5,8 V crete a crete).
COUT_HF = True
# Retard d'une periode : conversion + CLA + rechargement CMPA (C2000).
RETARD = True
PREFIXE = "zr" if RETARD else "zd"


def prepare(tag, kp, n_mes=None):
    n = etape.etape0(p=P1, vin=z.VIN, charge=True, rl=R1, cout=z.COUT,
                     ser=True, v8pa22=True, mos=z.MOS, n_etab=0,
                     n_mes=n_mes or (N_AVANT + N_APRES), dtmax=200e-9,
                     kp=kp, vref=z.VREF, echelon=(R_AJ, N_AVANT / z.FSW),
                     sobre=True, cout_we=z.COUT_WE, tau_mes=z.TAU_MES,
                     echant=ECHANT, cout_hf=COUT_HF, retard=RETARD)
    f = ICI / f"{tag}.cir"
    f.write_text(n, encoding="utf-8")
    return f


def env(x, k):
    nb = len(x) // k
    return np.array([np.ptp(x[i * k:(i + 1) * k]) for i in range(nb)])


def classe(e, seuil):
    """Enveloppe par fenetres : sous le plancher = amortie ; sinon r."""
    n3 = max(len(e) // 3, 1)
    a, b = float(e[:n3].mean()), float(e[-n3:].mean())
    if b < seuil:
        return "amorti", b / a if a > 0 else 0.0
    r = b / a
    return ("decroit" if r < 0.8 else "croit" if r > 1.25
            else "constant"), r


def verdict(d):
    ts = N_AVANT / z.FSW
    tb, vb, db, im = d["tb"], d["vb"], d["db"], d["imin"]
    m = tb > ts + 0.5e-3
    v, dd = vb[m], db[m]
    # BF : <Vout> detrende sur 100 periodes, enveloppe par 50 periodes
    w = 100
    # mode="valid" : pas de zeros de bord (skill oscillogrammes, §5)
    tend = np.convolve(v, np.ones(w) / w, mode="valid")
    x = v[w // 2: w // 2 + len(tend)] - tend
    e_bf = env(x, 50)
    c_bf, r_bf = classe(e_bf, SEUIL_V)
    # fsw/2 : composante alternee de D
    alt = dd[1:-1] - 0.5 * (dd[:-2] + dd[2:])
    e_alt = env(alt, 50)
    c_alt, r_alt = classe(e_alt, SEUIL_ALT)
    butee = bool((dd.min() < 0.051) or (dd.max() > 0.949))
    ccm = float(np.mean(im[m] > 0.02))
    # FFT de <Vout> (BF) pour la frequence
    xx = (x - x.mean()) * np.hanning(len(x))
    sp = np.abs(np.fft.rfft(xx, 16 * len(xx)))
    fr = np.fft.rfftfreq(16 * len(xx), 1 / z.FSW)
    sel = (fr > 300) & (fr < 50e3)
    f_bf = float(fr[int(np.argmax(np.where(sel, sp, 0)))])
    inst = (c_bf in ("croit", "constant") or c_alt in ("croit", "constant")
            or butee)
    return dict(stable=not inst, c_bf=c_bf, r_bf=r_bf, c_alt=c_alt,
                r_alt=r_alt, app=float(e_bf[-3:].mean()),
                alt=float(e_alt[-3:].mean()), f_bf=f_bf, butee=butee,
                ccm=ccm, vfin=float(v[-100:].mean()))


def montre(kp, v):
    if v is None:
        print(f"     Kp {kp:8.4f}  INDETERMINE (simulation morte)")
        return
    print(f"     Kp {kp:8.4f} (K10W {kp*G10:7.1f})  "
          f"{'stable  ' if v['stable'] else 'INSTABLE'}  "
          f"BF {v['c_bf']:9s} r {v['r_bf']:4.2f} {v['app']*1e3:6.0f} mV "
          f"{v['f_bf']/1e3:5.2f} kHz | fsw/2 {v['c_alt']:9s} r {v['r_alt']:4.2f}"
          f" {v['alt']:.4f} | butee {'oui' if v['butee'] else 'non'}"
          f"  CCM {v['ccm']*100:4.1f} %  Vfin {v['vfin']:.2f}")


def un_tour(kps, n_tour):
    fs = [prepare(f"{PREFIXE}{n_tour}_{j}", float(k)) for j, k in enumerate(kps)]
    t0 = time.monotonic()
    res = ltspice_run.lance_lot(fs, procs=len(fs))
    dt = time.monotonic() - t0
    out = []
    for k, f in zip(kps, fs):
        r = res[f.stem]
        if not r["ok"]:
            out.append((float(k), None, r["diagnostic"][:90]))
            continue
        d = z.par_periode(f)
        np.savez(f.with_suffix(".npz"), **d)
        f.with_suffix(".raw").unlink()
        out.append((float(k), verdict(d), ""))
    return out, dt


def blanc(kp=1.0) -> int:
    print(f"  TEST A BLANC DCM -- echelon 5 -> 10 W, Kp {kp}")
    f = prepare("zd_blanc30", kp, n_mes=6)
    t0 = time.monotonic()
    r = ltspice_run.lance(f)
    print(f"     30 us : {'OK' if r['ok'] else 'ECHEC'} en "
          f"{time.monotonic()-t0:.0f} s  {r['diagnostic'][:90]}")
    if not r["ok"]:
        return 1
    f = prepare("zd_blanc", kp)
    t0 = time.monotonic()
    r = ltspice_run.lance(f)
    dt = time.monotonic() - t0
    print(f"     complet ({N_AVANT}+{N_APRES} periodes) : "
          f"{'OK' if r['ok'] else 'ECHEC'} en {dt:.0f} s  "
          f"{r['diagnostic'][:90]}")
    if not r["ok"]:
        return 1
    d = z.par_periode(f)
    print(f"     .raw {f.with_suffix('.raw').stat().st_size/1e6:.0f} Mo")
    np.savez(f.with_suffix(".npz"), **d)
    f.with_suffix(".raw").unlink()
    ts = N_AVANT / z.FSW
    av = (d["tb"] > 0.6e-3) & (d["tb"] < ts)
    print(f"     avant echelon : Vout {d['vb'][av].mean():.3f} V  "
          f"D {d['db'][av].mean():.4f}  I min {d['imin'][av].max():+.3f} A")
    montre(kp, verdict(d))
    return 0


def ksection(lo=0.1, hi=10.0, tol=1.1, n=4) -> int:
    print(f"  K-SECTION DCM -- echelon 5 -> 10 W, {z.MOS}, Wurth "
          f"{z.COUT_WE}, mesure filtree {z.TAU_MES*1e6:.0f} us")
    print(f"  bornes [{lo} ; {hi}], {n} cas par tour, arret a hi/lo <= {tol}\n")
    tous = []
    kps = np.geomspace(hi, lo, n)
    tour = 1
    while True:
        print(f"  tour {tour} : Kp = {[round(float(k), 4) for k in kps]}")
        res, dt = un_tour(kps, tour)
        print(f"     ({dt:.0f} s)")
        for k, v, diag in sorted(res, key=lambda r: -r[0]):
            montre(k, v)
        if any(v is None for _, v, _ in res):
            print("\n  Cas MORT : INDETERMINE, la k-section s'arrete.")
            return 1
        tous += [(k, v) for k, v, _ in res]
        st = [k for k, v in tous if v["stable"]]
        inst = [k for k, v in tous if not v["stable"]]
        if not st or not inst:
            print("\n  Pas d'encadrement : tous stables ou tous instables.")
            return 1
        lo = max(st)
        hi = min([k for k in inst if k > lo] or [max(inst)])
        print(f"  -> encadrement [{lo:.4f} ; {hi:.4f}], rapport {hi/lo:.3f}\n")
        if hi / lo <= tol:
            break
        kps = np.geomspace(hi, lo, n + 2)[1:-1]
        tour += 1
    print(f"  LIMITE DCM : Kp entre {lo:.4f} et {hi:.4f}  "
          f"(K10W {lo*G10:.0f} a {hi*G10:.0f})")
    np.save(ICI / f"r2_ziegler_dcm_{PREFIXE}_resultats.npy",
            dict(lo=lo, hi=hi, tous=tous), allow_pickle=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "ksection":
        raise SystemExit(ksection())
    raise SystemExit(blanc())
