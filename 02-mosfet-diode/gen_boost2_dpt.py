"""Chapitre 2 (extension 200-800 kHz) -- netlist boost en topologie
DOUBLE-PULSE, portable ngspice ET LTspice.

Deux differences avec gen_boost2_tech.py (le generateur d'origine) :

1. SORTIE RAIDE. Le couple Cout + Rload est remplace par une source de
   tension de 80 V. Consequences : plus d'ondulation de sortie, plus de
   transitoire d'etablissement, et surtout plus de reservoir a Q eleve --
   le piege numerique du chapitre 1 (Q = R*sqrt(C/L) > 10 impose
   reltol=1e-5) disparait par construction. Topologiquement, un boost a
   sortie raide EST un double-pulse test qui tourne en continu, donc les
   pertes de commutation sont directement comparables aux E_on/E_off de
   banc.

   PRIX A PAYER, sous-estime au moment de retenir cette topologie : le
   courant devient hypersensible au rapport cyclique. A l'equilibre
       I_L = [Vin - (1-D) Vout] / R_eff
   A D=0.7500 le courant est nul, a D=0.7600 il vaut ~8 A. Il faut donc
   D a 4 decimales -> resolution par secante (2-3 iterations depuis
   l'estimee analytique), plus une condition initiale sur I(L1) pour
   demarrer AU point de fonctionnement plutot que d'y converger.

2. ENTREE IDEALE. Cin infini = source de tension directe. Supprime une
   constante de temps sans rien couter : la source fournit l'ondulation
   de courant d'inductance, ce que fait un Cin infini par definition.

--------------------------------------------------------------------------
CE QUE MESURE SPICE, ET CE QU'IL NE MESURE PAS
--------------------------------------------------------------------------
SPICE mesure ici les pertes de CONDUCTION (Rds du switch, Vf de la diode,
DCR de l'inductance), les courants, et le mode CCM/DCM. Il ne mesure PAS :

  - la perte Coss : elle depend de Coss(V), fortement non lineaire, et un
    condensateur lineaire en SPICE donnerait 1/2 C V^2 avec le mauvais C
    (erreur de 23 % sur le Si ROHM, voir switch_energy). Elle vient donc
    du modele analytique, integre sur la courbe datasheet.
  - la perte de grille Qg*Vgs*fsw : la grille est pilotee par une source
    ideale en simulation, donc cette puissance n'apparait nulle part dans
    le bilan simule. Elle vient aussi du modele analytique.

Ce partage est assume et documente plutot que maquille : chaque mecanisme
est attribue a l'outil qui le connait vraiment. Le Coss present dans la
netlist ne sert qu'au CONDITIONNEMENT NUMERIQUE du noeud de commutation.
"""
from __future__ import annotations

import math
from pathlib import Path

import switch_energy as se
from switch_diode_models import DIODES, SWITCHES, diode_spice_model

