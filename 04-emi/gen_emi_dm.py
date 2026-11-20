"""Etape B -- premier spectre conduit, mode differentiel.

MONTAGE. Batterie -> LISN double 5 uH/50 ohms -> condensateur d'entree ->
convertisseur DCM. La tension est relevee sur la broche MEAS du LISN, cote
ligne positive, et convertie en dBuV.

CE QUI EST REEL ET CE QUI NE L'EST PAS, a dire avant de lire un chiffre :

  reel        le GaN (modele constructeur EPC), la diode (Vishay V8PA22),
              l'inductance (modele a 4 elements synthetise du datasheet
              SER2013-472), le condensateur d'entree (modele Wurth), le
              LISN (topologie normative, controlee par balayage .ac).
  absent      le chassis, donc AUCUN mode commun. Ce spectre est du MODE
              DIFFERENTIEL PUR. Le mode commun, d'ordinaire dominant,
              viendra a l'etape D.
  indetermine l'amortissement de l'inductance (Rp), balaye entre les
              bornes du corpus -- le spectre sort en ENVELOPPE.

PIEGE DE DEMARRAGE. Le LISN place 5 uH en serie avec le condensateur
d'entree : cela forme un circuit resonnant a quelques dizaines de kHz,
tres peu amorti, dont l'etablissement prend des MILLISECONDES. Sans
conditions initiales, il faudrait simuler mille periodes de decoupage pour
que ce transitoire s'eteigne, et le spectre serait celui du demarrage. On
impose donc `.ic` sur le courant du LISN et la tension d'entree.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
LIB = RACINE / "lib_spice_commun"

VIN, VOUT, FSW = 19.0, 80.0, 400e3

# INDUCTANCES -- parametres du modele CONSTRUCTEUR Coilcraft, aplatis depuis
# Model1D (CoilcraftTemplates.lib) :
#
#     Lin --[Rs]-- N001 --+-- [Rp] --+-- Lout
#                         +-- [L]  --+
#                         +--[Rc+Cp]-+
#
# Rp (PkZ au catalogue) est l'impedance de CRETE a la resonance propre :
# c'est elle qui gouverne l'amortissement, et elle est PUBLIEE ici. Le
# chapitre 3 la balayait faute de donnee pour le SER2013-472, qui n'a
# aucun modele publie. Ce n'est plus necessaire.
#                 (nom,            L,      Rs,      Cp,        Rp,      Rc)
INDUCTANCES = {
    "47u": ("SER2211-473", 47.0e-6, 0.0107, 8.183e-12, 7315.8901, 140.0),
    "4u7": ("SER1360-472",  4.7e-6, 0.0055, 4.578e-12, 1778.0,      0.0),
}
IND_DEFAUT = "47u"
L_BOUCLE, RG_EXT, VGS = 20e-9, 1.0, 5.0
P_VISEE = 47.0
# RESEAU D'ENTREE -- (etiquette, C, ESR, ESL, R_serie)
#
# ARCHITECTURE RETENUE PAR LE CONCEPTEUR, trois branches en parallele.
# La troisieme porte une resistance PLACEE, pas une ESR : elle amortit la
# resonance du filtre d'entree sans dissiper le courant continu.
#
# VALEURS POSEES, NON RELEVEES : l'ESR et l'ESL des electrolytiques. Des
# Panasonic haute temperature ont ete indiques sans reference precise.
# L'ESR du 220 uF commande la marge de Middlebrook -- de -3,4 dB (polymere
# a 2 mOhm, instable sans la branche amortie) a +28,9 dB (100 mOhm). A
# remplacer des que la reference est connue.
C_BULK220 = ("220 uF Al (ESR POSEE)",     220e-6, 20.0e-3,  8.0e-9, 0.0)
C_AMORTIE = ("1000 uF Al + 500 mOhm",    1000e-6, 20.0e-3, 12.0e-9, 0.5)
C_MLCC    = ("1 uF X7R 0805 - 885012207103", 1.0e-6, 5.31e-3, 283e-12, 0.0)

VARIANTES = {
    "complet":   [C_BULK220, C_AMORTIE, C_MLCC],   # l'architecture retenue
    "sans_amor": [C_BULK220, C_MLCC],              # ce que la R rapporte
}

DIODE = ("DV8PA22",
         "D(is=7e-05 rs=0.00741429 n=2.62377 xti=13.7366 bv=220 eg=0.71 "
         "cjo=6.85e-10 m=1 vj=5.36 tt=7.73585e-10 ikf=0 fc=0.5 "
         "ibv=1e-10 isr=-7.00037e-07 trs1=-0.00514056)")


def sous_circuit(fichier, nom):
    txt = Path(fichier).read_bytes().decode("utf-8", "replace")
    m = re.search(rf"^\.subckt\s+{re.escape(nom)}\b.*?^\.ends.*?$",
                  txt, re.S | re.M | re.I)
    if not m:
        raise LookupError(f"{nom} absent de {Path(fichier).name}")
    return m.group(0).strip()


def duty_dcm(pout, vin=VIN, eta=0.97, l_h=None):
    l_h = INDUCTANCES[IND_DEFAUT][1] if l_h is None else l_h
    return math.sqrt(2.0 * pout * l_h * FSW * (VOUT - vin)
                     / (eta * vin**2 * VOUT))


def bloc_cin(cin):
    """Branches RLC du reseau d'entree, et les `.ic` qui vont avec.

    Une branche par reference : l'ESL de l'une ne se melange pas a celle de
    l'autre, et chaque resonance propre reste ou elle est. La resistance
    serie `rd`, quand elle est non nulle, est un AMORTISSEUR PLACE -- elle
    s'ajoute a l'ESR et c'est tout l'interet de la branche.
    """
    lignes, ics, desc, ctot = [], [], [], 0.0
    for i, (lib, c, esr, esl, rd) in enumerate(cin):
        rtot = esr + rd
        ctot += c
        srf = 1.0 / (2 * math.pi * math.sqrt(esl * c))
        desc.append(f"*   {lib}"
                    f"  ->  {c*1e6:.1f} uF, R {rtot*1e3:.2f} mOhm"
                    f"{' (dont ' + format(rd*1e3, '.0f') + ' PLACES)' if rd else ''},"
                    f" ESL {esl*1e9:.1f} nH, SRF {srf/1e3:.2f} kHz")
        lignes.append(f"Rcin{i} nin   nca{i} {rtot:.4e}")
        lignes.append(f"Lcin{i} nca{i} ncb{i} {esl:.4e}")
        lignes.append(f"Ccin{i} ncb{i} nret  {c:.4e}")
        ics.append(f"V(nca{i})={VIN:.3f} V(ncb{i})={VIN:.3f}")
    return "\n".join(desc), "\n".join(lignes), " ".join(ics), ctot


def duty_ccm():
    """Rapport cyclique en conduction continue : 1 - Vin/Vout."""
    return 1.0 - VIN / VOUT


def netlist(rp=None, duty=None, n_etab=24, n_mes=16, dtmax=0.5e-9, cin=None,
            ind=IND_DEFAUT):
    """Banc complet.

    `ind` designe l'inductance dans INDUCTANCES. `rp` ne sert plus qu'a
    FORCER un amortissement different de celui du constructeur ; a None,
    c'est la valeur publiee qui s'applique -- et c'est ce qu'on veut.
    """
    nom_l, l_h, dcr_l, cp_l, rp_l, rc_l = INDUCTANCES[ind]
    if rp is not None:
        rp_l = rp
    tsw = 1.0 / FSW
    # CCM des que la frontiere est franchie : 7,1 W pour 47 uH, donc
    # toujours ici. Le rapport cyclique n'y depend plus de la charge.
    d_i = VIN * duty_ccm() / (l_h * FSW)
    ccm = (P_VISEE / 0.97 / VIN) >= d_i / 2
    if duty is None:
        # PASSER l_h : sans lui, duty_dcm retombe sur l'inductance par
        # defaut et on applique le rapport cyclique d'une 47 uH a une
        # 4,7 uH -- 94 A dans la self, constate.
        duty = duty_ccm() if ccm else duty_dcm(P_VISEE, l_h=l_h)
    t0, t1 = n_etab * tsw, (n_etab + n_mes) * tsw
    i_in = P_VISEE / 0.97 / VIN                 # courant continu d'entree
    cin = VARIANTES["bulk"] if cin is None else cin
    desc_cin, lignes_cin, ic_cin, ctot = bloc_cin(cin)
    return f"""* Etage 1 {'CCM' if ccm else 'DCM'} derriere un LISN CISPR 25 -- mode differentiel
