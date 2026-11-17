"""Architecture 1 du chapitre 3 : GaN en DCM permanent, 400 kHz, 4,7 uH.

Topologie double-pulse (sortie 80 V raide), comme au chapitre 2 : pas de
reservoir, donc pas de piege de facteur Q, et les pertes de commutation
sont directement comparables a un essai de banc.

CE QUI CHANGE PAR RAPPORT AU CHAPITRE 2 -- et c'est l'objet de ce
chapitre : les trois composants sont modelises FINEMENT, parce qu'en DCM
les grandeurs qui decident ne sont plus les memes qu'en CCM.

  Coss NON LINEAIRE du switch. En CCM il suffisait d'une energie
  (E_oss x fsw). En DCM le noeud oscille librement pendant le temps mort,
  et c'est Coss(V) qui fixe la frequence de resonance et la duree de la
  transition. Modelise par une jonction CJO/VJ/M ajustee sur la Fig.5 du
  datasheet EPC2007C : ecart <= 5.5 %, et le modele redonne Qoss(50V) a
  +1.9 % et Eoss(80V) a +0.8 % des valeurs de reference.

  CONDUCTION EN 3e QUADRANT du GaN. Un GaN n'a PAS de diode de corps :
  sa conduction inverse demarre a V_SD = 2.1 V (p.1 du datasheet), contre
  ~0.9 V pour la diode de corps d'un MOSFET silicium. C'est elle qui
  ecrete l'oscillation de temps mort -- donc elle fixe la fenetre de ZVS
  et la perte pendant le palier. La MEME jonction sert aux deux roles :
  bloquee elle fait le Coss, passante elle fait le clamp.

  DIODE recalibree. Le modele SPICE trouve en ligne etait cale sur la
  chute a 125 degC (0.60 V) sans declarer de temperature, sous-estimant
  donc de 27 a 31 % a 25 degC ; sa capacite etait fausse de -28 a +30 %
  selon la tension ; et il portait TT = 5 ns sur une Schottky, ce qui
  fabrique ~408 mW de recouvrement inexistant a 400 kHz. Tout est
  reajuste sur les tables et courbes du doc Vishay 98199.

  CAPACITE PROPRE DE L'INDUCTANCE, deduite de sa SRF (32 MHz a 4.7 uH
  -> 5.26 pF). Faible, mais elle entre dans le budget du noeud.

  INDUCTANCE DE MAILLE DE COMMUTATION : ESTIMEE, non sourcee -- et de ce
  fait BALAYEE (10 / 20 / 40 / 80 nH) plutot que postulee. Elle est placee
  dans la BRANCHE DIODE, pas en serie avec L1 : la maille qui compte est
  celle que le courant doit traverser quand il bascule du switch vers la
  diode (noeud -> diode -> sortie -> masse -> switch). Une inductance
  placee en serie avec L1 serait en serie avec 4,7 uH et ne ferait
  dynamiquement rien ; c'est bien dans la maille de commutation qu'elle
  fabrique le depassement et la resonance HF.

  Un seul element localise represente la maille entiere (branche diode +
  ESL du condensateur + retour de masse + inductance de source). LIMITE
  ASSUMEE : la part cote source agit aussi sur la grille (inductance de
  source commune), ce qu'un interrupteur idealise ne peut pas rendre. Le
  balayage donne donc la sensibilite du noeud de puissance, pas celle de
  la commande.
"""
from __future__ import annotations

import math

VIN, VOUT = 20.0, 80.0
L_H, DCR, C_SELF = 4.7e-6, 5.50e-3, 5.26e-12     # SER1360-472KL, doc 290-1
L_BOUCLE = 20e-9          # ESTIMEE, non sourcee -> balayee, cf. docstring
L_BOUCLES = (10e-9, 20e-9, 40e-9, 80e-9)
FSW = 400e3

# --- EPC2007C, doc rev. avril 2021 -------------------------------------
GAN = dict(part="EPC2007C", rds=0.030, rds_hot=0.040, vgs=5.0,
           qg=1.6e-9, qgd=0.3e-9, rg_int=0.4,
           # jonction ajustee sur la Fig.5 (Coss vs VDS)
           cjo=275e-12, vj=27.15, m=0.852,
           vsd=2.1,                              # conduction 3e quadrant, p.1
           # IS/N ajustes pour que la MEME jonction ecrete a V_SD = 2.1 V a
           # 0.5 A. Avec les valeurs d'une diode silicium (IS=1e-12, N=1) le
           # noeud s'ecretait a -0.7 V : le modele fabriquait une diode de
           # corps que le GaN n'a pas, et sous-estimait donc la perte de
           # palier d'un facteur 3.
           is_q3=5.6820e-15, n_q3=2.5)

# --- V6PW12C, doc Vishay 98199 rev. 17-Mar-2022 ------------------------
# IS/N/RS ajustes sur les DEUX points 25 degC de la table p.2
# (0.58 V a 1.5 A, 0.73 V a 3.0 A) ; CJO/VJ/M sur la Fig.5 p.3.
DIODE = dict(part="V6PW12C", is_a=1.147e-7, n=1.06, rs=0.0873,
             cjo=519.8e-12, vj=4.596, m=0.933, tt=0.0)

I_DRV_ON, I_DRV_OFF = 2.0, 3.0    # A, driver de grille retenu


def duty_dcm(pout: float, eta: float = 0.98) -> float:
    """Rapport cyclique en DCM : Pout = Vin^2 D^2 /(2 L fsw) * Vout/(Vout-Vin)."""
    return math.sqrt(2.0 * pout * L_H * FSW * (VOUT - VIN) / (eta * VIN**2 * VOUT))


