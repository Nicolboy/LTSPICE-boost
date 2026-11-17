"""Architecture 2 sous LTspice : CCM 400 kHz, MOSFET Si + diode Schottky.

Pendant de `gen_dcm_ltspice.py`, meme topologie double-pulse (la source Vo
remplace condensateur de sortie et charge) et meme methode de bilan, pour
que les deux architectures soient comparables poste a poste.

COMPOSANTS
----------
  - inductance WE-HCF 100 uH (74437429203101), valeurs du modele SPICE
    constructeur Wurth, recopiees en elements discrets plutot qu'appelees
    par .include : ca evite toute question de hierarchie sur la mesure du
    cuivre, et le modele n'est qu'un reseau RLC a quatre elements.
  - MOSFET BSC360N15NS3, modele Infineon, variante `_L1` : elle est
    ISOTHERME (E1 fixe Tj a {TEMP}) la ou le modele de base porte un
    reseau de Cauer dont les constantes de temps, de l'ordre de 20 ms,
    ne s'etabliraient jamais sur un run de 60 us.
  - diode V8PA15 150 V / 8 A.

MESURE DES PERTES DU MOSFET
---------------------------
Le modele Infineon calcule LUI-MEME sa dissipation instantanee : dans la
variante _L1, `G_power` somme metal de source, grille, metal de drain et
coeur (par I(Vp)), et l'injecte dans le noeud thermique. C'est exactement
la methode par elements etablie au chapitre 2, faite par le constructeur,
et elle exclut d'office le stockage capacitif reversible.

    P_mosfet = I(xm1:g_power)

CE QUE VAUT Rp DU MODELE WURTH
------------------------------
Rp (18,3 kOhm aux bornes) est un amortissement de resonance propre, PAS
un modele de pertes fer : excite par le creneau de 400 kHz il dissipe de
l'ordre de 60 mW, quand REDEXPERT donne 16,7 mW de pertes AC au point
nominal. On le garde dans le circuit, parce qu'il porte la dynamique HF,
mais sa dissipation est reportee a part et ne vaut pas comme perte fer.

LE RAPPORT CYCLIQUE EST RAIDE EN CCM, ET L'ETABLISSEMENT TRES LONG
------------------------------------------------------------------
Avec les deux tensions imposees, l'equilibre des volt-secondes ne laisse
que les chutes resistives pour fixer le courant : dI/dD vaut environ
860 A par unite de rapport cyclique, donc il faut D a 1e-4 pres. Pire,
la constante de temps du courant vaut L/Reff = 104,8 uH / 93 mOhm, soit
1,1 ms -- 450 periodes de decoupage. Attendre l'etablissement depuis un
courant nul est hors de portee : 1350 periodes a 0,25 ns de pas font
34 millions de points.

On POSE donc le courant initial par `.ic I(L1)`, et le rapport cyclique
n'a plus qu'a limiter la DERIVE sur la fenetre de mesure. A 1e-4 pres il
reste 8 mV d'erreur de volt-seconde, soit 76 A/s, soit 5 mA sur 70 us :
negligeable. Six periodes suffisent alors a etablir les transitoires
rapides, et le courant moyen mesure donne la puissance reelle.
"""
from __future__ import annotations

import math
from pathlib import Path

VIN, VOUT = 19.0, 80.0
FSW = 400e3

# WE-HCF 100 uH -- lib_spice_commun/WurthElektronik/.../sub/WE-HCF.lib,
# subckt 2920_74437429203101_100u
L_H, DCR, R_PAR, C_PAR = 104.807e-6, 0.0359, 18328.0, 13.548e-12

L_BOUCLE = 20e-9      # identique a l'archi 1 : routage commun aux deux
RG_EXT = 2.0          # Rg interne du BSC360N15NS3 = 2,1 Ohm
VGS = 10.0            # les OptiMOS sont specifies a Vgs = 10 V

MOSFET = "BSC360N15NS3_L1"
LIB_MOS = Path(r"C:\Users\Nicolas\workspace_ccstheia\lib_spice_commun"
               r"\Infineon\OptiMOS3_150V_LTSpice.lib")

