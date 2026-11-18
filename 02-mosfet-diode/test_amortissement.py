"""Amortissement de l'oscillation de temps mort -- banc de test.

LE CONSTAT A EXPLIQUER. Sur les oscillogrammes du chapitre 3, le noeud de
commutation montre trois phases : switch ferme, rien ; switch ouvert,
decharge de l'inductance avec une oscillation haute frequence amortie ;
puis, des que I(L) = 0, une oscillation basse frequence QUI NE S'AMORTIT
PAS jusqu'a l'allumage suivant. La troisieme n'est pas physique.

LE MECANISME. Pendant le temps mort la diode est bloquee et le switch
aussi : le noeud flotte, et l'inductance se retrouve en parallele avec
Coss du GaN, Cj de la diode et sa propre capacite. Ce circuit resonnant
n'a, dans le banc actuel, qu'une seule resistance : la DCR de 1,7 mOhm.
Avec Z0 = sqrt(L/C) de l'ordre de 180 Ohm, cela donne un facteur de
qualite de Z0/DCR, soit plus de 100 000. L'oscillation ne peut pas
s'amortir : rien ne dissipe.

CE QUE CE BANC TESTE. Cinq variantes d'inductance, au MEME point de
fonctionnement, pour separer les causes au lieu de les supposer :

  ideal        L + DCR 1,70 mOhm + Cpar 7,4 pF -- l'etat actuel du banc
  dcr_reelle   idem mais DCR 5,5 mOhm et Cpar 4,578 pF du modele reel,
               ce qui isole l'effet de la seule resistance SERIE
  pkz          dcr_reelle plus une resistance en PARALLELE sur L, qui
               isole l'effet du seul amortissement parallele
  constructeur SER1360-472_imp, modele Coilcraft complet (Model1D)
  snubber      constructeur plus un reseau RC sur le noeud, pour chiffrer
               ce que couterait un amortissement ajoute

--------------------------------------------------------------------------
POURQUOI LE MODELE _imp ET PAS LE MODELE _freq
--------------------------------------------------------------------------
Coilcraft publie DEUX modeles par reference, et le dit dans l'en-tete de
chaque bloc :

  <ref>_freq  "Inductor Frequency Model -- Use model for Frequency Domain
              simulations"  -> Model1A, ou les pertes sont deux sources
              LAPLACE en racine de f (k1*sqrt(f) en serie, k2*sqrt(f) en
              parallele).
  <ref>_imp   "Inductor Impedance Model -- Use model for Time Domain
              simulations"  -> Model1D, pur R/L/C, ou tout l'amortissement
              tient a UNE resistance PkZ en parallele sur L.

`PkZ` est l'impedance de CRETE mesuree a la resonance propre : a la
resonance L et C s'annulent et il ne reste que cette resistance, donc
Coilcraft y cale directement la valeur relevee. C'est une donnee de
mesure, pas un ajustement libre.

ATTENTION, ce banc utilise la SER1360-472 et NON la SER2013-472 retenue au
chapitre 3 : Coilcraft ne publie aucun modele pour la SER2013-472 (la
famille s'arrete a 2,0 uH). La SER1360-472 est le seul 4,7 uH de la gamme
SER modelise, et le chapitre etablit par ailleurs que les deux familles
partagent le materiau de noyau. Elle sert donc de SUBSTITUT documente pour
la question de l'amortissement, pas de composant retenu.
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE / ".claude/skills/sim-spice/scripts"))
from ltspice_run import lance                                   # noqa: E402

TRAVAIL = ICI / "results" / "amortissement"
FIGURES = ICI / "illustrations" / "amortissement"

LIB_EPC = RACINE / "lib_spice_commun/EPC/EPCGaNLibrary.lib"
DIR_CC = RACINE / "lib_spice_commun/Coilcraft"

# --- point de fonctionnement : 20 V / 15 W, pris dans la liste des neuf
# points de validation. Choisi parce que son intervalle a courant nul dure
# ~1,4 us, soit une dizaine de cycles de l'oscillation a mesurer.
VIN, VOUT, FSW = 20.0, 80.0, 400e3
L_H = 4.7e-6
L_BOUCLE = 20e-9
RG_EXT, VGS = 1.0, 5.0
P_VISEE = 15.0

N_ETAB, N_MES = 4, 8          # DCM : le regime s'etablit en 1-2 periodes
DTMAX = 0.2e-9               # 0,2 ns -> Nyquist a 2,5 GHz apres reechant.

DIODE = ("DV8PA22",
         "D(is=7e-05 rs=0.00741429 n=2.62377 xti=13.7366 bv=220 eg=0.71 "
         "cjo=6.85e-10 m=1 vj=5.36 tt=7.73585e-10 ikf=0 fc=0.5 "
         "ibv=1e-10 isr=-7.00037e-07 trs1=-0.00514056)")

# --- modele constructeur, extrait du fichier Coilcraft (cf. docstring)
SER1360_472 = dict(R1=230.0, R2=5.5e-3, Cpar=4.578e-12, L=4.7e-6,
                   PkZ=1777.83393)
# reseau RC d'amortissement, variante `snubber` : R calee sur Z0 du
# circuit resonnant, C a quelques fois la capacite parasite.
SN_R, SN_C = 180.0, 220e-12


def subckt_vendor(fichier: Path, nom: str) -> str:
    """Extrait un bloc `.subckt ... .ends` VERBATIM d'un fichier fournisseur.

    On recopie au lieu d'inclure le fichier entier parce que SER1360.lib
    commence par `.inc CoilcraftTemplates.lib` : inclure les deux donnerait
    une double definition des templates, que LTspice refuse.
    """
    txt = fichier.read_bytes().decode("utf-8", "replace")
    m = re.search(rf"^\.subckt\s+{re.escape(nom)}\b.*?^\.ends.*?$",
                  txt, re.S | re.M | re.I)
    if not m:
        raise LookupError(f"{nom} absent de {fichier.name}")
    return m.group(0).strip()


# ------------------------------------------------------------- inductances

def bloc_inductance(variante: str) -> tuple[str, str]:
    """Rend (lignes du circuit, lignes de definition) pour une variante.

    L'inductance est toujours entre `nla` et `nsw`, derriere une sonde de
    courant 0 V, pour que I(Vl) designe le meme courant dans les cinq cas.
    """
    v = SER1360_472
    if variante == "ideal":
        return (f"L1   nla  nl   {L_H:.4e}\n"
                f"Rdcr nl   nsw  1.70e-3\n"
                f"Cl   nla  nsw  7.40e-12"), ""
    if variante == "dcr_reelle":
        return (f"L1   nla  nl   {v['L']:.4e}\n"
                f"Rdcr nl   nsw  {v['R2']:.4e}\n"
                f"Cl   nla  ncl  {v['Cpar']:.4e}\n"
                f"Rcl  ncl  nsw  {v['R1']:.1f}"), ""
    if variante == "pkz":
        return (f"L1   nla  nl   {v['L']:.4e}\n"
                f"Rdcr nl   nsw  {v['R2']:.4e}\n"
                f"Cl   nla  ncl  {v['Cpar']:.4e}\n"
                f"Rcl  ncl  nsw  {v['R1']:.1f}\n"
                f"Rpkz nla  nsw  {v['PkZ']:.4f}"), ""
    if variante in ("constructeur", "snubber"):
        return ("XL   nla  nsw  SER1360-472_imp",
                subckt_vendor(DIR_CC / "CoilcraftTemplates.lib", "Model1D")
                + "\n" + subckt_vendor(DIR_CC / "SER1360.lib",
                                       "SER1360-472_imp"))
    raise ValueError(variante)


# ---------------------------------------------------------------- netlist

def duty_dcm(pout: float, eta: float = 0.98) -> float:
    return math.sqrt(2.0 * pout * L_H * FSW * (VOUT - VIN)
                     / (eta * VIN**2 * VOUT))


def netlist(variante: str, duty: float, *, n_etab: int = N_ETAB,
            n_mes: int = N_MES, dtmax: float = DTMAX,
            sonnerie: float = 0.0) -> str:
    """Netlist du banc. `sonnerie` > 0 coupe la grille apres `n_etab`
    periodes et observe la decroissance libre pendant ce temps-la.

    POURQUOI UNE SONNERIE LIBRE. Mesurer un facteur de qualite sur le seul
    intervalle a courant nul demande d'ajuster une exponentielle sur
    1,4 us. Quand l'amortissement est faible, la decroissance n'y est que
    de quelques pour cent : l'ajustement est mal conditionne et le Q qui en
    sort n'est pas une mesure. En laissant le circuit sonner sur 30 us on
    observe plusieurs constantes de temps, et le Q devient lisible.
    """
    tsw = 1.0 / FSW
    t0 = n_etab * tsw            # les allumages tombent sur les multiples
    t1 = t0 + (sonnerie if sonnerie else n_mes * tsw)
    circuit, defs = bloc_inductance(variante)
    snub = (f"Rsn  nsw  nsc  {SN_R:.1f}\nCsn  nsc  0    {SN_C:.4e}"
            if variante == "snubber" else "")
    # le .save et le .meas du snubber n'existent que dans cette variante :
    # le controleur de netlist refuse toute grandeur mesuree hors .save.
    sv_sn = " I(Rsn)" if variante == "snubber" else ""
    ms_sn = (f".meas TRAN psn AVG V(nsw)*I(Rsn) FROM {t0:.6e} TO {t1:.6e}"
             if variante == "snubber" else "")
    # Ncycles, 8e champ de PULSE : la grille s'arrete apres n_etab cycles
    # et le circuit est livre a lui-meme.
    ncyc = f" {n_etab}" if sonnerie else ""
    return f"""* Amortissement du temps mort -- variante {variante} -- {VIN:.0f} V
