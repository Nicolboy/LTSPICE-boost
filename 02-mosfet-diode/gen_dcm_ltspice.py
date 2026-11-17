"""Architecture 1 sous LTspice, avec le modele CONSTRUCTEUR de l'EPC2207.

POURQUOI LTSPICE ET PLUS NGSPICE. Le modele EPC est un modele physique
comportemental : le canal est une source B dont l'equation est symetrique
en v(drain,source), et les trois capacites sont definies EN CHARGE
(`C... Q=(...)`). ngspice ne sait pas lire la syntaxe `Q=` d'un
condensateur. Le modele ajuste a la main qu'on utilisait avant (jonction
CJO/VJ/M plus une diode de clamp) reproduisait Qoss a +1,9 % et l'ecretage
a 2,1 V, mais il FABRIQUAIT la separation Coss / 3e quadrant, alors que
sur un GaN c'est le MEME canal qui fait les deux.

CE QUE LE MODELE CONSTRUCTEUR APPORTE, concretement :
  - la conduction en 3e quadrant sort de la physique du canal, pas d'une
    diode postiche : l'ecretage tombe a -1,92 V, contre 1,7 V annonces au
    datasheet a 0,5 A (le courant resonant du palier depasse 0,5 A, donc
    une tension un peu superieure est attendue) ;
  - les capacites sont non lineaires ET croisees (Cgd depend de v(gate,
    drain), Csd de v(source,drain)) ;
  - la derive en temperature est incluse.

--------------------------------------------------------------------------
METHODE DE BILAN -- etablie et verifiee, ne pas la refaire a l'oeil
--------------------------------------------------------------------------
Les pertes se somment UNIQUEMENT sur les elements DISSIPATIFS, jamais par
la puissance entrante aux bornes du composant.

  POURQUOI. La puissance aux bornes du GaN inclut le stockage capacitif,
  reversible : a la coupure les capacites absorbent (+188 mW sur 20 ns),
  pendant le temps mort elles restituent (-182 mW). Ces deux termes se
  compensent en theorie, mais leur integration numerique laisse un residu.
  Mesure : la methode par bornes donne 56,63 mW a 94 ps de pas moyen et
  52,25 mW a 48,6 ps, tandis que la methode par elements donne 51,95 mW
  AUX DEUX PAS. Seule la seconde est convergee.

  PLANCHER DE BOUCLAGE ASSUME : 1,8 % des pertes (0,024 point de
  rendement). Verifie que ce n'est PAS un poste manquant -- ni derive de
  regime (20 periodes d'etablissement au lieu de 4 : inchange), ni methode
  d'integration (trap / modified trap / gear : 1,80 / 1,81 / 1,67 %), ni
  fenetrage (bornes au milieu du temps mort : inchange). C'est l'erreur
  d'integration sur les elements REACTIFS rapides, demontree par un
  Tellegen complet ou l'inductance de maille Lb -- ideale, donc sans
  pertes -- ressort a +1,6 mW sur trois periodes entieres.

--------------------------------------------------------------------------
PIEGES LTSPICE RENCONTRES
--------------------------------------------------------------------------
  - `.options plotwinsize=0` est OBLIGATOIRE : la compression de formes
    d'onde par defaut (300 points par fenetre) detruit les integrales de
    pertes sur des fronts de quelques nanosecondes.
  - le pas moyen reel compte plus que dTmax : a dTmax=0,3125 ns le pas
    moyen est de 94 ps, insuffisant pour les pointes capacitives.
  - choisir un instant de reference par `argmax(I(L1))` tombe PAR
    CONSTRUCTION sur la coupure dans un boost, pas en pleine conduction.
"""
from __future__ import annotations

import math
from pathlib import Path

