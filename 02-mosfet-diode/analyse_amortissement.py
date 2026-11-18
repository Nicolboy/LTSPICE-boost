"""Depouillement du banc d'amortissement : formes d'onde, FFT, FFT court terme.

CE QU'ON CHERCHE A MESURER, et pas seulement a voir :

  f_BF, Q_BF   la raie de temps mort -- frequence et facteur de qualite.
               Q est tire de l'ENVELOPPE : env(t) = A exp(-t/tau) donne
               Q = pi f0 tau. C'est la seule facon de distinguer "amorti"
               de "pas amorti" par un nombre.
  f_HF         la resonance de maille, excitee a la coupure.
  spectre      la FFT sur la fenetre entiere, en amplitude de sinus.

EXIGENCES NUMERIQUES. Une FFT sur un echantillonnage NON UNIFORME n'a
aucun sens, et LTspice ne produit que du non uniforme. On reechantillonne
donc sur une grille reguliere, mais seulement vers une resolution PLUS
FINE que le pas moyen reel du solveur -- sinon on decime, et on replie les
fronts de 150 ps dans la bande utile. Le controle est affiche.

La fenetre couvre un NOMBRE ENTIER de periodes de decoupage et porte une
fenetre de Hann : sans cela les fuites spectrales fabriquent des raies qui
n'existent pas.

LIMITE DE VALIDITE A NE PAS OUBLIER. Le modele Coilcraft est declare
valide de 100 kHz a 110 MHz. Au-dela, le spectre affiche est celui du
modele, pas celui du composant.
"""
from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                 # noqa: E402
from matplotlib.ticker import LogLocator                        # noqa: E402

import test_amortissement as ta                                 # noqa: E402

DT_GRILLE = 0.1e-9           # grille uniforme de reechantillonnage
F_AFFICHE = 1e9              # borne haute des traces frequentielles
F_VALIDE = 110e6             # validite declaree du modele Coilcraft

# Palette calee sur FOND SOMBRE : les teintes matplotlib par defaut y
# perdent trop de contraste. Saturation et clarte remontees, teintes
# conservees pour rester comparables aux figures du chapitre 3.
COULEUR = {"ideal": "#ff6b6b", "dcr_reelle": "#ffa94d",
           "pkz": "#4dabf7", "constructeur": "#51cf66",
           "snubber": "#cc8fff"}
FOND, PAPIER, ENCRE, TRAIT = "#14171b", "#1b1f25", "#e8eaed", "#9aa4b0"


def style_sombre():
    """Fond sombre pour toutes les figures. A appeler avant tout trace."""
    plt.rcParams.update({
        "figure.facecolor": FOND, "savefig.facecolor": FOND,
        "axes.facecolor": PAPIER, "axes.edgecolor": TRAIT,
        "axes.labelcolor": ENCRE, "axes.titlecolor": ENCRE,
        "text.color": ENCRE, "xtick.color": TRAIT, "ytick.color": TRAIT,
        "grid.color": TRAIT, "figure.edgecolor": FOND,
        "legend.facecolor": PAPIER, "legend.edgecolor": TRAIT,
        "legend.framealpha": .88, "legend.labelcolor": ENCRE,
        "font.size": 11, "axes.titlesize": 12,
    })


ETIQ = {"ideal": "L idéale (banc actuel, DCR 1,7 mΩ)",
        "dcr_reelle": "DCR réelle 5,5 mΩ seule",
        "pkz": "+ PkZ 1778 Ω en parallèle",
        "constructeur": "modèle constructeur SER1360-472_imp",
        "snubber": "constructeur + snubber RC 180 Ω / 220 pF"}


# ------------------------------------------------------- outils de mesure

def uniforme(t, y, dt=DT_GRILLE):
    """Reechantillonne sur une grille reguliere. Rend (tu, yu, pas_moyen)."""
    n = int(np.floor((t[-1] - t[0]) / dt))
    tu = t[0] + np.arange(n) * dt
    return tu, np.interp(tu, t, y), float(np.diff(t).mean())


