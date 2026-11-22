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


def cout_wurth(ref):
    """Condensateur de sortie CONSTRUCTEUR Wurth, lu dans la bibliotheque
    LOCALE `lib_spice_commun/WurthElektronik/ltspice-capacitors-v1`.

    Les elements du sous-circuit (Rser, Lser, C1, Rpar) sont LUS dans le
    .lib du fabricant et ecrits a plat, avec ic=80 V sur la capacite.

    POURQUOI PAS `X... sous-circuit` + `.ic V(nout)=80` (essaye le
    2026-11-22) : pendant le point de repos, la source de .ic qui tient
    nout fournit le courant de charge a la place du condensateur ; l'ESL
    part donc a 0 A et doit sauter a 0,5 A a t = 0+ -- nout s'effondrait
    a 3,5 V en 20 fs, le noeud interne a -57 V. Avec ic= sur la capacite
    elle-meme, la contrainte est aux bornes de C, le courant de charge
    traverse Rser et Lser des le point de repos : etat initial coherent.
    Rend (lignes de netlist, nom du sous-circuit).
    """
    import re
    base = LIB / "WurthElektronik" / "ltspice-capacitors-v1" / "sub"
    for f in sorted(base.glob("*.lib")):
        t = f.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(?ms)^\.subckt (" + re.escape(ref)
                      + r"_\S+) 1 2\s*$(.*?)^\.ends", t)
        if m:
            break
    else:
        raise ValueError(f"{ref} introuvable dans {base}")
    el = {}
    for ligne in m.group(2).splitlines():
        c = ligne.split()
        if len(c) == 4 and c[0] in ("Rser", "Lser", "C1", "Rpar"):
            el[c[0]] = c[3]                 # texte du fabricant, tel quel
    if set(el) != {"Rser", "Lser", "C1", "Rpar"}:
        raise ValueError(f"{m.group(1)} : elements inattendus {el}")
    return chr(10).join((
        f"* sortie CONSTRUCTEUR Wurth {m.group(1)} -- {f.name}, "
        f"bibliotheque locale, elements lus tels quels",
        f"Rcs  nout nc3  {el['Rser']}",
        f"Cout nc3  nc4  {el['C1']} ic={VOUT:.1f}",
        f"Rcp  nc3  nc4  {el['Rpar']}",
        f"Lcs  nc4  0    {el['Lser']}")), m.group(1)


