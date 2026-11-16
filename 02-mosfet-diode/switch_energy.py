"""Chapitre 2 (extension 200-800 kHz) -- energie de commutation du switch.

Ce module AJOUTE a switch_diode_models.py les deux mecanismes que le
modele d'origine ne capturait pas, et qui sont precisement ceux qui
separent les technologies quand la frequence monte :

  1. E_oss  -- energie stockee dans Coss a l'etat bloque, dissipee DANS LE
     SWITCH a chaque allumage en commutation dure. Proportionnelle a fsw.
  2. P_gate -- Qg x Vgs x fsw, la puissance prise au driver. Proportionnelle
     a fsw elle aussi, et c'est la que l'ecart Si/GaN est le plus net
     (9.1 nC @ 10 V contre 2.1 nC @ 5 V).

Sans ces deux termes, le balayage d'origine concluait que Si et GaN sont
« quasiment indiscernables » (README S6.2) -- constat exact pour le modele
d'alors, mais qui tenait surtout a ce que les deux pieces retenues sont
appariees sur Rds_on (30 mOhm) ET sur Coss (115 vs 118 pF), les deux seuls
parametres que ce modele voyait.

--------------------------------------------------------------------------
RELATIONS UTILISEES (et le sens dans lequel elles vont)
--------------------------------------------------------------------------
    Qoss(V) = integrale(0->V) Coss(v) dv        donc  Coss = dQoss/dV
    Eoss(V) = integrale(0->V) Coss(v) v dv  =  integrale v dQoss
    Qoss    = Qgd + Qds                     car   Coss = Cgd + Cds
    Coss_ER = 2 Eoss / V^2   (capacite equivalente EN ENERGIE)
    Coss_TR =   Qoss / V     (capacite equivalente EN TEMPS)

--------------------------------------------------------------------------
DEUX REGIMES DE SOURCE, A NE PAS CONFONDRE
--------------------------------------------------------------------------
GaN (EPC2007, EPC2052) : Coss(v) suit tres bien une loi de puissance
    Coss(v) = Coss(50) * (50/v)^gamma
avec gamma DEDUIT du couple (Coss, Qoss) tous deux publies en table :
    Qoss(50) = Coss(50)*50/(1-gamma)  =>  gamma = 1 - Coss(50)*50/Qoss(50)
Methode VALIDEE sur l'EPC2052, seul des trois a publier Coss_ER (227 pF) :
la valeur recalculee tombe a -1.8 %. C'est le controle qui autorise a
appliquer la meme methode a l'EPC2007, qui ne publie pas Coss_ER.

Si (RD3P04BBKHRB) : la loi de puissance NE S'APPLIQUE PAS. La courbe a un
plateau (~700 pF sous 1 V) puis un genou brutal entre 30 et 55 V. Donc
integration numerique d'une lecture de la Fig.17 p.9 (method=graph_read),
ancree sur les valeurs TABULEES a 50 V (Coss=115 pF, Crss=9 pF).

Consequence chiffree, et c'est un piege a signaler : le raccourci
1/2*Coss(50V)*V^2 sous-estime le Si de 23 % (368 contre 475 nJ a 80 V)
alors qu'il ne se trompe que de 1.5 a 4 % sur les deux GaN -- justement
parce que les GaN sont quasi-plats la ou le Si a son genou.
"""
from __future__ import annotations

import math

import numpy as np

