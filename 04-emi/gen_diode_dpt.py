"""Pertes diode — banc repris de `02-mosfet-diode/gen_boost2_dpt.py`.

CE GENERATEUR N'INVENTE RIEN. Il reprend la structure du double-pulse du
chapitre 2, qui tourne depuis des mois, et n'y change qu'une chose : la
diode devient un MODELE CONSTRUCTEUR au lieu d'un `.model D`.

CE QUE J'AVAIS OUBLIE, ET QUI EXPLIQUE TROIS HEURES D'ECHECS :

  .options method=gear maxord=2     integration de Gear, ordre 2
  .options chgtol=1e-15             tolerance de charge
  Cosn nsw 0 <qq centaines de pF>   CAPACITE EXPLICITE sur le noeud de
                                    commutation

Le troisieme point est le decisif. Un noeud de commutation sans capacite
vers la masse laisse le pas de temps s'effondrer des qu'un modele
encapsule y fait basculer une source comportementale -- et c'est
exactement le symptome releve : pas de 5e-16 s, instant fige, tolerance
relachee en boucle. Le chapitre 2 appelle cela « conditionnement numerique
du noeud de commutation », et je l'ai redecouvert a la main apres l'avoir
ignore.

La sortie est RAIDE. Pas de reservoir, donc pas de piege de facteur Q, et
surtout : un boost a sortie raide EST topologiquement un double-pulse qui
tourne en continu. Les pertes de commutation y sont directement
comparables aux E_on/E_off de banc.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import gen_emi_dm as g                                    # noqa: E402

VOUT, FSW, ETA = 80.0, 400e3, 0.97
RDS, VGS = 5.0e-3, 10.0
# Conditionnement du noeud de commutation. VALEUR CHOISIE, PAS SUBIE :
# cette capacite se decharge dans l'interrupteur a chaque amorcage et
# dissipe 1/2.C.V^2.f, soit 384 mW a 300 pF -- du meme ordre que ce qu'on
# cherche a mesurer. A 50 pF elle tombe a 64 mW, reste dans l'INTERRUPTEUR
# et non dans la diode, et se retranche exactement du bilan.
# En dessous de 50 pF le CoolSiC G6 ne converge plus.
C_NOEUD = 50e-12
P_CNOEUD = 0.5 * C_NOEUD * 80.0 ** 2 * 400e3      # 64 mW, a retrancher
DCR = {"4u7": 5.5e-3, "10u": 3.3e-3, "47u": 10.7e-3}
L_VAL = {"4u7": 4.7e-6, "10u": 10e-6, "47u": 47e-6}

DIODES = {
    "inf": ("IDH04G65C6_L1", g.LIB / "Infineon" / "CoolSiC_G6_650V.lib",
            "Infineon CoolSiC G6 · 4 A / 650 V", 2),
    "c6d": ("C6D04065A", g.LIB / "Wolfspeed" / "C6D04065A.lib",
            "Wolfspeed C6D · 4 A / 650 V", 5),
    "c3d": ("C3D16065D1", g.LIB / "Wolfspeed" / "C3D16065D1.lib",
            "Wolfspeed C3D · 16 A / 650 V", 6),
    "si":  (None, None, "Vishay V8PA22 · 8 A / 200 V", 0),
}


def mode_duty(l_h, pout, vin):
    d_ccm = 1.0 - vin / VOUT
    d_i = vin * d_ccm / (l_h * FSW)
    if pout / ETA / vin >= d_i / 2:
        return "CCM", d_ccm
    return "DCM", math.sqrt(2.0 * pout * l_h * FSW * (VOUT - vin)
                            / (ETA * vin ** 2 * VOUT))


def bloc_diode(dio):
    """Connexion de la diode. Le brochage est LU dans le .SUBCKT."""
    nom, lib, _, broches = DIODES[dio]
    if dio == "si":
        return f"D1   nsw  nd   DMOD", f".model DMOD {g.DIODE[1]}"
    if broches == 2:                       # ANODE KATODE
        return f"XD1  nsw  nd   {nom}", g.texte_lib(lib)
    if broches == 5:                       # A K Case Tj Tc
        return (f"XD1  nsw  nd   ncase ntj ntc {nom}\n"
                f"Rcase ncase 0 1meg\nVtc  ntc 0 DC 25"), g.texte_lib(lib)
    # NC A K Case Tj Tc -- la premiere broche n'est PAS connectee
    return (f"XD1  nnc  nsw  nd   ncase ntj ntc {nom}\n"
            f"Rnc nnc 0 1meg\nRcase ncase 0 1meg\nVtc ntc 0 DC 25"), \
           g.texte_lib(lib)


def netlist(ind, dio, pout, vin=20.0, n_etab=20, n_mes=10, duty=None,
            reltol=1e-3, cosn=None):
    # La capacite de conditionnement est un REGLAGE par cas : certains
    # modeles encapsules ne convergent qu'au-dela d'une valeur. Elle ne
    # touche pas la mesure de diode -- elle se decharge dans
    # l'interrupteur -- mais elle entre dans le bilan, donc on la rend.
    cosn = C_NOEUD if cosn is None else cosn
    _, _, libelle, _ = DIODES[dio]
    l_h = L_VAL[ind]
    m, d0 = mode_duty(l_h, pout, vin)
    duty = d0 if duty is None else duty
    tsw = 1.0 / FSW
    ton = duty * tsw
    t0, t1 = n_etab * tsw, (n_etab + n_mes) * tsw
    bloc, mod = bloc_diode(dio)

    return f"""* Pertes diode -- {libelle}
