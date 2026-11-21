"""Montee en fidelite PAS A PAS, un seul changement par etape.

METHODE IMPOSEE PAR LE CONCEPTEUR, et deja inscrite deux fois dans le depot
(memoire `simulation_incremental_methodology`, skill `sim-spice`) :

  1. circuit SIMPLE, composants IDEAUX. Valider le montage lui-meme :
     cablage, topologie, physique de base, convergence -- avant toute
     question de fidelite de composant.
  2. remplacer UN SEUL composant ou branche par un reseau SPICE.
  3. RETESTER le meme petit jeu de mesures.
  4. ne passer au suivant QUE si les tests sont bons.
  5. en cas de doute : MONTRER LES COURBES.

Chaque etape est un couple (netlist, controle analytique). Le controle
n'est pas decoratif : c'est lui qui dit si l'etape est validee, par
comparaison a une formule fermee independante du simulateur.

ETAT DES ETAPES
  0  tout ideal                        source, L pure, interrupteur SW, diode .model
  1  + inductance constructeur         SER2211-473, modele Coilcraft Model1D
  2  + diode constructeur              Vishay V8PA22
  3  + transistor constructeur         Infineon IPD530N15N3
  4  + reseau d'entree a trois branches
  5  + LISN CISPR 25
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parents[2]
LIB = RAC / "lib_spice_commun"

VIN, VOUT, FSW, L_H, DCR = 19.0, 80.0, 200e3, 47e-6, 10.7e-3
RDS, VF = 53e-3, 0.45          # valeurs IDEALISEES pour l'etape 0
P_VISEE = 8.0


def attendu(p=P_VISEE, vin=VIN, l_h=L_H, fsw=FSW, rds=RDS, vf=VF):
    """Formule fermee, independante du simulateur. C'est l'etalon."""
    d = (VOUT + vf - vin) / (VOUT + vf)          # rapport cyclique ideal
    iin = p / (vin * 0.97)
    di = vin * d / (l_h * fsw)
    plim = vin ** 2 * (1 - vin / VOUT) * 0.97 / (2 * l_h * fsw)
    return dict(duty=d, iin=iin, di=di, ipk=iin + di / 2,
                mode="CCM" if p > plim else "DCM", plim=plim)


# parametres du modele CONSTRUCTEUR Coilcraft, aplatis depuis Model1D
#              (nom,          L,      Rs,      Cp,        Rp,       Rc)
SER2211 = ("SER2211-473", 47.0e-6, 0.0107, 8.183e-12, 7315.8901, 140.0)


def etape0(p=P_VISEE, duty=None, n_mes=8, charge=False, tr=5e-9,
           c_noeud=0.0, n_etab=20, dtmax=1e-9, cout=130e-6, ser=False,
           v8pa22=False, l_maille=10e-9):
    """TOUT IDEAL. Aucun modele constructeur, aucun parasite, aucun LISN.

    But : valider le CABLAGE et la PHYSIQUE. Si cette etape ne rend pas le
    rapport cyclique, le courant et le mode prevus par la formule fermee,
    rien de ce qui suit n'a de sens.
    """
    a = attendu(p)
    # ETAPE 1 : l'inductance IDEALE devient le modele CONSTRUCTEUR Coilcraft.
    # Model1D aplati -- Rs en serie, puis trois branches en parallele :
    #     Rp seul (impedance de CRETE a la resonance, PUBLIEE au catalogue)
    #     L
    #     Rc + Cp
    # C'est Rp qui amortit la sonnerie de temps mort du DCM. L'etape 0,
    # avec une L pure, ne pouvait pas la voir.
    if ser:
        nl, lh, rs, cp, rp, rc = SER2211
        bloc_l = chr(10).join((
            f"* inductance CONSTRUCTEUR {nl} -- Coilcraft Model1D aplati",
            f"Vsl  nin  nsl  DC 0", f"Rs_l nsl  n1l  {rs:.6e}",
            f"Rp_l n1l  nsw  {rp:.6g}",
            f"L1   n1l  nsw  {lh:.6e}",
            f"Rc_l n1l  n2l  {max(rc, 1e-9):.6g}",
            f"Cp_l n2l  nsw  {cp:.6e}"))
    else:
        bloc_l = chr(10).join((
            "* inductance IDEALE : L pure + DCR, rien d'autre",
            f"Vsl  nin  nsl  DC 0", f"L1   nsl  nl   {L_H:.6e}",
            f"Rdcr nl   nsw  {DCR:.6e}"))
    # ETAPE 2 : la diode IDEALE devient le modele CONSTRUCTEUR Vishay.
    # `.MODEL D`, donc prefixe D et JAMAIS X -- le gendarme refuse l'inverse.
    # INDUCTANCE DE MAILLE -- element PHYSIQUE, pas un artifice numerique.
    #
    # Sans elle, la diode est branchee a meme le drain : quand le MOSFET se
    # ferme sur un noeud laisse a -15 V par l'oscillation de temps mort, la
    # charge de Cosn et de la Cj est court-circuitee a travers Ron = 53 mOhm.
    # dV/Ron = 300 A, et seul le PAS D'INTEGRATION borne le courant -- la
    # valeur obtenue depend donc du pas, ce qui est la definition d'un
    # artefact. Mesure : 7,19 A de pointe pour 0,27 nC seulement.
    #
    # La maille reelle d'une boucle drain-diode-condensateur fait 2 a 20 nH.
    # Avec elle, la decharge devient une oscillation amortie bornee par
    # di/dt = V/L, et l'energie n'est plus comptee a tort dans S1.
    tete = (f"* maille de routage, {l_maille*1e9:.0f} nH -- borne le di/dt "
            f"a la fermeture", f"Lb   nsw  nda  {l_maille:.4e}")
    if v8pa22:
        bloc_d = chr(10).join(tete + (
            "* diode CONSTRUCTEUR Vishay V8PA22 -- Schottky TMBS 200 V / 8 A",
            "D1   nda  nd   DV8PA22",
            (LIB / "Vishay" / "V8PA22.lib").read_text(encoding="utf-8",
                                                      errors="replace")))
    else:
        bloc_d = chr(10).join(tete + (
            "* diode IDEALE",
            "D1   nda  nd   DID",
            ".model DID D(IS=1e-9 N=1.0 RS=0.02 CJO=100p BV=200)"))
    # RAPPORT CYCLIQUE DU BON MODE.
    #
    # Premiere version : duty = 1 - Vin/Vout, la formule CCM. Mais a 8 W le
    # point est en DCM (frontiere a 14,2 W), et en DCM la relation est tout
    # autre. Resultat : 0,760 impose la ou il fallait 0,564, et le banc
    # convergeait vers 104 V au lieu de 80 -- lentement, parce que
    # R.Cout = 104 ms. Les deux fautes se masquaient.
    #
    # En DCM sur charge R, l'equilibre verifie
    #     Vout^2 - Vin.Vout = R.Vin^2.D^2 / (2.L.f)
    # d'ou, pour viser Vout :
    if duty is None:
        if a["mode"] == "DCM":
            rl = VOUT ** 2 / p
            duty = math.sqrt((VOUT ** 2 - VIN * VOUT) * 2 * L_H * FSW
                             / (rl * VIN ** 2))
        else:
            rb = DCR + RDS * a["duty"]
            duty = 1.0 - (VIN - a["iin"] * rb - VF) / VOUT
    tsw = 1.0 / FSW
    t0, t1 = n_etab * tsw, (n_etab + n_mes) * tsw
    # DEUX SORTIES AU CHOIX, pour montrer ce que la topologie du banc change
    if charge:
        rl = VOUT ** 2 / p
        bloc_sortie = "\n".join((
            "* sortie sur CHARGE : le point se stabilise seul",
            f"Rl   nout 0    {rl:.4f}",
            f"Cout nout 0    {cout:.4e} ic={VOUT:.1f}"))
    else:
        bloc_sortie = "\n".join((
            "* sortie RAIDE : aucun rappel, le point est sur un fil",
            f"Vo   nout 0    DC {VOUT:.1f}"))
    return f"""* ETAPE 0 -- boost TOUT IDEAL, {VIN:.0f} V -> {VOUT:.0f} V, {p:.0f} W
