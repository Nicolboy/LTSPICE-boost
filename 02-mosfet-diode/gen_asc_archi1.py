"""Genere le schema LTspice de l'architecture 1, ouvrable et simulable.

Destine a etre manipule a la main dans LTspice : on peut y changer le
rapport cyclique, l'inductance de maille ou la frequence depuis les
directives `.param` affichees sur la feuille, puis relancer.

CHOIX DE TRACE : cablage par ETIQUETTES DE NET (`FLAG`), pas par fils
longs. Chaque broche sort de son symbole sur 48 px puis porte son nom de
net. C'est plus lisible qu'un plat de spaghettis sur douze composants, et
surtout c'est verifiable : il suffit de comparer la liste des etiquettes
a la netlist attendue, alors qu'un fil mal raccorde de 16 px ne se voit
pas a l'oeil.

CONTRAINTES DU FORMAT .asc, toutes verifiees contre la reference ADI :
  - encodage WINDOWS-1252, jamais UTF-8. Le caractere micro y est l'octet
    0xB5 ; on l'evite ici en ecrivant `4.7u` plutot que `4.7u` avec le
    symbole, pour qu'un futur passage d'outil ne puisse pas le casser.
  - `Version 4.1` en tete pour un fichier neuf.
  - grille de 16 unites, +y vers le BAS.
  - coordonnees de broche = transformee de l'orientation appliquee aux
    offsets locaux. Pour R0 : world = (sx+px, sy+py).
  - toute broche sort sur >= 48 px DANS SA DIRECTION avant tout virage,
    et aucun fil ne traverse un corps de symbole.

GEOMETRIE LOCALE UTILISEE (reference ADI, « Standard Symbol Geometry ») :
  voltage  : +[1]=(0,16)   -[2]=(0,96)
  res, ind : A[1]=(16,16)  B[2]=(16,96)
  cap      : A[1]=(16,0)   B[2]=(16,64)
  schottky : +[1]=(16,0)   -[2]=(16,64)
  EPCGaN   : gatein[1]=(0,0) sortie GAUCHE
             drainin[2]=(80,-96) sortie HAUT
             N_0[3]=(80,32) sortie BAS   (verifie sur EPCGaN.asy)

L'ORDRE DES BROCHES EST CE QUI COMPTE, pas le placement : le chiffre entre
crochets est la position du noeud sur la ligne de netlist generee. D'ou
l'attribution explicite ci-dessous (L1 porte vin sur A et nl sur B, etc.).
"""
from __future__ import annotations

from pathlib import Path

ICI = Path(__file__).resolve().parent
DEST = ICI / "ltspice"
LIB_EPC = Path(r"C:\Users\Nicolas\workspace_ccstheia\lib_spice_commun\EPC")

# --- geometrie locale des symboles (px, py) par ordre SPICE
GEOM = {
    "voltage":  [(0, 16), (0, 96)],
    "res":      [(16, 16), (16, 96)],
    "ind":      [(16, 16), (16, 96)],
    "cap":      [(16, 0), (16, 64)],
    "schottky": [(16, 0), (16, 64)],
    "EPCGaN":   [(0, 0), (80, -96), (80, 32)],
}
# direction de sortie de chaque broche, en local R0 (+y vers le bas)
SORTIE = {
    "voltage":  [(0, -1), (0, 1)],
    "res":      [(0, -1), (0, 1)],
    "ind":      [(0, -1), (0, 1)],
    "cap":      [(0, -1), (0, 1)],
    "schottky": [(0, -1), (0, 1)],
    "EPCGaN":   [(-1, 0), (0, -1), (0, 1)],
}
# boite d'encombrement locale (R0) : l'encre dessinee plus les ancres de
# broches, hors texte d'attribut. Source : reference ADI, meme tableau que
# la geometrie des broches.
BOITE = {
    "voltage":  (-32, 16, 32, 96),
    "res":      (0, 16, 32, 96),
    "ind":      (5, 16, 32, 96),
    "cap":      (0, 0, 32, 64),
    "schottky": (0, 0, 32, 64),
    "EPCGaN":   (0, -96, 119, 32),   # releve sur EPCGaN.asy (cercle a x=119)
}
STUB = 48          # longueur minimale de sortie de broche
MARGE = 16         # jeu minimal exige entre deux boites