# V8PA15, Vishay doc 87658 rev. 16-Jun-2020.
#   IS/N/RS : les DEUX points de la table p.2 a 25 degC (0,78 V a 4,0 A ;
#   1,10 V a 8,0 A) avec N=1,05 pose (une TMBS), d'ou RS=75,3 mOhm. La
#   corde des deux points vaut 80 mOhm : la lecture graphique anterieure,
#   a 41,9 mOhm, etait fausse d'un facteur 1,8.
#   CJO/VJ/M : pente prise sur la decade 10-100 V de la Fig.5 p.3
#   (M=0,72), ancrage sur le point tabule 510 pF a 4,0 V. Donne 67 pF a
#   80 V -- la valeur tabulee a bas VR n'a aucun sens pour le blocage.
#   TT=0 : Schottky, pas de charge de recouvrement.
# V8PA22 200 V retenue (cf. gen_dcm_ltspice.py pour l'ajustement).
DIODE = ("DV8PA22", "D(IS=1.08e-11 N=1.05 RS=0.0128 CJO=811p VJ=3.36 "
                    "M=0.9 FC=0.5 TT=0 EG=0.69 XTI=2 BV=400 IBV=1e-4)")

N_ETAB = 4           # periodes d'etablissement (le courant est POSE)
N_MES = 4            # periodes mesurees


def duty_ccm(i_l: float, vf: float = 0.57, rds: float = 0.0288,
             rd: float = 0.0753) -> float:
    """Rapport cyclique donnant un courant moyen i_l, chutes resistives
    comprises. Equilibre des volt-secondes sur une periode :

        D (Vin - i(Rdcr+Rds)) + (1-D)(Vin - i*Rdcr - Vf - i*Rd - Vout) = 0
    """
    a = VIN - i_l * DCR                       # terme commun
    on = a - i_l * rds
    off = a - vf - i_l * rd - VOUT
    return -off / (on - off)


def puissance(i_l: float) -> float:
    return VIN * i_l