# 19 V et non 20 : c'est le point DIMENSIONNANT (50 W n'est demande qu'a
# partir de 19 V d'entree), et c'est celui de l'archi 2. Comparer deux
# architectures a des tensions d'entree differentes n'aurait pas de sens.
VIN, VOUT = 19.0, 80.0
# SER2013-472 retenue. Meme 4,7 uH que la SER1360-472, donc meme marge de
# mode (30 % au cas dimensionnant 12 V / 25 W), mais 809 mW et 46 degC au
# point 400 kHz / 2,6 A IDC / 6,3 A dIL, contre 844 mW et 95 degC : la
# SER1360 n'avait aucune reserve thermique en ambiant realiste.
# La SER2915L-472 fait mieux encore (538 mW) mais pour 2,4 fois le volume
# et sans modele SPICE publie, donc sans acces a sa resonance propre.
#   DCR 1,70 mOhm et C_SELF 7,4 pF : modele a elements localises Coilcraft
#   doc 267-28, qui donne une resonance propre a 27,1 MHz (verifiee).
L_H, DCR, C_SELF = 4.7e-6, 1.70e-3, 7.40e-12
L_BOUCLE = 20e-9                                # ESTIMEE -> balayee
FSW = 400e3
RG_EXT = 1.0                                    # driver retenu
VGS = 5.0                                       # VGS max = 6 V (datasheet p.1)

LIB = Path(r"C:\Users\Nicolas\workspace_ccstheia\lib_spice_commun\EPC"
           r"\EPCGaNLibrary.lib")

# V6PW12C, doc Vishay 98199 rev. 17-Mar-2022. IS/N/RS ajustes sur les DEUX
# points 25 degC de la table p.2 (0,58 V a 1,5 A ; 0,73 V a 3,0 A),
# CJO/VJ/M sur la Fig.5 p.3. TT=0 : c'est une Schottky, Qrr nul.
# V8PA22, Vishay doc 87473 rev. 20-Apr-2023. Remplace la V6PW12C, qui
# etait calibree 120 V sur un rail de 80 V alors que la resonance de maille
# y porte la tension inverse a plus de 300 V. Le calibre 8 A, confortable
# en CCM, est NECESSAIRE ici : le courant crete du DCM atteint 8 A.
#   IS/N/RS : les deux points de la table p.2 a 25 degC (0,77 V a 4 A ;
#   0,84 V a 8 A), N=1,05 pose. CJO/VJ/M : ancrage sur 400 pF a 4 V,
#   pente du rapport lu a 80 V sur la Fig.5 p.3.
#   BV=400 : on ne veut PAS d'ecretage, on veut lire la contrainte reelle.
DIODE = ("DV8PA22",
         "D(is=7e-05 rs=0.00741429 n=2.62377 xti=13.7366 bv=220 eg=0.71 "
         "cjo=6.85e-10 m=1 vj=5.36 tt=7.73585e-10 ikf=0 fc=0.5 "
         "ibv=1e-10 isr=-7.00037e-07 trs1=-0.00514056)")

N_ETAB = 20          # periodes d'etablissement (4 ne suffisaient pas a
                     # stabiliser Pin a mieux que 10 mW)
N_MES = 4            # periodes mesurees


def duty_dcm(pout: float, eta: float = 0.98) -> float:
    """Rapport cyclique en DCM : Pout = Vin^2 D^2/(2 L fsw) * Vout/(Vout-Vin)."""
    return math.sqrt(2.0 * pout * L_H * FSW * (VOUT - VIN) / (eta * VIN**2 * VOUT))


def seuil_dcm(fsw: float = FSW, l_h: float = L_H) -> float:
    return VIN**2 * (1 - VIN / VOUT) / (2 * fsw * l_h)