class Feuille:
    """Accumule les lignes d'un .asc et verifie ce qu'elle produit."""

    def __init__(self, largeur: int = 2240, hauteur: int = 1520):
        self.l = [f"Version 4.1", f"SHEET 1 {largeur} {hauteur}"]
        self.nets: dict[str, list[tuple[int, int]]] = {}
        self.instances: list[tuple[str, list[str]]] = []
        self.boites: list[tuple[str, int, int, int, int]] = []
        self.textes: list[tuple[int, int, int]] = []

    def composant(self, symbole: str, sx: int, sy: int, nom: str,
                  valeur: str, nets: list[str], extra: str | None = None):
        """Place un symbole en R0 et etiquette chacune de ses broches.

        `nets` suit l'ORDRE SPICE des broches, pas leur position a l'ecran.
        """
        assert len(nets) == len(GEOM[symbole]), \
            f"{nom}: {len(nets)} nets pour {len(GEOM[symbole])} broches"
        bx0, by0, bx1, by1 = BOITE[symbole]
        self.boites.append((nom, sx + bx0, sy + by0, sx + bx1, sy + by1))
        self.l.append(f"SYMBOL {symbole} {sx} {sy} R0")
        self.l.append(f"SYMATTR InstName {nom}")
        if valeur:
            self.l.append(f"SYMATTR Value {valeur}")
        if extra:
            self.l.append(f"SYMATTR SpiceLine {extra}")
        for (px, py), (dx, dy), net in zip(GEOM[symbole], SORTIE[symbole], nets):
            x, y = sx + px, sy + py                      # transformee R0
            bx, by = x + dx * STUB, y + dy * STUB        # bout du stub
            self.l.append(f"WIRE {x} {y} {bx} {by}")
            self.l.append(f"FLAG {bx} {by} {net}")
            self.nets.setdefault(net, []).append((bx, by))
        self.instances.append((nom, nets))

    def texte(self, x: int, y: int, contenu: str, taille: int = 2):
        self.textes.append((x, y, len(contenu)))
        self.l.append(f"TEXT {x} {y} Left {taille} {contenu}")

    def rendu(self) -> str:
        return "\r\n".join(self.l) + "\r\n"