# --------------------------------------------------------------------------
# Si -- lecture de la Fig.17 p.9 du datasheet ROHM RD3P04BBKHRB (rev.005).
# Conditions de la figure : Ta=25 degC, f=1 MHz, VGS=0 V -- c'est EXACTEMENT
# la condition d'etat bloque qui definit Eoss, donc la bonne source.
# method=graph_read. Page rasterisee a 400 dpi puis recadree ; la couche
# texte de ce PDF decale les colonnes (meme piege que les Coilcraft).
# --------------------------------------------------------------------------
GRAPH_TABLE = {
    # Si bien calibre pour ce convertisseur. ROHM ne publie ni Qoss ni
    # Coss_ER -> seule voie, integrer la courbe.
    "Si": dict(
        tech="Si", part="RD3P04BBKHRB", boitier="TO-252 (DPAK)",
        rds_ohm=0.030, rds_hot_ohm=0.056, qg_c=9.1e-9, vgs=10.0, qgd_c=2.4e-9,
        # Courbe RELUE par la seconde passe, calibree au pixel a 900 dpi
        # (residu <= 0.16 % sur les decades des deux axes). La premiere
        # lecture, a l'oeil, s'en ecartait de -8 a +10 % selon le point,
        # SANS biais systematique -- d'ou un effet de seulement +2.4 % sur
        # Eoss, dans la tolerance annoncee. Contrairement au FDT86113LZ,
        # l'axe Y de cette figure est correctement etiquete (1/10/100/1000),
        # ce qui explique que l'erreur y soit restee faible.
        # Recoupement courbe/tableau a 50 V : +0.2 / +1.3 / +0.9 % sur
        # Ciss / Coss / Crss, dispersés et non d'un facteur commun.
        v=np.array([0.01, 0.1, 1, 2, 5, 10, 20, 30, 40, 50, 60, 80, 100], float),
        coss=np.array([693, 674, 592, 552, 486, 428, 349, 281, 185, 117, 99.2, 83.2, 73.7]) * 1e-12,
        crss=np.array([145, 140, 119, 107, 86.9, 67.1, 42.3, 25.8, 12.8, 9.08, 8.38, 7.60, 7.06]) * 1e-12,
        #                                                   ^^^^ table p.3 : 9 pF
        eoss_tol=0.05,   # seconde passe : +/-1.3 % zones plates, +/-5 % dans le coude
        src="datasheet ROHM RD3P04BBKHRB rev.005 p.3 (tbl) / p.9 Fig.17 (courbe)",
    ),
    # Si en PETIT boitier : meme classe de tension, puce ~3x plus petite.
    # C'est la piece qui porte la demonstration du calibre (README S7).
    # onsemi ne publie ni Qoss ni Coss_ER non plus.
    # COURBE CORRIGEE PAR LA SECONDE PASSE D'EXTRACTION.
    #
    # La premiere lecture, faite a l'oeil sur un rendu a 400 dpi, concordait
    # aux extremites (220 pF a 0.1 V, 46 a 50 V, 33 a 100 V) mais
    # sous-estimait le milieu de 30 a 44 % : 105 au lieu de 137 pF a 10 V,
    # 75 au lieu de 108 a 20 V, 60 au lieu de 83 a 30 V. Signature d'une
    # erreur de calibration de l'echelle logarithmique.
    #
    # Cette figure y expose particulierement : son axe Y porte un « 0 » en
    # bas, ce qui est IMPOSSIBLE sur une echelle log. La seconde passe a
    # etabli geometriquement que le bas vaut 1 pF (decade = 663.9 px,
    # reperes 10/100/200/300/400 a +/-1 px de la position predite), puis a
    # valide cette calibration en recoupant les TROIS courbes au tableau a
    # 50 V : -0.9 %, +1.1 %, +1.6 %. Une calibration fausse aurait decale
    # les trois d'un facteur commun et l'accord n'aurait pas tenu.
    #
    # Effet sur Eoss(80 V) : 153.5 -> 175.6 nJ, soit +14.4 % -- donc HORS
    # de la tolerance de +/-10 % que la premiere passe annoncait.
    "FDT86113LZ": dict(
        tech="Si", part="FDT86113LZ", boitier="SOT-223 (TO-223)",
        rds_ohm=0.075, rds_hot_ohm=0.140, qg_c=4.1e-9, vgs=10.0, qgd_c=0.85e-9,
        v=np.array([0.1, 1, 3, 10, 20, 30, 50, 100], float),
        coss=np.array([220, 194, 172, 137, 108, 83, 46.5, 33]) * 1e-12,
        crss=np.array([35.7, 29.0, 23.6, 16.0, 10.4, 6.3, 3.15, 2.45]) * 1e-12,
        #                                            ^^^^ ancre TABLE p.2 (3.1)
        eoss_tol=0.08,   # seconde passe : +/-3 % zones plates, +/-8 % dans le coude
        src="datasheet onsemi FDT86113LZ Rev.3 (mars 2025) p.2 (tbl) / p.5 Fig.8 "
            "(courbe, lue au pixel a 900 dpi lors de la seconde passe)",
    ),
}