* Aucun modele constructeur. Interrupteur et diode sont des .model simples.
* But : valider cablage, topologie, physique. PAS la fidelite.
.param tsw={tsw:.6e} duty={duty:.6f}

Vbat nin  0    DC {VIN}
{bloc_sortie}

{bloc_l}

* interrupteur IDEAL. Le `.model SW` est commande en TENSION : il n'a
* AUCUNE capacite de grille, donc une resistance de grille n'y change
* rien. Les fronts se ralentissent par leur DUREE. Les 10 ohms prendront
* leur sens a l'etape 3, avec l'IPD530N15N3 qui a un vrai Qg.
S1   nsw  0    ng 0 MSW
.model MSW SW(Ron={RDS:.6f} Roff=1meg Vt=2.5 Vh=0)
Vg   ng   0    PULSE(0 5 0 {tr:.3e} {tr:.3e} {{duty*tsw}} {{tsw}})

* PAS de condensateur sur le noeud de commutation aux etapes 0 a 2.
*
* Il y en avait un (50 pF), pose pour brider les +-50 A d'artefact que la
* Cj de la diode donnait dans un interrupteur parfait. La MAILLE regle ce
* probleme a la source ; la capacite, elle, en creait un autre, plus gros
* et mieux cache : sur un interrupteur IDEAL le canal est instantane, donc
* la decharge vaut V/Ron = 28,3/0,053 = 534 A, bornee par le seul PAS
* D'INTEGRATION. Releve : 220 A de pointe a l'etape 0, et un bilan
* energetique ouvert de 21,3 % -- l'energie partait dans un pic trop
* bref pour que moy(v.i) le voie.
*
* Le Coss est REEL, mais il est indissociable du gm fini qui borne sa
* decharge. Les deux arrivent ensemble a l'etape 3, avec l'IPD530N15N3.
* Les mettre separement, c'est modeliser la moitie qui fait mal.
Cosn nsw  0    {max(c_noeud, 1e-18):.3e}