def construit(duty: float = 0.40677, l_boucle: float = 20e-9,
              fsw: float = 400e3) -> Feuille:
    import gen_dcm_ltspice as g
    tsw = 1.0 / fsw
    f = Feuille()
    Y = 192          # ligne des symboles verticaux
    YC = 208         # cap et diode : broche haute deja a 208

    # ---- chaine de puissance
    f.composant("voltage", 96, Y, "V1", f"{g.VIN}", ["vin", "0"])
    f.composant("ind", 256, Y, "L1", "4.7u", ["vin", "nl"])
    f.composant("res", 416, Y, "Rdcr", "5.5m", ["nl", "nsw"])
    f.composant("cap", 576, YC, "Cl", "5.26p", ["vin", "nsw"])
    # ---- switch GaN, modele constructeur
    # InstName U1 et NON X1 : le symbole a `Prefix x`, donc un InstName
    # commencant par X fait ecrire a LTspice `X$X1` (marqueur de prefixe
    # deja present), et les noeuds internes ne se referencent plus par
    # `x1:...`. ATTENTION, c'est la vraie subtilite : dans un SCHEMA
    # LTspice prefixe toujours l'instance, mais la HIERARCHIE se designe
    # par l'InstName SEUL -- ici `u1:drain`, ni `u1:drain` ni `x1:drain`.
    # Ca differe d'une netlist ecrite a la main, ou l'instance est
    # litteralement `X1` et la hierarchie `x1:`. Constate sur les ports
    # exposes par .backanno, qui sortent en `Ix(u1:drainin)`.
    f.composant("EPCGaN", 736, 400, "U1", "EPC2207", ["ng", "nsw", "nss"])
    f.composant("voltage", 960, Y, "Vs", "0", ["nss", "0"])
    # ---- commande de grille
    f.composant("res", 1120, Y, "Rg", f"{g.RG_EXT}", ["ngd", "ng"])
    f.composant("voltage", 1280, Y, "Vg",
                f"PULSE(0 {g.VGS} 0 150p 150p {{duty*TSW}} {{TSW}})",
                ["ngd", "0"])
    # ---- maille de commutation et redressement
    f.composant("ind", 1440, Y, "Lb", "{LB}", ["nsw", "nda"])
    f.composant("schottky", 1600, YC, "D1", "DV6PW", ["nda", "nd"])
    f.composant("voltage", 1760, Y, "Vd", "0", ["nd", "vout"])
    f.composant("voltage", 1920, Y, "Vo", f"{g.VOUT}", ["vout", "0"])

    # ---- directives
    t0 = g.N_ETAB * tsw
    t1 = t0 + g.N_MES * tsw
    t_von = t0 + 2 * tsw - 100e-12
    # Le symbole EPC porte `SYMATTR ModelFile EPCGanlibrary.lib` et LTspice
    # ajoute TOUT SEUL la directive correspondante -- ce qui chargeait la
    # bibliotheque DEUX fois des qu'une copie locale existait, et LTspice
    # refuse alors le circuit (« more than one sub-circuit definition »).
    # On retire donc cet attribut de NOTRE copie du symbole (cf. plus bas)
    # et on reprend la main avec un `.lib` explicite RELATIF : un seul
    # chargement, et le dossier reste deplacable tel quel.
    d = [
        "!.lib EPCGaNLibrary.lib",
        f"!.model {g.DIODE[0]} {g.DIODE[1]}",
        f"!.param TSW={tsw:.6e} LB={l_boucle:.4e}",
        f"!.param duty={duty:.5f}",
        "!.options reltol=1e-5 abstol=1e-13 vntol=1e-9 chgtol=1e-16 plotwinsize=0",
        f"!.tran 0 {t1:.6e} {t0:.6e} 0.1n uic",
        # SANS ce .save, LTspice ne conserve PAS les noeuds internes du
        # sous-circuit, et les .meas qui les referencent echouent sur
        # « Voltage not found ». Une netlist ecrite a la main a le meme
        # besoin ; c'est facile a oublier en passant au schema.
        "!.save V(nsw) V(ng) V(nss) V(nda) V(nd) V(ngd) I(L1) I(V1) I(Vd) I(Vg)",
        "!.save V(u1:drain) V(u1:source) V(u1:gate)"
        " I(u1:bswitch) I(u1:rd) I(u1:rs) I(u1:rg)",
        f"!.meas TRAN pout AVG {g.VOUT}*I(Vd) FROM {t0:.6e} TO {t1:.6e}",
        f"!.meas TRAN pin  AVG {-g.VIN}*I(V1) FROM {t0:.6e} TO {t1:.6e}",
        f"!.meas TRAN ipk  MAX I(L1) FROM {t0:.6e} TO {t1:.6e}",
        f"!.meas TRAN vpk  MAX V(nsw) FROM {t0:.6e} TO {t1:.6e}",
        f"!.meas TRAN vmin MIN V(nsw) FROM {t0:.6e} TO {t1:.6e}",
        f"!.meas TRAN von  FIND V(nsw) AT={t_von:.9e}",
        f"!.meas TRAN pdio AVG (V(nda)-V(nd))*I(Vd) FROM {t0:.6e} TO {t1:.6e}",
        f"!.meas TRAN pcu  AVG I(L1)*I(L1)*{g.DCR:.4e} FROM {t0:.6e} TO {t1:.6e}",
        f"!.meas TRAN pcanal AVG (V(u1:drain)-V(u1:source))*I(u1:bswitch)"
        f" FROM {t0:.6e} TO {t1:.6e}",
        f"!.meas TRAN prd AVG (V(nsw)-V(u1:drain))*I(u1:rd) FROM {t0:.6e} TO {t1:.6e}",
        f"!.meas TRAN prs AVG (V(nss)-V(u1:source))*I(u1:rs) FROM {t0:.6e} TO {t1:.6e}",
    ]
    for i, ligne in enumerate(d):
        f.texte(96, 640 + i * 24, ligne)

    c = [
        ";Architecture 1 -- GaN EPC2207 (modele constructeur EPC) en DCM "
        f"permanent, {fsw/1e3:.0f} kHz, 4.7uH, {g.VIN:.0f} V -> {g.VOUT:.0f} V",
        ";Topologie DOUBLE-PULSE : Vo remplace Cout+charge. Pas de reservoir,",
        ";donc pas de piege de facteur Q, et les pertes de commutation sont",
        ";directement comparables a un essai de banc.",
        ";",
        ";A REGLER : `duty` fixe la puissance (0.19 -> 5 W, 0.41 -> 20 W,",
        ";0.52 -> 40 W, 0.63 -> 53 W). `LB` est l'inductance de maille de",
        ";commutation -- le SEUL parametre non source du modele, d'ou son",
        ";balayage (10 / 20 / 40 / 80 nH).",
        ";",
        ";NE PAS RETIRER `plotwinsize=0` : la compression de formes d'onde par",
        ";defaut detruit les integrales de pertes sur des fronts de quelques ns.",
        ";",
        ";Les pertes se lisent dans les .meas, et se somment UNIQUEMENT sur les",
        ";elements dissipatifs (pcanal+prd+prs pour le GaN, pdio, pcu). La",
        ";puissance aux BORNES du GaN inclut le stockage capacitif reversible",
        ";et ne converge qu'a pas tres fin -- ne pas s'en servir pour un bilan.",
    ]
    for i, ligne in enumerate(c):
        f.texte(96, 1120 + i * 20, ligne, taille=1)
    return f