# Retro-compatibilite : plusieurs scripts du chapitre referencent encore
# ces noms pour la piece ROHM.
SI_V_V = GRAPH_TABLE["Si"]["v"]
SI_COSS_F = GRAPH_TABLE["Si"]["coss"]
SI_CRSS_F = GRAPH_TABLE["Si"]["crss"]

# Incertitude retenue sur Eoss du ROHM RD3P04BBKHRB (pas du FDT, qui a la
# sienne dans GRAPH_TABLE). Obtenue par variation du point le plus fragile
# (Coss a 40 V, en plein genou) de 150 a 260 pF : Eoss bouge de -4.2 % a
# +5.0 %. On retient +/-10 % pour couvrir aussi l'incertitude sur la
# POSITION du genou, non testee par cette variation-la.
#
# RESERVE OUVERTE PAR LA SECONDE PASSE. La courbe du FDT86113LZ, lue de la
# MEME facon (a l'oeil, rendu 400 dpi), s'est revelee fausse de +14.4 %
# apres relecture calibree au pixel. La courbe ROHM ci-dessus n'a PAS ete
# soumise a cette seconde passe : elle porte donc le meme risque, non
# quantifie. Son axe Y est correctement etiquete (1 / 10 / 100 / 1000),
# contrairement a celui du FDT dont le bas porte un « 0 » impossible --
# ce qui rend l'erreur moins probable, mais ne l'exclut pas. A verifier
# avant de s'appuyer sur la FOM du ROHM pour une decision de conception.
SI_EOSS_TOL = 0.10

# --------------------------------------------------------------------------
# Controle de la lecture graphique, mene puis INTERPRETE (voir README S5bis)
# --------------------------------------------------------------------------
# Crss EST Cgd. Son integrale de 0 a 50 V devrait redonner le Qgd publie
# (2.4 nC, p.3). Resultat : 1.82 nC, soit -24 %.
#
# Ce n'est PAS une erreur de lecture : les deux grandeurs ne sont pas
# mesurees dans la meme condition. La Fig.17 donne Crss a VGS=0 V, canal
# bloque, en petit signal ; le Qgd de table est releve PENDANT le palier
# Miller, canal conducteur a ID=10 A, ou la capacite grille-drain est
# nettement plus elevee (charge d'inversion sous le recouvrement de grille).
# L'ecart va donc dans le sens attendu, et son ordre de grandeur est
# plausible.
#
# Portee : ce controle vaut comme validation d'ORDRE DE GRANDEUR, pas comme
# validation serree. Il ne remet pas en cause Eoss, qui est une grandeur
# d'etat BLOQUE -- donc lue dans la bonne condition. La garantie sur Eoss
# vient du test de sensibilite, pas de ce controle.
SI_QGD_INTEGRE_NC = 1.82
SI_QGD_TABLE_NC = 2.40


