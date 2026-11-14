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

## 7. Synthèse — quelle combinaison retenir

Intègre rendement, taille, EMI, souplesse et stabilité — pas seulement
le rendement isolé des §6.1-6.2.

### Diode : Schottky (`NTSV20U100CT`), les 4 critères convergent

| Critère | Schottky | Ultrafast |
|---|---|---|
| Rendement | 98,76% moyen | 97,998% moyen (écart croissant avec fsw : 0,53pt à 100kHz → 2,51pt à 400kHz) |
| EMI (proxy `Vds_overshoot`) | 3,32V moyen | 3,69V moyen |
| Souplesse | Pas de recouvrement par nature (`TT=0`), indépendant du `di/dt` réel | `trr` daté à faible courant (1A), pas au point de fonctionnement réel (§9) |
| Stabilité | Résultats lisses à toutes fréquences/L testées | Partage switch/diode numériquement instable (zigzag confirmé §9, pas un artefact de lecture) |

Aucun des quatre critères ne penche pour l'ultrafast à cette classe de
tension.

### Switch : rester sur Si (`RD3P04BBKHRB`) — pas un verdict contre le GaN

| Critère | Si | GaN |
|---|---|---|
| Rendement | Indiscernable du GaN ici (écart <0,02pt) — **non tranché**, pas une égalité prouvée (§6.2, limite de `dtmax`) |
| Taille | TO-252 | Puce nue/CSP — réellement plus petit, avantage non quantifié ici mais physiquement acquis (datasheet EPC2007 p.1) |
| EMI | Fronts 14/8,7ns (publiés) | Fronts ~4x plus rapides (estimés, §3) — *a priori* plus de contenu harmonique HF |
| Souplesse de commande | `VGS` jusqu'à 10V | `VGS` abs. max **6V** (datasheet) — marge de commande plus étroite |

Le rendement ne départage pas, et les deux critères qui restent (EMI,
souplesse de commande) penchent plutôt pour le Si à ce stade. **Pas une
conclusion contre le GaN** — juste pas de raison de migrer sans un
modèle plus fin qui montrerait un vrai gain de rendement à haute
fréquence (précisément là où l'avantage GaN est censé apparaître, et
précisément ce que ce modèle ne peut pas trancher — §9).

### Fréquence : 200kHz confirmé, cinq critères à l'appui

| | 100kHz | 200kHz | 300kHz | 400kHz |
|---|---|---|---|---|
| Rendement moyen (4 combinaisons) | 98,49% | 98,33% | 98,00% | 97,55% |
| Mode au coin dur (24V→100V/40W, L=47µH) | **DCM** ⚠ | CCM | CCM* | CCM |
| Marge Isat (L=47µH, 40W nominal) | ×1,46 | ×1,87 | ×2,03 | ×2,10 |
| Marge Irms (L=47µH, 40W nominal) | ×4,85 | ×5,20 | ×5,14 | ×5,06 |
| `Vds_overshoot` moyen, proxy EMI (toutes configs) | **6,55V** | 3,25V | 2,31V | 1,90V |
| Écart Schottky/Ultrafast (sensibilité au choix diode) | 0,53pt | 1,25pt | 1,86pt | **2,51pt** |

*300kHz au coin dur : point non convergé (§9, `D`=0,625 au lieu de
~0,76 attendu, `Vout` mesuré 64,19V) — CCM prédit et cohérent partout
ailleurs, non confirmé numériquement à ce point précis.

