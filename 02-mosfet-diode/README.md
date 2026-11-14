# Chapitre 2 — Technologie switch/diode

Suite directe du chapitre 1 (fréquence/inductance), qui a validé
200kHz/47µH avec switch et diode **idéaux/génériques** — explicitement
différé : « technologie transistor/diode » et « pertes de commutation ».

> **État** : switch et diode **réels** (modèles simples mais paramétrés
> sur des pièces réelles), inductance balayée sur 3 valeurs dans la même
> famille/boîtier que le chapitre 1. Pas de modèle vendeur complet
> (licence, lenteur) — c'est l'objet d'une éventuelle passe de
> raffinement ultérieure, sur moins de paramètres libres.

## 1. Pourquoi cette étude

Trois questions laissées ouvertes par le chapitre 1 :

- Le switch Si incumbent a-t-il un intérêt à être remplacé par du GaN, à
  cette classe de tension (100V) ?
- La diode : Schottky Si ou ultrafast PN Si ?
- Le rendement ne variait quasiment pas avec la fréquence au chapitre 1
  (switch/diode idéaux) — est-ce toujours vrai avec de vraies pertes de
  commutation/recouvrement ? Le choix 200kHz tient-il ?

**Pas de SiC dans ce chapitre.** Il n'existe pas de MOSFET SiC commercial
réaliste en classe 100V (le SiC cible 650V+ par nature, le marché des
Schottky SiC basse tension est quasi inexistant) — réservé à une étude à
plus haute tension.

**Redressement synchrone écarté.** À `Vout`≈80-100V, la perte `Vf` d'une
diode ne représente qu'une fraction marginale de la puissance (~0,3-1%,
référence littérature sur un cas très proche, boost 24V→200V) — gain net
classique en basse tension/fort courant (≤5V), pas ici : le
driver/switch supplémentaire coûterait probablement plus qu'il ne
ferait gagner à cette tension.

**GaN cascode et MOSFET Si superjonction écartés ici** — différence
d'architecture de driver (cascode) ou avantage trop faible à 100V
(superjonction, plus pertinent à plus haute tension) pour justifier une
3e variante.

## 2. Comparaison retenue

| | Option A | Option B |
|---|---|---|
| Switch | Si — `RD3P04BBKHRB` (incumbent) | GaN — `EPC2007` (candidat) |
| Diode | Schottky Si — `NTSV20U100CT` (candidat) | Ultrafast PN Si — `STTH2002` (candidat) |

4 combinaisons testées : (Si,Schottky) / (Si,Ultrafast) / (GaN,Schottky)
/ (GaN,Ultrafast). Fiches techniques constructeur non incluses dans ce
dépôt (licences respectives EPC/onsemi/ST/ROHM) — voir les sites des
fabricants pour les références exactes.

## 3. Modèles SPICE — simples, paramétrés sur les pièces réelles

Pas de modèle vendeur complet — un modèle simple par technologie, calibré
sur les grandeurs publiées (`switch_diode_models.py`) :

- **Switch** : `RD` = Rds_on réel (max, Tj=25°C) — Si 30mΩ, GaN 30mΩ
  (même classe, comparaison directe). `Coss` réel en shunt du nœud de
  commutation (Si 115pF, GaN 118pF — remplace la capacité numérique non
  sourcée du chapitre 1). Tension de grille PROPRE à chaque techno (Si
  10V, GaN 5V — l'EPC2007 a un VGS abs max de 6V, 10V le détruirait).
  Fronts de commande : Si — tr/tf publiés directement (14/8,7ns,
  RG=1Ω) ; GaN — **estimés** (non publiés par EPC) par le ratio QGD(GaN)/
  QGD(Si) appliqué aux tr/tf réels du Si (le palier Miller, dominé par
  QGD, gouverne la durée de transition à courant de grille ~constant) :
  tr≈3,56ns, tf≈2,21ns. **Hypothèse de modélisation documentée dans
  `switch_diode_models.py`, pas une donnée datasheet.**
- **Diode** : `IS` résolu (pas deviné) pour que le modèle statique
  (`N·VT·ln(I/IS) + I·RS`) retombe sur le `Vf` datasheet au courant de
  test publié. Schottky : `TT=0` (porteurs majoritaires, pas de
  recouvrement par nature). Ultrafast : `TT=16ns`, calé sur le `trr`
  typique publié (testé à faible courant par le fabricant — voir limites
  §9).
- **Self parasite au nœud de commutation** : ESTIMÉE (pas mesurée),
  variant modestement avec L (20/30/40nH pour 12/27/47µH — toutes les 3
  valeurs restent dans le même boîtier, donc pas de saut d'ordre de
  grandeur). Sans elle, le recouvrement inverse ne produit aucun
  dépassement de tension observable — l'intérêt de la Schottky resterait
  invisible en simulation (voir §4).

## 4. Bug/ajustement trouvé : pas de temps (`dtmax`) trop grossier

Premier essai, `dtmax` hérité du chapitre 1 (10ns) : le dépassement de
tension (`Vds_switch_max`) sortait QUASI IDENTIQUE entre Schottky et
ultrafast, alors que les pertes mesurées, elles, divergeaient déjà
nettement. Cause : l'anneau LC `Lstray`/`Coss` (~13-14ns de période avec
les valeurs de ce chapitre) et le recouvrement diode (`TT`=16ns) sont
plus courts que le pas de 10ns hérité du chapitre 1 — sous-échantillonnés,
donc lissés avant que le solveur ne puisse en capturer le pic.

