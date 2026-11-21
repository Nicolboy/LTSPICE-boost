"""Surtension DRAIN du transistor — ce que le chapitre 4 n'avait pas mesuré.

CE QUI MANQUAIT. Le chapitre 4 a mesuré la surtension de la DIODE, et sa loi
ΔV = L_σ·di/dt y est vérifiée à 0,4 % sans paramètre libre. Mais le drain du
transistor subit un AUTRE événement : la coupure du courant d'inductance par
le canal, pas le recouvrement de la diode. On ne peut pas transporter la loi
de l'un à l'autre, et c'est pourtant le transistor qui a la marge la plus
serrée :

    V8PA22      200 V x 0,8 - 80 = 80 V de budget
    IPD530N15N3 150 V x 0,8 - 80 = 40 V de budget   <- le contraignant

CE QUE LE MODELE APPORTE, ET QU'IL NE FAUT PAS RATER. Les QUATRE modeles
portent LEURS PROPRES inductances de boitier -- il ne faut donc surtout
pas en rajouter a l'exterieur, ce serait les compter deux fois :

    IPD530N15N3  DPAK       Ls=2n     Ld=1n     -> 3,00 nH
    FDD770N15A   DPAK       Ls=2,666n Ld=0,1n   -> 2,77 nH
    IPD320N20N3  DPAK       Ls=1,5n   Ld=1n     -> 2,50 nH
    BSC900N20NS3 SuperSO8   Ls=460p   Ld=100p   -> 0,56 nH

Le DPAK part donc avec ~2,2 a 2,4 nH de handicap AVANT le moindre routage.
Le choix de boitier « plus robuste et plus facile a changer » se paie en
marge de tension, et c'est exactement la grandeur en question.

BROCHAGE LU dans chaque .SUBCKT, pas devine (faute C3) :
    Infineon : drain gate source Tj Tcase   (5 noeuds)
    onsemi   : .SUBCKT FDD770N15A 2 1 3     (3 noeuds, 1=G 2=D 3=S)

NI `ic=` NI `uic` : c'est la cause racine de trois heures perdues (faute D1).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parents[1]
LIB = RAC / "lib_spice_commun"

VIN, VOUT, FSW, L_H, DCR = 20.0, 80.0, 200e3, 47e-6, 10.7e-3
RG = 10.0                      # tranche au chapitre 4
C_NOEUD = 50e-12               # conditionnement, 1/2.C.V^2.f = 16 mW a 200 kHz

# ref, bibliotheque, calibre, tenue, L_boitier (Ls+Ld), boitier
PIECES = {
    "ipd530": ("IPD530N15N3", "OptiMOS3_150V_LTSpice.lib", 53e-3, 150.0,
               3.0e-9, "DPAK"),
    "ipd320": ("IPD320N20N3", "OptiMOS3_200V_LTSpice.lib", 32e-3, 200.0,
               2.5e-9, "DPAK"),
    "bsc900": ("BSC900N20NS3", "OptiMOS3_200V_LTSpice.lib", 90e-3, 200.0,
               0.56e-9, "SuperSO8"),
    # onsemi : .SUBCKT FDD770N15A 2 1 3 -- TROIS noeuds, ordre drain gate
    # source (le DPAK numerote 1=G, 2=D, 3=S), pas de broches thermiques.
    # Il porte AUSSI ses inductances : Ldrain 0,1 nH + Lsource 2,666 nH
    # = 2,77 nH, LU dans le fichier. Comparable aux Infineon DPAK.
    "fdd770": ("FDD770N15A", "FDD770N15A.lib", 61e-3, 150.0,
               2.77e-9, "DPAK"),
}
NOEUDS = {"ipd530": 5, "ipd320": 5, "bsc900": 5, "fdd770": 3}
SOUS_REP = {"fdd770": "onsemi"}
L_PCB = [1e-9, 2e-9, 5e-9, 10e-9, 20e-9, 40e-9]      # routage SEUL


def texte_lib(p: Path) -> str:
    """Inline du modele. Huit instances LTspice partageant un meme `.inc`
    se figent sur `Changing Tseed` ; le meme fichier passe seul en 6 s."""
    return p.read_text(encoding="utf-8", errors="replace")


def netlist(piece: str, l_pcb: float, i_cible: float = 2.6,
            n_etab: int = 12, n_mes: int = 4) -> str:
    ref, lib, rds, vbr, l_boit, boit = PIECES[piece]
    # DOUBLE-PULSE, ET PAS UN CONVERTISSEUR AUTO-COHERENT.
    #
    # Premiere tentative : rapport cyclique calcule pour viser 2,6 A, par
    # I = [Vin - (1-D).Vout]/R_boucle. Resultat : le courant mesure allait
    # de 0,18 a 2,71 A selon la piece, donc LES QUATRE NE COUPAIENT PAS LE
    # MEME COURANT et les surtensions n'etaient pas comparables.
    #
    # Cause : la formule ignore la chute directe de la diode. Sur le fil du
    # rasoir de la sortie raide, 0,5 V de Vf divisent le courant par 30 --
    # verifie. Aucune formule ne sera robuste ici.
    #
    # Le double-pulse supprime le probleme : on charge l'inductance sous Vin
    # pendant t_on = L.I/Vin, ce qui donne le courant VOULU exactement, puis
    # on coupe et on mesure. Identique pour les quatre pieces, par
    # construction. C'est le banc du chapitre 2 et de banc-diode/.
    ton = L_H * i_cible / VIN
    t_gap = 2.0e-6
    t_p2 = 1.0e-6
    t0, t1 = ton - 0.2e-6, ton + t_gap + t_p2 + 1.0e-6
    modele = texte_lib(LIB / SOUS_REP.get(piece, "Infineon") / lib)
    diode = texte_lib(LIB / "Vishay" / "V8PA22.lib") \
        if (LIB / "Vishay" / "V8PA22.lib").exists() else None

    # DV8PA22 est declare par `.MODEL D`, PAS par `.SUBCKT` : prefixe D,
    # jamais X. Le gendarme refuse l'inverse depuis le 2026-11-21.
    #
    # ET IL FAUT INLINER LA BIBLIOTHEQUE, pas seulement tester sa presence :
    # la premiere version lisait le fichier et ne l'inserait jamais, d'ou
    # `Undefined model "dv8pa22"`. Attrape par le cas temoin de campagne(),
    # avant que les 24 cas du lot ne partent.
    if diode:
        d_ligne, lib_diode = "D1   nda  nd   DV8PA22", diode
    else:
        d_ligne = "D1   nda  nd   DMOD"
        lib_diode = (".model DMOD D(IS=3.5e-6 N=1.05 RS=11m CJO=400p M=0.5 "
                     "VJ=0.5 BV=200 IBV=1m TT=1n)")

    # AUCUNE inductance de boitier ajoutee a l'exterieur : les QUATRE
    # modeles la portent en interne. L'onsemi a `Ldrain 2 5 0.1e-9` et
    # `Lsource 3 7 2.666e-9`, soit 2,77 nH -- verifie dans le fichier, pas
    # suppose. En ajouter dessus la compterait DEUX FOIS.
    if NOEUDS[piece] == 3:
        bloc_m = f"XM1  nsw  ng   0  {ref}"
    else:
        bloc_m = (f"XM1  nsw  ng   0  ntj ntc {ref}\n"
                  f"Rtj  ntj  0    1meg\n"
                  f"Vtc  ntc  0    DC 25")
    return f"""* Surtension DRAIN -- {ref} {boit}, {vbr:.0f} V, {rds*1e3:.0f} mOhm