def _integ(v: np.ndarray, c: np.ndarray, vmax: float, poids: int) -> float:
    """Integrale de c(v)*v^poids de 0 a vmax, trapezes sur la grille lue.

    La grille lue demarre au premier point de l'axe du graphe (0.01 V pour
    la Fig.17 ROHM, 0.1 V pour la Fig.8 onsemi), pas a zero : la tranche
    manquante est ajoutee a capacite constante. Negligeable dans les deux
    cas (1e-15 J sur Eoss, 22 pC sur Qoss du FDT) mais explicite.
    """
    if vmax > v[-1]:
        raise ValueError(f"vmax={vmax} hors de la plage lue (max {v[-1]} V)")
    m = v <= vmax
    vv, cc = v[m], c[m]
    if vv[-1] < vmax:  # interpolation log-log jusqu'a vmax
        c_fin = np.exp(np.interp(np.log(vmax), np.log(v), np.log(c)))
        vv, cc = np.append(vv, vmax), np.append(cc, c_fin)
    base = c[0] * v[0] ** (poids + 1) / (poids + 1)
    return float(np.trapezoid(cc * vv**poids, vv)) + base


# --------------------------------------------------------------------------
# Pieces dont le couple (Coss, Qoss) est TABULE -> loi de puissance.
# Vaut pour les GaN comme pour le Si OptiMOS : ce n'est pas la technologie
# qui decide de la methode, c'est ce que le fabricant publie.
# --------------------------------------------------------------------------
POWERLAW_TABLE = {
    "EPC2007": dict(
        tech="GaN", rds_ohm=0.030,
        coss50_f=118e-12, qoss50_c=10.2e-9, qg_c=2.1e-9, vgs=5.0, qgd_c=0.61e-9,
        coss_er_f=None,  # non publie sur ce datasheet (2013)
        src="datasheet EPC EPC2007 p.2 Dynamic Characteristics (typ)",
    ),
    "EPC2007C": dict(
        tech="GaN", rds_ohm=0.030,
        coss50_f=110e-12, qoss50_c=8.3e-9, qg_c=1.6e-9, vgs=5.0, qgd_c=0.30e-9,
        coss_er_f=None,  # notes 2/3 la DEFINISSENT mais la ligne est absente
                         # du tableau -- verifie sur la page rasterisee p.2
        src="datasheet EPC EPC2007C rev. avril 2021 p.2 Dynamic Characteristics (typ)",
    ),
    "EPC2052": dict(
        tech="GaN", rds_ohm=0.0135,
        coss50_f=195e-12, qoss50_c=13.0e-9, qg_c=3.5e-9, vgs=5.0, qgd_c=0.50e-9,
        coss_er_f=227e-12,  # PUBLIE -> sert de controle de la methode
        src="datasheet EPC EPC2052 rev. 2022-09-26 p.2 Dynamic Characteristics (typ)",
    ),
    # Si haute performance, mais TRES SURDIMENSIONNE pour ce convertisseur
    # (7 mOhm / 80 A la ou l'optimum est a ~61 mOhm / 2 A). Retenu
    # precisement pour chiffrer ce que coute un mauvais calibre : voir
    # README S7. Valeurs lues sur la page RASTERISEE p.4 (tbl 4/5/6) --
    # la couche texte de ce PDF est decalee (Coss y sort a 16 pF, qui est
    # la valeur de Crss, et Crss y sort en nanosecondes).
    "BSC070N10NS5": dict(
        tech="Si", rds_ohm=0.0070,
        coss50_f=340e-12, qoss50_c=41.0e-9, qg_c=30.0e-9, vgs=10.0, qgd_c=6.0e-9,
        coss_er_f=None,
        src="datasheet Infineon BSC070N10NS5 rev.2.3 (2019-11-13) p.4 tbl 5/6 (typ)",
    ),
}

# NB : les deux pieces Si sont decrites dans GRAPH_TABLE en tete de module
# (leurs fabricants ne publient ni Qoss ni Coss_ER, d'ou l'integration de
# courbe). Il n'y a donc pas de table Si separee ici.


