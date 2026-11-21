"""Banc de PERTES -- distinct du banc EMI, et pour une raison de fond.

LE BANC EMI A UNE SOURCE DE TENSION EN SORTIE. Elle fige Vout, ce qui est
exactement ce qu'il faut pour relever un spectre : le point de mesure est le
LISN, et la sortie ne doit pas bouger. Mais a rapport cyclique fige, une
source de tension ne definit PAS la puissance -- en conduction continue le
courant d'inductance diverge, et les cas du 2026-11-20 sont sortis entre
16,2 et 46,9 W. On ne compare pas des rendements a des puissances qui
varient d'un facteur 3.

D'OU CE BANC : charge RESISTIVE, R = Vout^2 / P. La puissance est alors
fixee par la charge, en DCM comme en CCM, et le rapport cyclique n'a plus
qu'a amener Vout au voisinage de 80 V.

Le condensateur de sortie est gros ET pre-charge par `.ic` : sans lui il
faudrait simuler des millisecondes d'etablissement. Avec 220 uF charges a
80 V, la derive sur la fenetre de mesure reste sous 0,2 V a 40 W.

MESURE DES PERTES -- la faute a ne pas refaire :

    p = moyenne(v * i)        et JAMAIS moyenne(|v * i|)

La valeur absolue rend chaque echantillon positif, donc tout echange
reactif -- Coss contre la maille, ondulation de L -- compte comme une
perte. Constate : 17,4 W de transistor annonces a cote d'un rendement de
97,87 %, deux chiffres qui se contredisent dans la meme ligne.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import gen_emi_dm as g                                    # noqa: E402

VOUT, FSW = 80.0, 400e3
L_BOUCLE, RG, VGS = 20e-9, 10.0, 5.0
C_OUT = 220e-6
ETA = 0.97

# Quatre diodes, meme calibre de tension sauf la Si qui n'existe pas au-dela
# de 200 V. Les trois SiC sont des sous-circuits ; la Si est un `.model`.
DIODES = {
    "inf":  ("IDH04G65C6_L1", g.LIB / "Infineon" / "CoolSiC_G6_650V.lib",
             "Infineon CoolSiC G6 · 4 A / 650 V", 650.0, 2),
    "c6d":  ("C6D04065A", g.LIB / "Wolfspeed" / "C6D04065A.lib",
             "Wolfspeed C6D · 4 A / 650 V", 768.0, 5),
    "c3d":  ("C3D16065D1", g.LIB / "Wolfspeed" / "C3D16065D1.lib",
             "Wolfspeed C3D · 16 A / 650 V (génération antérieure)", 650.0, 6),
    "si":   (None, None, "Vishay V8PA22 · 8 A / 200 V (Schottky Si)", 220.0, 0),
}


def mode(l_h, pout, vin):
    """DCM ou CCM, et le rapport cyclique qui va avec."""
    d_ccm = 1.0 - vin / VOUT
    d_i = vin * d_ccm / (l_h * FSW)
    i_moy = pout / ETA / vin
    if i_moy >= d_i / 2:
        return "CCM", d_ccm
    return "DCM", math.sqrt(2.0 * pout * l_h * FSW * (VOUT - vin)
                            / (ETA * vin ** 2 * VOUT))


def netlist(ind, dio, pout, vin=20.0, n_etab=12, n_mes=8, dtmax=0.5e-9,
            rg=RG, lb=L_BOUCLE, duty=None):
    nom_l, l_h, dcr_l, cp_l, rp_l, rc_l = g.INDUCTANCES[ind]
    nom_d, lib_d, libelle, vbr, broches = DIODES[dio]
    m, d0 = mode(l_h, pout, vin)
    duty = d0 if duty is None else duty
    tsw = 1.0 / FSW
    t0, t1 = n_etab * tsw, (n_etab + n_mes) * tsw
    rload = VOUT ** 2 / pout
    i_in = pout / ETA / vin

    if dio == "si":
        bloc_d = f"D1   nda  nout  {g.DIODE[0]}"
        mod_d = f".model {g.DIODE[0]} {g.DIODE[1]}"
    elif broches == 2:
        bloc_d = f"XD1  nda  nout  {nom_d}"
        mod_d = g.texte_lib(lib_d)
    elif broches == 5:                       # A K Case Tj Tc
        bloc_d = (f"XD1  nda  nout ncase ntj ntc {nom_d}\n"
                  f"Rcase ncase nret 1e9\nVtc  ntc  0    25")
        mod_d = g.texte_lib(lib_d)
    else:
        # C3D : `.SUBCKT C3D16065D1 NC A K Case Tj Tc` — la PREMIÈRE broche
        # n'est pas connectée, l'anode est la DEUXIÈME. Câblé à l'aveugle
        # par analogie avec le C6D, la diode débitait 0,00 W : elle
        # convergeait parfaitement et ne conduisait rien. Un brochage se LIT
        # dans le `.SUBCKT`, il ne se devine pas.
        bloc_d = (f"XD1  nnc  nda  nout ncase ntj ntc {nom_d}\n"
                  f"Rnc  nnc  nret 1e9\nRcase ncase nret 1e9\n"
                  f"Vtc  ntc  0    25")
        mod_d = g.texte_lib(lib_d)

    return f"""* Banc de PERTES -- {libelle}