def fft_amplitude(y, dt, pad=1):
    """FFT en AMPLITUDE DE SINUS (et non en densite), fenetre de Hann.

    `pad` complete par des zeros. Cela n'ajoute AUCUNE information et
    n'ameliore pas la resolution reelle, mais interpole le spectre : sur
    une sinusoide amortie isolee, le sommet tombe alors a sa vraie place
    au lieu d'etre accroche au bin le plus proche. Indispensable pour la
    resonance de maille, dont la salve ne dure que quelques dizaines de ns.
    """
    w = np.hanning(len(y))
    n = int(len(y) * pad)
    sp = np.fft.rfft((y - y.mean()) * w, n=n)
    return np.fft.rfftfreq(n, dt), 2.0 * np.abs(sp) / w.sum()


def enveloppe_log(f, a, par_decade=140, fmin=1e5, fmax=1e9):
    """Maximum par bande log -- la lecture d'un recepteur a detection de
    crete, et le seul trace lisible : a 50 kHz de resolution les creux
    entre harmoniques descendent a -150 dB et noircissent la figure.
    """
    n = int(par_decade * np.log10(fmax / fmin))
    bords = np.logspace(np.log10(fmin), np.log10(fmax), n + 1)
    k = np.digitize(f, bords)
    fo, ao = [], []
    for i in range(1, len(bords)):
        m = k == i
        if m.any():
            fo.append(np.sqrt(bords[i - 1] * bords[i]))
            ao.append(a[m].max())
    return np.asarray(fo), np.asarray(ao)