def netlist(duties: tuple[float, ...], l_boucle: float = L_BOUCLE,
            fsw: float = FSW, dtmax: float = 0.1e-9) -> str:
    """Netlist LTspice balayant le rapport cyclique par `.step`.

    Un seul run donne tout le domaine de puissance : chaque pas fournit son
    couple (Pout, tension du noeud a l'allumage), ce qui evite le trim
    iteratif et garantit que tous les points partagent exactement le meme
    modele et les memes options.
    """
    tsw = 1.0 / fsw
    t_etab = N_ETAB * tsw
    # les allumages tombent sur les multiples de tsw ; on cale la fenetre de
    # mesure sur le PREMIER allumage apres l'etablissement, pour integrer un
    # nombre entier de periodes a phase identique
    t0 = math.ceil(t_etab / tsw) * tsw
    t1 = t0 + N_MES * tsw
    # instant de lecture de la tension du noeud : 100 ps AVANT un allumage
    # (le front de grille dure 150 ps, donc le noeud y est encore libre)
    t_von = t0 + 2 * tsw - 100e-12
    tr = 0.15e-9
    # LTspice refuse un .step a un seul pas : en run unique on passe donc
    # par un .param, ce qui donne exactement le meme circuit.
    if len(duties) == 1:
        bal = f".param duty={duties[0]:.6f}"
    else:
        bal = ".step param duty list " + " ".join(f"{d:.5f}" for d in duties)
    return f"""* Architecture 1 -- EPC2207 (modele constructeur), DCM {fsw/1e3:.0f} kHz
* genere par gen_dcm_ltspice.py -- ne pas editer a la main
.lib {LIB}

.param TSW={tsw:.6e} LB={l_boucle:.4e} RGEXT={RG_EXT}
{bal}
.temp 25

V1   vin  0    DC {VIN}
Vo   vout 0    DC {VOUT}

* --- inductance SER1360-472KL : L, DCR, capacite propre (SRF 32 MHz).
* Elle arrive directement sur le noeud chaud : l'inductance de sa piste est
* negligeable devant {L_H*1e6:.1f} uH et n'aurait aucun effet dynamique.
L1   vin  nl   {L_H:.4e}
Rdcr nl   nsw  {DCR:.4e}
Cl   vin  nsw  {C_SELF:.4e}

* --- switch : modele constructeur EPC2207 (gatein drainin sourcein).
* Vs est une sonde 0 V : elle permet de mesurer le courant de source sans
* rien changer au circuit.
X1   ng   nsw  nss  EPC2207
Vs   nss  0    DC 0
Rg   ngd  ng   {{RGEXT}}
Vg   ngd  0    PULSE(0 {VGS} 0 {tr:.3e} {tr:.3e} {{duty*TSW}} {{TSW}})

* --- INDUCTANCE DE MAILLE DE COMMUTATION, dans la branche diode : c'est
* la maille noeud -> diode -> sortie -> masse -> switch que le courant doit
* traverser pour basculer du switch vers la diode. La placer en serie avec
* L1 n'aurait aucun effet, elle y serait en serie avec {L_H*1e6:.1f} uH.
Lb   nsw  nda  {{LB}}

* --- diode Schottky V6PW12C (une seule jambe du boitier double)
D1   nda  nd   {DIODE[0]}
Vd   nd   vout DC 0

.model {DIODE[0]} {DIODE[1]}

* plotwinsize=0 : sans lui la compression de formes d'onde detruit les
* integrales de pertes sur des fronts de quelques nanosecondes
.options reltol=1e-5 abstol=1e-13 vntol=1e-9 chgtol=1e-16 plotwinsize=0
.tran 0 {t1:.6e} {t_etab:.6e} {dtmax:.3e} uic

.save V(nsw) V(ng) V(nss) V(nda) V(nd) V(ngd) I(L1) I(V1) I(Vd) I(Vg)
.save I(x1:bswitch) I(x1:rd) I(x1:rs) I(x1:rg)
.save V(x1:drain) V(x1:source) V(x1:gate)

* --- grandeurs de fonctionnement
.meas TRAN pout  AVG {VOUT}*I(Vd)          FROM {t0:.6e} TO {t1:.6e}
.meas TRAN pin   AVG {-VIN}*I(V1)          FROM {t0:.6e} TO {t1:.6e}
.meas TRAN pvg   AVG -V(ngd)*I(Vg)         FROM {t0:.6e} TO {t1:.6e}
.meas TRAN ipk   MAX I(L1)                 FROM {t0:.6e} TO {t1:.6e}
.meas TRAN ilrms RMS I(L1)                 FROM {t0:.6e} TO {t1:.6e}
.meas TRAN vpk   MAX V(nsw)                FROM {t0:.6e} TO {t1:.6e}
.meas TRAN vmin  MIN V(nsw)                FROM {t0:.6e} TO {t1:.6e}
* contrainte en tension inverse de la diode -- JAMAIS mesuree jusqu'ici
.meas TRAN vdrev MIN (V(nda)-V(nd))        FROM {t0:.6e} TO {t1:.6e}
* LA grandeur qui decide du ZVS : tension du noeud juste avant l'allumage
.meas TRAN von   FIND V(nsw) AT={t_von:.9e}

* --- pertes, par elements DISSIPATIFS uniquement (cf. docstring)
.meas TRAN pcanal AVG (V(x1:drain)-V(x1:source))*I(x1:bswitch) FROM {t0:.6e} TO {t1:.6e}
.meas TRAN prd    AVG (V(nsw)-V(x1:drain))*I(x1:rd)            FROM {t0:.6e} TO {t1:.6e}
.meas TRAN prs    AVG (V(nss)-V(x1:source))*I(x1:rs)           FROM {t0:.6e} TO {t1:.6e}
.meas TRAN prgi   AVG (V(ng)-V(x1:gate))*I(x1:rg)              FROM {t0:.6e} TO {t1:.6e}
.meas TRAN pdio   AVG (V(nda)-V(nd))*I(Vd)                     FROM {t0:.6e} TO {t1:.6e}
.meas TRAN pcu    AVG I(L1)*I(L1)*{DCR:.4e}                    FROM {t0:.6e} TO {t1:.6e}
.meas TRAN prge   AVG (V(ngd)-V(ng))*(V(ngd)-V(ng))/{RG_EXT}   FROM {t0:.6e} TO {t1:.6e}
.end
"""


