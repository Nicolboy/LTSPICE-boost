"""R2 — le correcteur PROPORTIONNEL. Le plus simple, et le premier.

POURQUOI IL VIENT AVANT L'INTEGRATEUR

Un P n'ajoute AUCUNE phase. C'est le correcteur le plus docile du lot, et
il ne peut pas saturer puisqu'il n'integre pas. J'avais commence par
l'integrateur -- qui ajoute -90 degres PARTOUT, le plus contraignant --
en pretendant suivre "le plus simple d'abord". Le concepteur a redresse.

DEUX CHOSES QU'IL MESURE, et qu'aucun autre ne mesure aussi proprement

  1. LE GAIN DE BOUCLE, par son erreur residuelle. Avec
         Vout = (Vout_ouvert + Kp.G.Vref) / (1 + Kp.G)
     l'ecart a la consigne donne Kp.G directement. Pas de modele, pas
     d'hypothese : une division.

  2. LA LIMITE DE STABILITE SANS AUCUN DEPHASAGE AJOUTE. Si un P pur ne
     peut deja pas monter, c'est que le PLANT est en cause -- son pic de
     resonance -- et non le correcteur. C'est ce que R3 a suggere sans
     pouvoir le prouver, l'integrateur melangeant les deux effets.

CE QUE R3 A DEJA ETABLI (integrateur pur)
  erreur statique annulee exactement a 10, 20 et 40 W : 80,000 V
  plafond a 790 Hz, fixe par le PIC DE RESONANCE et non par la phase au
  croisement -- |T| repasse au-dessus de 1 a 4 kHz ou la phase vaut -204
  echec a 5 W, cause NON ETABLIE : deux hypotheses refutees, la
  non-linearite du plant (gain local constant a 163 V) et la saturation
  au demarrage (partir du bon rapport cyclique ne change rien)

C'est ce dernier point que le P doit trancher : s'il tient a 5 W, le
probleme est dans l'integration ; s'il echoue aussi, il est ailleurs.

RETOUR D'EXPERIENCE DU 2026-11-22 -- pourquoi ce fichier ne contient
QU'UN TEMOIN pour l'instant

La premiere version lancait CINQ cas par `subprocess.Popen` direct, apres
avoir CHARCUTE la netlist generee : `.save` supprime puis reduit a deux
signaux (en laissant les `.meas` orphelins), `plotwinsize=0` remplace par
256, `cshunt` ajoute. Resultat : cinq `.raw` vides, `Direct Newton
iteration failed to find operating point`, et SIX griefs que le gendarme
aurait rendus en quelques secondes sur UN cas. Le garde de lancement
(simcommun.garde_lancement) interdit desormais ce chemin.

Donc ici : la netlist TELLE QUE GENEREE par etape0 -- qui est
auto-coherente, son .save couvre ses .meas -- et UN cas, par
`ltspice_run.campagne()`, controle contre un attendu. Le balayage sera
ecrit APRES que ce temoin aura ete lu et valide, pas avant.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parent
for q in (str(RAC / "04-emi/etapes"),
          str(RAC.parent / ".claude/skills/sim-spice/scripts"),
          str(RAC.parent / ".claude/skills/sim-commun")):
    sys.path.insert(0, q)
import etape                                                 # noqa: E402
import ltspice_run                                           # noqa: E402
from simcommun.lecture import lire                           # noqa: E402

FSW, VIN, VREF, COUT, DUTY0 = 200e3, 20.0, 80.0, 2.2e-6, 0.750929

# Vout en boucle OUVERTE au rapport cyclique de reference, par charge.
# Mesures des bancs R0/R1b. C'est le point de depart contre lequel le P
# se mesure.
OUV = {1280.0: 134.3, 640.0: 103.0, 320.0: 80.0, 160.0: 79.90}


def prepare(tag, kp, rl, n_etab=120, n_mes=150):
    """La netlist TELLE QUE GENEREE. Aucune retouche apres coup.

    n_etab=120 : boucle fermee avec Kp.G ~ 3, la constante de temps vaut
    R.C/(1+Kp.G) ~ 84 us soit 17 periodes ; 120 en laisse 7 fois plus.
    n_mes=150 : la resonance du plant est a ~3,9 kHz (256 us, 51
    periodes) ; 150 periodes en couvrent trois alternances.
    """
    n = etape.etape0(p=40.0, vin=VIN, charge=True, rl=rl, cout=COUT,
                     ser=True, v8pa22=True, mos="ipd530", n_etab=n_etab,
                     n_mes=n_mes, dtmax=200e-9, duty=DUTY0, kp=kp, vref=VREF)
    f = ICI / f"{tag}.cir"
    f.write_text(n, encoding="utf-8")
    return f


def lis(f):
    """Rend (Vout moyen, ondulation BF, duty min, duty max).

    REECHANTILLONNAGE UNIFORME D'ABORD, et ce n'est pas un detail : les
    pas de LTspice se resserrent sur les fronts de commutation, donc une
    moyenne glissante par ECHANTILLONS est une moyenne ponderee par la
    densite de pas, pas une moyenne temporelle. Constate le 2026-11-22
    sur ce temoin : 79,933 V par echantillons contre 80,087 V en vraie
    moyenne temporelle -- 0,15 V d'ecart, plus gros que l'erreur de
    boucle qu'on pretendait mesurer.
    """
    r = lire(str(Path(f).with_suffix(".raw")))
    t = np.asarray(r.x)
    np_ = 256                      # points par periode, grille uniforme
    n = max(int(round((t[-1] - t[0]) * FSW)) * np_, 4 * np_)
    tu = np.linspace(t[0], t[-1], n)
    vu = np.interp(tu, t, np.asarray(r.trace("V(nout)")).real)
    du = np.interp(tu, t, np.asarray(r.trace("V(nctrl)")).real)

    def gliss(y):
        c = np.concatenate(([0.0], np.cumsum(y)))
        return (c[np_:] - c[:-np_]) / np_

    vm, dm = gliss(vu), gliss(du)
    tm = tu[np_ // 2: np_ // 2 + len(vm)]
    m = tm > tm[0] + 0.7 * (tm[-1] - tm[0])
    return (float(np.mean(vm[m])), float(vm[m].max() - vm[m].min()),
            float(dm.min()), float(dm.max()))


def temoin(kp=0.002) -> int:
    """UN cas, lu et verifie. Rien d'autre tant qu'il n'est pas bon.

    Kp = 0,002 par defaut, et ce n'est pas de la prudence vague : avec le
    gain statique 321 mesure en R1, Kp.G = 0,64 < 1 PARTOUT, donc aucune
    oscillation entretenue n'est possible, quel que soit le dephasage.
    C'est le discriminant : si CE cas aboutit, le banc est sain, et
    l'echec releve a Kp = 0,01 (blocage a 439 us apres 88 periodes
    regulees, noeud interne du modele Infineon) est un RESULTAT -- la
    limite de stabilite du P, precisement ce que R2 doit mesurer. S'il
    echoue aussi, la cause est numerique (nctrl suit nout
    instantanement dans le comparateur) et c'est le banc qu'il faut
    corriger.
    """
    rl = 160.0
    print("  LE TEMOIN R2 -- ce qu'il doit trancher, AVANT tout balayage\n")
    print("  Question : le banc en boucle P produit-il un point de")
    print("  fonctionnement -- un .raw complet, Vout plausible, rapport")
    print("  cyclique hors butees ? C'est ce que les cinq cas lances en")
    print("  aveugle le 2026-11-22 n'ont jamais etabli.\n")
    print("  Parametres retenus, et pourquoi :")
    print(f"     Kp      = {kp}      Kp.G ~ {kp*321:.2f} avec le gain 321")
    print("                        mesure en R1" +
          (" : < 1 partout, aucune oscillation" if kp * 321 < 1 else ""))
    print(f"     charge  = {rl:.0f} ohms  40 W, le point nominal CCM valide")
    print(f"     Vin     = {VIN:.0f} V    duty0 = {DUTY0}  Vref = {VREF:.0f} V")
    print(f"     Cout    = {COUT*1e6:.1f} uF   fenetre 120+150 periodes,")
    print("                        dtmax 200 ns")
    print("  Attendu impose a campagne() : V(nout) moyen dans [72, 88],")
    print("  I(L1) moyen dans [1,0, 3,0] A (2,05 A au bilan 40 W).\n")

    f = prepare("p_temoin", kp, rl)
    t0 = time.monotonic()
    r = ltspice_run.campagne([f], attendu={"V(nout)": (72.0, 88.0),
                                           "I(L1)": (1.0, 3.0)})
    dt = time.monotonic() - t0
    res = r["resultats"].get("p_temoin", {})
    print(f"  campagne() : {'OK' if r['ok'] else 'REFUS'} en {dt:.0f} s")
    print(f"     {r['diagnostic']}")
    if not r["ok"]:
        return 1

    m = res.get("meas", {})
    print(f"\n  .meas du journal : iin = {m.get('iin', float('nan')):.3f} A"
          f"   il = {m.get('il', float('nan')):.3f} A"
          f"   ilmx = {m.get('ilmx', float('nan')):.3f} A")
    v, osc, dmin, dmax = lis(f)
    err = VREF - v
    print(f"\n  Lecture du .raw (derniers 30 % de la fenetre) :")
    print(f"     Vout moyen   {v:8.3f} V   (boucle ouverte : "
          f"{OUV[rl]:.2f} V, consigne {VREF:.0f} V)")
    print(f"     erreur       {err:+8.3f} V")
    print(f"     ondulation BF {osc:7.3f} V")
    print(f"     rapport cyclique dans [{dmin:.4f}, {dmax:.4f}]"
          f"   (butees a 0,05 / 0,95)")
    print("\n  NOTE sur le gain de boucle : a 40 W la boucle ouverte est")
    print("  deja a 79,90 V, a 0,1 V de la consigne. La division")
    print("  (Vouv-Vout)/(Vout-Vref) y est mal conditionnee -- le gain se")
    print("  mesurera aux charges ou l'ecart ouvert est franc (5-10 W).")
    print("  Le temoin, lui, repond a la question posee : le banc tourne.")
    return 0


def _vm(f):
    """Moyennes par periode sur grille UNIFORME : (tm, vm, dm)."""
    r = lire(str(Path(f).with_suffix(".raw")))
    t = np.asarray(r.x)
    np_ = 256
    n = max(int(round((t[-1] - t[0]) * FSW)) * np_, 4 * np_)
    tu = np.linspace(t[0], t[-1], n)
    vu = np.interp(tu, t, np.asarray(r.trace("V(nout)")).real)
    du = np.interp(tu, t, np.asarray(r.trace("V(nctrl)")).real)

    def gliss(y):
        c = np.concatenate(([0.0], np.cumsum(y)))
        return (c[np_:] - c[:-np_]) / np_

    vm, dm = gliss(vu), gliss(du)
    return tu[np_ // 2: np_ // 2 + len(vm)], vm, dm


N_ETAB, N_MES = 120, 400


def enveloppe(tm, vm):
    """Taux de decroissance de l'oscillation de la moyenne : (f, sigma, zeta).

    Regression de ln(crete) contre t, sur les cretes POSITIVES autour de
    la moyenne de la seconde moitie. sigma < 0 : l'oscillation s'eteint.
    C'est le SIGNE qui tranche, pas un seuil : la premiere version
    exigeait a3 <= 0,35.a1 entre premier et dernier tiers, et a classe
    ENTRETENU un cas qui decroissait a tau = 5,4 ms (zeta = 0,005) --
    stable, a peine, mais stable. Le seuil etait arbitraire, le signe ne
    l'est pas.
    """
    from scipy.signal import find_peaks
    x = vm - np.mean(vm[len(vm) // 2:])
    dt = tm[1] - tm[0]
    # cretes ET creux : sur un cas qui meurt tot (0,0063 : 1,7 periode
    # d'oscillation lisible) les cretes seules ne font pas quatre points.
    d = max(int(5e-5 / dt), 1)
    ph, _ = find_peaks(x, distance=d, height=0.0)
    pb, _ = find_peaks(-x, distance=d, height=0.0)
    pk = np.sort(np.concatenate((ph, pb)))
    if len(pk) < 3:
        return float("nan"), float("nan"), float("nan")
    tp, ap = tm[pk], np.abs(x[pk])
    T = 2.0 * float(np.median(np.diff(tp)))
    sig = float(np.polyfit(tp, np.log(ap), 1)[0])
    return 1.0 / T, sig, -sig / np.hypot(sig, 2 * np.pi / T)


def un_cas(kp):
    """UN cas, lance par le chemin controle, et son verdict.

    Le demarrage depuis `.ic` excite la resonance du plant en boucle
    fermee, a f0.sqrt(1+Kp.G) -- 4,9 a 6,7 kHz sur le domaine balaye.
    Verdict : le SIGNE du taux de decroissance de l'enveloppe.

    UNE SIMULATION MORTE N'EST PAS UNE BOUCLE INSTABLE. La premiere
    version le decretait, et ca s'est trouve juste a Kp = 0,0063 -- mais
    par chance : relance avec sauvegarde depuis t = 0, le cas montre une
    oscillation qui CROIT (cretes 82,4 -> 83,0 V) puis meurt a 304 us sur
    un noeud interne du modele Infineon, Vout = 79 V et IL = 4 A, rien
    d'aberrant. La mort est numerique ; l'instabilite, elle, se lit dans
    les donnees d'avant. Donc : morte = INDETERMINE, et la dichotomie
    s'arrete pour qu'on aille lire.
    """
    tag = ("d" + f"{kp:.6f}".rstrip("0")).replace(".", "p")
    f = prepare(tag, kp, 160.0, n_etab=N_ETAB, n_mes=N_MES)
    t0 = time.monotonic()
    r = ltspice_run.lance(f)
    dt = time.monotonic() - t0
    if not r["ok"]:
        d = r["diagnostic"]
        if any(x in d for x in ("ABANDON", "Iteration limit", "Time step",
                                "TRONQUE", "aucun .raw")):
            return dict(kp=kp, stable=None, mort=True, s=dt,
                        diag=d.splitlines()[0][:90])
        raise RuntimeError(f"{f.name} : {d}")   # faute de banc : on arrete
    tm, vm, dm = _vm(f)
    fo, sig, zeta = enveloppe(tm, vm)
    m = tm > tm[0] + 0.7 * (tm[-1] - tm[0])
    return dict(kp=kp, stable=bool(sig < 0), mort=False, s=dt, f=fo,
                sig=sig, zeta=zeta, vmoy=float(np.mean(vm[m])),
                dmin=float(dm.min()), dmax=float(dm.max()))


def dichotomie(lo=0.002, hi=0.2) -> int:
    """La limite de stabilite du P pur a 40 W, par bissection.

    Demande par le concepteur : iteration en dichotomie, un cas a la
    fois, plutot qu'un balayage parallele. Bissection GEOMETRIQUE (un
    gain se place en log), arret quand hi/lo <= 2 -- connaitre la limite
    a un facteur 2 pres suffit pour placer R4.
    """
    print("  DICHOTOMIE R2 -- limite de stabilite du P pur, 40 W CCM")
    print(f"     bornes [{lo} ; {hi}], critere : l'oscillation de la")
    print("     moyenne (resonance ~4,5 kHz excitee au demarrage)")
    print("     decroit entre le 1er et le 3e tiers de 2 ms, ou non.")
    print("     Cas acheves via lance(), fenetre 120+400 periodes.\n")
    fmt = ("     Kp {kp:8.5f}  {v:10s}  {s:4.0f} s  {reste}")

    def montre(r):
        if r["mort"]:
            v, reste = "INDETERMINE", "simulation morte : " + r["diag"][:60]
        else:
            v = "stable" if r["stable"] else "INSTABLE"
            reste = (f"{r['f']/1e3:.2f} kHz  sigma {r['sig']:+.0f} /s  "
                     f"zeta {r['zeta']:+.4f}   Vout {r['vmoy']:.2f} V   "
                     f"duty [{r['dmin']:.3f}, {r['dmax']:.3f}]")
        print(fmt.format(kp=r["kp"], v=v, s=r["s"], reste=reste))

    def morte(r):
        if r["mort"]:
            print("\n  Cas MORT : verdict INDETERMINE. Relancer ce cas avec la")
            print("  sauvegarde depuis t = 0 et lire l'enveloppe AVANT la mort.")
        return r["mort"]

    r = un_cas(lo)
    montre(r)
    if morte(r):
        return 1
    if not r["stable"]:
        print("\n  La borne BASSE est deja instable : rien a bissecter,")
        print("  le P ne tient a aucun gain du domaine demande.")
        return 1
    r = un_cas(hi)
    montre(r)
    if morte(r):
        return 1
    if r["stable"]:
        print(f"\n  La borne HAUTE {hi} est stable : la limite est")
        print("  au-dela du domaine demande.")
        return 0
    while hi / lo > 2.0:
        k = float(np.sqrt(lo * hi))
        r = un_cas(k)
        montre(r)
        if morte(r):
            return 1
        if r["stable"]:
            lo = k
        else:
            hi = k
    print(f"\n  LIMITE DE STABILITE : entre Kp = {lo:.5f} (stable) et "
          f"{hi:.5f} (instable)")
    print(f"  soit Kp.G(DC) entre {lo*321:.2f} et {hi*321:.2f} avec le "
          f"gain 321 de R1.")
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "temoin":
        return temoin(float(sys.argv[2]) if len(sys.argv) > 2 else 0.002)
    return dichotomie()


if __name__ == "__main__":
    raise SystemExit(main())