def fiche(part: str) -> dict:
    """Donnees de la piece, quelle que soit la voie d'obtention du Coss."""
    return GRAPH_TABLE[part] if part in GRAPH_TABLE else POWERLAW_TABLE[part]


def gamma_gan(part: str) -> float:
    """gamma tel que Coss(v) = Coss(50)*(50/v)^gamma, deduit de Qoss=∫Coss."""
    d = POWERLAW_TABLE[part]
    return 1.0 - d["coss50_f"] * 50.0 / d["qoss50_c"]


def fom(part: str, vds: float = 80.0) -> float:
    """Figure de merite Eoss x Rds_on, en J.Ohm.

    La surface de puce s'annule dans ce produit (Eoss y est proportionnelle,
    Rds inversement proportionnelle) : c'est donc une constante de
    TECHNOLOGIE, independante du calibre de la piece. C'est elle qu'il faut
    comparer pour opposer Si et GaN -- pas Eoss seule, ni Rds seul.
    """
    return eoss(part, vds) * fiche(part)["rds_ohm"]


def rds_optimal(part: str, irms: float, fsw: float, vds: float = 80.0) -> float:
    """Rds qui minimise (conduction + Coss) a ce courant et cette frequence.

    P(R) = Irms^2 R + FOM/R * fsw   ->   R* = sqrt(FOM*fsw)/Irms
    Croit comme sqrt(fsw) : monter en frequence impose un transistor PLUS
    PETIT, pas plus gros. Contre-intuitif, et c'est le point du S7.
    """
    return math.sqrt(fom(part, vds) * fsw) / irms


def p_min_optimal(part: str, irms: float, fsw: float, vds: float = 80.0) -> float:
    """Perte (conduction + Coss) au calibre optimal : 2*Irms*sqrt(FOM*fsw).

    C'est le gain de TECHNOLOGIE pur -- ce que vaut le materiau une fois le
    calibre bien choisi, sans etre pollue par le choix de reference.
    """
    return 2.0 * irms * math.sqrt(fom(part, vds) * fsw)


def eoss(part: str, vds: float) -> float:
    """Energie stockee dans Coss a vds, en joules. Dissipee dans le switch
    a chaque allumage en commutation dure."""
    if part in GRAPH_TABLE:
        d = GRAPH_TABLE[part]
        return _integ(d["v"], d["coss"], vds, 1)
    d, g = POWERLAW_TABLE[part], gamma_gan(part)
    return d["coss50_f"] * 50.0**g * vds ** (2 - g) / (2 - g)


def qoss(part: str, vds: float) -> float:
    """Charge de sortie a vds, en coulombs. Qoss = Qgd + Qds."""
    if part in GRAPH_TABLE:
        d = GRAPH_TABLE[part]
        return _integ(d["v"], d["coss"], vds, 0)
    d, g = POWERLAW_TABLE[part], gamma_gan(part)
    return d["coss50_f"] * 50.0**g * vds ** (1 - g) / (1 - g)


def p_gate(part: str, fsw: float) -> float:
    """Puissance prise au driver de grille : Qg*Vgs*fsw, en watts.

    N'apparait PAS dans le bilan de la simulation SPICE (la grille y est
    pilotee par une source ideale) : c'est une perte du circuit de
    commande, a ajouter explicitement au bilan systeme. C'est aussi le
    terme ou l'ecart Si/GaN est le plus franc.
    """
    d = fiche(part)
    return d["qg_c"] * d["vgs"] * fsw


def p_coss(part: str, vds: float, fsw: float) -> float:
    """Perte Coss = Eoss*fsw, en watts (commutation dure)."""
    return eoss(part, vds) * fsw


def controle_methode() -> dict:
    """Rejoue le controle qui autorise la loi de puissance : l'EPC2052
    publie Coss_ER, on verifie que la methode le retrouve."""
    d = POWERLAW_TABLE["EPC2052"]
    e = eoss("EPC2052", 50.0)
    cer = 2 * e / 50.0**2
    return dict(coss_er_calcule_f=cer, coss_er_publie_f=d["coss_er_f"],
                ecart_pct=100 * (cer / d["coss_er_f"] - 1))


