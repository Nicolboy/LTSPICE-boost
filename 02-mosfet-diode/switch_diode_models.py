"""Chapitre 2 (switch/diode) -- parametres SPICE simples, un par
technologie reelle, derives des fiches techniques constructeur (pas de
modele vendeur complet -- une seule resistance/capacite/temps de
commutation par piece, calibres sur les valeurs datasheet publiees ;
fiches elles-memes non incluses dans ce depot, voir README du chapitre
pour les references).

Comparaison retenue -- PAS de SiC ici (aucun MOSFET SiC commercial
realiste en classe 100V, le SiC cible 650V+ par nature -- reserve a une
etude a plus haute tension) :
  - switch  : Si (RD3P04BBKHRB, incumbent) vs GaN (EPC2007, candidat)
  - diode   : Schottky Si (NTSV20U100CT) vs ultrafast PN Si (STTH2002)
"""
import math

VT = 0.02585  # V, tension thermique ~300K -- calibration Vf de premier ordre


def solve_is(vf_target, i_test, n=1.0, rs_ohm=0.010):
    """IS tel que N*VT*ln(I/IS) + I*RS = Vf_target a I=i_test (modele
    diode simple, N*VT*ln + chute RS serie) -- method: computed, pas une
    valeur datasheet directe (IS n'est jamais publie par les fabricants
    pour ces pieces)."""
    return i_test / math.exp((vf_target - i_test * rs_ohm) / (n * VT))


# --- Switches : RD domine la resistance a l'etat passant (meme esprit
# que MIDEAL_SW du chapitre 1), mais RD/Coss/temps de commutation/tension
# de grille sont maintenant REELS, par technologie. ---

SWITCHES = {
    "Si": dict(
        part="RD3P04BBKHRB",
        rd_ohm=0.030,     # rds_on, basis=max, VGS=10V/ID=10A/Tj=25degC
        coss_f=115e-12,   # basis=typ, VDS=50V/VGS=0V/f=1MHz
        vgs_drive=10.0,   # V -- condition de mesure tr/tf/Qg du datasheet
        tr_ns=14.0,       # publie directement : RG=1 Ohm, VDD~50V, ID=10A
        tf_ns=8.7,        # idem
        src="fiche technique RD3P04BBKHRB (ROHM)",
    ),
    "GaN": dict(
        part="EPC2007",
        rd_ohm=0.030,     # rds_on, basis=max, VGS=5V/ID=6A/Tj=25degC
        coss_f=118e-12,   # basis=typ, VDS=50V/VGS=0V
        vgs_drive=5.0,    # V -- VGS abs max = 6V (datasheet p.1) : PAS 10V,
                           # contrairement au Si, ca detruirait le composant
        tr_ns=None,       # non publie par EPC -- estime ci-dessous
        tf_ns=None,
        src="fiche technique EPC2007 (EPC)",
    ),
}

# Temps de commutation GaN ESTIME (pas publie), PAS une donnee datasheet :
# le palier Miller (QGD) domine la duree de la transition en tension a
# courant de grille ~constant -- on transpose le ratio QGD(GaN)/QGD(Si) sur
# les tr/tf REELS et publies du Si, mesures au meme esprit (RG faible,
# meme ordre de VDS/ID). Hypothese de modelisation documentee ici, a
# reprendre si une passe de raffinement vendeur devient necessaire.
_QGD_SI_NC = 2.4    # fiche RD3P04BBKHRB, VGS=10V, ID=10A
_QGD_GAN_NC = 0.61  # fiche EPC2007, typ, VGS=5V, ID=6A
_qgd_ratio = _QGD_GAN_NC / _QGD_SI_NC
SWITCHES["GaN"]["tr_ns"] = SWITCHES["Si"]["tr_ns"] * _qgd_ratio
SWITCHES["GaN"]["tf_ns"] = SWITCHES["Si"]["tf_ns"] * _qgd_ratio


def switch_spice_model(tech, model_name):
    s = SWITCHES[tech]
    return (f".model {model_name} NMOS(VTO=2 KP=200 RD={s['rd_ohm']:.4f} "
            f"RS=0 IS=1e-12)")


