# Session LTspice — architecture 1 (GaN EPC2207, DCM 400 kHz)

Ouvrir `archi1_epc2207.asc` dans LTspice et lancer (Run). Le dossier est
autonome : le symbole et la bibliothèque EPC sont à côté du schéma, on
peut le déplacer tel quel.

Généré par `../gen_asc_archi1.py` — **ne pas éditer le `.asc` à la main**
si on veut pouvoir le régénérer ; modifier le générateur à la place. En
revanche, changer une valeur *dans LTspice* pour explorer est exactement
l'usage prévu.

## Ce que c'est

Boost 20 V → 80 V en conduction discontinue permanente, 4,7 µH, 400 kHz,
avec le **modèle constructeur EPC** du GaN (pas un modèle ajusté à la
main). Topologie **double-pulse** : la source `Vo` remplace le
condensateur de sortie et la charge. Pas de réservoir, donc pas de piège
de facteur Q, et les pertes de commutation sont directement comparables à
un essai de banc.

## Les trois réglages

| paramètre | effet |
|---|---|
| `duty` | fixe la puissance : 0,19 → 5 W · 0,41 → 20 W · 0,52 → 40 W · 0,63 → 53 W |
| `LB` | inductance de maille de commutation — le **seul** paramètre non sourcé du modèle |
| `TSW` | période de découpage (2,5 µs = 400 kHz) |

Le lien `duty` → puissance n'est pas exactement quadratique : les temps de
montée de grille décalent le temps de conduction effectif de quelques
pourcents. Lire `pout` plutôt que de se fier à la formule.

## Lire les résultats

Les `.meas` sortent dans **View → SPICE Error Log** (Ctrl+L).

Les pertes se somment **uniquement sur les éléments dissipatifs** :

```
GaN    = pcanal + prd + prs
diode  = pdio
cuivre = pcu
```

**Ne pas utiliser la puissance aux bornes du GaN** pour un bilan : elle
inclut le stockage capacitif, réversible, et ne converge qu'à pas de temps
très fin. Mesuré : 56,63 mW à 94 ps de pas moyen contre 52,25 mW à 48,6 ps,
alors que la somme par éléments donne 51,95 mW aux deux pas.

Le bouclage résiduel du bilan est de **1,8 % des pertes** (0,024 point de
rendement). Ce n'est pas un poste manquant : vérifié contre la durée
d'établissement, la méthode d'intégration (trap / modified trap / gear) et
le fenêtrage, tous sans effet. C'est l'erreur d'intégration sur les
éléments réactifs rapides — un Tellegen complet montre l'inductance de
maille `Lb`, pourtant idéale, à +1,6 mW sur trois périodes entières.

## La grandeur qui décide : `von`

`von` est la tension du nœud **100 ps avant l'allumage du canal**. Elle
décide de tout le reste :

- `von ≈ 0` → allumage à zéro de tension, E_oss récupérée ;
- `von` grand → E_oss(von) × f_sw dissipée dans le canal, jusqu'à 262 mW.

À fréquence et rapport cyclique fixes, elle **n'est pas maîtrisée** : la
résonance de temps mort tourne vers 7 MHz pendant que le découpage est à
400 kHz, donc l'allumage tombe à une phase arbitraire. Balayage mesuré de
5 à 53 W : `von` saute entre 0 et 43 V sans tendance monotone, et à 5,6 W
le GaN dissipe plus qu'à 29 W pour cette seule raison. `vmin` reste à
−1,8 V partout : la résonance **atteint** toujours zéro, elle n'est
simplement jamais **capturée**. C'est l'argument pour le valley switching.

## Pièges rencontrés en construisant ce schéma

À connaître avant d'en dériver un autre.

1. **`plotwinsize=0` est obligatoire.** La compression de formes d'onde par
   défaut (300 points par fenêtre) détruit les intégrales de pertes sur des
   fronts de quelques nanosecondes. Ne pas la retirer.
2. **Les nœuds internes d'un sous-circuit ne sont pas sauvés d'office.**
   Sans la directive `.save V(u1:drain) …`, les `.meas` qui les référencent
   échouent sur « Voltage not found ».
3. **La hiérarchie se désigne par l'InstName seul.** Depuis un schéma c'est
   `u1:drain`, ni `xu1:drain` ni `x1:drain` — alors que depuis une netlist
   écrite à la main où l'instance s'appelle littéralement `X1`, c'est
   `x1:`. Les deux voies ne se nomment pas pareil.
4. **Le symbole `EPCGaN.asy` d'origine porte `SYMATTR ModelFile`**, ce qui
   fait ajouter à LTspice une directive `.lib` relative en plus de la
   nôtre : la bibliothèque est alors chargée deux fois et LTspice refuse le
   circuit (« more than one sub-circuit definition »). La copie locale du
   symbole en est amputée.

## Correspondance avec les scripts

Ce schéma est le pendant manipulable de `../gen_dcm_ltspice.py`, qui génère
la même chose en netlist pour les balayages automatisés. Les deux voies ont
été confrontées sur le point 20 W : Pout 20,6550 contre 20,6550 W, `von`
19,574 contre 19,57 V, `vpk` 106,52 contre 106,5 V.
