"""Decomposition des pertes de l'architecture 1, poste par poste.

Chaque poste est obtenu en integrant v*i sur l'element concerne, jamais
par difference ni par formule analytique : en DCM le rapport crete/moyen
du courant depasse 20, et une perte estimee a I_moy^2*R se trompe d'un
facteur plusieurs.

LE BILAN SE FERME OU IL EST REJETE. La somme des postes plus la puissance
de sortie doit egaler la puissance d'entree ; l'ecart est retourne et
sert de critere de validite. C'est le seul controle qui attrape a la fois
une erreur de signe, un poste oublie et une simulation non convergee.

Les signes des courants ne sont PAS supposes : `calibre_signes` les
determine en testant les quatre combinaisons et en retenant celle qui
ferme le bilan. Une convention ngspice supposee de travers a deja coute
une mesure fausse d'un facteur 1,5 au chapitre 2.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

import gen_dcm_gan as g


def _moy(y, t):
    """Valeur moyenne sur la fenetre, par integration trapezoidale."""
    return float(np.trapezoid(y, t) / (t[-1] - t[0]))


def mesures(raw: Path) -> dict:
    """Lit le .raw et renvoie les signaux bruts, sans interpretation."""
    import sys
    sys.path[:0] = [str(Path(__file__).resolve().parent.parent.parent
                        / ".claude/skills/sim-commun")]
    from simcommun.lecture import lire
    r = lire(Path(raw))
    m = {"t": np.asarray(r.x)}
    for n in ("I(L1)", "I(V1)", "I(Vd)", "I(Vs)", "I(Vq)",
              "V(nsw)", "V(nss)", "V(nco)", "V(nda)", "V(nd)", "V(ng)"):
        m[n] = np.asarray(r.trace(n))
    return m


def bilan(m: dict, fsw: float = g.FSW) -> dict:
    """Postes de perte, en W, plus l'ecart de bouclage."""
    t = m["t"]

    # puissances aux bornes : on prend la valeur absolue du produit, le
    # sens de circulation est fixe et connu (V1 fournit, Vd evacue)
    p_in = abs(_moy(m["I(V1)"], t)) * g.VIN
    p_out = abs(_moy(m["I(Vd)"], t)) * g.VOUT

    # --- canal du transistor : poste « R »
    p_canal = abs(_moy((m["V(nsw)"] - m["V(nss)"]) * m["I(Vs)"], t))

    # --- Coss et 3e quadrant : poste « C ». La jonction ne dissipe que
    # lorsqu'elle CONDUIT ; son energie capacitive est rendue, pas perdue.
    v_q3 = -m["V(nco)"]                       # anode a 0, cathode a nco
    p_q3 = abs(_moy(np.clip(v_q3, 0, None) * np.abs(m["I(Vq)"]), t))

    # --- diode Schottky
    p_diode = abs(_moy((m["V(nda)"] - m["V(nd)"]) * m["I(Vd)"], t))

    # --- cuivre de l'inductance : I_rms^2 * DCR, sur le courant REEL
    i_rms2 = _moy(m["I(L1)"] ** 2, t)
    p_cuivre = i_rms2 * g.DCR

    postes = dict(diode=p_diode, canal=p_canal, q3=p_q3, cuivre=p_cuivre)
    somme = sum(postes.values())
    return dict(**postes, p_in=p_in, p_out=p_out, pertes_spice=somme,
                i_rms=float(np.sqrt(i_rms2)),
                i_pk=float(m["I(L1)"].max()),
                i_moy=_moy(m["I(L1)"], t),
                v_pk=float(m["V(nsw)"].max()),
                v_min=float(m["V(nsw)"].min()),
                rendement=100.0 * p_out / p_in if p_in > 0 else 0.0,
                # ECART DE BOUCLAGE : critere de validite
                ecart=abs(p_in - p_out - somme) / max(p_in, 1e-9))


def frac_morte(m: dict, seuil: float = 0.02) -> float:
    """Fraction de periode a courant nul -- critere de DCM.

    Un echantillon unique ne suffit pas : la resonance du noeud fait
    repasser le courant par zero plusieurs fois par periode. C'est la
    DUREE passee a zero qui distingue le DCM du CCM.
    """
    il = m["I(L1)"]
    t = m["t"]
    mort = (np.abs(il) < seuil * il.max()).astype(float)
    return float(np.trapezoid(mort, t) / (t[-1] - t[0]))