* {ind} {l_h*1e6:.1f} uH, {m}, {vin:.0f} V -> {VOUT:.0f} V, {pout:.0f} W, 400 kHz
* structure reprise de 02-mosfet-diode/gen_boost2_dpt.py
.param vin={vin} vout={VOUT}

V1   vin  0    DC {{vin}}
* sortie RAIDE : pas de reservoir, donc pas de piege de facteur Q
Vo   vout 0    DC {{vout}}

L1   vin  nl   {l_h:.6e}
Rdcr nl   nsw  {DCR[ind]:.6e}

M1   nsw  ng   0 0 MSW
Vg   ng   0    PULSE(0 {VGS:.1f} 0 2n 2n {ton:.6e} {tsw:.6e})
* CONDITIONNEMENT NUMERIQUE du noeud de commutation. Sans cette capacite,
* le pas de temps s'effondre a 1e-16 s des qu'un modele encapsule y fait
* basculer une source comportementale. Elle ne porte aucune perte : le
* Coss du transistor n'est pas modelise ici, ce banc mesure la DIODE.
Cosn nsw  0    {cosn:.6e}

{bloc}
* Aucune resistance ni capacite parasite ajoutee autour de la diode.
* J'en avais mis (10 MOhm // 10 pF) pour debloquer un modele recalcitrant ;
* elles faussaient la mesure -- `I(Vd)` devenait le courant de la diode
* MOINS celui du condensateur, et a faible charge le second domine, d'ou
* des pertes de diode NEGATIVES. Le vrai probleme etait `uic`, pas le
* conditionnement : les retirer est a la fois plus juste et plus propre.
* sonde de courant portable : une source de 0 V en serie
Vd   nd   vout DC 0

.model MSW NMOS(VTO=2 KP=200 RD={RDS:.6f} RS=0 IS=1e-12)
{mod}

.options reltol={reltol:g} abstol=1e-12 vntol=1e-9 chgtol=1e-15
.options method=gear maxord=2 plotwinsize=0
* NI `ic=` NI `uic`. C'est la cle, et elle a coute trois heures.
*
* `uic` demande a LTspice de sauter le point de fonctionnement et de
* construire sa matrice initiale depuis les seules conditions imposees.
* Les noeuds INTERNES des modeles encapsules n'en ont alors aucune : le
* CoolSiC G6 d'Infineon porte un noeud thermique TJ pilote par
* `E1 TJ w value={{TEMP}}` et un noeud k1 coince entre une source
* comportementale et une source nulle. Sans point de fonctionnement, sa
* matrice est SINGULIERE -- et aucune option (gshunt, gmin, cshunt, gear,
* tolerances) n'y change rien. Verifie : le modele tourne parfaitement
* SEUL, avec ou sans uic ; c'est la combinaison avec le convertisseur qui
* le tue.
*
* On peut s'en passer parce que la sortie est RAIDE : aucun reservoir a
* charger, le courant d'inductance s'etablit en quelques periodes, et on
* en simule vingt avant de mesurer.
.tran 0 {t1:.6e} {t0:.6e} 2n

.save I(L1) I(V1) I(Vo) I(Vd) V(nsw) V(nd)
.meas TRAN pdio AVG (V(nsw)-V(nd))*I(Vd) FROM {t0:.6e} TO {t1:.6e}
.meas TRAN pout AVG {VOUT}*I(Vo)         FROM {t0:.6e} TO {t1:.6e}
.meas TRAN pin  AVG {vin}*I(L1)          FROM {t0:.6e} TO {t1:.6e}
.meas TRAN irms RMS I(L1)                FROM {t0:.6e} TO {t1:.6e}
.end
"""