* genere par test_amortissement.py -- ne pas editer a la main
.lib {LIB_EPC}

.param TSW={tsw:.6e} duty={duty:.6f}
.temp 25

V1   vin  0    DC {VIN}
Vo   vout 0    DC {VOUT}

* --- sonde de courant d'inductance : 0 V, sans effet sur le circuit
Vl   vin  nla  DC 0

{circuit}

X1   ng   nsw  nss  EPC2207
Vs   nss  0    DC 0
Rg   ngd  ng   {RG_EXT}
Vg   ngd  0    PULSE(0 {VGS} 0 0.15n 0.15n {{duty*TSW}} {{TSW}}{ncyc})

Lb   nsw  nda  {L_BOUCLE:.4e}
D1   nda  nd   {DIODE[0]}
Vd   nd   vout DC 0
{snub}

.model {DIODE[0]} {DIODE[1]}
{defs}

.options reltol=1e-5 abstol=1e-13 vntol=1e-9 chgtol=1e-16 plotwinsize=0
.tran 0 {t1:.6e} {t0:.6e} {dtmax:.3e} uic

.save V(nsw) V(nda) V(nd) V(ng) I(Vl) I(Vd) I(V1) I(Vg){sv_sn}

.meas TRAN pout AVG {VOUT}*I(Vd)      FROM {t0:.6e} TO {t1:.6e}
.meas TRAN pin  AVG {-VIN}*I(V1)      FROM {t0:.6e} TO {t1:.6e}
.meas TRAN ipk  MAX I(Vl)             FROM {t0:.6e} TO {t1:.6e}
.meas TRAN vpk  MAX V(nsw)            FROM {t0:.6e} TO {t1:.6e}
.meas TRAN vmin MIN V(nsw)            FROM {t0:.6e} TO {t1:.6e}
{ms_sn}
.end
"""


# -------------------------------------------------------------- impedance

def netlist_ac(variante: str) -> str:
    """Impedance de l'inductance SEULE : 1 A injecte, donc V = Z."""
    circuit, defs = bloc_inductance(variante)
    circuit = circuit.replace("nla", "n1").replace("nsw", "0")
    return f"""* Impedance de l'inductance -- variante {variante}
.param TSW=1
I1   0    n1   AC 1
{circuit}
{defs}
.options plotwinsize=0
.ac dec 400 10k 300Meg
.save V(n1)
.end
"""


