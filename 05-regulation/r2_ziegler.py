"""R2 -- Ziegler-Nichols en boucle fermee : gain ultime Ku et periode Tu.

Demande du concepteur (2026-11-22) :
    echelon de charge 40 W -> 30 W (40 -> 20 touchait le DCM), CCM, Vin 20 V, Vout 80 V, Cout 10 uF
    recherche de la limite PAR LES FORTES VALEURS, en k-section parallele
    entretenu  = l'ENVELOPPE de l'oscillation reste constante
    frequence  = lue sur une FFT, fenetre assez longue

ATTENDU (modele moyen ideal, a verifier) :
    f0 = D'/(2.pi.sqrt(L.C)) = 1,83 kHz, zero RHP 33,6 kHz (40 W) et
    67 kHz (20 W), G = Vin/D'^2 = 322 V. En boucle P, Kc = wz/(Q.w0) = 1
    exactement, independant de C et R : Kp_u ~ 1/322 = 0,0031, et la
    frequence a la limite f0.sqrt(1+Kc) = 2,6 kHz, soit Tu ~ 0,39 ms.
    Les pertes amortissent : a 40 W / 2,2 uF on avait mesure la limite
    entre K = 1,14 et 2,03. D'ou Kp_u attendu dans [0,0035 ; 0,006].

TRANSISTOR : IPD530N15N3_L0, modele niveau 0 Infineon de la MEME piece.
Le _L1 se bloquait sur sa source comportementale e_eds7. Le test a blanc
compare _L0 a l'interrupteur ideal sur le meme cas, pour chiffrer ce que
le transistor change a la boucle.
"""
from __future__ import annotations

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
DUTY0 = 0.750929          # 40 W CCM, mesure au chapitre 04 (etape 3)
# ECHELON 40 -> 30 W (demande du concepteur apres le test a blanc).
# 40 -> 20 W faisait toucher le DCM a 13-15 % des periodes de la premiere
# milliseconde (Imin -0,14 A) : le point 20 W n'a que 0,2 A de marge.
# 30 W : Imin ~ 0,75 A, CCM franc meme pendant le transitoire.
P_APRES = 30.0
R_BASE = VREF ** 2 / P_APRES                       # 213,3 ohms, branchee
R_OUV = 1.0 / (1.0 / 160.0 - 1.0 / R_BASE)         # 640 ohms, ouverte
# Condensateur de sortie : None = 10 uF IDEAL (premiere k-section) ;
# sinon reference Wurth, bibliotheque LOCALE (lib_spice_commun).
# 860130874006 : WCAP-ATET alu 10 uF / 100 V, Rser 0,37 ohm, Lser 5,6 nH
# -- zero d'ESR vers 43 kHz, loin au-dessus de Tu (~4 kHz).
COUT_WE = "860130874006"
SUFFIXE = "f" if COUT_WE else ""
N_AVANT, N_APRES = 200, 1200     # 1 ms puis 6 ms : ~15 Tu, FFT a 167 Hz


def prepare(tag, kp, mos):
    n = etape.etape0(p=40.0, vin=VIN, charge=True, rl=R_BASE, cout=COUT,
                     ser=True, v8pa22=True, mos=mos, n_etab=0,
                     n_mes=N_AVANT + N_APRES, dtmax=200e-9, duty=DUTY0,
                     kp=kp, vref=VREF, echelon=(R_OUV, N_AVANT / FSW, "-"),
                     sobre=True, cout_we=COUT_WE, tau_mes=TAU_MES)
    f = ICI / f"{tag}.cir"
    f.write_text(n, encoding="utf-8")
    return f


def par_periode(f):
    """Moyenne par periode (blocs disjoints, grille uniforme 256/periode)."""
    r = lire(str(Path(f).with_suffix(".raw")))
    t = np.asarray(r.x)
    np_ = 256
    nb = int(round((t[-1] - t[0]) * FSW))
    tu = np.linspace(t[0], t[0] + nb / FSW, nb * np_, endpoint=False)
    def bloc(nom, red="mean"):
        y = np.interp(tu, t, np.asarray(r.trace(nom)).real).reshape(nb, np_)
        return getattr(y, red)(1)
    tb = t[0] + (np.arange(nb) + 0.5) / FSW
    return dict(tb=tb, vb=bloc("V(nout)"), db=bloc("V(nctrl)"),
                imin=bloc("I(L1)", "min"), npts=len(t))