# --------------------------------------------------------------------------
# Matrice ISO-MODE : L choisie a chaque frequence pour placer la frontiere
# DCM/CCM a ~15 W, de sorte que tous les points partagent la meme carte de
# mode et que l'effet frequence ne soit pas confondu avec un changement de
# mode. L = Vin^2 (1-Vin/Vout) / (2 fsw P_seuil) = 10/fsw a 20->80 V.
#
# Les seuils obtenus tiennent dans 13.6-16.7 W, et le courant de VALLEE de
# l'inductance a 40 W (= le courant que la diode porte a l'instant ou le
# switch s'allume, donc ce qui declenche le recouvrement) reste entre 1.19
# et 1.34 A sur toute la plage : les conditions de commutation sont donc
# comparables d'un bout a l'autre du balayage.
# --------------------------------------------------------------------------
# UNE SEULE FAMILLE : SER2211. Une version anterieure melangeait SER2211 et
# SER1390 pour serrer les seuils dans 13.6-16.7 W. Le DCR y sautait de 3.15
# a 21 mOhm (facteur 6.7), soit 0.19 point de rendement -- l'ordre de
# grandeur meme de l'effet de technologie recherche. Rester dans la famille
# ramene l'etendue a 3.15-8.95 mOhm (facteur 2.8) et le biais a 0.06 point :
# on corrige la cause au lieu de normaliser l'effet apres coup.
#
# Prix paye : les seuils s'etalent de 11.1 a 20.8 W au lieu de 13.6-16.7,
# parce que la serie ne porte pas de 15 ni de 22 uH (3.0 / 5.3 / 8.2 / 12 /
# 27 / 33 / 47). C'est ce qui impose de deplacer le point 20 W a 25 W, voir
# POUTS plus bas.
#
# Benefice secondaire : deux paires partagent la MEME piece -- 400/500 kHz
# en 27 uH, 600/800 kHz en 12 uH. Chaque paire isole un effet de frequence
# pur, a DCR rigoureusement identique.
MATRICE_ISO_MODE = [
    # fsw_Hz,  L_H,     DCR_typ, reference,        P_seuil_W, I_vallee_A
    (200e3, 47.0e-6, 8.95e-3, "SER2211-473MED", 15.96, 1.22),
    (300e3, 33.0e-6, 8.95e-3, "SER2211-333MED", 15.15, 1.26),
    (400e3, 27.0e-6, 6.84e-3, "SER2211-273MED", 13.89, 1.33),
    (500e3, 27.0e-6, 6.84e-3, "SER2211-273MED", 11.11, 1.46),
    (600e3, 12.0e-6, 3.15e-3, "SER2211-123MED", 20.83, 0.98),
    (800e3, 12.0e-6, 3.15e-3, "SER2211-123MED", 15.62, 1.24),
]

# Switches retenus pour l'extension. Les quatre premiers portent la
# demonstration du CALIBRE (meme classe de tension, tailles de puce de
# 7 a 75 mOhm) ; les GaN portent celle de la TECHNOLOGIE.
SWITCHES_V2 = ("Si", "FDT86113LZ", "BSC070N10NS5", "EPC2007C", "EPC2052")
DIODES_V2 = ("Schottky", "Ultrafast")

VIN, VOUT, POUT = 20.0, 80.0, 40.0

# Capacite de jonction de la diode. SANS ELLE, ngspice diverge sur 25 des
# 60 cellules ("Timestep too small ... trouble with dmod-instance d1") :
# une diode a modele purement exponentiel, en serie avec une inductance,
# n'a rien qui borne son dI/dt au blocage, et le probleme devient
# infiniment raide. Toute diode reelle a une Cj ; l'omettre n'est pas
# "plus ideal", c'est non physique.
#
# 100 pF est un ORDRE DE GRANDEUR representatif des Schottky 100 V de ce
# calibre (le chapitre a releve 28 a 130 pF sur trois candidats reels,
# voir REAL_DIODES dans switch_diode_models.py) -- PAS une valeur
# datasheet de la piece generique simulee ici. Son influence sur les
# pertes mesurees est verifiee a part (voir controle_cj.py).
CJO_DIODE_F = 100e-12
N_PERIODES_ETABLISSEMENT = 12   # avant la fenetre de mesure
N_PERIODES_MESURE = 8           # fenetre d'integration
PTS_PAR_PERIODE = 2000          # impose dtmax ; critique pour les cretes


def duty_estimee(vin: float, vout: float, r_eff: float, i_cible: float) -> float:
    """D tel que I_L = [Vin - (1-D)Vout]/R_eff vaille i_cible.

    Point de depart de la secante. R_eff = resistance vue en moyenne sur
    la periode (Rds pendant D, Vf/I de la diode pendant 1-D, DCR partout).
    """
    return 1.0 - (vin - i_cible * r_eff) / vout


def duty_estimee_dcm(pout: float, lh: float, fsw: float,
                     vin: float = VIN, vout: float = VOUT) -> float:
    """D en conduction DISCONTINUE, ou la loi n'a rien a voir avec le CCM.

    En DCM le courant repart de zero a chaque periode : le rapport cyclique
    ne fixe plus le RAPPORT de tension (c'est la charge qui le fixe), il
    fixe le COURANT CRETE, donc l'energie transferee par cycle.
        Pout = Vin^2 D^2 / (2 L fsw) * Vout/(Vout-Vin)
    d'ou D. A 5 W / 200 kHz / 47 uH cela donne D = 0.42, contre 0.75 en
    CCM : amorcer une cellule DCM avec l'estimateur CCM vise ~16 W et aucun
    encadrement raisonnable ne redescend jusqu'a 5 W. C'est ce qui faisait
    echouer 108 des 360 cellules.
    """
    return math.sqrt(2.0 * pout * lh * fsw * (vout - vin) / (vin**2 * vout))