* genere par gen_emi_dm.py -- ne pas editer a la main
.lib {LIB / "EPC/EPCGaNLibrary.lib"}

.param TSW={tsw:.6e} duty={duty:.6f}
.temp 25

Vbat bp   0    DC {VIN}

* --- retour a la masse : UN SEUL LISN, sur la ligne positive. Avec deux
* reseaux, le retour flotte sur 5 uH et le condensateur d'entree voit ses
* DEUX bornes deriver ensemble -- 0,04 V entre elles au demarrage. Mesure
* de MODE DIFFERENTIEL pur, ce qui est l'objet de l'etape B ; le mode
* commun demande un chassis, absent du modele (etape D).
Rret nret 0    1e-6

* --- LISN CISPR 25, APLATI et non appele en sous-circuit : `.ic` ne sait
* pas viser le courant d'une inductance interne a un .subckt, et sans
* conditions initiales la resonance LISN/Cin met des millisecondes a
* s'eteindre. Valeurs identiques a lisn_cispr25.lib, qui fait foi.
*   Le C_batt de la ligne negative n'est pas repris : la borne moins de la
*   batterie EST la masse ici, le condensateur y serait degenere.
C_batt_p bp   0        1u
L_line_p bp   nlp      5u
R_damp_p bp   nlp      10k
R_par_p  nlp  nin      0.001
C_meas_p nin  mp       0.1u
R_term_p mp   0        50