* {nom_l} {l_h*1e6:.1f} uH, {m}, Vin {vin:.0f} V -> {VOUT:.0f} V, {pout:.0f} W
* genere par gen_pertes.py -- ne pas editer a la main
.lib {g.LIB / "EPC/EPCGaNLibrary.lib"}

.param TSW={tsw:.6e} duty={duty:.6f}
.temp 25

Vbat bin  0    DC {vin}
Rret nret 0    1e-6

* --- entree : un simple decouplage, le LISN n'a pas lieu d'etre ici.
* Ce banc mesure des PERTES, pas un spectre : le reseau stabilisateur
* ajouterait une resonance a etablir sans rien apporter au bilan.
Rin  bin  nin  5m
Cin  nin  nret 100u

* --- inductance : modele constructeur Coilcraft aplati
Vl   nin  nla  DC 0
Rs_l nla  n1l  {dcr_l:.4e}
Rp_l n1l  nsw  {rp_l:.6g}
L1   n1l  nsw  {l_h:.4e}
Cp_l n1l  n2l  {cp_l:.4e}
Rc_l n2l  nsw  {max(rc_l, 1e-9):.6g}

* --- commutation
X1   ng   nsw  nss  EPC2207
Vs   nss  nret DC 0
Rg   ngd  ng   {rg:.4g}
Vg   ngd  nret PULSE(0 {VGS} 0 0.15n 0.15n {{duty*TSW}} {{TSW}})
Lb   nsw  nda  {lb:.4e}
{bloc_d}

* --- SORTIE : SOURCE DE TENSION RAIDE, et c'est deliberе.
*
* Une charge RC pre-chargee par `.ic` paraissait plus physique. Elle est
* inutilisable : avec `uic`, LTspice met a zero tout ce que `.ic` ne nomme
* pas -- Y COMPRIS LES NOEUDS INTERNES DES MODELES ENCAPSULES. Le CoolSiC
* d'Infineon echoue alors sur sa propre capacite de jonction
* (`xd1:x$sd:x$cap:e_b#branch`), et AUCUN modele a sous-circuit n'y
* survivrait. Retirer `uic` ne sauve rien : 320 ohms sur 220 uF font 70 ms
* d'etablissement, soit 28 000 periodes de decoupage.
*
* Une source raide impose 80 V au noeud quelles que soient les conditions
* initiales : l'initialisation devient consistante pour tout le monde. Et
* elle est FIDELE au montage -- l'etage 2 regule derriere, la tension
* intermediaire est tenue, pas flottante.
*
* La puissance n'est alors plus fixee par la charge mais par le RAPPORT
* CYCLIQUE, via l'equilibre que les resistances parasites imposent. Elle
* se trouve par recherche : cf. `cherche_duty()`.
Vo   nout nret DC {VOUT:.3f}

{mod_d}

.ic V(nin)={vin:.3f} I(L1)={i_in:.4f}

.options reltol=1e-4 abstol=1e-11 vntol=1e-7 plotwinsize=0
.tran 0 {t1:.6e} {t0:.6e} {dtmax:.3e} uic

.save V(nin) V(nsw) V(nda) V(nout) I(Vl) I(Vs) I(Vo) I(L1)
.end
"""