def r_eff_estimee(switch: str, diode: str, dcr: float, i: float, d: float) -> float:
    """Resistance equivalente moyenne sur la periode, pour l'amorcage."""
    rds = se.fiche(switch)["rds_ohm"]
    from switch_diode_models import diode_vf_at
    r_diode = diode_vf_at(diode, i) / max(i, 1e-6)
    return dcr + d * rds + (1.0 - d) * r_diode


def netlist(switch: str, diode: str, fsw: float, lh: float, dcr: float,
            duty: float, il0: float, reltol: float = 1e-5) -> str:
    """Netlist SPICE portable (ngspice et LTspice) du boost double-pulse."""
    s = se.fiche(switch)
    tsw = 1.0 / fsw
    ton = duty * tsw
    # Temps de commutation : Qgd / courant de grille du driver retenu.
    # Meme convention que le S9 du README d'origine, pour que les deux
    # volets du chapitre restent comparables.
    i_drv_on, i_drv_off = 4.0, 6.0
    tr = max(s["qgd_c"] / i_drv_on, 1e-10)
    tf = max(s["qgd_c"] / i_drv_off, 1e-10)
    tstart = N_PERIODES_ETABLISSEMENT * tsw
    tstop = tstart + N_PERIODES_MESURE * tsw
    dtmax = tsw / PTS_PAR_PERIODE
    # Coss au point de fonctionnement, pour le conditionnement numerique
    # du noeud. Valeur EQUIVALENTE EN TEMPS (Qoss/V), pas Coss(50V) :
    # c'est celle qui donne la bonne constante de temps de transition.
    coss_tr = se.qoss(switch, VOUT) / VOUT

    return f"""* boost double-pulse -- {switch} / {diode} / {fsw/1e3:.0f} kHz / {lh*1e6:.0f} uH
* genere par gen_boost2_dpt.py -- ne pas editer a la main
.param vin={VIN} vout={VOUT}

V1   vin  0    DC {{vin}}
* sortie RAIDE : pas de reservoir, donc pas de piege de facteur Q
Vo   vout 0    DC {{vout}}

L1   vin  nl   {lh:.6e} ic={il0:.6f}
Rdcr nl   nsw  {dcr:.6e}

M1   nsw  ng   0 0 MSW
Vg   ng   0    PULSE(0 {s['vgs']:.1f} 0 {tr:.4e} {tf:.4e} {ton:.6e} {tsw:.6e})
* conditionnement numerique du noeud de commutation (voir en-tete du
* generateur : la perte Coss NE vient PAS d'ici, elle est analytique)
Cosn nsw  0    {coss_tr:.6e}

D1   nsw  nd   DMOD
* sonde de courant de diode : ngspice n'expose pas I(D1) dans un .save
* (il faudrait @d1[id], syntaxe non portable). Une source de 0 V en serie
* est la forme portable -- elle ne change rien au circuit.
Vd   nd   vout DC 0

.model MSW NMOS(VTO=2 KP=200 RD={s['rds_ohm']:.6f} RS=0 IS=1e-12)
{diode_spice_model(diode, 'DMOD')[:-1]} CJO={CJO_DIODE_F:.3e} VJ=0.6 M=0.5)

.options reltol={reltol:g} abstol=1e-12 vntol=1e-9 chgtol=1e-15
.options method=gear maxord=2
.tran {dtmax:.6e} {tstop:.6e} {tstart:.6e} {dtmax:.6e} uic
* pas de @m1[id] : syntaxe ngspice, non portable LTspice. Le courant de
* switch se deduit par KCL au noeud nsw (I(L1)-I(D1)), exact a l'etat
* passant ou le Coss est decharge et ne debite rien.
.save I(L1) I(V1) I(Vo) I(Vd) V(nsw) V(ng)
.end
"""