def etape0(p=P_VISEE, duty=None, n_mes=8, charge=False, tr=5e-9,
           c_noeud=0.0, n_etab=20, dtmax=1e-9, cout=130e-6, ser=False,
           v8pa22=False, l_maille=10e-9, mos=False, rg=10.0, vgs=10.0,
           vin=None, rl=None, pwm=None, ki=None, kp=None, vref=None,
           echelon=None, sobre=False, cout_we=None, tau_mes=None, echant=False, cout_hf=False, retard=False,
           force_ic=False):
    """TOUT IDEAL. Aucun modele constructeur, aucun parasite, aucun LISN.

    But : valider le CABLAGE et la PHYSIQUE. Si cette etape ne rend pas le
    rapport cyclique, le courant et le mode prevus par la formule fermee,
    rien de ce qui suit n'a de sens.
    """
    vin = VIN if vin is None else vin
    a = attendu(p, vin=vin)
    # MESURE DE Vout FILTREE (tau_mes, s) : le filtre RC anti-repliement
    # de l'entree ADC. Sans lui, Bctrl lit V(nout) INSTANTANE : avec un
    # condensateur reel (ESR + ESL) le blocage fait sauter nout de
    # plusieurs volts pile au croisement rampe/commande, la commande
    # repasse de part et d'autre de la rampe et la grille bascule sans fin
    # -- pas de temps effondre a 3,7565 us, Infineon _L0 ET onsemi FDD770
    # (2026-11-22). Avec un condensateur ideal nout ne bougeait pas.
    vmes = "nvm" if tau_mes else "nout"
    # ECHANTILLONNAGE de la mesure une fois par periode (echant=True), en
    # debut de periode, quand la rampe repart de 0 : la commande est
    # constante sur la periode, la rampe ne la croise qu'UNE fois. C'est
    # ce que fait le C2000 (ADC declenche par l'ePWM, CMPA recharge au
    # compteur nul). Le filtre tau_mes reste EN AMONT, comme l'RC d'entree
    # de l'ADC. En DCM a Kp ~ 1, le filtre seul ne suffisait plus : 390
    # relachements de tolerance, tous aux blocages (2026-11-22).
    vsrc, vmes = vmes, ("nsh" if echant else vmes)
    # RETARD D'UNE PERIODE (retard=True, avec echant) : la valeur figee a la
    # fin de la periode k ne commande que la periode k+2 -- conversion ADC,
    # calcul CLA et rechargement de CMPA au compteur nul ne tiennent pas
    # dans les ~10 ns qui restent apres un echantillon a 0,998 T. Modele :
    # un second bloqueur, cadence 0,001 T AVANT le premier,
    # recopie la valeur de la periode precedente ; la commande lit celui-ci.
    if echant and retard:
        vmes = "nsh2"
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
            # `vin` et non la constante VIN (19 V) : la premiere version
            # rendait 0,4456 au lieu de 0,4198 sous 20 V (2026-11-22).
            duty = math.sqrt((VOUT ** 2 - vin * VOUT) * 2 * L_H * FSW
                             / (rl * vin ** 2))
        else:
            # D = 1 - (Vin - I.R_boucle) / (Vout + Vf), avec
            # R_boucle = DCR + Ron.D. Estimation en une passe ; la charge
            # resistive est assez amortie pour qu'une iteration de Newton
            # suffise ensuite : dD = dVout.(1-D)/Vout.
            d_id = 1.0 - vin / VOUT
            rb = DCR + RDS * d_id
            iin = p / (vin * 0.96)
            duty = 1.0 - (vin - iin * rb) / (VOUT + VF)
    # ETAPE 3 : l'interrupteur IDEAL devient le transistor CONSTRUCTEUR.
    #
    # Variante `_L1` : trois broches, AVEC l'inductance de boitier publiee
    # (Ls = 2 nH, Ld = 1 nH, Lg = 3 nH). Le modele porte la sienne, on ne
    # lui en ajoute jamais une de l'exterieur -- la maille Lb de 10 nH
    # represente le ROUTAGE de la carte, pas les fils de bonding, et les
    # deux coexistent.
    #
    # DEUX PARAMETRES DU MODELE VALIDENT LA COMPARAISON
    #   Rmax = 53 m  exactement le Ron qu'on avait pose en ideal
    #   Unn  = 10 V  la grille nominale -- les 5 V venaient du GaN
    #
    # LES 10 OHMS DE GRILLE PRENNENT ENFIN LEUR SENS ICI. Le `.model SW`
    # est commande en TENSION, il n'a aucune capacite de grille : une
    # resistance de grille n'y changeait rien, et les fronts devaient
    # etre ralentis par leur DUREE. Le transistor reel a un vrai Qg, et
    # 2,1 ohms de grille internes qui s'ajoutent aux 10 externes.
    #
    # CE QU'IL FAUT ATTENDRE : la diode de CORPS. L'interrupteur ideal
    # laissait V(nsw) descendre a -78 V pendant la sonnerie de temps
    # mort ; le transistor reel l'ecretera vers -0,8 V. Le temps mort
    # portait 46 % des pertes a l'etape 2 : il va changer beaucoup.
    #
    # DEUX MODELES, PARCE QUE LE PREMIER NE CONVERGE PAS.
    #
    # L'IPD530N15N3 ne passe qu'a Rg = 10 ohms. A 2,2, 4,7, 22 et 47 il
    # casse au PREMIER pas transitoire -- le point de repos, lui, converge
    # ("Direct Newton iteration succeeded"). Le journal designe le coupable :
    # `trouble with node x1:x1:e_eds7#branch`, une source comportementale
    # interne. Le modele est RAIDE, ce n'est pas une faute de cablage : les
    # cinq netlists ne different que par la valeur de Rgx.
    #
    # Le FDD770N15A est de structure toute differente : 69 lignes, coeur
    # BSIM3 (LEVEL=7), et surtout DES RESISTANCES D'AMORTISSEMENT en
    # parallele sur chaque inductance de boitier (RLgate 55 ohms, RLdrain
    # 1 ohm, RLsource 27 ohms). C'est precisement ce qui manque au modele
    # Infineon, dont les inductances sont pures.
    #
    # Les deux sont comparables par ailleurs : DPAK, 150 V, et un Rdson
    # de 51,5 mohms (48,6 de drain + 2,9 de source) contre 53.
    #
    # LES DEUX RESTENT DISPONIBLES. Un modele constructeur ne se remplace
    # pas par un autre a la legere -- la session a deja paye cette lecon
    # (Wolfspeed 180 s d'abandon contre Infineon 2,8 s). On garde donc les
    # deux et on compare, au lieu de substituer en silence.
    # PI (kp ET ki) : le terme constant D0 du P devient l'INTEGRALE de
    # l'erreur, V(nint), initialisee a D0. Sans ki, texte inchange.
    d0x = "V(nint)" if (kp and ki) else f"{duty:.6f}"
    nom_mos = {True: "ipd530", False: None}.get(mos, mos)
    if nom_mos == "fdd770":
        bloc_s = chr(10).join((
            f"* transistor CONSTRUCTEUR onsemi FDD770N15A, DPAK 150 V",
            f"* boitier inclus et AMORTI (Lg 5,5n//55R, Ld 0,1n//1R, "
            f"Ls 2,7n//27R)",
            f"X1   nsw  ngg  0    FDD770N15A",
            f"Rgx  ng   ngg  {rg:.4g}",
            (chr(10).join((
                 "* BOUCLE FERMEE -- correcteur PROPORTIONNEL, etape R2",
                 "* Aucune phase ajoutee, aucune saturation possible.",
                 "* L'erreur statique residuelle mesure le gain de boucle.",
                 f"Bctrl nctrl 0  V=limit({d0x} + {kp:.6g}*"
                 f"({vref:.4f} - V({vmes})), 0.05, 0.95)",
                 f"Vramp nramp 0  PULSE(0 1 0 {{tsw*0.999}} {{tsw*0.001}} "
                 f"0 {{tsw}})",
                 f"Bg    ng    0  V=if(V(nctrl)>V(nramp), {vgs:.3g}, 0)"))
             if kp else
             chr(10).join((
                 "* BOUCLE FERMEE -- integrateur pur, etape R3",
                 "* C = 1 F charge par une source de courant commandee :",
                 "* dV/dt = I, donc V(nint) = integrale de l'erreur.",
                 f"Gint 0 nint VALUE={{{ki:.6g}*({vref:.4f} - V(nout))}}",
                 f"Cint nint 0  1 ic={{{(duty if pwm is None else 0):.6f}}}",
                 "* ecretage du rapport cyclique",
                 "Bctrl nctrl 0  V=limit(V(nint), 0.05, 0.95)",
                 f"Vramp nramp 0  PULSE(0 1 0 {{tsw*0.999}} {{tsw*0.001}} "
                 f"0 {{tsw}})",
                 f"Bg    ng    0  V=if(V(nctrl)>V(nramp), {vgs:.3g}, 0)"))
             if ki else
             (f"Vg   ng   0    PULSE(0 {vgs:.3g} 0 {tr:.3e} {tr:.3e} "
             f"{{duty*tsw}} {{tsw}})" if not pwm else chr(10).join((
                 "* MODULATEUR PWM : dent de scie contre tension de commande",
                 "* C'est ici que la boucle viendra se brancher (etape R2).",
                 f"Vramp nramp 0  PULSE(0 1 0 {{tsw*0.999}} {{tsw*0.001}} "
                 f"0 {{tsw}})",
                 f"{'Bctrl nctrl 0  ' if str(pwm).lstrip().upper().startswith('V') else 'Vctrl nctrl 0  '}{pwm}",
                 f"Bg    ng    0  V=if(V(nctrl)>V(nramp), {vgs:.3g}, 0)")))),
            (LIB / "onsemi" / "FDD770N15A.lib").read_text(encoding="utf-8",
                                                          errors="replace")))
    elif nom_mos:
        bloc_s = chr(10).join((
            f"* transistor CONSTRUCTEUR Infineon IPD530N15N3, DPAK 150 V",
            (f"* variante _L1 : boitier inclus (Ls 2n, Ld 1n, Lg 3n), NON amorti"
             if nom_mos != "ipd530_l0" else
             chr(10).join((
                 "* variante _L0 : modele NIVEAU 0 Infineon de la MEME piece --",
                 "* elements SPICE standard seulement (MOS niveau 3, diodes,",
                 "* sources lineaires), sans la source comportementale e_eds7",
                 "* sur laquelle _L1 se bloque. Boitier identique (Lg 3n, Ld 1n,",
                 "* Ls 2n), Rg interne 2,1 ohms. Retenu pour les boucles de R2."))),
            f"X1   nsw  ngg  0    "
            f"{'IPD530N15N3_L0' if nom_mos == 'ipd530_l0' else 'IPD530N15N3_L1'}",
            f"Rgx  ng   ngg  {rg:.4g}",
            (chr(10).join((
                 "* BOUCLE FERMEE -- correcteur PROPORTIONNEL, etape R2",
                 "* Aucune phase ajoutee, aucune saturation possible.",
                 "* L'erreur statique residuelle mesure le gain de boucle.",
                 f"Bctrl nctrl 0  V=limit({d0x} + {kp:.6g}*"
                 f"({vref:.4f} - V({vmes})), 0.05, 0.95)",
                 f"Vramp nramp 0  PULSE(0 1 0 {{tsw*0.999}} {{tsw*0.001}} "
                 f"0 {{tsw}})",
                 f"Bg    ng    0  V=if(V(nctrl)>V(nramp), {vgs:.3g}, 0)"))
             if kp else
             chr(10).join((
                 "* BOUCLE FERMEE -- integrateur pur, etape R3",
                 "* C = 1 F charge par une source de courant commandee :",
                 "* dV/dt = I, donc V(nint) = integrale de l'erreur.",
                 f"Gint 0 nint VALUE={{{ki:.6g}*({vref:.4f} - V(nout))}}",
                 f"Cint nint 0  1 ic={{{(duty if pwm is None else 0):.6f}}}",
                 "* ecretage du rapport cyclique",
                 "Bctrl nctrl 0  V=limit(V(nint), 0.05, 0.95)",
                 f"Vramp nramp 0  PULSE(0 1 0 {{tsw*0.999}} {{tsw*0.001}} "
                 f"0 {{tsw}})",
                 f"Bg    ng    0  V=if(V(nctrl)>V(nramp), {vgs:.3g}, 0)"))
             if ki else
             (f"Vg   ng   0    PULSE(0 {vgs:.3g} 0 {tr:.3e} {tr:.3e} "
             f"{{duty*tsw}} {{tsw}})" if not pwm else chr(10).join((
                 "* MODULATEUR PWM : dent de scie contre tension de commande",
                 "* C'est ici que la boucle viendra se brancher (etape R2).",
                 f"Vramp nramp 0  PULSE(0 1 0 {{tsw*0.999}} {{tsw*0.001}} "
                 f"0 {{tsw}})",
                 f"{'Bctrl nctrl 0  ' if str(pwm).lstrip().upper().startswith('V') else 'Vctrl nctrl 0  '}{pwm}",
                 f"Bg    ng    0  V=if(V(nctrl)>V(nramp), {vgs:.3g}, 0)")))),
            f'.inc "{(LIB / "Infineon" / "OptiMOS3_150V_LTSpice.lib").as_posix()}"'))
    else:
        bloc_s = chr(10).join((
            "* interrupteur IDEAL. Le `.model SW` est commande en TENSION :",
            "* il n'a AUCUNE capacite de grille, donc une resistance de",
            "* grille n'y change rien. Les fronts se ralentissent par leur",
            "* DUREE. Les 10 ohms prendront leur sens a l'etape 3.",
            f"S1   nsw  0    ng 0 MSW",
            f".model MSW SW(Ron={RDS:.6f} Roff=1meg Vt=2.5 Vh=0)",
            # BOUCLE P sur interrupteur ideal (carte de stabilite R2) : le
            # modele Infineon s'y bloquait en DCM sur un front ordinaire,
            # circuit calme (Vout 79,8 V), 2010 relachements a 222 us.
            chr(10).join((
                "* BOUCLE FERMEE -- correcteur PROPORTIONNEL, interrupteur ideal",
                f"Bctrl nctrl 0  V=limit({d0x} + {kp:.6g}*"
                f"({vref:.4f} - V({vmes})), 0.05, 0.95)",
                f"Vramp nramp 0  PULSE(0 1 0 {{tsw*0.999}} {{tsw*0.001}} "
                f"0 {{tsw}})",
                "Bg    ng    0  V=if(V(nctrl)>V(nramp), 5, 0)"))
            if kp else
            f"Vg   ng   0    PULSE(0 5 0 {tr:.3e} {tr:.3e} "
            f"{{duty*tsw}} {{tsw}})"))
    sv_rg = " I(Rgx)" if nom_mos else ""
    sv_pwm = ((" V(nctrl) V(nramp)" if pwm else "")
              + (" V(nint) V(nctrl)" if ki else "")
              + (" V(nctrl)" if (kp and not ki) else ""))
    # SAUVEGARDE SOBRE : les longues fenetres de la carte de stabilite
    # (des milliers de periodes) font des .raw de plusieurs centaines de Mo
    # avec les 22 traces completes. On ne garde que ce que lisent les
    # .meas (I(Vbat), I(L1), I(Vd)) et la boucle (V(nout), V(nctrl)) --
    # le .save couvre TOUJOURS les .meas, c'est la regle qui a manque le
    # 2026-11-22 quand la netlist avait ete charcutee apres coup.
    if sobre:
        sauve = (f".save V(nout) I(L1) I(Vd) I(Vbat){sv_pwm}"
                 + (" V(nsh)" if echant else "")
                 + (" V(nsh2)" if (echant and retard) else ""))
    else:
        sauve = (f".save V(nsw) V(nin) V(nout) V(n1l) V(n2l) V(nsl) V(ng) "
                 f"V(nda) V(ngg){sv_pwm}\n"
                 f".save I(L1) I(Vd) I(Vbat) I(Vsl) I(Rp_l) I(Cp_l) I(Rs_l) "
                 f"I(Cosn) I(Lb){sv_rg}")
    tsw = 1.0 / FSW
    t0, t1 = n_etab * tsw, (n_etab + n_mes) * tsw
    # BOUCLE P SEULEMENT. Le point de fonctionnement DC d'un hacheur n'a
    # pas de sens : la rampe vaut 0 a t=0, le comparateur laisse la grille
    # ON en continu, et l'inductance est un court-circuit -- 114,65 A
    # releves dans p_temoin.op.raw le 2026-11-22. Le transitoire partait
    # de la et chassait Vout hors du domaine des modeles constructeur
    # (MOSFET 150 V) : blocage a 10,9 us, 2010 relachements de tolerance.
    # `.ic I(L1)=` impose le courant moyen attendu PENDANT l'OP (la
    # reference LTspice l'admet pour les courants d'inductance), donc le
    # transitoire part du voisinage du regime etabli. Vout est deja tenu
    # par le ic= du condensateur de sortie, constate dans le meme .op.raw.
    # force_ic : meme .ic en BOUCLE OUVERTE (identification du plant), pour
    # ne pas demarrer a 114 A quand la rampe vaut 0 a t = 0.
    bloc_ic = (f".ic I(L1)={a['iin']:.4f}" + chr(10)
               if (kp or force_ic) else "")
    # DEUX SORTIES AU CHOIX, pour montrer ce que la topologie du banc change
    if charge:
        rl = VOUT ** 2 / p if rl is None else rl
        bloc_sortie = "\n".join((
            "* sortie sur CHARGE : le point se stabilise seul",
            f"Rl   nout 0    {rl:.4f}",
            (f"Cout nout 0    {cout:.4e} ic={VOUT:.1f}"
             if not cout_we else cout_wurth(cout_we)[0])))
        # ECHELON DE CHARGE (etape R2, carte de stabilite) : une seconde
        # resistance branchee a t_step par un interrupteur commande. Ron
        # 1 mOhm devant des centaines d'ohms, front de 100 ns : l'echelon
        # est franc a l'echelle de la boucle (kHz) sans etre une marche
        # infiniment raide pour le solveur.
        if echelon:
            # (r2, t_step) branche r2 a t_step (charge qui MONTE) ;
            # (r2, t_step, "-") part avec r2 branchee et l'ouvre a t_step
            # (charge qui DESCEND, ex. 40 -> 20 W).
            r2, t_step = echelon[:2]
            baisse = len(echelon) > 2 and echelon[2] == "-"
            v0, v1 = (1, 0) if baisse else (0, 1)
            bloc_sortie += "\n" + "\n".join((
                f"* echelon de charge : {'-' if baisse else '+'} {r2:.4g} ohms "
                f"a t = {t_step:.6e} s",
                f"Rl2  nout nrl2 {r2:.4f}",
                f"Sstp nrl2 0    nstp 0 MSTP",
                f".model MSTP SW(Ron=1m Roff=1G Vt=0.5 Vh=0)",
                f"Vstp nstp 0    PWL(0 {v0} {t_step:.6e} {v0} "
                f"{t_step + 100e-9:.6e} {v1})"))
    else:
        bloc_sortie = "\n".join((
            "* sortie RAIDE : aucun rappel, le point est sur un fil",
            f"Vo   nout 0    DC {VOUT:.1f}"))
    if cout_hf:
        # DECOUPLAGE HF DE LA FICHE (banc.toml, reseau_sortie) :
        # 1 uF X7R 200 V 1812 + 0,2 ohm placee, en parallele sur la sortie.
        # Valeurs du modele C_MLCC1812 de gen_emi_dm.py : 0,92 uF effectif
        # (derate), ESR 4 mOhm, ESL 1,6 nH. Sans lui, la charge de Cj de la
        # diode au rallumage DCM passait toute par l'ESL de l'electrolytique :
        # +6 a +14 V de pic sur nout a 180 MHz (2026-11-22).
        bloc_sortie += chr(10) + chr(10).join((
            "* decouplage HF de la fiche : 1 uF X7R 200 V 1812 + 0,2 ohm",
            f"Chf  nout nh1  0.92e-6 ic={VOUT:.1f}",
            "Rhf  nh1  nh2  0.204",
            "Lhf  nh2  0    1.6e-9"))
    # INSTANT D'ECHANTILLONNAGE : echant=True -> debut de periode (0,002 T,
    # historique) ; echant=<fraction> -> a cette fraction de la periode.
    # Le debut de periode tombe SUR le rallumage : l'echantillon y captait
    # la charge de Cj de la diode (gigue de D, 2026-11-22). Le C2000 place
    # son declenchement ADC loin des fronts.
    phase_ech = 0.002 if echant is True else float(echant or 0)
    if echant:
        bloc_sortie += chr(10) + chr(10).join((
            "* echantillonneur-bloqueur de la mesure, horloge = debut de periode",
            f"Vclk nclk 0   PULSE(0 1 {{tsw*{phase_ech:g}}} 1n 1n {{tsw*0.01}} {{tsw}})",
            f"Ash  {vsrc} 0 nclk 0 0 0 nsh 0 SAMPLEHOLD Vhigh=1000 Vlow=-1000"))
        if retard:
            if phase_ech < 0.01:
                raise ValueError("retard : echantillonner en fin de periode")
            bloc_sortie += chr(10) + chr(10).join((
                "* retard d'une periode : second bloqueur, 0,001 T avant le premier",
                f"Vclk2 nclk2 0 PULSE(0 1 {{tsw*{phase_ech - 0.001:g}}} 1n 1n "
                f"{{tsw*0.0005}} {{tsw}})",
                "Ash2 nsh 0 nclk2 0 0 0 nsh2 0 SAMPLEHOLD Vhigh=1000 Vlow=-1000"))
        # Vhigh/Vlow : par defaut la sortie d'un SAMPLEHOLD plafonne a
        # 10 V -- la mesure de 80 V ressortait a 10 V et D collait a 0,95.
    if kp and ki:
        # INTEGRATEUR DU PI. Meme principe que l'etape R3 (G charge 1 F,
        # dV/dt = I), plus un ANTI-WINDUP par arret d'integration : quand
        # V(nint) est en butee (0,05 / 0,95) et que l'erreur pousse plus
        # loin, le courant d'integration est coupe. Sans lui, l'integrale
        # s'emballerait au demarrage et pendant les saturations de D.
        e = f"({vref:.4f} - V({vmes}))"
        bloc_sortie += chr(10) + chr(10).join((
            f"* PI : integrale de l'erreur, Ki = {ki:.6g} /V/s, anti-windup",
            f"Gint 0 nint VALUE={{if((V(nint)>=0.95 & {e}>0) | "
            f"(V(nint)<=0.05 & {e}<0), 0, {ki:.6g}*{e})}}",
            f"Cint nint 0  1 ic={duty:.6f}"))
    if tau_mes:
        bloc_sortie += chr(10) + chr(10).join((
            f"* mesure de Vout : filtre RC anti-repliement ADC, tau {tau_mes*1e6:.3g} us",
            "Rfm  nout nvm  1k",
            f"Cfm  nvm  0    {tau_mes/1e3:.4e} ic={VOUT:.1f}"))
    return f"""* ETAPE 0 -- boost TOUT IDEAL, {VIN:.0f} V -> {VOUT:.0f} V, {p:.0f} W
* Aucun modele constructeur. Interrupteur et diode sont des .model simples.
* But : valider cablage, topologie, physique. PAS la fidelite.
.param tsw={tsw:.6e} duty={duty:.6f}

Vbat nin  0    DC {vin}
{bloc_sortie}

{bloc_l}

{bloc_s}

* PAS de condensateur sur le noeud de commutation aux etapes 0 a 2.
*
* Il y en avait un (50 pF), pose pour brider les +-50 A d'artefact que la
* Cj de la diode donnait dans un interrupteur parfait. La MAILLE regle ce
* probleme a la source ; la capacite, elle, en creait un autre, plus gros
* et mieux cache : sur un interrupteur IDEAL le canal est instantane, donc
* la decharge vaut V/Ron = 534 A, bornee par le seul PAS D'INTEGRATION.
* Releve : 220 A de pointe, et un bilan ouvert de 21,3 % -- l'energie
* partait dans un pic trop bref pour que moy(v.i) le voie.
*
* Le Coss est REEL, mais indissociable du gm fini qui borne sa decharge.
* Les deux arrivent ensemble a l'etape 3, avec l'IPD530N15N3.
*
* La valeur de 1 aF n'est pas un composant : c'est une sonde. Elle laisse
* `I(Cosn)` exister pour que les scripts d'analyse restent identiques
* d'une etape a l'autre -- c'est ce qui rend deux etapes comparables.
Cosn nsw  0    {max(c_noeud, 1e-18):.3e}

{bloc_d}
Vd   nd   nout DC 0

.options plotwinsize=0
{bloc_ic}.tran 0 {t1:.6e} {t0:.6e} {dtmax:.3e}

{sauve}
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