* --- reseau d'entree, APLATI. Total {ctot*1e6:.3f} uF.
* Le sous-circuit Wurth place sa capacite entre deux noeuds INTERNES :
* `.ic` aux broches ne peut donc pas la charger, elle demarre a 0 V, et le
* convertisseur part sur une entree nulle. Aplati, `.ic` l'atteint.
* Une branche par reference : melanger les ESL confondrait les resonances.
{desc_cin}
{lignes_cin}

* --- inductance : {nom_l}, modele CONSTRUCTEUR Coilcraft aplati.
* Mode : {'CCM' if ccm else 'DCM'}.  Rp = {rp_l:.1f} ohm est PUBLIE (PkZ au
* catalogue), il n'est plus balaye. Aplati parce que `.ic` ne sait pas
* viser un noeud interne a un .subckt.
Vl   nin  nla  DC 0
Rs_l nla  n1l  {dcr_l:.4e}
Rp_l n1l  nsw  {rp_l:.6g}
L1   n1l  nsw  {l_h:.4e}
Cp_l n1l  n2l  {cp_l:.4e}
Rc_l n2l  nsw  {max(rc_l, 1e-9):.6g}

* --- commutation
X1   ng   nsw  nss  EPC2207
Vs   nss  nret DC 0
Rg   ngd  ng   {RG_EXT}
Vg   ngd  nret PULSE(0 {VGS} 0 0.15n 0.15n {{duty*TSW}} {{TSW}})
Lb   nsw  nda  {L_BOUCLE:.4e}
D1   nda  nd   {DIODE[0]}
Vd   nd   nout DC 0
Vo   nout nret DC {VOUT}

.model {DIODE[0]} {DIODE[1]}


* Conditions initiales : sans elles, la resonance LISN/Cin -- quelques
* dizaines de kHz, tres peu amortie -- met des millisecondes a s'eteindre
* et le spectre serait celui du demarrage, pas du regime etabli.
.ic I(L_line_p)={i_in:.4f} V(nin)={VIN:.3f} {ic_cin}

.options reltol=1e-4 abstol=1e-11 vntol=1e-7 plotwinsize=0
.tran 0 {t1:.6e} {t0:.6e} {dtmax:.3e} uic

.save V(mp) V(nin) V(nsw) I(Vl) I(Vbat) I(Vd)
.meas TRAN pout AVG {VOUT}*I(Vd)  FROM {t0:.6e} TO {t1:.6e}
.meas TRAN iin  AVG -I(Vbat)      FROM {t0:.6e} TO {t1:.6e}
.meas TRAN vmp  RMS V(mp)         FROM {t0:.6e} TO {t1:.6e}
.end
"""