if __name__ == "__main__":
    ctl = controle_methode()
    print("CONTROLE de la methode (EPC2052, seul a publier Coss_ER) :")
    print(f"  Coss_ER calcule = {ctl['coss_er_calcule_f']*1e12:.0f} pF"
          f"   publie = {ctl['coss_er_publie_f']*1e12:.0f} pF"
          f"   ecart = {ctl['ecart_pct']:+.1f} %\n")

    print(f"CONTROLE de la lecture graphique Si (Qgd par integrale de Crss) :")
    print(f"  integre = {SI_QGD_INTEGRE_NC:.2f} nC   table = {SI_QGD_TABLE_NC:.2f} nC"
          f"   ecart = {100*(SI_QGD_INTEGRE_NC/SI_QGD_TABLE_NC-1):+.1f} %")
    print("  -> ecart ATTENDU : Fig.17 est a VGS=0 (bloque), Qgd au palier")
    print("     Miller (canal conducteur). Validation d'ordre de grandeur.\n")

    VDS, IRMS, POUT = 80.0, 1.75, 40.0
    PARTS = ("Si", "FDT86113LZ", "BSC070N10NS5", "EPC2007", "EPC2007C", "EPC2052")

    print(f"A VDS = {VDS:.0f} V (le point reel du boost 20->80) :")
    print(f"{'piece':14s} {'boitier':18s} {'Rds':>8s} {'Eoss':>9s}"
          f" {'Qoss':>8s} {'FOM':>10s}")
    for part in PARTS:
        d = fiche(part)
        boit = d.get("boitier", "puce nue / SuperSO8")
        print(f"{part:14s} {boit:18s} {d['rds_ohm']*1e3:6.1f} mO"
              f" {eoss(part, VDS)*1e9:7.1f} nJ {qoss(part, VDS)*1e9:6.1f} nC"
              f" {fom(part, VDS)*1e9:6.1f} nJ.O")

    print(f"\nPertes reelles de CHAQUE PIECE, a {POUT:.0f} W / {VDS:.0f} V"
          f" (Irms={IRMS} A), en points de rendement :")
    print(f"{'fsw':>7s} | " + " | ".join(f"{p:^14s}" for p in PARTS))
    for f in (200e3, 400e3, 800e3):
        cells = []
        for part in PARTS:
            p = p_coss(part, VDS, f) + p_gate(part, f) + IRMS**2 * fiche(part)["rds_ohm"]
            cells.append(f"{100*p/POUT:12.2f}pt")
        print(f"{f/1e3:5.0f}kHz | " + " | ".join(cells))

    print(f"\nCALIBRE OPTIMAL : Rds qui minimise conduction+Coss a {IRMS} A,"
          f" et perte atteinte")
    print(f"{'fsw':>7s} | " + " | ".join(f"{p:^20s}" for p in PARTS))
    for f in (200e3, 400e3, 800e3):
        cells = []
        for part in PARTS:
            r, p = rds_optimal(part, IRMS, f, VDS), p_min_optimal(part, IRMS, f, VDS)
            cells.append(f"R*={r*1e3:5.1f}mO {100*p/POUT:5.2f}pt")
        print(f"{f/1e3:5.0f}kHz | " + " | ".join(cells))

    print("\n-> Lire les deux tableaux ensemble : le second donne le gain de")
    print("   TECHNOLOGIE (calibre optimal pour chacun), le premier ce que")
    print("   donnent les pieces TELLES QU'ELLES EXISTENT. L'ecart entre les")
    print("   deux est le cout du mauvais calibre -- et il domine largement")
    print("   l'ecart Si/GaN pour le BSC070N10NS5.")