# Puissances balayees. Le seuil DCM/CCM etant place a ~15 W a TOUTES les
# frequences par construction (matrice iso-mode), les deux points bas sont
# en DCM et les quatre hauts en CCM, de facon identique sur toute la plage
# de frequence -- c'est ce qui rend les surfaces lisibles : une bascule de
# mode au meme endroit partout, au lieu d'une frontiere qui serpente.
# LES POINTS DE CHARGE DOIVENT S'ECARTER DES SEUILS, qui s'etalent de
# 11.11 W (500 kHz) a 20.83 W (600 kHz).
#
# 25 W et non 20 W : a 20 W le point serait en DCM a 600 kHz et en CCM
# partout ailleurs, et une difference de MODE se lirait comme une
# difference de frequence.
#
# 50 W et non 60 W : c'est le maximum de la specification. Une version
# anterieure caracterisait jusqu'a 60 W, donc AU-DELA du domaine
# d'emploi -- les marges de saturation et les temperatures de jonction
# y etaient pessimistes sans que cela corresponde a un cas reel.
#
# 8 W et non 10 W : a 10 W le point n'est qu'a 10 % sous le seuil de
# 500 kHz. Juste a la frontiere, ni la loi DCM ni la loi CCM ne vaut, le
# solveur de rapport cyclique n'encadre plus la cible -- resultat, UNE
# SEULE piece sur cinq avait une mesure a 500 kHz / 10 W, et deux autres
# y divergeaient franchement. A 8 W la marge passe a 28 % au point le plus
# serre, et a 62 % a 600 kHz.
POUTS = (5.0, 8.0, 25.0, 30.0, 40.0, 50.0)


def cellules(pouts: tuple[float, ...] = POUTS) -> list[dict]:
    """Toutes les cellules du balayage etendu (frequence x puissance)."""
    out = []
    for fsw, lh, dcr, ref, p_seuil, i_vallee in MATRICE_ISO_MODE:
        for p in pouts:
            for sw in SWITCHES_V2:
                for di in DIODES_V2:
                    out.append(dict(switch=sw, diode=di, fsw=fsw, lh=lh,
                                    dcr=dcr, l_ref=ref, p_seuil=p_seuil,
                                    i_vallee=i_vallee, pout=p,
                                    mode_attendu="CCM" if p > p_seuil else "DCM"))
    return out


def pertes_analytiques(switch: str, fsw: float) -> dict:
    """Les deux mecanismes que SPICE ne voit pas (voir en-tete)."""
    return dict(p_coss=se.p_coss(switch, VOUT, fsw),
                p_gate=se.p_gate(switch, fsw))


if __name__ == "__main__":
    cs = cellules()
    print(f"{len(cs)} cellules = {len(MATRICE_ISO_MODE)} frequences"
          f" x {len(SWITCHES_V2)} switches x {len(DIODES_V2)} diodes\n")
    print("Matrice iso-mode :")
    print(f"{'fsw':>7s} {'L':>7s} {'reference':16s} {'P_seuil':>8s}"
          f" {'I_vallee':>9s} {'mode@40W':>9s}")
    for fsw, lh, dcr, ref, ps, iv in MATRICE_ISO_MODE:
        print(f"{fsw/1e3:5.0f}k {lh*1e6:5.0f}u {ref:16s} {ps:6.2f} W"
              f" {iv:7.2f} A {'CCM' if POUT > ps else 'DCM':>9s}")

    i_cible = POUT / (0.99 * VIN)
    print(f"\nAmorcage du rapport cyclique (cible I_in = {i_cible:.3f} A) :")
    for sw in SWITCHES_V2:
        fsw, lh, dcr = MATRICE_ISO_MODE[0][:3]
        r = r_eff_estimee(sw, "Schottky", dcr, i_cible, 0.75)
        d = duty_estimee(VIN, VOUT, r, i_cible)
        print(f"  {sw:14s} R_eff={r*1e3:6.1f} mOhm -> D0 = {d:.5f}")

    ex = netlist("Si", "Schottky", 200e3, 47e-6, 8.95e-3, 0.7525, 2.02)
    Path("exemple_dpt.cir").write_text(ex, encoding="utf-8")
    print(f"\nExemple de netlist ecrit : exemple_dpt.cir ({len(ex)} caracteres)")
