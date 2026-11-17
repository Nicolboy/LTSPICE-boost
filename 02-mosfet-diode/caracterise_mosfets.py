"""Extraction de Coss(V), Qoss(V) et Eoss(V) depuis les modeles LTspice
constructeur (Infineon OptiMOS 150 V), par injection de courant constant.

Methode
-------
Grille court-circuitee a la source, un courant constant IINJ injecte dans
le drain. La tension de drain monte alors en chargeant la seule capacite
de sortie, et tout se lit en integrales temporelles :

    Qoss(v) = integrale de i dt           (integrateur Bq/Cq dans le circuit)
    Eoss(v) = integrale de v*i dt         (integrateur Be/Ce dans le circuit)
    Coss(v) = dQoss/dv

Le courant est rampe sur TRAMP au lieu d'etre applique en echelon : un
echelon sur un noeud purement capacitif, sans chemin continu vers la
masse, fait echouer le point de fonctionnement (« Time step too small,
trouble with node x1:x1:e_eds7#branch »). Les deux integrateurs sont dans
le circuit plutot que calcules en Qoss = i*t, ce qui rend la mesure
indifferente a la forme du courant pendant la rampe.

On derive t par rapport a v, et non v par rapport a t : la rampe est
naturellement lente la ou C est grand, donc t(v) est bien conditionne sur
toute la plage alors que dv/dt varie de trois decades.

Au-dela de la tenue en tension le modele part en avalanche et ecrete : les
points au-dessus ne valent rien, mais ceux d'en dessous ne sont pas
affectes, donc on laisse courir sans chercher a arreter la simulation.

Controle de validite
--------------------
L'IPD200N15N3 est la seule piece du lot dont on ait le datasheet, qui
tabule Coss=214 pF et Qoss=60 nC a 75 V. C'est le point de controle : si
l'extraction ne le retrouve pas, le reste du tableau ne vaut rien.
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent.parent
LIBS = RACINE / "lib_spice_commun" / "Infineon"
TRAVAIL = ICI / "results" / "coss"
LTSPICE = Path(r"C:/Program Files/ADI/LTspice/LTspice.exe")

IINJ = 1e-3       # A -- 4 decades au-dessus de l'Idss, donc pas de fuite
TRAMP = 500e-9    # s -- etablissement doux du courant
TSTOP = 150e-6    # s -- couvre la plus grosse puce jusqu'a VSTOP
TMAX = 10e-9      # s -- 0,125 V par pas au plus rapide (80 pF a 1 mA)
RFUITE = 1e9      # Ohm -- chemin continu vers la masse, 0,012 % a 120 V
# Laisse libre, la rampe va jusqu'a l'avalanche du modele (176 V) ou le
# solveur echoue. On coupe donc le courant bien avant, en douceur : une
# coupure franche relancerait le probleme de convergence qu'on vient de
# regler. 105 V laisse 25 V de marge au-dessus du V_inter de 80 V.
VSTOP = 105.0     # V

# Pieces retenues : la bande 28-36 mOhm max encadre l'optimum thermique
# calcule (22-31 mOhm typ), plus les deux extremes comme bornes.
PIECES = [
    # (modele,            lib,         generation, act,  Rmax_mOhm)
    ("IPD200N15N3",       "OptiMOS3",  "OptiMOS 3", 9.06, 20.0),
    ("IQE220N15NM5",      "OptiMOS5",  "OptiMOS 5", 4.63, 22.0),
    ("BSB280N15NZ3",      "OptiMOS3",  "OptiMOS 3", 5.80, 28.0),
    ("BSZ300N15NS5",      "OptiMOS5",  "OptiMOS 5", 3.21, 30.0),
    ("IPC331N15NM5R",     "OptiMOS5",  "OptiMOS 5", None, 33.1),
    ("BSC360N15NS3",      "OptiMOS3",  "OptiMOS 3", 4.45, 36.0),
    ("IPD530N15N3",       "OptiMOS3",  "OptiMOS 3", 3.32, 53.0),
]

LIBFILE = {
    "OptiMOS3": "OptiMOS3_150V_LTSpice.lib",
    "OptiMOS5": "OptiMOS5_150V_LTSpice.lib",
    "OptiMOS6": "OptiMOS6_150V_LTSpice.lib",
}

# Datasheet IPD200N15N3 rev 2.07 p.2-3. Les modeles Infineon decrivent le
# composant TYPIQUE : on compare donc aux colonnes typ, pas aux max.
CONTROLE = {"piece": "IPD200N15N3", "v": 75.0, "coss_pf": 214.0, "qoss_nc": 60.0,
            "rds_mohm": 16.0, "rds_id": 50.0, "rds_vgs": 10.0}

# Point dimensionnant archi 2 : Vin 19 V, 50 W, Vinter 80 V, 400 kHz,
# L 104,8 uH -> D 0,763, IL 2,63 A, Irms 2,30 A.
IRMS = 2.30       # A
FSW = 400e3       # Hz
VINTER = 80.0     # V
TJ_CHAUD = 125.0  # degC

# Charge partielle : Vin 15 V, 15 W -> D 0,813, IL 1,00 A, Irms 0,90 A.
# La conduction y chute en I^2 alors que la commutation ne bouge pas, ce
# qui deplace l'optimum vers les petites puces. Le convertisseur passant
# 5 a 50 W, le point plein seul ne suffit pas a trancher.
IRMS_PARTIEL = 0.90   # A


def netlist(piece, lib):
    """Banc d'extraction. Le modele de base est a 5 bornes
    (drain gate source Tj Tcase) : Tcase est pilotee en volts = degC,
    Tj est calculee par le reseau de Cauer interne."""
    return f"""* Extraction Coss/Qoss/Eoss -- {piece}