def seuil_dcm() -> float:
    return VIN**2 * (1 - VIN / VOUT) / (2 * FSW * L_H)


def netlist(pout: float, duty: float | None = None,
            l_boucle: float | None = None, n_periodes: int = 4,
            pts_par_periode: int = 8000, reltol: float = 1e-5) -> str:
    """Netlist double-pulse. `duty` impose le rapport cyclique (sinon la
    formule DCM) ; `l_boucle` impose l'inductance de maille."""
    d = duty_dcm(pout) if duty is None else duty
    lb = L_BOUCLE if l_boucle is None else l_boucle
    tsw = 1.0 / FSW
    ton = d * tsw
    tr = max(GAN["qgd"] / I_DRV_ON, 1e-10)
    tf = max(GAN["qgd"] / I_DRV_OFF, 1e-10)
    # on laisse 4 periodes s'etablir, on enregistre les n_periodes suivantes
    tstart = 4 * tsw
    tstop = tstart + n_periodes * tsw
    dtmax = tsw / pts_par_periode
    g, di = GAN, DIODE
    return f"""* Architecture 1 -- GaN DCM permanent, {pout:.0f} W, {FSW/1e3:.0f} kHz, {L_H*1e6:.1f} uH, maille {lb*1e9:.0f} nH
* genere par gen_dcm_gan.py -- ne pas editer a la main
V1   vin  0    DC {VIN}
Vo   vout 0    DC {VOUT}

* --- inductance SER1360-472KL : L, DCR, et sa capacite propre (SRF 32 MHz)
* elle arrive DIRECTEMENT sur le noeud chaud : l'inductance de sa piste est
* negligeable devant 4,7 uH, et la placer la n'aurait aucun effet dynamique
L1   vin  nl   {L_H:.4e}
Rdcr nl   nsw  {DCR:.4e}
Cl   vin  nsw  {C_SELF:.4e}

* --- switch GaN EPC2007C
* canal : INTERRUPTEUR COMMANDE, pas un MOSFET. Le modele NMOS de SPICE
* embarque une jonction substrat-drain qui conduit vers 0,8 V -- elle
* fabriquerait au GaN une diode de corps qu'il n'a pas, et ecreterait la
* resonance de temps mort trois fois trop tot.
* SONDES : chaque chemin porte sa propre source 0 V, pour pouvoir
* separer les postes de perte -- canal (R) et Coss/3e quadrant (C) --
* au lieu de les deduire par difference, ce qui les melangerait pendant
* la transition, precisement la ou ils comptent.
S1   nsw  nss  ng 0 SWGAN
Vs   nss  0    DC 0
Vg   ng   0    PULSE(0 {g['vgs']:.1f} 0 {tr:.4e} {tf:.4e} {ton:.6e} {tsw:.6e})
* Dgan joue DEUX roles : bloquee elle porte le Coss non lineaire,
* passante elle fait la conduction 3e quadrant qui ecrete la resonance
Dgan 0    nco  DGAN
Vq   nco  nsw  DC 0

* --- INDUCTANCE DE MAILLE DE COMMUTATION, dans la branche diode : c'est
* la maille noeud -> diode -> sortie -> masse -> switch que le courant
* doit traverser pour basculer du switch vers la diode. {lb*1e9:.0f} nH ici.
Lb   nsw  nda  {lb:.4e}

* --- diode Schottky V6PW12C (une seule jambe du boitier double)
D1   nda  nd   DV6PW
Vd   nd   vout DC 0

.model SWGAN SW(VT=2.5 VH=0.2 RON={g['rds']:.5f} ROFF=1e9)
.model DGAN D(IS={g['is_q3']:.4e} N={g['n_q3']} RS=0.05 CJO={g['cjo']:.4e} VJ={g['vj']:.3f}
+ M={g['m']:.3f} FC=0.5 TT=0 BV=150 IBV=1e-6)
.model DV6PW D(IS={di['is_a']:.4e} N={di['n']} RS={di['rs']:.4f}
+ CJO={di['cjo']:.4e} VJ={di['vj']:.3f} M={di['m']:.3f} FC=0.5 TT=0
+ EG=0.69 XTI=2 BV=150 IBV=1e-4)

.options reltol={reltol:g} abstol=1e-13 vntol=1e-9 chgtol=1e-16
.options method=gear maxord=2
.tran {dtmax:.4e} {tstop:.6e} {tstart:.6e} {dtmax:.4e} uic
.save I(L1) I(V1) I(Vd) I(Vs) I(Vq) V(nsw) V(nss) V(nco) V(nda) V(nd) V(ng)
.end
"""


if __name__ == "__main__":
    print(f"Seuil DCM/CCM a {FSW/1e3:.0f} kHz / {L_H*1e6:.1f} uH : "
          f"{seuil_dcm():.1f} W  -> DCM garanti sur 5-50 W\n")
    print(f"{'Pout':>6} {'D':>7} {'Ipk':>7} {'t_on':>8} {'t_diode':>9} {'t_mort':>9}")
    for p in (5, 20, 40, 50):
        d = duty_dcm(p)
        ipk = VIN * d / (L_H * FSW)
        ton, toff = ipk * L_H / VIN, ipk * L_H / (VOUT - VIN)
        print(f"{p:5.0f} W {d:7.4f} {ipk:6.2f} A {ton*1e9:7.0f}n "
              f"{toff*1e9:8.0f}n {(1/FSW-ton-toff)*1e9:8.0f}n")