**Corrigé** : `dtmax` resserré à 1ns pour le point FINAL retenu (~13
points par anneau, suffisant pour voir un pic sans être excessif).
Resserrer `dtmax` sur toute la fenêtre de réglage du chapitre 1 (4000
périodes) aurait rendu le balayage impraticable (dizaines de secondes
par point) — réglé en réduisant `Cout` à 0,22µF (10x plus petit qu'au
chapitre 1, même justification : la constante de temps `Cout×Rload` doit
rester compatible avec une fenêtre de simulation courte) et en calculant
`settle_periods`/`measure_periods` pour une durée ABSOLUE fixe (~3ms de
réglage) plutôt qu'un nombre de périodes fixe (qui ferait exploser le
temps de calcul aux basses fréquences). La recherche du duty cycle par
bissection (`find_duty2.py`) tourne avec un `dtmax` grossier (10ns) et
une fenêtre courte (150 périodes) — rapide, un `Vout` approximatif
suffit pour converger en direction — puis UNE seule simulation finale,
précise, est relancée au `D` retenu : c'est celle-ci qui fournit les
mesures réellement exploitées.

## 5. Ce que révèle le modèle (point nominal 20V→80V/40W, 200kHz, L=47µH)

| | Si+Schottky | Si+Ultrafast |
|---|---|---|
| `Vds_overshoot` | 5,08V (+6,4%) | 5,47V (+6,9%) |
| `Ploss_switch_total` | 0,234W | 0,603W (**+158%**) |
| `Ploss_diode_total` | 0,268W | 0,478W (**+79%**) |

**Constat important, pas anticipé au départ** : le dépassement de
tension crête (`Vds_overshoot`) n'est PAS le signal le plus discriminant
— il est présent mais modeste dans les deux cas (l'anneau LC de base,
présent sur CHAQUE front de commutation même sans recouvrement, domine
déjà le pic). Le signal réellement décisif est la **perte**
(commutation switch +158%, conduction+recouvrement diode +79%) : le
courant de recouvrement de la diode ultrafast circule surtout à travers
le switch pendant son propre front de montée déjà en train de sonner,
ajoutant de l'énergie dissipée plus qu'un pic de tension supplémentaire
net.

## 6. Résultats du balayage complet (240 points)

`run_sweep_tech.py` → `results/stage1_tech_sweep.csv` (non versionné,
régénérable), `make_plots_tech.py` → `plots/stage1_tech_*.png`.

**Qualité des données — 193/240 points fiables (80%)**, 47 points
rejetés des statistiques ci-dessous. Tous les rejets (sauf un) suivent
le MÊME schéma, déjà rencontré au chapitre 1 : en DCM profond, à faible
puissance (5-20W) avec les DEUX plus petites valeurs de L (12/27µH —
précisément celles qui n'étaient PAS sur la grille du chapitre 1),
`Vout` est hypersensible à `D` et la bissection grossière (150 périodes,
tolérance 2%, 8 itérations) ne converge pas en deçà de 5% sur `Vout`.
C'est un effet du balayage élargi de ce chapitre (plus de valeurs de L
testées → plus de combinaisons tombent en DCM profond à basse
puissance), pas une régression de méthode. Un point isolé (300kHz,
47µH, coin le plus dur, 40W — pourtant prédit et mesuré CCM) a aussi
échoué à converger — anomalie de recherche ponctuelle, pas corrélée au
schéma DCM ci-dessus. **Les verdicts ci-dessous utilisent uniquement les
193 points convergés.**

