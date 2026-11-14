"""Volet EMI/resonance (README S9) -- estimation de l'inductance de
boucle chaude (inductance/switch/diode de cet etage) a partir du
PLACEMENT DEJA FAIT sur le PCB (carte placee, pas encore routee --
aucune geometrie de piste reelle a lire). Le fichier PCB lui-meme n'est
pas inclus dans ce depot public (projet materiel prive) ; les distances
mesurees ci-dessous sont reprises telles quelles de ce placement.

Methode : perimetre minimal atteignable avec CE placement (distance
centre-a-centre des 3 empreintes du noeud de commutation) x valeur
nH/cm heuristique de litterature -- sert de BUDGET CIBLE pour guider
le routage a venir, PAS une mesure sur cuivre reel. A revERIFIER une
fois routee.

Heuristique nH/cm : carte 2 couches, AUCUNE zone de cuivre definie
actuellement -- pas de plan de masse rapproche sous la boucle pour
l'instant, donc valeur haute de la fourchette habituelle en
electronique de puissance pour une boucle "en l'air" (piste simple,
sans retour rapproche) : ~8-12 nH/cm (ordre de grandeur courant des
notes d'application de layout pour boucles de commutation de
convertisseurs a decoupage, ex. ~1 nH/mm sans plan de retour). Un
retour (plan ou piste large juste sous la boucle) au routage pourrait
reduire cette valeur vers 3-5 nH/cm -- cible a viser, pas garantie par
le placement seul.
"""
import math

# Distances centre-a-centre mesurees sur le placement reel (mm).
DIST_L_SWITCH_MM = 18.59
DIST_SWITCH_DIODE_MM = 13.99
DIST_DIODE_L_MM = 19.53

NH_PER_CM_NO_PLANE = (8.0, 12.0)   # fourchette basse/haute, pas de plan proche
NH_PER_CM_WITH_RETURN = (3.0, 5.0)  # cible si retour soigne au routage


def main():
    perimeter_mm = DIST_L_SWITCH_MM + DIST_SWITCH_DIODE_MM + DIST_DIODE_L_MM
    perimeter_cm = perimeter_mm / 10.0

    print("Distances centre-a-centre (empreintes deja placees, non routees) :")
    print(f"  L <-> switch  : {DIST_L_SWITCH_MM:.2f} mm")
    print(f"  switch <-> diode : {DIST_SWITCH_DIODE_MM:.2f} mm")
    print(f"  diode <-> L   : {DIST_DIODE_L_MM:.2f} mm")
    print(f"  Perimetre triangle L/switch/diode : {perimeter_mm:.2f} mm "
          f"({perimeter_cm:.3f} cm)\n")

    for label, (lo, hi) in [("sans plan de retour rapproche (etat actuel)",
                              NH_PER_CM_NO_PLANE),
                             ("avec retour soigne au routage (cible)",
                              NH_PER_CM_WITH_RETURN)]:
        l_lo = perimeter_cm * lo
        l_hi = perimeter_cm * hi
        print(f"Lboucle estimee, {label} :")
        print(f"  {l_lo:.1f} - {l_hi:.1f} nH "
              f"(perimetre x {lo:.0f}-{hi:.0f} nH/cm)\n")

    return perimeter_cm


if __name__ == "__main__":
    main()