* L_boitier {l_boit*1e9:.2f} nH + L_pcb {l_pcb*1e9:.1f} nH
* {VIN:.0f} V -> {VOUT:.0f} V, 47 uH, {FSW/1e3:.0f} kHz, Rg = {RG:.0f} Ohm
.param vin={VIN} vout={VOUT}

V1   vin  0    DC {{vin}}
* sortie RAIDE : pas de reservoir, donc pas de piege de facteur Q
Vo   vout 0    DC {{vout}}

L1   vin  nl   {L_H:.6e}
Rdcr nl   nsw  {DCR:.6e}

* le transistor, modele constructeur, brochage LU dans le .SUBCKT
{bloc_m}
Rg1  ngd  ng   {RG:.6g}
* DOUBLE-PULSE : charge a {i_cible:.2f} A, coupure (c'est la qu'on mesure),
* puis seconde impulsion courte pour voir le reamorcage.
Vg   ngd  0    PWL(0 0 1n 10 {ton:.6e} 10 {ton+2e-9:.6e} 0
+ {ton+t_gap:.6e} 0 {ton+t_gap+2e-9:.6e} 10
+ {ton+t_gap+t_p2:.6e} 10 {ton+t_gap+t_p2+2e-9:.6e} 0)

* CONDITIONNEMENT du noeud de commutation. Sans cette capacite le pas de
* temps s'effondre a 1e-16 s des qu'un modele encapsule y bascule une source
* comportementale. 1/2.C.V^2.f = 16 mW, dans l'INTERRUPTEUR, pas dans la
* mesure de surtension.
Cosn nsw  0    {C_NOEUD:.6e}

* INDUCTANCE DE MAILLE : seulement le ROUTAGE. Celle du boitier est DEJA
* dans le modele ({l_boit*1e9:.2f} nH), il ne faut pas la compter deux fois.
Lb   nsw  nda  {l_pcb:.6e}
{d_ligne}
Vd   nd   vout DC 0

{modele}
{lib_diode}

.options reltol=1e-3 abstol=1e-12 vntol=1e-9 chgtol=1e-15
.options method=gear maxord=2 plotwinsize=0
* cshunt : les modeles OptiMOS 200 V echouent sans lui des t = 1e-12 s,
* sur `xm1:x1:e_eds6#branch` -- une source comportementale interne sans
* capacite a son noeud. Pas un reglage de confort : sans ca, zero cas.
.options cshunt=1e-15
* NI ic= NI uic -- cause racine de trois heures (D1)
.tran 0 {t1:.6e} 0 100p

.save V(nsw) V(nda) V(nd) I(L1) I(Vd) I(Vo)
.meas TRAN vdmax MAX V(nsw)        FROM {t0:.6e} TO {t1:.6e}
.meas TRAN vdamax MAX V(nda)       FROM {t0:.6e} TO {t1:.6e}
.meas TRAN ilmax MAX I(L1)         FROM {t0:.6e} TO {t1:.6e}
.meas TRAN pout AVG {VOUT}*I(Vo)   FROM {t0:.6e} TO {t1:.6e}
.end
"""


if __name__ == "__main__":
    n = netlist("ipd530", 10e-9)
    print(n[:900])
    print(f"\n... netlist de {len(n.splitlines())} lignes")