### 6.1 Diode : Schottky bat ultrafast PN, nettement et partout

| | Si+Schottky | Si+Ultrafast | GaN+Schottky | GaN+Ultrafast |
|---|---|---|---|---|
| η moyen (nominal, toutes L/fsw/P convergées) | **98,76%** | 97,998% | **98,76%** | 97,98% |

Écart ~0,78 point d'efficacité, **quel que soit le switch** — cohérent
avec le test de fumée (§5) : le courant de recouvrement de l'ultrafast
ajoute une perte réelle et mesurable, qui domine largement l'effet du
choix de switch (ci-dessous). L'écart grandit avec la fréquence (plus de
commutations par seconde = plus d'événements de recouvrement par
seconde) :

| | 100kHz | 200kHz | 300kHz | 400kHz |
|---|---|---|---|---|
| η Si+Schottky (L=47µH, 40W nominal) | 98,79% | 98,73% | 98,61% | 98,47% |
| η Si+Ultrafast (L=47µH, 40W nominal) | 98,26% | 97,48% | 96,75% | 95,96% |
| Écart | 0,53pt | 1,25pt | 1,86pt | **2,51pt** |

**Verdict diode : Schottky Si nettement préférable à l'ultrafast PN à
cette classe de tension — l'écart s'aggrave avec la fréquence,
renforçant le choix si une fréquence plus haute que 200kHz était
envisagée.**

### 6.2 Switch : Si et GaN quasiment indiscernables dans ce modèle simple

| | Si+Schottky | GaN+Schottky | Écart |
|---|---|---|---|
| η moyen (nominal, convergé) | 98,760% | 98,759% | 0,001pt |
| η moyen avec Ultrafast | 97,998% | 97,977% | 0,021pt |

**Résultat non anticipé au départ** : avec `Rds_on` et `Coss` quasiment
identiques (30mΩ/115-118pF pour les deux pièces, même classe 100V) et
une perte de conduction qui domine largement la perte de commutation à
ces niveaux de courant (quelques A), la différence de vitesse de
commutation (fronts GaN ~4x plus rapides, estimés — voir §3) ne se
traduit PAS en un gain d'efficacité mesurable dans ce modèle. **Limite
méthodologique identifiée, pas une conclusion définitive sur le GaN** :
le `dtmax`=1ns retenu pour rendre les 240 points praticables (§4)
résout correctement les fronts du Si (8,7-14ns, ~9-14 points/front)
mais SOUS-échantillonne ceux du GaN (2,2-3,6ns, ~2-4 points/front
seulement) — la perte de commutation du GaN, déjà petite en valeur
absolue (dizaines à centaines de mW sur 40W), est en dessous du bruit
de résolution temporelle à ce `dtmax`. **Ne pas conclure "le GaN n'a
aucun intérêt ici" — conclure "ce modèle simple, à ce `dtmax`, ne
permet pas de trancher" — voir §9.**

### 6.3 Fréquence : le compromis rendement/fréquence, enfin visible

Contrairement au chapitre 1 (switch/diode idéaux, rendement quasi
constant 98,6-99,5% sur les 4 fréquences), **le rendement baisse
maintenant clairement avec la fréquence** une fois les pertes de
commutation/recouvrement réelles introduites — exactement ce que le
chapitre 1 avait annoncé comme différé ici :

| | 100kHz | 200kHz | 300kHz | 400kHz |
|---|---|---|---|---|
| η moyen (40W nominal, 4 combinaisons, convergé) | **98,49%** | 98,33% | 98,00% | 97,55% |

**Tension avec le verdict CCM/DCM du chapitre 1** : 100kHz reste écarté
pour la même raison déjà établie (le coin le plus dur à 40W reste en
DCM à cette fréquence même à L=47µH, confirmé à nouveau ici). **200kHz
reste donc le meilleur compromis** parmi les fréquences qui atteignent
le CCM sur les 3 coins — pas la fréquence la plus efficace dans
l'absolu (100kHz le serait, mais au prix du retour en DCM profond au
coin le plus dur), mais la plus basse qui tienne la stratégie
DCM-léger/CCM-fort du chapitre 1 tout en limitant la perte de
recouvrement diode. **L'hypothèse de départ (200kHz) reste confirmée,
avec une justification plus complète qu'au chapitre 1** (qui ne pouvait
pas encore voir ce compromis).

### 6.4 Inductance : le choix du chapitre 1 n'est pas remis en cause

