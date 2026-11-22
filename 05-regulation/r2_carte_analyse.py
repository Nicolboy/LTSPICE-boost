"""R2 -- lecture et carte de stabilite, depuis les .npz de r2_carte.py.

Pour chaque Kp, apres l'echelon 5 -> 10 W :

  BASSE FREQUENCE  sur la moyenne par periode de Vout. Extrema au-dessus
                   du bruit -> regression ln|a| contre t -> sigma, f, zeta.
                   Moins de 3 extrema : APERIODIQUE (zeta >= 1).
  SOUS-HARMONIQUE  sur le rapport cyclique cycle a cycle : la composante
                   alternee d[k] - (d[k-1]+d[k+1])/2, que la moyenne
                   glissante efface. Son enveloppe donne un sigma a fsw/2.

  Classes, selon le verdict du gendarme du 2026-11-22 (un signe brut est
  fragile pres de zero) :
     aperiodique  aucun balancement lisible
     amorti       sigma < 0 au-dela de la bande d'incertitude
     entretenu    |sigma| dans la bande -- la bande est la dispersion
                  entre la premiere et la seconde moitie des extrema
     divergent    sigma > 0 au-dela de la bande

  Drapeaux grand signal : butee du rapport cyclique atteinte, passage en
  CCM (courant minimal par periode > 0). La carte d'un P en DCM n'a de
  sens lineaire que sans eux.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from r2_carte import KPS, FSW, VREF, dcm, P2                # noqa: E402


def sigma_fit(t, a):
    """Pente de ln|a| contre t, et sa bande : ecart entre les deux moities."""
    s = float(np.polyfit(t, np.log(np.abs(a)), 1)[0])
    n = len(t)
    if n >= 6:
        s1 = float(np.polyfit(t[:n // 2], np.log(np.abs(a[:n // 2])), 1)[0])
        s2 = float(np.polyfit(t[n // 2:], np.log(np.abs(a[n // 2:])), 1)[0])
        bande = abs(s1 - s2) / 2
    else:
        bande = abs(s) * 0.3          # trop peu de points : bande large
    return s, bande


def classe(s, bande):
    if abs(s) <= bande:
        return "entretenu"
    return "amorti" if s < 0 else "divergent"


def analyse(i, kp):
    """Classement sur le RAPPORT CYCLIQUE PAR CYCLE, pas sur Vout moyen.

    Premiere version : extrema de la moyenne par periode, espaces d'au
    moins 3 periodes -- ce qui plafonnait la frequence lisible a fsw/6 =
    33,3 kHz. Le cas Kp = 5,6 est sorti a 33 333 Hz pile : le plafond, pas
    une mesure. Et l'alternance d[k] - moyenne(voisins) mesuree sur les
    cas stables n'etait que la courbure de la reponse lisse (correlation
    k/k+1 de +0,9 : rien n'alterne). D'ou ce classement :

      1. composante oscillante = d moins sa tendance (moyenne glissante
         sur 50 periodes) ; aucune oscillation si son efficace < 1e-3
      2. frequence dominante par FFT, resolution fsw/N, jusqu'a fsw/2
      3. croissance : efficace du dernier tiers contre le premier tiers
         -> zeta equivalent = -ln(r) / (2.pi.f.dt)
      4. butee de D atteinte : regime GRAND SIGNAL, le zeta n'y est pas
         celui d'un mode lineaire
    """
    f = ICI / f"c{i:02d}.npz"
    if not f.exists():
        return dict(kp=kp, cls="echec")
    z = np.load(f)
    tb, vb, db, imin, ts = z["tb"], z["vb"], z["db"], z["imin"], float(z["t_step"])
    post = tb > ts + 2 / FSW
    t, v, d, im = tb[post], vb[post], db[post], imin[post]
    nfin = max(len(v) // 4, 10)
    out = dict(kp=kp, vfin=float(v[-nfin:].mean()),
               butee=bool((d.min() < 0.051) or (d.max() > 0.949)),
               ccm=bool(im.max() > 0.02), imin_max=float(im.max()))
    w = 50
    tend = np.convolve(d, np.ones(w) / w, mode="same")
    ac = (d - tend)[w:-w]
    n3 = len(ac) // 3
    e1, e3 = float(np.std(ac[:n3])), float(np.std(ac[-n3:]))
    out.update(eff1=e1, eff3=e3)
    # critere sur le DERNIER tiers : une oscillation ENTRETENUE. Sur le
    # premier, le residu du detrend d'une reponse lisse passait 1e-3
    # (Kp = 0,1 et 0,178) et ouvrait la voie a un faux mode.
    if e3 < 1e-3:
        # PAS d'oscillation entretenue dans D. Reste a savoir si la reponse
        # a l'echelon DEPASSE : c'est la que vit un second mode amorti.
        # Le detrend sur 50 periodes ne le voit pas quand tau_cl ~ 50
        # periodes -- il avait sorti un faux "amorti a 6 kHz" a Kp = 0,1.
        # On lit donc le depassement sur Vout lui-meme :
        #   OS = |creux sous la valeur finale| / ecart initial
        #   zeta = -ln(OS) / sqrt(pi^2 + ln^2 OS),  fd = 1 / (2.t_creux)
        # Sous 1 % de depassement, c'est indiscernable du bruit de la
        # valeur finale : APERIODIQUE (zeta >= ~0,83 au moins).
        xv = v - out["vfin"]
        k = int(np.argmin(xv))
        # ecart TOTAL : Vout avant l'echelon moins la valeur finale. Pris a
        # 2 periodes apres l'echelon, il sous-estimait l'ecart des que
        # tau_cl ~ quelques periodes -- 42 % de depassement lus a Kp =
        # 1,78 au lieu d'une dizaine.
        av = (tb > ts - 20 / FSW) & (tb < ts)
        ecart = float(vb[av].mean() - out['vfin'])
        os_ = float(-xv[k] / ecart) if ecart > 0 else 0.0
        out.update(os=os_)
        if os_ >= 0.01 and 0 < k < len(xv) - nfin:
            lo = np.log(os_)
            out.update(cls="amorti", f=float(FSW / (2 * (k + 2))),
                       zeta=float(-lo / np.hypot(np.pi, lo)), purete=np.nan)
        else:
            out.update(cls="aperiodique", f=np.nan, zeta=1.0, purete=np.nan)
        return out
    x = ac[-2 * n3:]
    sp = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    fr = np.fft.rfftfreq(len(x), 1 / FSW)
    k = int(np.argmax(sp[1:])) + 1
    fo = float(fr[k])
    purete = float(sp[max(k - 2, 0):k + 3].sum() / sp[1:].sum())
    dt = (len(ac) - n3) / FSW
    r = e3 / e1 if e1 > 0 else np.inf
    zeta = float(-np.log(r) / (2 * np.pi * fo * dt))
    if out["butee"]:
        cls = "grand signal"
    elif abs(np.log(r)) < 0.2:          # moins de 20 % d'evolution en 1 ms
        cls = "entretenu" if purete > 0.5 else "irregulier"
    else:
        cls = "amorti" if r < 1 else "divergent"
    out.update(cls=cls, f=fo, zeta=zeta, purete=purete)
    return out


def main():
    _, g2, _ = dcm(P2)
    rows = [analyse(i, float(k)) for i, k in enumerate(KPS)]
    print(f"  {'Kp':>8s} {'Kp.G10W':>8s} {'classe':>13s} {'f [Hz]':>9s} "
          f"{'purete':>7s} {'eff D 1/3':>10s} {'eff D 3/3':>10s} "
          f"{'zeta':>8s} {'Vfin':>7s} {'butee':>6s} {'CCM':>5s}")
    for r in rows:
        if r["cls"] == "echec":
            print(f"  {r['kp']:8.4f}  ECHEC (pas de .npz)")
            continue
        print(f"  {r['kp']:8.4f} {r['kp']*g2:8.2f} {r['cls']:>13s} "
              f"{r['f']:9.0f} {r['purete']:7.2f} {r['eff1']:10.5f} "
              f"{r['eff3']:10.5f} {r['zeta']:+8.4f} {r['vfin']:7.2f} "
              f"{'oui' if r['butee'] else 'non':>6s} "
              f"{'oui' if r['ccm'] else 'non':>5s}")
    np.save(ICI / "r2_carte_resultats.npy", rows, allow_pickle=True)
    return rows


if __name__ == "__main__":
    main()