**100kHz** a le meilleur rendement mais échoue le critère de souplesse
le plus dur (reste en DCM au coin le plus exigeant — la stratégie
DCM-léger/CCM-fort du chapitre 1 n'est pas tenue partout) et a le pire
EMI mesuré ici (overshoot 2 à 3x plus élevé qu'aux autres fréquences).
**Écarté**, comme au chapitre 1.

**400kHz** a la meilleure marge Isat et le meilleur EMI, mais le pire
rendement et surtout la plus forte sensibilité au choix de diode
(2,51pt) — elle amplifie l'enjeu d'un mauvais choix plutôt que de le
tolérer. Candidate seulement si la compacité devient une contrainte
dure.

**200kHz reste le meilleur compromis** : rendement proche du maximum
(-0,16pt vs 100kHz), CCM atteint sur les 3 coins, EMI déjà très réduit
par rapport à 100kHz, marge thermique confortable, et sensibilité
modérée au choix de diode (1,25pt).

### Recommandation

**200kHz, Si+Schottky, L=47µH (SER2211-473)** — la combinaison déjà
retenue après les deux chapitres. Rien dans cette synthèse ne la remet
en cause ; chaque critère nouvellement intégré (EMI, souplesse,
stabilité) converge vers elle plutôt que de l'affaiblir.

**Seule porte ouverte** : un GaN à fréquence plus haute (300-400kHz)
pourrait rattraper son déficit de taille par un vrai gain de
rendement — mais ça demande le modèle plus fin déjà identifié comme
hors périmètre ici (§9), pas une conclusion à tirer de ces données.

## 8. Sélection de candidats réels (TO-252)

Suite au choix Si+Schottky, recherche de candidats réels pour
remplacer les pièces génériques de simulation — contraintes : boîtier
**TO-252**, facilement disponible, performances excellentes.
Inductance **SER2211 déjà retenue, inchangée**.

**Démarche** : recherche par fabricant (pas par distributeur
d'abord — le distributeur sert à vérifier la disponibilité une fois
les candidats identifiés) auprès de fabricants reconnus pour ce
segment (Infineon, Vishay, onsemi pour le switch ; onsemi, Vishay,
Diodes Incorporated pour la diode), puis **lecture directe de la fiche
technique officielle de chaque candidat** (pas d'un résumé de moteur
de recherche) pour en extraire `Rds(on)`/`Qg`/`tr`/`tf` (switch) ou
`Vf`/`Cj` (diode) avec leurs conditions de test exactes — même
discipline que le reste de ce chapitre, aucune valeur retenue sans
l'avoir lue à la source.

### Switch (N-MOS 100V, TO-252) — trois candidats, vérifiés sur fiche officielle

| | Infineon [`IPD050N10N5`](https://infineon.com/cms/en/product/power/mosfet/n-channel/ipd050n10n5) | Vishay [`SUD70090E`](https://www.vishay.com/docs/65437/sud70090e.pdf) | onsemi [`NVD6824NL`](https://www.onsemi.com/products/discrete-power-modules/mosfets/low-medium-voltage-mosfets/nvd6824nl) |
|---|---|---|---|
| `Rds(on)` | 4,3mΩ typ / 5,0mΩ max @10V/40A | 7,4mΩ typ / 8,9mΩ max @10V/20A | 16,5mΩ typ / 20mΩ max @10V/20A |
| `Qg` total | 51nC @0-10V/40A | 33nC @10V/20A | 66nC @10V/20A |
| `tr`/`tf` | 7ns / 7ns @50V/40A/RG=1,6Ω | 27ns / 45ns @50V/10A/RG=1Ω | 55ns / 42ns @80V/20A/RG=2,5Ω |
| `ID` continu | 80A (Tc=25°C) | 50A (limité boîtier) | 41A (Tc=25°C) |
| Boîtier | P-TO252-3 | TO-252 | DPAK (Case 369C) |
| Note | Meilleur `Rds(on)` ET fronts les plus rapides des trois | Compromis `Qg`/vitesse intermédiaire | AEC-Q101 ; `Rds(on)` le plus faible gain vs l'incumbent `RD3P04BBKHRB`, mais encore ×1,5 mieux |

Les trois battent l'incumbent `RD3P04BBKHRB` (`Rds(on)` 23mΩ typ/30mΩ
max) de ×1,5 à ×5,3 — net gain sur la perte de conduction qui domine
le bilan à ces niveaux de courant (§6.2).

### Diode (Schottky ~100V, TO-252/DPAK) — trois candidats, vérifiés sur fiche officielle

| | onsemi [`MBRD5H100T4G`](https://www.onsemi.com/products/discretes-drivers/diodes-rectifiers/schottky-diodes-schottky-rectifiers/mbrd5h100t4g) | Vishay [`VS-6CWQ10FN-M3`](https://www.vishay.com/en/product/93318/) | Diodes Inc [`SBR15U100CTL`](https://www.diodes.com/part/view/SBR15U100CTL) |
|---|---|---|---|
| `Vf` max | 0,71V @5A/25°C (0,60V@125°C) | 0,63V @3A/125°C (0,81V@25°C) | 0,80V @7,5A/25°C (0,65V@125°C) |
| Configuration | Simple (pin 1 NC) | Double cathode commune, 3,5A/jambe | Double cathode commune |
| `Cj` | ~150-1000pF (dépend `VR`, graphe) | 92pF @5V | 200pF @4V |
| Note | Le plus simple à câbler, pas de jambe inutilisée | `Vf` le plus bas au point chaud | Technologie SBR (hybride MOS/Schottky), **avalanche-testée** (`EAS`=192mJ) — tolère un dépassement que la Schottky pure ne tolère pas |

Les trois sont de vraies Schottky (ou assimilées, SBR) — pas de
recouvrement inverse, même argument que celui qui a fait gagner
`NTSV20U100CT` en simulation (§6.1).

### Non vérifié à ce stade

Disponibilité/prix réels chez un distributeur (Digikey, Mouser) pas
encore croisés pour ces six références précises — seulement les
fiches techniques officielles lues directement. À faire avant de
figer un choix final.

### Risque EMI identifié — traité au §9

Le choix ci-dessus ne traite que le rendement/taille/stabilité. Un
risque EMI (`dV/dt`/`dI/dt` des switchs rapides, anneau de résonance
de la boucle chaude avec les inductances/capacités parasites du PCB
et des composants eux-mêmes) doit aussi encadrer le choix final — voir
§9 pour l'estimation des pertes natives des 3 candidats switch et le
rôle des 3 candidats diode dans l'anneau de boucle.

## 9. EMI/résonance — pertes natives des 3 candidats switch, rôle de la diode dans l'anneau de boucle

Un switch rapide (meilleur `Rds(on)` ET fronts rapides, cas de
l'`IPD050N10N5` ci-dessus) peut coûter plus cher en CEM qu'il ne
rapporte en pertes — un switch plus lent avec moins de perte `Coss`
pourrait être préférable. Côté diode, sa capacité de jonction
participe avec les inductances parasites de la boucle chaude à un
système résonant. Démarche : d'abord évaluer si le compromis existe
réellement (pertes, dépassement de tension) avant de changer quoi que
ce soit au choix du §8.

### `Qgd`/`Cj` vérifiés à la source, pas réutilisés tels quels

`Qgd` n'était pas encore extrait au §8 (qui ne donnait que `Qg`
total) — relu directement sur chaque fiche officielle : `IPD050N10N5`
10nC typ/16nC max (`VDD`=50V/`ID`=40A) ; `SUD70090E` 7,5nC typ
(`VDS`=50V/`VGS`=10V/`ID`=20A) ; `NVD6824NL` 18nC typ
(`VGS`=10V/`VDS`=80V/`ID`=20A).

`Cj` diode relue au point proche du régime réel (~80-100V), pas le
point tabulé à bas `VR` souvent seul publié en table — piège
vérifié : `VS-6CWQ10FN-M3` publie 92pF à `VR`=5V en table, mais sa
courbe `C(VR)` tombe à ~28pF au point réel (~90V), un facteur ~3,3 de
différence. Les deux autres candidats (`MBRD5H100T4G` ~130pF,
`SBR15U100CTL` ~53pF au même point, ce dernier extrapolé au-delà de
la courbe tracée) n'avaient de toute façon qu'un graphe, pas de table.

### Pertes à vitesse native (pas ralentie)

Méthode : pas les `tr`/`tf` publiés (conditions de test différentes
d'un fabricant à l'autre, piège déjà signalé §6.2), mais recalculés
depuis `Qgd` et le driver de grille déjà retenu pour cet étage (4A pic
source / 6A pic puits) :

```
t_sw_on  = Qgd / I_source     t_sw_off = Qgd / I_sink
Eon  = 0,5 * Vds * I_valley * t_sw_on
Eoff = 0,5 * Vds * I_peak   * t_sw_off
Psw  = (Eon + Eoff) * fsw
```

Aucune nouvelle simulation : calculé directement depuis les points
déjà mesurés au §6 (switch=Si/diode=Schottky générique, 20V→80V/40W,
L=47µH, les 4 fréquences) — le courant au point de fonctionnement ne
dépend pas du `Rds(on)`/`Qgd` réellement monté.

| Switch | `fsw` | `P_cond` (W) | `Psw` (W) | `P_total` (W) | `Psw`/`Ptotal` |
|---|---|---|---|---|---|
| `IPD050N10N5` | 100kHz | 0,015 | 0,030 | 0,045 | 66% |
| `IPD050N10N5` | 200kHz | 0,013 | 0,063 | 0,076 | 82% |
| `IPD050N10N5` | 400kHz | 0,014 | 0,138 | 0,152 | 91% |
| `SUD70090E` | 100kHz | 0,026 | 0,022 | 0,049 | 46% |
| `SUD70090E` | 200kHz | 0,023 | 0,047 | 0,070 | 67% |
| `SUD70090E` | 400kHz | 0,025 | 0,103 | 0,128 | 81% |
| `NVD6824NL` | 100kHz | 0,059 | 0,054 | 0,113 | 48% |
| `NVD6824NL` | 200kHz | 0,052 | 0,113 | 0,165 | 69% |
| `NVD6824NL` | 400kHz | 0,055 | 0,248 | 0,303 | 82% |

![Pertes switch à vitesse native, conduction vs commutation](plots/emi_switch_losses.png)

**Constat** : même à vitesse native, la commutation **domine** le
bilan (66-91% selon candidat/fréquence) — à l'opposé du §6.2, qui
trouvait la conduction dominante avec les modèles génériques. Mais en
absolu, `P_total` reste **très faible** (45 à 303mW sur 40W) : les 3
candidats sont largement surdimensionnés en courant pour cette
application. La rapidité de l'`IPD050N10N5` ne coûte donc pas
significativement en pertes absolues.

### Boucle chaude : estimation par placement (pré-routage)

Carte déjà placée mais pas encore routée (aucune géométrie de piste
réelle disponible) — estimation par placement + littérature
uniquement, sert de budget cible, à revérifier au routage. Périmètre
mesuré directement sur le placement réel de l'inductance/switch/diode
de cet étage : **52mm**. Heuristique nH/cm (carte sans plan de masse
rapproché actuellement) : ~8-12nH/cm pour une boucle sans retour
proche, ordre de grandeur courant en littérature de layout pour
boucles de commutation ; un retour soigné au routage viserait plutôt
~3-5nH/cm. Fourchette résultante : **42-62nH** (état actuel) contre
**16-26nH** (cible routage).

### Calcul à la main vs confirmation SPICE

Calcul : `f0 = 1/(2π√(Lboucle×(Coss+Cj)))`,
`Vpic = Vout + Ipk_L×√(Lboucle/(Coss+Cj))`. Confirmation SPICE : les 9
combinaisons switch×diode, point nominal, `Lstray`=52nH (état actuel) :

| Switch | Diode | `f0` calculé | `Vpic` calculé | `Vds` simulé | Écart |
|---|---|---|---|---|---|
| `IPD050N10N5` | `MBRD5H100T4G` | 26,5MHz | 104,1V | 83,9V | -19% |
| `IPD050N10N5` | `VS-6CWQ10FN-M3` | 28,8MHz | 106,1V | 83,8V | -21% |
| `SUD70090E` | `MBRD5H100T4G` | 22,3MHz | 100,3V | 84,1V | -16% |
| `NVD6824NL` | `VS-6CWQ10FN-M3` | 47,6MHz | 123,2V | 83,5V | -32% |

(tableau complet des 9 combinaisons : voir le script de reproduction)

![Dépassement de tension : calcul (borne sup.) vs simulation](plots/emi_resonance_overshoot.png)

**Écart systématique, toujours dans le même sens** (calculé > simulé,
16 à 32%) — pas un écart aléatoire, mais un artefact de modélisation
identifié : la formule à la main suppose que tout le courant
d'inductance charge le réservoir `Lstray`-`C` depuis zéro, comme si
aucun chemin de roue libre n'existait. En réalité, les 3 candidats
diode sont des Schottky/SBR **sans recouvrement inverse** (même
argument qui a fait gagner `NTSV20U100CT` au §6.1) : dès que le switch
bloque, la diode conduit quasi instantanément et **clampe** le nœud de
commutation près de `Vout`, consommant l'essentiel de l'énergie qui
aurait fait sonner le réservoir LC. La formule à la main reste une
**borne supérieure conservatrice utile**, mais surestime le risque réel
pour ce jeu de candidats.

**Dépassement réel observé** : `Vds_switch_max` ≈ 83,5-84,1V pour
`Vout_avg` ≈ 78,5-80V, soit **4 à 5,5V (~5-7%)** — quel que soit le
candidat. Sensibilité à `Lstray` testée (52nH vs 21nH cible routage) :
dépassement **quasi identique** — le clamp par la diode rend le
dépassement insensible à `Lstray` dans cette fourchette.

### Verdict

- **Risque de dépassement de tension sur le switch : faible**, grâce
  au clamp quasi-instantané des diodes Schottky/SBR retenues.
- **Risque dI/dt / spectre conduit : non tranché par cette passe** —
  le faible dépassement de tension ne dit rien du `dI/dt` réel dans la
  boucle, grandeur pertinente pour le spectre CEM conduit, non mesurée
  ici.
- Le compromis rapidité/EMI évoqué en préambule **ne se lit pas** dans
  les pertes (toutes sous 0,3W) ni dans le dépassement de tension
  (insensible au candidat) pour ce jeu de candidats précis.

### Ce qui reste ouvert sur ce point

- **Spectre CEM conduit** (réseau LISN + FFT) — pas fait dans cette
  passe : le faible dépassement de tension trouvé rendait la
  justification moins pressante dans l'immédiat.
- **Estimation de boucle pré-routage** — fourchette de littérature,
  à revérifier une fois la boucle réellement routée.
- **`Coss` du `NVD6824NL`** lu à `VDS`=25V (pas 50-80V comme les 2
  autres candidats) — probablement surestimé au point réel, sans
  autre donnée publiée pour corriger. N'affecte pas le verdict (ce
  candidat n'est de toute façon pas le switch recommandé au §8).
- **Extraction de la période d'oscillation depuis la forme d'onde** —
  abandonnée après une anomalie d'outillage sans rapport avec les
  résultats ; la comparaison `Vpic`/`Vds_switch_max` reste la
  vérification retenue, `f0` n'est donné qu'au titre du calcul à la
  main.
- **Candidats diode avec recouvrement réel** non retestés — écartés
  dès le §6.1, mais le clamp qui explique le faible dépassement ici
  dépend spécifiquement de l'absence de recouvrement.

## 10. Ce qui reste ouvert / différé

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
- **Le partage switch/diode de la perte totale est numériquement bruité
  à `dtmax`=1ns — confirmé par re-simulation, pas juste suspecté.**
  Repéré en relisant `plots/stage1_tech_switching_loss.png` (colonne de
  droite, Si+Ultrafast, L=47µH) : `Ploss_diode_recovery_est` zigzague
  avec la fréquence (0,030/0,074/0,033/0,091W aux 4 fréquences) au lieu
  d'évoluer progressivement. Diagnostic en deux temps :
  1. **Ce n'est pas qu'un artefact de la décomposition conduction/
     recouvrement** (l'estimateur `Vf` statique à `Iout_avg` constant
     reste une simplification réelle, séparée) — `Ploss_diode_total`,
     la mesure SPICE **directe**, zigzague déjà elle-même
     (0,4276/0,4848/0,4359/0,4983W aux 4 fréquences), alors que
     `Ploss_switch_total` et le rendement, mesurés dans la même fenêtre,
     restent lisses. Le partage entre les deux intégrales
     (`Id(M1)*V(n_sw)` et `I(D1)*(V(n_sw)-V(vout))`) est donc instable,
     pas seulement le post-traitement qui en dérive.
  2. **Confirmé par re-simulation ciblée** des 4 points (Si+Ultrafast,
     L=47µH, 100-400kHz) à `dtmax`=0,2ns (5x plus fin) : la série
     `Ploss_diode_total` devient quasi monotone (0,427/0,445/0,441/
     0,471W) — le zigzag se résorbe très largement. `Ploss_switch_total`
     reste lisse aux deux résolutions, mais se décale de -12 à -14% aux
     deux fréquences les plus basses — un biais réel à `dtmax`=1ns, pas
     seulement du bruit, mais qui n'affecte pas la forme de la courbe.
  **Conséquence** : le graphique `stage1_tech_switching_loss.png` (les
  deux colonnes, pas seulement le recouvrement diode) est à lire comme
  qualitatif — ordre de grandeur, tendance générale avec la fréquence —
  pas comme des valeurs absolues fiables. Refaire les 240 points à
  `dtmax`=0,2ns est impraticable ici (5x le temps déjà mesuré à 1ns, de
  l'ordre de plusieurs heures) ; non fait dans ce chapitre. **Les
  verdicts du §6.1/§6.2 restent valables** : ils comparent le rendement,
  mesuré directement et resté lisse aux deux résolutions testées — pas
  la décomposition switch/diode.
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