def netlist(duties: tuple[float, ...], il_init: float, 
            l_boucle: float = L_BOUCLE, fsw: float = FSW,
            dtmax: float = 0.25e-9, temp: float = 25.0) -> str:
    tsw = 1.0 / fsw
    # Le retard du premier creneau se regle au COMPROMIS. Nul, le solveur
    # echoue des le premier pas (e_eds2) : le point de fonctionnement sort
    # du Gmin stepping, pas de Newton direct, et l'etat interne du modele
    # n'est pas assez propre pour encaisser un front immediat. D'une
    # periode entiere, l'inductance se vide dans la sortie a (Vin-Vout)/L
    # = -587 kA/s et les 1,2 A poses par .ic tombent a -0,12 A.
    # 250 ns laissent le solveur s'etablir ; les 147 mA perdus au passage
    # sont rattrapes par l'iteration sur le rapport cyclique.
    td = 250e-9
    t_etab = td + N_ETAB * tsw
    t0 = td + N_ETAB * tsw          # phase calee sur les fronts de grille
    t1 = t0 + N_MES * tsw
    tr = 2.0e-9                      # fronts de grille d'un driver Si
    if len(duties) == 1:
        bal = f".param duty={duties[0]:.7f}"
    else:
        bal = ".step param duty list " + " ".join(f"{d:.7f}" for d in duties)
    return f"""* Architecture 2 -- {MOSFET} + V8PA15, CCM {fsw/1e3:.0f} kHz
* genere par gen_ccm_ltspice.py -- ne pas editer a la main
.lib {LIB_MOS}

.param TSW={tsw:.6e} LB={l_boucle:.4e} RGEXT={RG_EXT}
{bal}
.temp {temp:.1f}

V1   vin  0    DC {VIN}
Vo   vout 0    DC {VOUT}

* --- inductance WE-HCF 100 uH : L + DCR en serie, Rp et Cp aux bornes.
* Rp porte l'amortissement de resonance propre, pas les pertes fer.
L1   vin  nl   {L_H:.6e}
Rdcr nl   nsw  {DCR:.4e}
Cpar vin  nsw  {C_PAR:.4e}
* Rp du modele Wurth RETIREE : ce n'est pas un modele de pertes fer mais
* un amortissement de resonance propre a 4,2 MHz, et Coilcraft ne fournit
* aucun equivalent pour l'archi 1 (son R1=230 Ohm est en SERIE avec la
* capacite parasite, pas en parallele). La garder donnait a l'archi 2 un
* poste de 63 mW sans homologue. Les pertes fer viennent desormais des
* calculateurs constructeur, des deux cotes : symetrique et mieux source.

* --- MOSFET : modele Infineon isotherme (drain gate source)
XM1  nsw  ng   nss  {MOSFET}
Vs   nss  0    DC 0
Rg   ngd  ng   {{RGEXT}}
Vg   ngd  0    PULSE(0 {VGS} {td:.3e} {tr:.3e} {tr:.3e} {{duty*TSW}} {{TSW}})

* --- inductance de maille de commutation, dans la branche diode (cf.
* gen_dcm_ltspice.py : la placer en serie avec L1 n'aurait aucun effet)
Lb   nsw  nda  {{LB}}

* --- diode Schottky V8PA15
D1   nda  nd   {DIODE[0]}
Vd   nd   vout DC 0

.model {DIODE[0]} {DIODE[1]}

* Tolerances NETTEMENT plus laches que celles de l'archi 1, volontairement.
* Le modele Infineon embarque un pseudo-circuit thermique ou le courant
* porte des WATTS et la tension des DEGRES, relies par des resistances de
* 1 uOhm : abstol=1e-13 y demande 0,1 pW de resolution et vntol=1e-9 des
* nanovolts sur des microohms. Avec les reglages de l'archi 1 le solveur
* produisait 66 219 avertissements de relachement de tolerance et
* n'aboutissait pas. Les fronts du MOSFET Si durent ~10 ns, contre moins
* d'une ns pour le GaN : ce relachement ne coute pas de precision ici,
* et la convergence est verifiee en divisant le pas par deux.
* cshunt=1e-15 : 1 fF a la masse sur chaque noeud. C'est 1e-5 du Coss du
* transistor, donc sans effet electrique, mais ca regularise le jacobien
* et supprime les echecs immediats sur e_eds7 au point de fonctionnement.
.options reltol=1e-4 abstol=1e-10 vntol=1e-6 chgtol=1e-14 plotwinsize=0 cshunt=1e-15
.ic I(L1)={il_init:.5f}
* pas de uic : le point de fonctionnement est resolu avec I(L1) contraint,
* ce qui place nsw a Vout+Vf et rend le demarrage coherent.
* tstart = 0 IMPERATIVEMENT : avec tstart={t_etab:.3e} le solveur echouait
* PILE a cet instant (e_eds2, une capacite du coeur du modele), alors que
* le meme circuit va au bout en sauvant depuis zero. On paie quelques
* megaoctets de .raw, pas de la precision.
.tran 0 {t1:.6e} 0 {dtmax:.3e}

.save V(vin) V(nsw) V(ng) V(nss) V(nda) V(nd) V(ngd) I(L1) I(V1) I(Vd) I(Vg)
.save I(xm1:g_power)

* --- grandeurs de fonctionnement
.meas TRAN pout  AVG {VOUT}*I(Vd)       FROM {t0:.6e} TO {t1:.6e}
.meas TRAN pin   AVG {-VIN}*I(V1)       FROM {t0:.6e} TO {t1:.6e}
.meas TRAN il    AVG I(L1)              FROM {t0:.6e} TO {t1:.6e}
.meas TRAN ilrms RMS I(L1)              FROM {t0:.6e} TO {t1:.6e}
.meas TRAN ipk   MAX I(L1)              FROM {t0:.6e} TO {t1:.6e}
.meas TRAN imin  MIN I(L1)              FROM {t0:.6e} TO {t1:.6e}
.meas TRAN vdrev MIN (V(nda)-V(nd))     FROM {t0:.6e} TO {t1:.6e}
* bornes du courant pour le terme de STOCKAGE : tant que le courant derive,
* l'inductance absorbe 0,5*L*d(i^2)/dt, qui apparait sinon comme une perte
* fantome dans Pin-Pout. A 1,8 A elle valait 0,83 W sur 2,42 W de pertes.
.meas TRAN il0   FIND I(L1) AT={t0:.9e}
.meas TRAN il1   FIND I(L1) AT={t1:.9e}
.meas TRAN vpk   MAX V(nsw)             FROM {t0:.6e} TO {t1:.6e}
.meas TRAN vmin  MIN V(nsw)             FROM {t0:.6e} TO {t1:.6e}

* --- pertes, par elements DISSIPATIFS uniquement
* pmos : dissipation calculee par le modele constructeur lui-meme
.meas TRAN pmos  AVG I(xm1:g_power)                          FROM {t0:.6e} TO {t1:.6e}
.meas TRAN pdio  AVG (V(nda)-V(nd))*I(Vd)                    FROM {t0:.6e} TO {t1:.6e}
.meas TRAN pcu   AVG I(L1)*I(L1)*{DCR:.4e}                   FROM {t0:.6e} TO {t1:.6e}
.meas TRAN prge  AVG (V(ngd)-V(ng))*(V(ngd)-V(ng))/{RG_EXT}  FROM {t0:.6e} TO {t1:.6e}
.meas TRAN pvg   AVG -V(ngd)*I(Vg)                           FROM {t0:.6e} TO {t1:.6e}
.end
"""


if __name__ == "__main__":
    import run_ccm                                   # noqa: F401