def lecture(z, ts=N_AVANT / FSW):
    """Apres l'echelon : enveloppe (constante ?) et frequence par FFT.

    Composante oscillante = Vout moyen moins sa tendance lente (ajustement
    exponentiel ecarte : la tendance d'un P a l'echelon est elle-meme une
    reponse ; on retire une moyenne glissante sur ~2 Tu attendus, 200
    periodes, qui laisse passer la bande 1-10 kHz).
    Enveloppe = amplitude crete-a-crete par fenetres de 100 periodes ;
    rapport dernier tiers / premier tiers.
    """
    tb, vb = z["tb"], z["vb"]
    m = tb > ts + 20 / FSW
    t, v = tb[m], vb[m]
    w = 200
    tend = np.convolve(v, np.ones(w) / w, mode="same")
    x = (v - tend)[w:-w]
    tx = t[w:-w]
    k = 100
    nb = len(x) // k
    env = np.array([np.ptp(x[i * k:(i + 1) * k]) for i in range(nb)])
    n3 = max(nb // 3, 1)
    r = float(env[-n3:].mean() / env[:n3].mean()) if env[:n3].mean() > 0 else np.nan
    # FFT : Hann, zero-padding x8, interpolation parabolique du pic
    xx = (x - x.mean()) * np.hanning(len(x))
    nfft = 8 * len(xx)
    sp = np.abs(np.fft.rfft(xx, nfft))
    fr = np.fft.rfftfreq(nfft, 1 / FSW)
    sel = (fr > 300) & (fr < 50e3)
    i = int(np.argmax(np.where(sel, sp, 0)))
    a, b, c = np.log(sp[i - 1:i + 2] + 1e-30)
    dlt = 0.5 * (a - c) / (a - 2 * b + c)
    fpk = float(fr[i] + dlt * (fr[1] - fr[0]))
    return dict(env=env, r=r, f=fpk, resol=FSW / len(x),
                app=float(env.mean()), vfin=float(v[-200:].mean()),
                ccm=bool(z["imin"][m].min() > 0),
                imin=float(z["imin"][m].min()),
                butee=bool((z["db"][m].min() < 0.051) or (z["db"][m].max() > 0.949)))


def blanc(kp=0.003) -> int:
    print("  TEST A BLANC Ziegler-Nichols -- echelon 40 -> 20 W CCM, "
          f"Cout {COUT*1e6:.0f} uF, Kp {kp}\n")
    print(f"  fenetre : {N_AVANT} periodes avant, {N_APRES} apres "
          f"({(N_AVANT+N_APRES)/FSW*1e3:.1f} ms), dtmax 200 ns\n")
    fs = [prepare("z_blanc_ideal", kp, False),
          prepare("z_blanc_l0", kp, "ipd530_l0")]
    t0 = time.monotonic()
    res = ltspice_run.lance_lot(fs, procs=2)
    dt = time.monotonic() - t0
    print(f"  2 cas en parallele : {dt:.0f} s\n")
    for f in fs:
        r = res[f.stem]
        print(f"  {f.stem:16s} {'OK' if r['ok'] else 'ECHEC'} -- "
              f"{r['diagnostic'][:110]}")
        if not r["ok"]:
            continue
        z = par_periode(f)
        L_ = lecture(z)
        av = (z["tb"] > 0.6 * N_AVANT / FSW) & (z["tb"] < N_AVANT / FSW)
        print(f"     .raw {f.with_suffix('.raw').stat().st_size/1e6:.0f} Mo, "
              f"{z['npts']} points")
        print(f"     avant echelon : Vout {z['vb'][av].mean():.3f} V   "
              f"D {z['db'][av].mean():.4f}")
        print(f"     apres         : Vout final {L_['vfin']:.3f} V, "
              f"I min {L_['imin']:+.3f} A ({'CCM' if L_['ccm'] else 'DCM touche'})"
              f", butee {'oui' if L_['butee'] else 'non'}")
        print(f"     oscillation   : f = {L_['f']:.0f} Hz (resolution FFT "
              f"brute {L_['resol']:.0f} Hz), crete-a-crete moyenne "
              f"{L_['app']*1e3:.1f} mV")
        print(f"     enveloppe     : {np.round(L_['env']*1e3, 1).tolist()} mV")
        print(f"     rapport dernier/premier tiers : {L_['r']:.3f}")
    return 0


# =====================================================================
# K-SECTION : la limite par les fortes valeurs, 4 cas en parallele
# =====================================================================
# MOSFET onsemi FDD770N15A : l'Infineon (_L1 puis _L0) est abandonne
# sur demande du concepteur. Le blocage commun aux deux constructeurs
# venait en fait du comparateur lisant V(nout) INSTANTANE -- d'ou
# TAU_MES, le filtre RC de l'entree ADC (1 us, -1,4 deg a 3,9 kHz).
MOS = "fdd770"
TAU_MES = 1e-6
T_LIRE = 1e-3           # on lit l'enveloppe a partir de 1 ms apres l'echelon


def verdict(z):
    """Enveloppe de l'oscillation : decroit, constante, ou croit.

    Enveloppe = crete-a-crete de la composante oscillante de Vout moyen
    par fenetres de 100 periodes (0,5 ms, ~1,3 Tu), a partir de T_LIRE.
    sigma = pente de ln(enveloppe) contre t, et rapport r = dernier tiers
    / premier tiers. Seuils : r < 0,8 decroit, r > 1,25 croit, entre les
    deux CONSTANTE -- la definition du concepteur de l'entretenu.

    Un cas qui DIVERGE finit lui aussi en enveloppe constante, mais
    bornee par une non-linearite : butee de D ou entree en DCM. Une
    enveloppe constante AVEC l'un de ces drapeaux est donc classee
    instable (cycle limite grand signal), pas entretenue.
    """
    ts = N_AVANT / FSW
    tb, vb, db, im = z["tb"], z["vb"], z["db"], z["imin"]
    m = tb > ts + T_LIRE
    v = vb[m]
    w = 200
    x = (v - np.convolve(v, np.ones(w) / w, mode="same"))[w:-w]
    tx = tb[m][w:-w]
    k = 100
    nb = len(x) // k
    env = np.array([np.ptp(x[i * k:(i + 1) * k]) for i in range(nb)])
    te = np.array([tx[i * k:(i + 1) * k].mean() for i in range(nb)])
    sig = float(np.polyfit(te, np.log(env), 1)[0])
    n3 = max(nb // 3, 1)
    r = float(env[-n3:].mean() / env[:n3].mean())
    # FFT sur toute la fenetre lue
    xx = (x - x.mean()) * np.hanning(len(x))
    nfft = 16 * len(xx)
    sp = np.abs(np.fft.rfft(xx, nfft))
    fr = np.fft.rfftfreq(nfft, 1 / FSW)
    sel = (fr > 300) & (fr < 50e3)
    i = int(np.argmax(np.where(sel, sp, 0)))
    fpk = float(fr[i])
    mt = tb > ts + T_LIRE
    dcm = float(np.mean(im[mt] < 0))
    butee = bool((db[mt].min() < 0.051) or (db[mt].max() > 0.949))
    if r < 0.8:
        cls = "decroit"
    elif r > 1.25:
        cls = "croit"
    elif butee or dcm > 0:
        cls = "cycle limite (borne par non-linearite)"
    else:
        cls = "ENTRETENU"
    stable = cls == "decroit"
    return dict(cls=cls, stable=stable, sig=sig, r=r, f=fpk,
                env=env, dcm=dcm, butee=butee,
                app=float(env[-n3:].mean()), resol=FSW / len(x))


def un_tour(kps, n_tour):
    fs = [prepare(f"zk{SUFFIXE}{n_tour}_{j}", float(k), MOS) for j, k in enumerate(kps)]
    t0 = time.monotonic()
    res = ltspice_run.lance_lot(fs, procs=len(fs))
    dt = time.monotonic() - t0
    out = []
    for k, f in zip(kps, fs):
        r = res[f.stem]
        if not r["ok"]:
            out.append(dict(kp=float(k), cls="INDETERMINE (simulation morte)",
                            stable=None, diag=r["diagnostic"][:90]))
            continue
        z = par_periode(f)
        np.savez(f.with_suffix(".npz"), **z)
        f.with_suffix(".raw").unlink()
        v = verdict(z)
        v["kp"] = float(k)
        out.append(v)
    return out, dt


def montre(v):
    if v["stable"] is None:
        print(f"     Kp {v['kp']:.5f}  {v['cls']} -- {v['diag']}")
        return
    print(f"     Kp {v['kp']:.5f}  (K {v['kp']*322:5.2f})  {v['cls']:40s}"
          f" r {v['r']:5.2f}  sigma {v['sig']:+7.0f} /s  f {v['f']:6.0f} Hz"
          f"  env fin {v['app']*1e3:6.1f} mV  DCM {v['dcm']*100:4.1f} %")


def ksection(lo=0.001, hi=0.03, tol=1.1, n=4) -> int:
    print("  K-SECTION Ziegler-Nichols -- echelon 40 -> 30 W, CCM, Cout "
          f"{COUT*1e6:.0f} uF, {MOS}")
    print(f"  bornes [{lo} ; {hi}], {n} cas par tour, arret a hi/lo <= {tol}\n")
    tous = []
    # tour 1 : les bornes INCLUSES, en partant des fortes valeurs
    kps = np.geomspace(hi, lo, n)
    tour = 1
    while True:
        print(f"  tour {tour} : Kp = {[round(float(k), 5) for k in kps]}")
        res, dt = un_tour(kps, tour)
        print(f"     ({dt:.0f} s)")
        for v in sorted(res, key=lambda v: -v["kp"]):
            montre(v)
        if any(v["stable"] is None for v in res):
            print("\n  Cas MORT : verdict INDETERMINE, la k-section s'arrete.")
            return 1
        tous += res
        st = [v["kp"] for v in tous if v["stable"]]
        inst = [v["kp"] for v in tous if not v["stable"]]
        if not st or not inst:
            print("\n  Pas d'encadrement : tous stables ou tous instables.")
            return 1
        lo, hi = max(st), min([k for k in inst if k > max(st)] or [max(inst)])
        print(f"  -> encadrement [{lo:.5f} ; {hi:.5f}], rapport {hi/lo:.3f}\n")
        if hi / lo <= tol:
            break
        kps = np.geomspace(hi, lo, n + 2)[1:-1]
        tour += 1
    # Ku : zero de sigma interpole en log(Kp) entre les deux voisins
    a = min((v for v in tous if v["kp"] == lo), key=lambda v: 0)
    b = min((v for v in tous if v["kp"] == hi), key=lambda v: 0)
    if b["sig"] > a["sig"]:
        u = a["sig"] / (a["sig"] - b["sig"])
        ku = float(np.exp(np.log(lo) + u * (np.log(hi) - np.log(lo))))
    else:
        ku = float(np.sqrt(lo * hi))
    # Tu : FFT du cas le plus proche de sigma = 0
    proche = min((a, b), key=lambda v: abs(v["sig"]))
    tu = 1.0 / proche["f"]
    print(f"  Ku = {ku:.5f}  (Kp.G = {ku*322:.2f} avec G = 322 V)")
    print(f"  Tu = {tu*1e3:.4f} ms  (f = {proche['f']:.0f} Hz, cas Kp "
          f"{proche['kp']:.5f}, resolution FFT brute {proche['resol']:.0f} Hz)")
    np.save(ICI / f"r2_ziegler{SUFFIXE}_resultats.npy",
            dict(ku=ku, tu=tu, tous=tous), allow_pickle=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "ksection":
        raise SystemExit(ksection())
    raise SystemExit(blanc())