def stft(y, dt, nperseg, hop):
    """FFT court terme, ecrite a la main : aucune dependance d'API."""
    w = np.hanning(nperseg)
    n = 1 + (len(y) - nperseg) // hop
    s = np.empty((nperseg // 2 + 1, n))
    for i in range(n):
        seg = y[i * hop:i * hop + nperseg]
        s[:, i] = 2.0 * np.abs(np.fft.rfft((seg - seg.mean()) * w)) / w.sum()
    return (np.fft.rfftfreq(nperseg, dt),
            (np.arange(n) * hop + nperseg / 2) * dt, s)


def peigne(f, a, f0, fmax=1e9):
    """Amplitude a chaque harmonique de f0 -- la seule chose qui existe.

    Un signal periodique n'a d'energie qu'aux multiples de sa frequence de
    decoupage. Entre deux harmoniques il n'y a que la fuite de la fenetre,
    qui descend ici a -150 dB : la tracer remplit la figure d'encre sans
    rien apprendre. On releve donc le maximum local dans +/- un pas de
    frequence autour de chaque multiple.
    """
    df = f[1] - f[0]
    k = np.arange(1, int(fmax / f0) + 1)
    fo, ao = [], []
    for n in k:
        c = n * f0
        m = (f >= c - 1.5 * df) & (f <= c + 1.5 * df)
        if m.any():
            fo.append(c)
            ao.append(a[m].max())
    return np.asarray(fo), np.asarray(ao)


def raie(f, a, fmin, fmax):
    """Frequence et amplitude du maximum dans une bande."""
    m = (f >= fmin) & (f <= fmax)
    i = int(np.argmax(a[m]))
    return float(f[m][i]), float(a[m][i])


def decroissance(t, y, f0):
    """Q sur une sonnerie libre longue. Rend (Q, tau, enveloppe, ajustement).

    La ligne de base est retiree par moyenne glissante sur deux periodes
    de l'oscillation, et non par une droite : apres la coupure le noeud
    rejoint Vin de facon exponentielle, ce qu'une droite ne decrit pas.
    L'ajustement ne porte que sur la plage ou l'enveloppe vaut entre 90 %
    et 2 % de sa valeur initiale : au-dessus on est encore dans le
    transitoire d'arret, au-dessous dans le bruit numerique.
    """
    from scipy.signal import hilbert
    nan = float("nan")
    dt = float(t[1] - t[0])
    n = max(5, int(round(2.0 / f0 / dt)))
    n += 1 - n % 2                      # impair : centrage exact
    k, noyau = (n - 1) // 2, np.ones(n) / n

    # mode="valid" et NON "same". Avec "same" numpy complete par des zeros,
    # si bien qu'en fin de trace la moyenne glissante s'effondre vers zero :
    # la ligne de base disparait, et `y - base` rend la tension CONTINUE
    # elle-meme. L'enveloppe y affiche alors 2 V d'oscillation la ou le
    # signal est plat a 20,000 V, l'ajustement traverse ce faux plateau et
    # sort un tau 25 fois trop grand. Constate.
    tv = t[k:len(t) - k]
    x = y[k:len(y) - k] - np.convolve(y, noyau, mode="valid")
    env = np.convolve(np.abs(hilbert(x)), noyau, mode="valid")
    tv = tv[k:len(tv) - k]

    emax = float(env.max())
    bon = env > max(0.02 * emax, 1e-3)
    idx = np.where(bon)[0]
    if len(idx) < 50:
        return dict(q=nan, tau=nan, t=tv, env=env, chute=nan,
                    ajust=np.full_like(env, nan))
    # PREMIER segment contigu seulement : au-dela, l'oscillation est eteinte
    # et tout ce qui depasse le seuil est du bruit numerique. Ajuster a
    # travers le trou relierait le debut de la decroissance a ce bruit.
    coupe = np.where(np.diff(idx) > 1)[0]
    if len(coupe):
        idx = idx[:coupe[0] + 1]
    if len(idx) < 50:
        return dict(q=nan, tau=nan, t=tv, env=env, chute=nan,
                    ajust=np.full_like(env, nan))
    p = np.polyfit(tv[idx], np.log(env[idx]), 1)
    tau = -1.0 / p[0] if p[0] < 0 else float("inf")
    # chute observee : si elle est faible, tau est une EXTRAPOLATION et non
    # une mesure. A dire, pas a cacher derriere un chiffre.
    chute = float(env[idx[0]] / env[idx[-1]])
    # l'ajustement n'est rendu que SUR SA PLAGE : prolonge sur toute la
    # trace il descend a 1e-35 et ecrase l'echelle logarithmique.
    return dict(q=float(np.pi * f0 * tau), tau=float(tau), t=tv, env=env,
                chute=chute, t_aj=tv[idx],
                ajust=np.exp(np.polyval(p, tv[idx])))


def facteur_qualite(t, y, f0):
    """Q depuis la decroissance de l'enveloppe : env ~ exp(-t/tau).

    Q = pi f0 tau. On retire une tendance lineaire (le noeud derive
    lentement vers Vin), on prend le module de la transformee de Hilbert,
    et on ajuste le logarithme. Les 10 premiers et 15 derniers pour cent
    sont ecartes : la transformee de Hilbert est fausse aux bords.
    """
    from scipy.signal import hilbert
    y = y - np.polyval(np.polyfit(t, y, 1), t)
    env = np.abs(hilbert(y))
    i0, i1 = int(0.10 * len(t)), int(0.85 * len(t))
    tt, ee = t[i0:i1], env[i0:i1]
    bon = ee > ee.max() * 1e-3
    if bon.sum() < 20:
        return float("nan"), float("nan")
    p = np.polyfit(tt[bon], np.log(ee[bon]), 1)
    tau = -1.0 / p[0] if p[0] < 0 else float("inf")
    return float(np.pi * f0 * tau), float(tau)


# ------------------------------------------------------------- decoupages

def periode(t, duty, fsw=ta.FSW):
    """Instants remarquables d'UNE periode, en partant d'un allumage.

    La fenetre de simulation commence a un allumage (tstart est un
    multiple de TSW et l'impulsion de grille monte sur ces multiples).
    """
    tsw = 1.0 / fsw
    return dict(tsw=tsw, t_off=duty * tsw)


def fin_conduction(t, il, t_off, seuil=0.02):
    """Instant ou le courant d'inductance s'annule apres la coupure."""
    m = t > t_off
    i = np.argmax(il[m] < seuil * il.max())
    return float(t[m][i]) if m.any() else float("nan")


# ------------------------------------------------------------------ traces

def figure_temps(don, duty, sortie, n_per=2):
    tsw = 1.0 / ta.FSW
    fig, ax = plt.subplots(2, 1, figsize=(16, 9), sharex=True,
                           height_ratios=[2, 1])
    for v in ("ideal", "constructeur"):
        t, s = don[v]["t"], don[v]["sig"]
        m = t <= n_per * tsw
        ax[0].plot(t[m] * 1e6, s["V(nsw)"][m], lw=.9, color=COULEUR[v],
                   label=ETIQ[v])
        ax[1].plot(t[m] * 1e6, s["I(Vl)"][m], lw=.9, color=COULEUR[v])
    ax[0].set_ylabel("nœud de commutation  V(nsw)   [V]")
    ax[1].set_ylabel("courant\ninductance [A]")
    ax[1].set_xlabel("temps  [µs]")
    ax[1].axhline(0, color=TRAIT, lw=.7, ls=":")
    for a in ax:
        a.grid(which="major", alpha=.35)
        a.grid(which="minor", alpha=.12)
        a.minorticks_on()
        for k in range(n_per + 1):
            a.axvline(k * tsw * 1e6, color=TRAIT, lw=.9, alpha=.75)
            a.axvline((k * tsw + duty * tsw) * 1e6, color=TRAIT, lw=.7,
                      alpha=.55, ls="--")
    ax[0].legend(loc="upper right", fontsize=10)
    ax[0].set_title(f"Temps mort : effet du modèle d'inductance — "
                    f"{ta.VIN:.0f} V / {ta.VOUT:.0f} V, "
                    f"{ta.FSW/1e3:.0f} kHz, D = {duty:.4f}\n"
                    "trait plein = allumage, tireté = coupure", fontsize=12)
    fig.tight_layout()
    fig.savefig(sortie, dpi=170)
    plt.close(fig)


def figure_mesuree(don, mes, duty, sortie, ref="constructeur",
                   comp="ideal", n_per=2):
    """Oscillogramme INSTRUMENTE sur deux periodes : 17 mesures portees.

    Les grandeurs sont RELEVEES sur la trace, pas recopiees d'une formule :
    les pentes de courant sont ajustees sur la rampe, la tension de palier
    est une mediane sur l'intervalle de conduction de la diode, et la
    decroissance de la sonnerie compare la premiere alternance a la
    derniere. Les valeurs theoriques figurent a cote, pour comparaison.
    """
    import sys
    sys.path.insert(0, str(ta.RACINE / ".claude/skills/oscillogrammes/scripts"))
    import oscillo as osc

    tsw = 1.0 / ta.FSW
    d = don[ref]
    t, v, il = d["t"], d["sig"]["V(nsw)"], d["sig"]["I(Vl)"]
    t_off = duty * tsw
    t_i0 = mes[ref]["t_i0"]
    f_bf, f_hf = mes[ref]["f_bf"], mes[ref]["f_hf"]

    def fen(a, b):
        return (t >= a) & (t <= b)

    def pente(a, b):
        m = fen(a, b)
        return float(np.polyfit(t[m], il[m], 1)[0])

    # --- pentes de courant, ajustees sur la partie droite des rampes
    di_montee = pente(0.15 * t_off, 0.85 * t_off)
    di_chute = pente(t_off + 0.15 * (t_i0 - t_off),
                     t_off + 0.80 * (t_i0 - t_off))
    # --- dV/dt a la coupure
    m = fen(t_off, t_off + 25e-9)
    dvdt = float(np.abs(np.diff(v[m]) / np.diff(t[m])).max())
    # --- palier de conduction de la diode
    v_pal = float(np.median(v[fen(t_off + .45 * (t_i0 - t_off),
                                  t_i0 - 25e-9)]))
    # --- sonnerie de temps mort : amplitude de la premiere et de la
    # derniere CRETE au-dessus de la valeur moyenne du temps mort.
    #   Ne PAS prendre (max-min)/2 sur une fenetre calee sur t_i0 : cette
    #   fenetre contient encore la chute depuis le palier de la diode, et
    #   rend 40 V la ou la sonnerie n'en fait que 23. On detecte donc les
    #   cretes, et on ignore la premiere demi-alternance de transition.
    from scipy.signal import find_peaks
    mm = fen(t_i0, tsw - 20e-9)
    t_m, v_m = t[mm], v[mm]
    ecart = int(0.6 / f_bf / float(np.diff(t_m).mean()))
    # Le courant s'annule AVANT que la tension ne quitte le palier de la
    # diode : la fenetre commence donc a 80 V, et une recherche de cretes
    # naive y trouve le palier lui-meme (62,9 V d'"amplitude" relevee au
    # lieu de 23). On repart du PREMIER CREUX, qui est le vrai debut de la
    # sonnerie.
    creux, _ = find_peaks(-v_m, distance=ecart, prominence=2.0)
    if len(creux):
        t_m, v_m = t_m[creux[0]:], v_m[creux[0]:]
    v_moy = float(v_m.mean())
    pics, _ = find_peaks(v_m, distance=ecart, prominence=2.0)
    amp1 = float(v_m[pics[0]] - v_moy)
    amp2 = float(v_m[pics[-1]] - v_moy)
    t_p1, t_p2 = float(t_m[pics[0]]), float(t_m[pics[-1]])
    t_p15 = float(t_m[pics[min(1, len(pics) - 1)]])
    i_pk = int(np.argmax(il[fen(0, tsw)]))
    t_vmax = float(t[fen(0, tsw)][int(np.argmax(v[fen(0, tsw)]))])
    v_max = float(v[fen(0, tsw)].max())
    t_vmin = float(t[fen(0, tsw)][int(np.argmin(v[fen(0, tsw)]))])
    v_min = float(v[fen(0, tsw)].min())
    i_moy = float(il[fen(0, tsw)].mean())
    v_on = float(v[fen(tsw - 3e-9, tsw)][0])

    C = COULEUR
    V, I = 0, 1                                     # indices de panneau
    # Onze reperes seulement sur la courbe. Les six autres grandeurs
    # restent au tableau sans pastille (`repere=False`) : dans les zones
    # denses -- salve de coupure, cretes de sonnerie -- une pastille de
    # plus ne renseigne rien et masque le trace.
    M = [
        dict(n=1, panneau=I, genre="intervalle", t1=0, t2=tsw, y=-0.95,
             libelle="période de découpage",
             valeur=f"{tsw*1e6:.3f} µs / {ta.FSW/1e3:.1f} kHz"),
        dict(n=2, panneau=I, genre="intervalle", t1=0, t2=t_off, y=-1.30,
             libelle=f"conduction interrupteur,  D = {duty:.4f}",
             valeur=f"{t_off*1e9:.0f} ns"),
        dict(n=3, panneau=I, genre="intervalle", t1=t_off, t2=t_i0,
             y=-1.65, libelle="décharge de l'inductance",
             valeur=f"{(t_i0-t_off)*1e9:.0f} ns"),
        dict(n=4, panneau=I, genre="intervalle", t1=t_i0, t2=tsw, y=-2.00,
             libelle="temps mort  (courant nul)",
             valeur=f"{(tsw-t_i0)*1e9:.0f} ns"),
        dict(n=5, panneau=I, genre="point", t=float(t[fen(0, tsw)][i_pk]),
             y=float(il[fen(0, tsw)][i_pk]), couleur=C[ref],
             libelle="courant crête",
             valeur=f"{float(il[fen(0,tsw)][i_pk]):.2f} A"),
        dict(n=6, panneau=I, genre="niveau", y=i_moy, t=0.42 * tsw,
             libelle="courant moyen = courant d'entrée",
             valeur=f"{i_moy:.3f} A"),
        dict(n=7, panneau=V, genre="point", t=t_vmax, y=v_max, couleur=C[ref],
             libelle="tension crête au dépassement",
             valeur=f"{v_max:.1f} V"),
        dict(n=8, panneau=V, genre="point", t=t_vmin, y=v_min,
             couleur=C[ref],
             libelle="minimum, écrêtage 3ᵉ quadrant",
             valeur=f"{v_min:.2f} V"),
        dict(n=9, panneau=V, genre="point", t=tsw - 2e-9, y=v_on,
             couleur=C[ref],
             libelle="tension À L'ALLUMAGE  (enjeu ZVS)",
             valeur=f"{v_on:.1f} V"),
        dict(n=10, panneau=V, genre="point", t=t_p1,
             y=float(np.interp(t_p1, t, v)), couleur=C[ref],
             libelle=f"1ʳᵉ crête de sonnerie  (/{v_moy:.1f} V moyen)",
             valeur=f"+{amp1:.1f} V"),
        dict(n=11, panneau=V, genre="point", t=t_off + 4e-9,
             y=float(np.interp(t_off + 4e-9, t, v)), couleur=C[ref],
             libelle="dV/dt à la coupure",
             valeur=f"{dvdt/1e9:.1f} V/ns"),
        # --- relevés sans repère sur la courbe
        dict(n=0, repere=False, libelle="pente de montée   /   théorie Vin/L",
             valeur=f"{di_montee/1e6:.2f} / {ta.VIN/ta.L_H/1e6:.2f} A/µs"),
        dict(n=0, repere=False,
             libelle="pente de descente   /   (Vout−Vin)/L",
             valeur=f"{di_chute/1e6:.2f} / {-(ta.VOUT-ta.VIN)/ta.L_H/1e6:.2f}"),
        dict(n=0, repere=False,
             libelle=f"palier diode  (Vout + {v_pal-ta.VOUT:.2f} V)",
             valeur=f"{v_pal:.1f} V"),
        dict(n=0, repere=False, libelle="résonance de MAILLE (coupure)",
             valeur=f"{f_hf/1e6:.1f} MHz / {1e9/f_hf:.1f} ns"),
        dict(n=0, repere=False, libelle="résonance de TEMPS MORT",
             valeur=f"{f_bf/1e6:.2f} MHz / {1e9/f_bf:.0f} ns"),
        dict(n=0, repere=False,
             libelle="dernière crête  →  décroissance",
             valeur=f"+{amp2:.1f} V   ÷{amp1/amp2:.2f}"),
    ]

    # Chaque variante a son PROPRE nombre de points : le solveur adapte son
    # pas independamment. Un masque calcule sur une base de temps ne peut
    # pas indexer l'autre -- il faut en decouper un par variante.
    mv = (t >= 0) & (t <= n_per * tsw)
    tc = don[comp]["t"]
    mc = (tc >= 0) & (tc <= n_per * tsw)
    panneaux = [
        ("nœud de commutation  V(nsw)   [V]", [
            (tc[mc], don[comp]["sig"]["V(nsw)"][mc], ETIQ[comp],
             dict(color=C[comp], lw=.9, alpha=.75)),
            (t[mv], v[mv], ETIQ[ref], dict(color=C[ref], lw=1.1))]),
        ("courant inductance   I(L)   [A]", [
            (tc[mc], don[comp]["sig"]["I(Vl)"][mc], "",
             dict(color=C[comp], lw=.9, alpha=.75)),
            (t[mv], il[mv], "", dict(color=C[ref], lw=1.1))]),
    ]
    osc.trace_annote(
        panneaux, M, sortie,
        titre=f"Oscillogramme mesuré — {ta.VIN:.0f} V → {ta.VOUT:.0f} V, "
              f"{ta.FSW/1e3:.0f} kHz, {mes[ref]['pout']:.2f} W — "
              f"{n_per} périodes\nmesures relevées sur « {ETIQ[ref]} » ; "
              f"valeurs théoriques entre parenthèses",
        xlim=(-0.05, n_per * tsw * 1e6 + 0.05),
        notes=("", f"écarts de « {ETIQ[comp]} » :",
               f"   tension crête        {mes[comp]['vpk']:.1f} V  "
               f"(au lieu de {mes[ref]['vpk']:.1f})",
               f"   puissance de sortie  {mes[comp]['pout']:.2f} W  "
               f"(au lieu de {mes[ref]['pout']:.2f})",
               f"   facteur de qualité   {mes[comp]['q_son']:.0f}  "
               f"(au lieu de {mes[ref]['q_son']:.0f})"))
    return sortie


def figure_zoom(don, mes, t_deb, t_fin, sortie):
    """Zoom sur l'intervalle a courant nul, toutes variantes, grille fine."""
    fig, ax = plt.subplots(figsize=(16, 9))
    for v, d in don.items():
        t, s = d["t"], d["sig"]
        m = (t >= t_deb - 0.05e-6) & (t <= t_fin + 0.02e-6)
        q = mes[v]["q_bf"]
        # `pkz` et `constructeur` se superposent EXACTEMENT : c'est le
        # resultat, mais sans tirete la courbe bleue disparait sous la verte.
        st = "--" if v == "pkz" else "-"
        ax.plot(t[m] * 1e6, s["V(nsw)"][m], lw=1.6 if v == "pkz" else 1.0,
                ls=st, color=COULEUR[v],
                label=f"{ETIQ[v]} — {mes[v]['f_bf']/1e6:.2f} MHz"
                      + (f", Q = {q:.0f}" if np.isfinite(q) else ""))
    ax.axvspan(t_deb * 1e6, t_fin * 1e6, color="#ffffff", alpha=.05,
               label="intervalle à courant nul")
    ax.set_xlabel("temps  [µs]")
    ax.set_ylabel("nœud de commutation  V(nsw)   [V]")
    ax.grid(which="major", alpha=.4)
    ax.grid(which="minor", alpha=.15)
    ax.minorticks_on()
    ax.set_title("Oscillation de temps mort — la DCR ne l'amortit pas, "
                 "la résistance parallèle oui", fontsize=12)
    ax.legend(loc="lower right", fontsize=10)
    fig.tight_layout()
    fig.savefig(sortie, dpi=170)
    plt.close(fig)


def figure_fft(don, mes, sortie):
    """Deux lectures : l'enveloppe sur la fenetre entiere (ce que verrait
    un recepteur) et le spectre du SEUL intervalle a courant nul, ou la
    raie de temps mort est isolee de tout le reste."""
    fig, ax = plt.subplots(2, 1, figsize=(16, 11))
    for v, d in don.items():
        fe, ae = peigne(*d["fft"], ta.FSW, fmax=F_AFFICHE)
        ax[0].semilogx(fe, 20 * np.log10(np.maximum(ae, 1e-9)),
                       lw=1.2, color=COULEUR[v], label=ETIQ[v], alpha=.9)
        f, a = d["fft_mort"]
        m = (f > 5e5) & (f <= 1e8)
        ax[1].semilogx(f[m], 20 * np.log10(np.maximum(a[m], 1e-9)),
                       lw=1.1, color=COULEUR[v], alpha=.9,
                       label=f"{ETIQ[v]} — {mes[v]['f_bf']/1e6:.2f} MHz")
    ax[0].set_title(f"Spectre de V(nsw) — amplitude à chaque harmonique de "
                    f"{ta.FSW/1e3:.0f} kHz, "
                    f"fenêtre de {ta.N_MES} périodes "
                    f"({ta.N_MES/ta.FSW*1e6:.0f} µs), Hann, "
                    f"Δf = {ta.FSW/ta.N_MES/1e3:.0f} kHz", fontsize=12)
    ax[1].set_title("Spectre du seul intervalle à courant nul — "
                    "la raie de temps mort, isolée", fontsize=12)
    for a_ in ax:
        a_.axvline(F_VALIDE, color=TRAIT, ls="--", lw=1.1)
        a_.set_xlabel("fréquence  [Hz]")
        a_.set_ylabel("amplitude de V(nsw)   [dBV]")
        a_.grid(which="major", alpha=.4)
        a_.grid(which="minor", alpha=.15)
        a_.xaxis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10)))
        a_.legend(loc="upper right", fontsize=9)
    ax[0].text(F_VALIDE * 1.1, ax[0].get_ylim()[0] + 6,
               "validité déclarée\ndu modèle Coilcraft", fontsize=9)
    fig.tight_layout()
    fig.savefig(sortie, dpi=170)
    plt.close(fig)