* genere par extrait_coss.py -- ne pas editer a la main
.include {LIBS / LIBFILE[lib]}

X1 nd 0 0 ntj ntc {piece}
Vtc ntc 0 25
.param IINJ={IINJ}
.param TRAMP={TRAMP}
.param VSTOP={VSTOP}
.func inj() {{IINJ*min(1,time/TRAMP)/(1+exp(min(40,(V(nd)-VSTOP)/0.5)))}}

Bi 0 nd I=inj()
Rfuite nd 0 {RFUITE:g}

* integrateurs : V(nq) vaut la charge en coulombs, V(ne) l'energie en joules
Bq 0 nq I=inj()
Cq nq 0 1
Rfq nq 0 1G
Be 0 ne I=V(nd)*inj()
Ce ne 0 1
Rfe ne 0 1G

.ic V(nd)=0 V(nq)=0 V(ne)=0
.tran 0 {TSTOP} 0 {TMAX}
.options plotwinsize=0
.save V(nd) V(nq) V(ne)
.end
"""


def netlist_rdson(piece, lib, idtest):
    """R_ds(on) en fonction de la temperature de JONCTION, a Vgs=10 V.

    On pilote Tj directement, et non Tcase : en .dc l'auto-echauffement
    s'etablit completement, et au courant de test du datasheet (50 A) il
    atteint 48 W, soit +31 K sur les 0,64 K/W du reseau de Cauer. Piloter
    Tcase donnerait donc un Rds lu 20 % trop haut, alors que le datasheet
    mesure en impulsion a jonction froide. Tcase suit Tj par Etc, pour
    rester isotherme et ne pas laisser la borne flotter."""
    return f"""* R_ds(on) en temperature de jonction -- {piece} a Id={idtest} A
* genere par caracterise_mosfets.py -- ne pas editer a la main
.include {LIBS / LIBFILE[lib]}

X1 nd ng 0 ntj ntc {piece}
Vg ng 0 10
Ids 0 nd {idtest}
Vtj ntj 0 25
Etc ntc 0 ntj 0 1