def lit_log(log: Path) -> list[dict]:
    """Extrait les .meas d'un log LTspice stepped.

    Format : une ligne d'en-tete `Measurement: nom` puis une ligne par pas,
    `  <index>  <valeur>  <...>`. Les mesures non stepped sortent en
    `nom: ... =valeur`.
    """
    import re
    txt = log.read_text(encoding="utf-8", errors="replace")
    res: dict[str, dict[int, float]] = {}
    mesure = None
    for ligne in txt.splitlines():
        m = re.match(r"^Measurement:\s*(\S+)", ligne)
        if m:
            mesure = m.group(1).lower()
            res.setdefault(mesure, {})
            continue
        if mesure:
            m = re.match(r"^\s*(\d+)\s+([-+0-9.eE]+)", ligne)
            if m:
                res[mesure][int(m.group(1))] = float(m.group(2))
                continue
            if ligne.strip() and not ligne.startswith(" "):
                mesure = None
    if not res:          # run non stepped
        for m in re.finditer(r"^(\w+):\s*\S+=([-+0-9.eE]+)", txt, re.M):
            res.setdefault(m.group(1).lower(), {})[1] = float(m.group(2))
    n = max((max(v) for v in res.values() if v), default=0)
    return [{k: v.get(i) for k, v in res.items()} for i in range(1, n + 1)]


if __name__ == "__main__":
    print(f"Seuil DCM/CCM a {FSW/1e3:.0f} kHz / {L_H*1e6:.1f} uH : "
          f"{seuil_dcm():.1f} W -> DCM garanti de 5 a 50 W\n")
    print(f"{'Pout vise':>10} {'D (formule)':>12}")
    for p in (5, 10, 20, 30, 40, 50):
        print(f"{p:9.0f} W {duty_dcm(p):12.4f}")