Les valeurs plus petites (12/27µH) souffrent d'un défaut de convergence
numérique sévère en DCM profond (voir qualité des données ci-dessus)
sans apporter de bénéfice de rendement visible sur les points qui
CONVERGENT (écarts <0,1 point entre les 3 valeurs de L à
puissance/fréquence égales, dominés par le bruit plutôt que par un effet
réel de L sur la techno switch/diode — attendu : L ne change pas
directement `Rds_on`/`Vf`/`TT`, seulement le courant crête/efficace,
déjà étudié au chapitre 1). Rien dans ce chapitre ne contredit le choix
d'inductance déjà validé au chapitre 1.

### 6.5 Dépassement de tension (`Vds_overshoot`)

| | Schottky | Ultrafast |
|---|---|---|
| Moyenne (toutes configs) | 3,32V | 3,69V |

Confirme la tendance du test de fumée (§5) : l'ultrafast a un
dépassement un peu plus élevé, mais l'écart (~0,4V) reste modeste
devant l'anneau de base déjà présent sans recouvrement — **le signal
décisif reste la perte, pas le pic de tension** (§6.1).

## 9. Ce qui reste ouvert / différé

- **Verdict switch (Si vs GaN) non tranché, pas négatif** — le `dtmax`
  =1ns nécessaire pour tenir les 240 points en temps praticable
  sous-échantillonne les fronts GaN (2,2-3,6ns estimés, voir §6.2). Une
  comparaison fiable demanderait soit un `dtmax` plus fin sur un nombre
  de points réduit (ex. seulement la techno diode déjà gagnante, les 4
  fréquences, L=47µH — 2 switch x 4 fsw = 8 points au lieu de 240),
  soit une passe de raffinement vendeur. **Ne pas répéter la conclusion
  "Si et GaN ne changent rien" hors de ce modèle et de ce `dtmax`.**
- **47/240 points rejetés pour non-convergence** (§6) — tous en DCM
  profond à faible puissance avec les 2 plus petites valeurs de L. Un
  point isolé (300kHz/47µH/coin le plus dur/40W) a aussi échoué sans ce
  schéma — anomalie de recherche, à reprendre si ce point précis
  redevient pertinent.
- **Décomposition conduction/recouvrement diode bruitée** — le graphique
  `plots/stage1_tech_switching_loss.png` (colonne de droite) montre un
  `Ploss_diode_recovery_est` NON NUL même pour la Schottky (`TT=0`,
  structurellement sans recouvrement). Ce n'est pas un recouvrement réel :
  l'estimateur de perte de conduction (`Vf` statique évalué à `Iout_avg`
  constant) est un point unique sur une courbe non-linéaire, alors que le
  courant réel dans la diode est triangulaire — l'écart résiduel se
  retrouve classé "recouvrement" par soustraction, même quand il n'y en a
  pas. **Les verdicts du §6.1 n'utilisent PAS cette décomposition** (ils
  comparent le rendement global, mesuré directement) — seul ce graphique
  supplémentaire en hérite, à lire comme qualitatif (ordre de grandeur,
  tendance) plutôt que quantitatif.
- **Point de test `trr` de l'ultrafast à faible courant** — le `trr`
  datasheet (16ns) est mesuré à un courant bien plus faible que le
  courant nominal du composant ou le point de fonctionnement réel de ce
  chapitre. Le `TT` du modèle simple hérite de cette limite — une
  calibration plus fine nécessiterait le `Qrr` à un courant/di-dt plus
  représentatif (lecture graphique non faite ici).
- **Auto-échauffement non modélisé** — `Rds_on`/`Vf` utilisés à Tj=25°C
  (valeur datasheet directe), pas de boucle thermique (même limite que
  le chapitre 1).
- **Passe de raffinement avec modèles vendeur complets** — suite logique
  une fois la techno gagnante connue, sur moins de paramètres libres.
  Hors périmètre de ce chapitre.

## Reproduire

Simulation LTspice (mode batch), pilotée en Python — voir
commentaires de chaque script pour le chemin de l'exécutable LTspice à
adapter.

- Test fumée (un point) : `python find_duty2.py 20 80 40 200000 47e-6 8.95e-3 Si Schottky`
- Balayage complet (240 points, ~80 minutes) : `python run_sweep_tech.py`
- Graphiques : `python make_plots_tech.py`

Les CSV de résultats et les `.asc`/`.log`/`.raw` intermédiaires ne sont
pas versionnés (régénérables) — seuls les scripts et les PNG finaux le
sont.