.dc Vtj 25 150 5
.save V(nd)
.options plotwinsize=0
.end
"""


def rdson(piece, lib, idtest):
    """Renvoie (temperatures[degC], Rds[Ohm])."""
    from spicelib.raw.raw_read import RawRead
    raw = lance(f"rds_{piece}", netlist_rdson(piece, lib, idtest), piece)
    r = RawRead(str(raw))
    nom_x = r.get_trace_names()[0]
    tc = np.asarray(r.get_trace(nom_x).get_wave(), dtype=float).real
    v = np.asarray(r.get_trace("V(nd)").get_wave(), dtype=float).real
    return tc, v / idtest


def lance(base, texte, piece):
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    cir = TRAVAIL / f"{base}.cir"
    cir.write_text(texte, encoding="ascii")
    raw = cir.with_suffix(".raw")
    if raw.exists():
        raw.unlink()
    subprocess.run([str(LTSPICE), "-b", str(cir)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   check=False)
    log = cir.with_suffix(".log")
    txt = log.read_text(errors="replace") if log.exists() else ""
    if not raw.exists():
        raise RuntimeError(f"{piece} : pas de .raw\n{txt[-800:] or '(pas de log)'}")
    # LTspice ecrit un .raw TRONQUE meme quand la simulation echoue : sans
    # ce controle on depouille des donnees partielles sans s'en apercevoir.
    for marqueur in ("Simulation Failed", "Iteration limit reached",
                     "Time step too small", "Fatal Error"):
        if marqueur in txt:
            ligne = next(l.strip() for l in txt.splitlines() if marqueur in l)
            raise RuntimeError(f"{piece} : simulation echouee -- {ligne}")
    return raw


def simule(piece, lib):
    return lance(f"coss_{piece}", netlist(piece, lib), piece)


def depouille(raw, vmax_grille=100.0):
    """Renvoie (vgrid, Coss[F], Qoss[C], Eoss[J]) sur la portion montante."""
    from spicelib.raw.raw_read import RawRead
    r = RawRead(str(raw))
    v = np.asarray(r.get_trace("V(nd)").get_wave(), dtype=float).real
    q = np.asarray(r.get_trace("V(nq)").get_wave(), dtype=float).real
    e = np.asarray(r.get_trace("V(ne)").get_wave(), dtype=float).real

    # on ne garde que la montee strictement croissante : au-dela, le modele
    # est en avalanche et q(v) n'est plus une fonction
    croissant = np.concatenate(([True], np.diff(v) > 0))
    v, q, e = v[croissant], q[croissant], e[croissant]

    haut = min(vmax_grille, float(v[-1]) * 0.995)
    vg = np.linspace(0.5, haut, 1500)
    qv = np.interp(vg, v, q)
    ev = np.interp(vg, v, e)
    return vg, np.gradient(qv, vg), qv, ev


def a(vg, y, v):
    return float(np.interp(v, vg, y))


def main():
    res = {}
    for piece, lib, gen, act, rmax in PIECES:
        try:
            vg, coss, qoss, eoss = depouille(simule(piece, lib))
            tc, rds = rdson(piece, lib, IRMS)
        except Exception as exc:                      # noqa: BLE001
            print(f"  !! {piece} : {exc}", file=sys.stderr)
            continue
        res[piece] = dict(vg=vg, coss=coss, qoss=qoss, eoss=eoss,
                          tc=tc, rds=rds, gen=gen, act=act, rmax=rmax,
                          vhaut=float(vg[-1]))

    # --- controles de validite, avant toute exploitation ---
    c = CONTROLE
    print(f"CONTROLE -- {c['piece']} contre datasheet rev 2.07 (valeurs typ)")
    if c["piece"] not in res:
        print("  ECHEC : piece de controle non simulee."); return 1
    d = res[c["piece"]]
    _, rds_ds = rdson(c["piece"], "OptiMOS3", c["rds_id"])
    mesures = [
        ("Coss(75 V)", a(d["vg"], d["coss"], c["v"]) * 1e12, c["coss_pf"], "pF"),
        ("Qoss(75 V)", a(d["vg"], d["qoss"], c["v"]) * 1e9, c["qoss_nc"], "nC"),
        (f"Rds(25 C,{c['rds_id']:.0f} A)", float(rds_ds[0]) * 1e3,
         c["rds_mohm"], "mOhm"),
    ]
    ok = True
    for nom, mes, ref, unite in mesures:
        ecart = 100.0 * (mes - ref) / ref
        bon = abs(ecart) <= 15.0
        ok &= bon
        print(f"  {nom:<16} modele {mes:7.1f} {unite:<5}"
              f" / datasheet {ref:6.1f} {unite:<5}"
              f" ecart {ecart:+6.1f} %  {'ok' if bon else 'HORS TOLERANCE'}")
    if not ok:
        print("\n  Le tableau qui suit n'est pas exploitable en l'etat.")
        return 1

    # --- tableau de pre-selection ---
    print(f"\nPoint : Vin 19 V, 50 W, Vinter {VINTER:.0f} V, {FSW/1e3:.0f} kHz,"
          f" Irms {IRMS:.2f} A")
    print(f"\n{'piece':<16}{'gen':<11}{'act':>6}"
          f"{'Rds25':>7}{'Rds125':>7}{'k_T':>6}"
          f"{'Coss75':>8}{'Eoss80':>8}{'Pcond':>7}{'Pcom':>7}{'50 W':>8}"
          f"{'15 W':>7}")
    print(f"{'':<16}{'':<11}{'':>6}{'mOhm':>7}{'mOhm':>7}{'':>6}"
          f"{'pF':>8}{'nJ':>8}{'mW':>7}{'mW':>7}{'mW':>8}{'mW':>7}")
    table = []
    for piece, d in res.items():
        if d["vhaut"] < VINTER:
            print(f"{piece:<16}{d['gen']:<11}  n'atteint que {d['vhaut']:.0f} V")
            continue
        r25 = float(np.interp(25.0, d["tc"], d["rds"]))
        r125 = float(np.interp(TJ_CHAUD, d["tc"], d["rds"]))
        e80 = a(d["vg"], d["eoss"], VINTER)
        pcond = r125 * IRMS ** 2
        pcom = e80 * FSW
        partiel = r125 * IRMS_PARTIEL ** 2 + pcom
        table.append((pcond + pcom, piece, d, r25, r125, e80, pcond, pcom,
                      partiel))
    for tot, piece, d, r25, r125, e80, pcond, pcom, partiel in sorted(table):
        print(f"{piece:<16}{d['gen']:<11}{(d['act'] or float('nan')):>6.2f}"
              f"{r25*1e3:>7.1f}{r125*1e3:>7.1f}{r125/r25:>6.2f}"
              f"{a(d['vg'], d['coss'], 75.0)*1e12:>8.1f}{e80*1e9:>8.0f}"
              f"{pcond*1e3:>7.0f}{pcom*1e3:>7.0f}{tot*1e3:>8.0f}"
              f"{partiel*1e3:>7.0f}")

    fom = sorted((a(d['vg'], d['eoss'], VINTER)
                  * float(np.interp(25.0, d['tc'], d['rds'])) * 1e9, p)
                 for p, d in res.items() if d['vhaut'] >= VINTER)
    print("\nFOM = Eoss(80 V) x Rds(25 C), independant de la surface de puce :")
    print("  " + "  ".join(f"{p} {v:.1f}" for v, p in fom) + "   nJ.Ohm")

    print("\nPcom = Eoss x fsw : c'est un PLANCHER de perte de commutation,")
    print("pas la perte reelle. Le recouvrement et la capacite de la diode")
    print("s'y ajoutent -- seul le double-pulse les chiffre.")

    np.savez(TRAVAIL / "caracterisation.npz",
             **{f"{p}_{k}": d[k] for p, d in res.items()
                for k in ("vg", "coss", "qoss", "eoss", "tc", "rds")})
    print(f"\ncourbes -> {TRAVAIL / 'caracterisation.npz'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