# ------------------------------------------------------------------- runs

def run(nom: str, texte: str, essais: int = 2) -> dict:
    """Lance, et RELANCE une fois en cas d'echec transitoire.

    LTspice sort parfois en code 0 avec un .raw de 0 octet ; la relance a
    l'identique reussit. On ne retente que ce cas-la -- une netlist fausse
    echouerait a l'identique, et la retenter masquerait la faute.
    """
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    cir = TRAVAIL / f"{nom}.cir"
    cir.write_text(texte, encoding="ascii")
    for essai in range(essais):
        r = lance(cir)
        if r["ok"]:
            break
        if "VIDE" not in r["diagnostic"] or essai == essais - 1:
            raise RuntimeError(f"{nom} : {r['diagnostic']}")
        print(f"    ({nom} : .raw vide, relance)")
    if r["diagnostic"]:
        print(f"    (avertissement {nom} : {r['diagnostic']})")
    return r


def lit_raw(chemin, noms):
    from spicelib.raw.raw_read import RawRead
    r = RawRead(str(chemin))
    ax = r.get_trace(r.get_trace_names()[0]).get_wave()
    x = np.asarray(ax, dtype=complex) if np.iscomplexobj(ax) else \
        np.abs(np.asarray(ax, dtype=float))
    out = {}
    for n in noms:
        out[n] = np.asarray(r.get_trace(n).get_wave())
    return x, out
