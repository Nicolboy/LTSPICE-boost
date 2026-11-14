"""Chapitre 2 (switch/diode) -- parametres SPICE simples, un par
technologie reelle, derives de fiches techniques constructeur sourcees
(pas de modele vendeur complet -- une seule resistance/capacite/temps de
commutation par piece, calibres sur les valeurs datasheet publiees).

Comparaison retenue (PAS de SiC ici -- pas d'offre MOSFET SiC commerciale
realiste a cette classe de tension, 100V ; reserve a une etude a plus
haute tension) :
  - switch  : Si (RD3P04BBKHRB, incumbent) vs GaN (EPC2007, candidat)
  - diode   : Schottky Si (NTSV20U100CT) vs ultrafast PN Si (STTH2002)

Sources : fiches techniques constructeur de chaque piece (ROHM
RD3P04BBKHRB, EPC EPC2007, onsemi NTSV20U100CT, ST STTH2002) -- valeurs
reprises en commentaire a chaque parametre ci-dessous (page/tableau,
condition de mesure), pas de fichier de caracterisation fourni dans ce
depot (licences respectives des fabricants).
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
        src="datasheet ROHM RD3P04BBKHRB",
    ),
    "GaN": dict(
        part="EPC2007",
        rd_ohm=0.030,     # rds_on, basis=max, VGS=5V/ID=6A/Tj=25degC
        coss_f=118e-12,   # basis=typ, VDS=50V/VGS=0V
        vgs_drive=5.0,    # V -- VGS abs max = 6V (datasheet p.1) : PAS 10V,
                           # contrairement au Si, ca detruirait le composant
        tr_ns=None,       # non publie par EPC -- estime ci-dessous
        tf_ns=None,
        src="datasheet EPC EPC2007",
    ),
}

# Temps de commutation GaN ESTIME (pas publie), PAS une donnee datasheet :
# le palier Miller (QGD) domine la duree de la transition en tension a
# courant de grille ~constant -- on transpose le ratio QGD(GaN)/QGD(Si) sur
# les tr/tf REELS et publies du Si, mesures au meme esprit (RG faible,
# meme ordre de VDS/ID). Hypothese de modelisation documentee ici, a
# reprendre si une passe de raffinement vendeur devient necessaire.
_QGD_SI_NC = 2.4    # RD3P04BBKHRB, VGS=10V, ID=10A
_QGD_GAN_NC = 0.61  # EPC2007, typ, VGS=5V, ID=6A
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
        src="datasheet onsemi NTSV20U100CT/D",
    ),
    "Ultrafast": dict(
        part="STTH2002",
        vf_target=1.1, i_test=20.0,    # max, IF=20A, Tj=25degC (pas de typ a ce point)
        # trr typ datasheet (p.3 tbl.4, IF=1A/dIF/dt=-200A/us/VR=30V/Tj=25degC)
        # -- POINT DE DEPART pour TT, confirme a l'essai a blanc (voir README
        # ch.2 Sec4/5 : le recouvrement simule depend aussi du di/dt reel
        # au point de fonctionnement, pas juste de TT seul).
        tt_s=16e-9,
        src="datasheet ST STTH2002",
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
# aucun depassement de tension observable (voir README ch.2 Sec3). ---
LSTRAY_BY_L_H = {
    12e-6: 20e-9,
    27e-6: 30e-9,
    47e-6: 40e-9,
}


# --- Candidats REELS (TO-252), identifies au chapitre 2 S8 (voir README)
# pour remplacer les pieces generiques ci-dessus. Utilises UNIQUEMENT par
# estimate_switch_losses.py / run_resonance_check.py (volet EMI/resonance,
# S9 du README) -- PAS par gen_boost2_tech.py/SWITCHES/DIODES pour la
# comparaison generique Si/GaN/Schottky/ultrafast du balayage principal,
# gardee intacte et tracable separement.
#
# Qgd/Coss lus directement sur chaque fiche officielle (pas un resume de
# recherche) -- sources et conditions de test citees par candidat.
REAL_SWITCHES = {
    "IPD050N10N5": dict(
        manufacturer="Infineon",
        rds_on_ohm=0.0043, rds_on_basis="typ",  # VGS=10V, ID=40A
        qgd_nc=10.0, qgd_basis="typ",            # VDD=50V, ID=40A, VGS=0-10V
        qgd_nc_max=16.0,
        coss_f=560e-12, coss_basis="typ",        # VGS=0V, VDS=50V, f=1MHz
        vgs_drive=10.0,
        src="datasheet Infineon IPD050N10N5, p.4 Table 5/6 (lu directement)",
    ),
    "SUD70090E": dict(
        manufacturer="Vishay",
        rds_on_ohm=0.0074, rds_on_basis="typ",   # VGS=10V, ID=20A
        qgd_nc=7.5, qgd_basis="typ",             # VDS=50V, VGS=10V, ID=20A
        qgd_nc_max=None,
        coss_f=845e-12, coss_basis="typ",        # VGS=0V, VDS=50V, f=1MHz
        vgs_drive=10.0,
        src="datasheet Vishay SUD70090E, p.2 Dynamic table (lu directement)",
    ),
    "NVD6824NL": dict(
        manufacturer="onsemi",
        rds_on_ohm=0.0165, rds_on_basis="typ",   # VGS=10V, ID=20A
        qgd_nc=18.0, qgd_basis="typ",            # VGS=10V, VDS=80V, ID=20A
        qgd_nc_max=None,
        coss_f=187e-12, coss_basis="typ",        # VGS=0V, VDS=25V, f=1MHz --
        # ATTENTION condition VDS=25V, PAS 50V comme les 2 autres candidats :
        # Coss decroit fortement avec VDS (depletion MOS), donc CETTE valeur
        # est probablement SURESTIMEE par rapport a Coss au point reel
        # (VDS~80V) -- aucune autre valeur publiee sur la fiche a VDS plus
        # eleve, flag explicite plutot que comparaison trompeuse.
        vgs_drive=10.0,
        src="datasheet onsemi NVD6824NL, p.2 Charges/Capacitances table (lu directement)",
    ),
}

# Cj a un point proche de VR~80-100V reel (PAS le point tabule a bas VR,
# souvent le seul publie en table). Pour les 3 candidats, lu sur la courbe
# C(VR) de la fiche (method=graph_read, valeur approximative +/- tolerance
# indiquee), le trace precis au pixel n'etant pas disponible depuis une
# extraction PDF texte.
REAL_DIODES = {
    "MBRD5H100T4G": dict(
        manufacturer="onsemi",
        vf_v=0.71, vf_basis="max", vf_i_a=5.0,   # p.2 tbl, IF=5A, Tj=25degC
        cj_pf=130, cj_vr_v=90, cj_tol_pct=20,
        cj_basis="graph_read",
        cj_note="Fig.5 p.3 (C vs VR, f=1MHz, TJ=25degC) : lu visuellement au "
                "point le plus proche de VR=90V, pas le point bas-tension "
                "(la courbe n'a pas de table de valeurs a VR eleve).",
        src="datasheet onsemi MBRD5H100T4G, p.2-3 (lu directement)",
    ),
    "VS-6CWQ10FN-M3": dict(
        manufacturer="Vishay",
        vf_v=0.63, vf_basis="max", vf_i_a=3.0,   # p.2 tbl, IF=3A/jambe, Tj=125degC
        cj_pf=28, cj_vr_v=90, cj_tol_pct=25,
        cj_basis="graph_read",
        cj_note="ATTENTION : la table p.2 publie 92pF a VR=5V seulement -- "
                "valeur tabulee a bas VR, PAS reutilisable telle quelle. "
                "Fig.3 p.3 montre Cj decroitre fortement jusqu'a VR=100V ; "
                "lu visuellement au point le plus proche de VR=90V : ~28pF, "
                "soit ~3x PLUS BAS que le point tabule a 5V.",
        src="datasheet Vishay VS-6CWQ10FN-M3, p.2-3 (lu directement)",
    ),
    "SBR15U100CTL": dict(
        vf_v=0.80, vf_basis="max", vf_i_a=7.5,   # p.2 tbl, IF=7.5A/jambe, Tj=25degC
        manufacturer="Diodes Incorporated",
        cj_pf=53, cj_vr_v=90, cj_tol_pct=35,
        cj_basis="graph_read_extrapolated",
        cj_note="Fig.3 p.3 (log-log, 0,1-100V) : la courbe tracee s'arrete "
                "visuellement vers VR~45V (~75pF), PAS de donnee visible "
                "jusqu'a 100V -- extrapole en loi sqrt(V) typique Schottky/SBR "
                "(Cj ~ 1/sqrt(VR+Vbi)) : 75pF x sqrt(45/90) ~53pF. Tolerance "
                "plus large (35%) car extrapolation, pas lecture directe.",
        src="datasheet Diodes Incorporated SBR15U100CTL (DS35119 Rev.3), "
            "p.3 (lu directement)",
    ),
}


# --- Fusion des candidats REELS dans SWITCHES/DIODES (memes cles que les
# modeles generiques) pour que gen_boost2_tech.build() les utilise sans
# modification -- switch_tech="IPD050N10N5" etc. marche directement.
# tr_ns/tf_ns des candidats reels = PAS les valeurs tr/tf publiees (test
# a des RG/VDS differents d'un fabricant a l'autre, piege deja signale
# S6.2), mais le temps de commutation Qgd/driver (voir README S9 --
# MEME modele que les pertes de commutation, pour rester coherent entre
# le calcul direct et la simulation). ---
_GATE_DRIVER_ISOURCE_A = 4.0  # A, pic source -- driver de grille retenu
_GATE_DRIVER_ISINK_A = 6.0    # A, pic puits -- idem
for _name, _s in REAL_SWITCHES.items():
    SWITCHES[_name] = dict(
        part=_name,
        rd_ohm=_s["rds_on_ohm"],
        coss_f=_s["coss_f"],
        vgs_drive=_s["vgs_drive"],
        tr_ns=(_s["qgd_nc"] * 1e-9 / _GATE_DRIVER_ISOURCE_A) * 1e9,
        tf_ns=(_s["qgd_nc"] * 1e-9 / _GATE_DRIVER_ISINK_A) * 1e9,
        src=_s["src"],
    )

# Cj ajoutee en capacite EXPLICITE en parallele de la diode (meme esprit
# que Coss_TECH deja fait pour le switch) -- PAS les parametres CJO/VJ/M
# du modele diode SPICE (demanderaient plus d'un point de donnee pour
# etre ajustes correctement).
for _name, _d in REAL_DIODES.items():
    DIODES[_name] = dict(
        part=_name,
        vf_target=_d["vf_v"], i_test=_d["vf_i_a"],
        tt_s=0.0,  # Schottky/SBR, pas de recouvrement par nature (meme
                   # argument que DIODES["Schottky"] generique)
        cj_f=_d["cj_pf"] * 1e-12,
        src=_d["src"],
    )
    DIODES[_name]["is_a"] = solve_is(DIODES[_name]["vf_target"],
                                      DIODES[_name]["i_test"])
    DIODES[_name]["n"] = 1.0
    DIODES[_name]["rs_ohm"] = 0.010


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