# --- Diodes : Vf calibre sur le point datasheet reel (IS resolu, pas
# devine), TT calibre sur le trr datasheet pour l'ultrafast, TT=0 pour la
# Schottky (porteurs majoritaires, pas de recouvrement par nature). ---

DIODES = {
    "Schottky": dict(
        part="NTSV20U100CT",
        vf_target=0.658, i_test=10.0,  # typ, IF=10A (par jambe), Tj=25degC
        tt_s=0.0,
        src="fiche technique NTSV20U100CT (onsemi)",
    ),
    "Ultrafast": dict(
        part="STTH2002",
        vf_target=1.1, i_test=20.0,    # max, IF=20A, Tj=25degC (pas de typ a ce point)
        # trr typ datasheet (p.3 tbl.4, IF=1A/dIF/dt=-200A/us/VR=30V/Tj=25degC)
        # -- POINT DE DEPART pour TT, a confirmer/ajuster au test fumee
        # (le recouvrement simule depend aussi du di/dt reel au point de
        # fonctionnement, pas juste de TT seul) -- a confirmer/ajuster au
        # test fumee avant un balayage complet.
        tt_s=16e-9,
        src="fiche technique STTH2002 (ST)",
    ),
}
for _d in DIODES.values():
    _d["is_a"] = solve_is(_d["vf_target"], _d["i_test"])
    _d["n"] = 1.0
    _d["rs_ohm"] = 0.010


def diode_spice_model(tech, model_name):
    d = DIODES[tech]
    return (f".model {model_name} D(IS={d['is_a']:.4e} N={d['n']:.1f} "
            f"RS={d['rs_ohm']:.4f} TT={d['tt_s']:.4e})")


def diode_vf_at(tech, i_a):
    """Vf statique (N*VT*ln(I/IS) + I*RS) du MEME modele que celui
    injecte en SPICE, a un courant i_a quelconque -- utilise en
    post-traitement pour estimer la perte de CONDUCTION seule (donc, par
    difference avec Ploss_diode_total mesure en SPICE, isoler la perte de
    recouvrement) de facon coherente avec le modele reellement simule,
    plutot qu'avec le point de calibration datasheet (qui est a un
    courant different du point de fonctionnement reel)."""
    d = DIODES[tech]
    if i_a <= 0:
        return 0.0
    return d["n"] * VT * math.log(i_a / d["is_a"]) + i_a * d["rs_ohm"]


# --- Self parasite au noeud de commutation : ESTIMATION monotone selon
# L/nombre de spires -- toutes les 3 valeurs (ch.2) restent dans le MEME
# boitier SER2211 (11,5x11mm), donc variation modeste attendue, pas un
# saut d'ordre de grandeur. PAS mesuree -- documentee comme hypothese.
# Sans elle, le recouvrement inverse de la diode ultrafast ne produit
# aucun depassement de tension observable. ---
LSTRAY_BY_L_H = {
    12e-6: 20e-9,
    27e-6: 30e-9,
    47e-6: 40e-9,
}


if __name__ == "__main__":
    for tech, s in SWITCHES.items():
        print(f"SWITCH {tech:9s} ({s['part']}): RD={s['rd_ohm']*1e3:.1f}mOhm "
              f"Coss={s['coss_f']*1e12:.0f}pF VGSdrive={s['vgs_drive']}V "
              f"tr={s['tr_ns']:.2f}ns tf={s['tf_ns']:.2f}ns")
        print(f"  -> {switch_spice_model(tech, 'MTEST')}")
    for tech, d in DIODES.items():
        print(f"DIODE  {tech:9s} ({d['part']}): IS={d['is_a']:.3e}A "
              f"(Vf={d['vf_target']}V @ {d['i_test']}A) TT={d['tt_s']*1e9:.1f}ns")
        print(f"  -> {diode_spice_model(tech, 'DTEST')}")
    print("\nSelf parasite par L :", {f"{l*1e6:.0f}uH": f"{v*1e9:.0f}nH"
                                       for l, v in LSTRAY_BY_L_H.items()})