def figure_sonnerie(son, sortie):
    """Decroissance libre : la mesure propre du facteur de qualite."""
    fig, ax = plt.subplots(2, 1, figsize=(16, 10))
    emax = max(d["env"].max() for d in son.values())
    for v, d in son.items():
        ax[0].plot(d["t_plein"] * 1e6, d["y"], lw=.5, color=COULEUR[v],
                   alpha=.8,
                   label=f"{ETIQ[v]} — {d['f0']/1e6:.2f} MHz, "
                         f"τ = {d['tau']*1e6:.2f} µs, Q = {d['q']:.0f} "
                         f"(chute observée ×{d['chute']:.1f})")
        ax[1].semilogy(d["t"] * 1e6, np.maximum(d["env"], 1e-5), lw=1.2,
                       color=COULEUR[v])
        ax[1].plot(d["t_aj"] * 1e6, d["ajust"], lw=2.2, color="#ffffff",
                   ls=":", alpha=.85)
    ax[0].set_xlim(0, 8)
    ax[0].set_ylabel("nœud de commutation  V(nsw)   [V]")
    ax[0].set_xlabel("temps depuis l'arrêt de la grille  [µs]   "
                     "— 8 premières µs")
    # 1 mV en bas : c'est encore du signal. S'arreter a 5 mV cachait la
    # derniere decade de la decroissance, celle qui montre le mieux que la
    # droite d'ajustement tient jusqu'au bout.
    ax[1].set_ylim(1e-3, emax * 2)
    ax[1].set_ylabel("enveloppe  [V]   (échelle log)")
    ax[1].set_xlabel("temps depuis l'arrêt de la grille  [µs]   "
                     "— 30 µs entières ; pointillé noir = ajustement, "
                     "tracé sur sa seule plage")
    for a_ in ax:
        a_.grid(which="major", alpha=.4)
        a_.grid(which="minor", alpha=.15)
        a_.minorticks_on()
    ax[0].legend(loc="upper right", fontsize=9)
    ax[0].set_title("Sonnerie libre — la grille est coupée, le circuit est "
                    "livré à lui-même\nune droite en échelle log = une "
                    "décroissance exponentielle ; sa pente donne Q",
                    fontsize=12)
    fig.tight_layout()
    fig.savefig(sortie, dpi=170)
    plt.close(fig)