def verifie(f: Feuille) -> None:
    """Controles avant ecriture -- ce qu'un coup d'oeil ne verrait pas."""
    # 1. tout net cite doit l'etre au moins deux fois, sinon il flotte
    seuls = [n for n, p in f.nets.items() if len(p) < 2 and n != "0"]
    assert not seuls, f"nets a une seule broche (flottants) : {seuls}"
    # 2. deux FLAG differents ne doivent pas tomber au meme point
    pos: dict[tuple[int, int], str] = {}
    for net, points in f.nets.items():
        for p in points:
            autre = pos.get(p)
            assert autre in (None, net), \
                f"collision en {p} : '{net}' et '{autre}'"
            pos[p] = net
    # 3. AUCUN symbole ne doit en chevaucher un autre
    for i, (n1, ax0, ay0, ax1, ay1) in enumerate(f.boites):
        for n2, bx0, by0, bx1, by1 in f.boites[i + 1:]:
            if (ax0 - MARGE < bx1 and bx0 < ax1 + MARGE
                    and ay0 - MARGE < by1 and by0 < ay1 + MARGE):
                raise AssertionError(
                    f"{n1} ({ax0},{ay0})-({ax1},{ay1}) et "
                    f"{n2} ({bx0},{by0})-({bx1},{by1}) se chevauchent")
    # 4. aucune etiquette ni aucun texte ne doit tomber dans une boite
    for net, points in f.nets.items():
        for (px, py) in points:
            for nom, x0, y0, x1, y1 in f.boites:
                assert not (x0 <= px <= x1 and y0 <= py <= y1),                     f"etiquette '{net}' en ({px},{py}) dans la boite de {nom}"
    for (tx, ty, _n) in f.textes:
        for nom, x0, y0, x1, y1 in f.boites:
            assert not (x0 - 8 <= tx <= x1 + 8 and y0 - 8 <= ty <= y1 + 8),                 f"texte en ({tx},{ty}) dans la boite de {nom}"
    # 5. la masse doit exister
    assert "0" in f.nets, "pas de reference de masse"
    # 4. le fichier doit etre encodable en cp1252 (contrainte du format)
    f.rendu().encode("cp1252")
    print(f"  {len(f.instances)} composants, {len(f.nets)} nets : "
          f"{', '.join(sorted(f.nets))}")
    for nom, nets in f.instances:
        print(f"    {nom:<5} -> {' '.join(nets)}")


if __name__ == "__main__":
    import sys
    sys.path[:0] = [str(ICI)]
    DEST.mkdir(parents=True, exist_ok=True)
    f = construit()
    verifie(f)
    cible = DEST / "archi1_epc2207.asc"
    cible.write_bytes(f.rendu().encode("cp1252"))
    print(f"\n-> {cible}")
    # le symbole doit etre a cote du schema : LTspice cherche d'abord dans
    # le repertoire du fichier ouvert
    import shutil
    shutil.copy2(LIB_EPC / "EPCGaNLibrary.lib", DEST / "EPCGaNLibrary.lib")
    print(f"-> {DEST / 'EPCGaNLibrary.lib'}")
    # copie du symbole AMPUTEE de son `SYMATTR ModelFile` : sinon LTspice
    # ajoute un second `.lib` et refuse le circuit pour subckt en double
    asy = (LIB_EPC / "EPCGaN.asy").read_text(encoding="cp1252")
    gardees = [l for l in asy.splitlines()
               if not l.strip().startswith("SYMATTR ModelFile")]
    assert len(gardees) < len(asy.splitlines()), \
        "SYMATTR ModelFile introuvable dans EPCGaN.asy"
    asy = "\r\n".join(gardees) + "\r\n"
    (DEST / "EPCGaN.asy").write_text(asy, encoding="cp1252")
    print(f"-> {DEST / 'EPCGaN.asy'} (sans SYMATTR ModelFile)")
    print("   (dossier autonome : LTspice cherche symbole et bibliotheque "
          "d'abord a cote du schema)")