{bloc_d}
Vd   nd   nout DC 0

.options plotwinsize=0
.tran 0 {t1:.6e} {t0:.6e} {dtmax:.3e}

.save V(nsw) V(nin) V(nout) V(n1l) V(n2l) V(nsl) V(ng) V(nda)
.save I(L1) I(Vd) I(Vbat) I(Vsl) I(Rp_l) I(Cp_l) I(Rs_l) I(Cosn) I(Lb)
.meas TRAN iin  AVG -I(Vbat)     FROM {t0:.6e} TO {t1:.6e}
.meas TRAN il   AVG I(L1)        FROM {t0:.6e} TO {t1:.6e}
.meas TRAN ilmx MAX I(L1)        FROM {t0:.6e} TO {t1:.6e}
.meas TRAN ilmn MIN I(L1)        FROM {t0:.6e} TO {t1:.6e}
.meas TRAN idio AVG I(Vd)        FROM {t0:.6e} TO {t1:.6e}
.end
"""


if __name__ == "__main__":
    a = attendu()
    print(f"ATTENDU par la formule fermee, a {P_VISEE:.0f} W :")
    print(f"  rapport cyclique ideal {a['duty']:.4f}")
    print(f"  frontiere DCM/CCM      {a['plim']:.1f} W  -> mode {a['mode']}")
    print(f"  courant moyen          {a['iin']:.3f} A")
    print(f"  ondulation             {a['di']:.3f} A crete-a-crete")
    print(f"  courant crete          {a['ipk']:.3f} A")