def figure_stft(don, duty, sortie, quelles=("ideal", "constructeur")):
    tsw = 1.0 / ta.FSW
    # 4096 points = 0,41 us : compromis assume. Plus court, la raie de
    # 3,7 MHz n'est plus resolue ; plus long, elle couvre tout le temps
    # mort et on perd la localisation. La frequence exacte se lit sur la
    # figure 03, pas ici.
    nper = 4096
    fig, ax = plt.subplots(len(quelles), 1, figsize=(16, 10), sharex=True,
                           sharey=True)
    for a, v in zip(np.atleast_1d(ax), quelles):
        t, y = don[v]["tu"], don[v]["yu"]
        m = t <= 2 * tsw
        f, tt, s = stft(y[m], DT_GRILLE, nper, nper // 32)
        db = 20 * np.log10(np.maximum(s, 1e-7))
        fm = (f >= 1e6) & (f <= 3e8)
        im = a.pcolormesh(tt * 1e6, f[fm] / 1e6, db[fm], shading="nearest",
                          cmap="magma", vmin=db[fm].max() - 45,
                          vmax=db[fm].max())
        a.set_yscale("log")
        a.set_ylabel(f"{ETIQ[v]}\n\nfréquence  [MHz]", fontsize=9)
        for k in range(3):
            a.axvline(k * tsw * 1e6, color="w", lw=.8, alpha=.5)
            a.axvline((k * tsw + duty * tsw) * 1e6, color="w", lw=.8,
                      alpha=.5, ls="--")
        fig.colorbar(im, ax=a, label="dBV", pad=.01)
    np.atleast_1d(ax)[-1].set_xlabel("temps  [µs]")
    np.atleast_1d(ax)[0].set_title(
        "FFT court terme — où vit chaque raie dans la période\n"
        f"fenêtre glissante de {nper*DT_GRILLE*1e9:.0f} ns "
        f"(Δf = {1/(nper*DT_GRILLE)/1e6:.1f} MHz) ; "
        "trait plein = allumage, tireté = coupure", fontsize=12)
    fig.tight_layout()
    fig.savefig(sortie, dpi=170)
    plt.close(fig)


def figure_impedance(ac, sortie):
    fig, ax = plt.subplots(figsize=(16, 8))
    for v, (f, z) in ac.items():
        # La crete de la variante ideale n'est pas une valeur : la resonance
        # y est si aigue que le balayage, meme a 3000 points par decade, ne
        # tombe pas sur son sommet. Le chiffre affiche est un PLANCHER.
        borne = "≥ " if v in ("ideal", "dcr_reelle") else ""
        ax.loglog(f, z, lw=1.4, color=COULEUR[v],
                  label=f"{ETIQ[v]} — crête {borne}{z.max():.0f} Ω "
                        f"à {f[np.argmax(z)]/1e6:.1f} MHz")
    ax.axvline(F_VALIDE, color=TRAIT, ls="--", lw=1.1)
    ax.set_xlabel("fréquence  [Hz]")
    ax.set_ylabel("|Z| de l'inductance seule   [Ω]")
    ax.grid(which="major", alpha=.4)
    ax.grid(which="minor", alpha=.15)
    ax.set_title("Impédance propre de l'inductance — l'écart "
                 "d'amortissement se lit sur l'impédance de crête",
                 fontsize=12)
    ax.legend(loc="upper left", fontsize=10)
    fig.tight_layout()
    fig.savefig(sortie, dpi=170)
    plt.close(fig)
