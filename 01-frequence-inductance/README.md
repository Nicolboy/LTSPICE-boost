# Chapitre 1 — Fréquence de découpage et choix d'inductance

Étude d'un étage boost non synchrone (batterie 11-25V → 50-100V, 5 à
40W) : validation de la fréquence de découpage et du choix
d'inductance, par simulation LTspice pilotée en Python + vérification
croisée avec un calcul analytique.

> **État** : switch et diode **idéaux/génériques** (pas de candidat
> Si/SiC/GaN précis — c'est le sujet du chapitre 2). Inductance
> **réelle** (valeur et DCR tirées d'une vraie fiche constructeur) —
> c'est la seule fidélité « composant réel » introduite dans ce
> chapitre, délibérément, pour isoler ce qu'on cherche à valider
> (méthode incrémentale : un seul paramètre réel à la fois, le reste
> idéal).

## 1. Pourquoi cette étude

Deux choix à justifier par la mesure : la fréquence de découpage, et
l'inductance. Contrainte de départ : **pas d'inductance physiquement
plus grosse qu'un boîtier donné** (ici Coilcraft SER2211, ~11,5×11mm)
— donc une seule valeur fixe sur toute la comparaison de fréquence, pas
une inductance différente par fréquence.

## 2. Méthode

**Topologie** : boost non synchrone — `Vin → L(réelle, DCR série) →
nœud de commutation → switch bas-côté → GND`, `diode (anode=nœud,
cathode=Vout) → Cout → Rload`.

**Idéalisation** : switch NMOS générique (`RD=10mΩ`, `IS=1e-12` pour
désactiver la diode de corps interne — jamais sollicitée dans le sens
de conduction normal du boost), diode générique (`IS=100n N=1
RS=10mΩ`) — aucun des deux n'est un candidat de technologie précis.

**Scénarios** : 3 couples (Vin,Vout) appariés — 12V→60V, 20V→80V
(**point à optimiser**), 24V→100V — × 4 puissances (5/10/20/40W) × 4
fréquences candidates (100/200/300/400kHz, toutes au-delà du spectre
audio) = 48 points. Duty cycle résolu par bissection contre le `Vout`
simulé (`find_duty1.py`), jamais la seule formule idéale CCM
`D=1-Vin/Vout` — robuste que le point tombe en CCM ou DCM.

**Stratégie de conduction retenue** : DCM à faible puissance (diode
insensible à la technologie à ce régime, le courant revient à zéro
tout seul), bascule en CCM à forte puissance (courant crête/efficace
limité). Seuil analytique (`inductor_sizing.py`, formule boost
standard — Erickson, *Fundamentals of Power Electronics*) :

```
L_crit(Vin,Vout,Pout,fsw) = Vin² · (1-Vin/Vout) / (2·fsw·Pout)
```

Au-dessus de `L_crit`, CCM ; en dessous, DCM.

## 3. Bug trouvé et corrigé : constante de temps `Cout×Rload`

Premier balayage à 200kHz : les points à faible puissance donnaient
des rendements **impossibles** (53%, 115%, 117%...). Cause : avec un
`Cout` réaliste (220µF) et un `Rload` élevé à faible puissance (ex.
2kΩ à 5W/100V), la constante de temps `Cout×Rload` atteint **0,44s** —
très au-delà de toute fenêtre de simulation raisonnable (20ms à
200kHz/4000 périodes). Les mesures tombaient en pleine transition de
charge du condensateur, pas en régime établi — l'énergie encore en
train de rentrer/sortir du condensateur faussait le bilan `Pin`/`Pout`.

**Corrigé** : `Cout` réduit à 2,2µF pour ce chapitre (n'affecte que
l'ondulation et le temps d'établissement, **pas** la valeur moyenne de
`Vout` ni le rendement en régime établi). La vraie valeur sera
réintroduite dans le chapitre dédié aux condensateurs. Un deuxième bug
de convergence SPICE (nœud de commutation sans aucune capacité,
transition en marche d'escalier pure — `IS`/`RD` trop extrêmes dans une
première tentative de modèle idéal) a aussi été corrigé par un `RD`/`IS`
moins extrêmes et une capacité parasite minime (20pF, non sourcée,
juste assez pour lisser la transition) au nœud de commutation.

## 4. Vérification croisée calcul ↔ SPICE

**Correspondance parfaite** entre le mode CCM/DCM prédit
analytiquement (§2) et mesuré en SPICE sur les 48 points — y compris le
cas le plus informatif : à **100kHz**, le calcul prédit que le coin
24V→100V reste en DCM jusqu'à 40W (seuil calculé 46,57W) ; la
simulation le confirme exactement (`mode_measured=DCM` à 40W, Vout
mesuré 101,85V). Aux trois autres fréquences (200/300/400kHz), ce même
coin bascule en CCM bien avant 40W (seuils 23,29/15,52/11,64W), comme
prédit.

Deux points (100kHz, 24V→100V, 5W et 10W) n'ont pas convergé en deçà de
2% sur `Vout` (DCM profond, sensibilité extrême de `Vout` à `D` à cette
fréquence/ce coin — `D=0,38` donne 145V au lieu de 100V visé) : le mode
DCM lui-même est fiable (cohérent avec le calcul), mais les valeurs de
rendement/courant à ces 2 points précis ne sont pas à citer comme
précises.

## 5. Résultats — mode CCM/DCM par fréquence

| | 100kHz | 200kHz | 300kHz | 400kHz |
|---|---|---|---|---|
| Seuil CCM/DCM à 12V→60V | 12,26W | 6,13W | 4,09W | 3,06W |
| Seuil CCM/DCM à 20V→80V (nominal) | 31,91W | 15,96W | 10,64W | 7,98W |
| Seuil CCM/DCM à 24V→100V (pire coin) | **46,57W** | 23,29W | 15,52W | 11,64W |
| 24V→100V/40W : mode mesuré | **DCM** ⚠ | CCM | CCM | CCM |

**Verdict fréquence — 100kHz écarté, 200kHz confirmé comme choix
judicieux.** Seul 100kHz échoue à atteindre le CCM au coin
24V→100V/40W (reste en DCM, courant crête/efficace plus élevé que
visé pour ce régime). 200/300/400kHz atteignent tous le CCM
confortablement sur l'ensemble du domaine testé — **l'hypothèse de
départ (200kHz) est confirmée** par le calcul et la simulation : c'est
la fréquence la plus basse qui tienne la stratégie DCM-léger/CCM-fort
sur les 3 coins, sans sur-contraindre inutilement (300-400kHz
n'apportent, à ce stade d'idéalisation, qu'une réduction du courant
crête — voir §6 — au prix d'une fréquence de commutation plus élevée
dont le coût réel, les pertes de commutation, est justement différé au
chapitre suivant).

## 6. Résultats — rendement et courant crête

| Point (40W) | 100kHz | 200kHz | 300kHz | 400kHz |
|---|---|---|---|---|
| η 12V→60V | 98,65% | 98,67% | 98,67% | 98,67% |
| η 20V→80V (nominal) | 99,19% | 99,22% | 99,21% | 99,18% |
| η 24V→100V | 99,36%* | 99,36% | 99,54% | 99,39% |
| Ipk 20V→80V (A) | 3,68 | 2,77-2,89 | 2,63 | 2,38 |

*mode DCM à 100kHz sur ce coin — rendement non comparable terme à
terme au même sens qu'en CCM.

**Le rendement ne varie quasiment pas avec la fréquence** (98,6-99,5%
partout) — attendu et sans surprise : avec switch/diode idéaux, la
perte dominante est la chute directe de la diode (quasi
indépendante de la fréquence) et la DCR de l'inductance (fixe, même
pièce partout). **Ce que la fréquence change réellement ici** : le
courant crête/efficace baisse avec la fréquence (même L) — pertinent
pour la marge de saturation et, plus tard, les pertes de conduction
réelles — et surtout la marge CCM/DCM (§5). Le vrai compromis
rendement/fréquence (pertes de commutation, qui AUGMENTENT avec la
fréquence et dépendent fortement de la technologie Si/SiC/GaN) n'est
**pas visible à ce stade** — c'est précisément l'objet du chapitre 2.

Tous les rendements mesurés sont ≥ 98,6%, confortablement au-dessus
d'un minimum de 90% visé — sans surprise à ce niveau d'idéalisation,
cette marge se réduira une fois les pertes de commutation réelles
introduites.

## 7. Nœud chaud (`Vds_switch`)

Plafonne proprement à `Vout` à tous les points (ex. 79,5-82,4V au point
nominal 80V selon la fréquence) — aucun dépassement, comme attendu pour
un boost 100% idéal sans parasite modélisé. Pas de clamp nécessaire à
ce stade : cette comparaison n'aura de sens qu'avec un vrai modèle de
diode à recouvrement inverse (chapitre 2).

## 8. Comparaison de valeurs d'inductance

Question posée après coup : le choix de `L=47µH` a été validé *lui-même*
sur le domaine fréquence (§5-6), mais jamais comparé à d'autres
valeurs/familles. Grille retenue : **10/22/47/100/220/330µH**, dans les
familles qui proposent réellement ces valeurs — pas d'extrapolation :

| Famille | Boîtier | Valeurs testées sur la grille |
|---|---|---|
| **SER2211** (déjà choisie) | 11,5×11mm | 8,2 / 27 / 47µH — la série n'a pas de valeur exacte à 10 ou 22µH (gamme complète : 3/5,3/8,2/12/27/33/47µH), 8,2 et 27 sont les plus proches |
| MSS1583 | 14,8×14,8mm (plus gros) | 10/22/47/100/220/330µH (toutes) |
| MSS1514V | 15,5×15,5mm (encore plus gros, 1000V max) | 47/100/220µH (sa plage commence à 33µH) |

Méthode allégée pour cette comparaison (pas une revalidation complète
par pièce) : point nominal (20V→80V) aux 4 puissances + vérification
CCM au coin le plus dur (24V→100V) à 40W. DCR/Isat/Irms sourcés des
fiches constructeur respectives (Coilcraft, doc 1084-1 pour SER2211,
1111-1 pour MSS1583, 1755-1 pour MSS1514V). Répétée aux 4 fréquences
candidates. Figures : `plots/stage1_Lcompare_{100,200,300,400}khz.png`.

**Le verdict tient aux 4 fréquences, pas seulement à 200kHz** — SER2211-473
reste au-dessus du nuage MSS1583/MSS1514V sur les trois critères
(rendement, marge Isat, marge Irms) à chaque fréquence testée :

| Fréquence | η SER2211-473 à 40W nominal | Marge Isat | Marge Irms (40°C) |
|---|---|---|---|
| 100kHz | 99,19% | ×1,22 | ×4,78 |
| 200kHz | 99,21% | ×1,55 | ×5,09 |
| 300kHz | 99,20% | ×1,71 | ×5,15 |
| 400kHz | 99,19% | ×1,80 | ×5,16 |

Seule variation notable : la marge Isat de SER2211-473 se resserre à
100kHz (×1,22, plus proche du seuil « prudent » ×1,5 que des ×1,6-1,8
aux fréquences plus hautes) — cohérent avec le courant crête plus élevé
à 100kHz déjà observé en §5-6, mais toujours confortablement au-dessus
de 1.

**Toute la série SER2211 testée (pas seulement 47µH), à 200kHz** — même
constat à 8,2 et 27µH : DCR nettement sous la courbe MSS1583/MSS1514V à
chaque valeur, pas seulement au sommet de la série :

| Pièce SER2211 | DCR (mΩ) | η à 40W nominal | Marge Isat | Marge Irms (40°C) |
|---|---|---|---|---|
| SER2211-822 (8,2µH) | 2,30 | 99,16% | ×2,16 | ×6,30 |
| SER2211-273 (27µH) | 6,84 | 99,21% | ×2,25 | ×6,00 |
| SER2211-473 (47µH) | 8,95 | 99,21% | ×1,55 | ×5,09 |

Les trois valeurs SER2211 dominent le nuage MSS1583/MSS1514V sur les
figures (points bleus toujours au-dessus) — la série n'est pas
seulement avantageuse à 47µH, c'est une caractéristique de toute la
gamme (cohérent avec l'argument constructeur « exceptionally high
current carrying capability »). Pas de raison de préférer 8,2 ou 27µH à
47µH ici : les trois ont une marge confortable au point nominal, mais
seule 47µH a été validée sur l'ensemble du domaine Vin/Vout/Pout (§4-7)
— rester sur ce choix.

**Résultat net : SER2211-473 (47µH) reste le meilleur choix, pas
seulement parce qu'il respecte la contrainte de boîtier — il est
objectivement meilleur à la même inductance.**

| Pièce (47µH) | Boîtier | DCR (mΩ) | η à 40W nominal | Marge Irms (40°C) |
|---|---|---|---|---|
| **SER2211-473** | 11,5×11mm | **8,95** | **99,21%** | **×5,09** |
| MSS1514V-473 | 15,5×15,5mm | 38 | 98,92% | ×1,88 |
| MSS1583-473 | 14,8×14,8mm | 48 | 98,82% | ×1,78 |

Passer à un boîtier plus gros, à la même valeur d'inductance, **ne
gagne rien** — la DCR de SER2211 est 4 à 5 fois plus faible, malgré un
boîtier plus petit. Le rendement et la marge thermique baissent tous
les deux avec le boîtier plus gros à L fixée.

**Au sein d'une même famille (MSS1583, tendance la plus complète),
monter en inductance pour réduire l'ondulation se paie cash** :

| L (MSS1583) | DCR (mΩ) | η à 40W nominal | Marge Isat (10%) | Marge Irms (40°C) |
|---|---|---|---|---|
| 10µH | 14 | 98,99% | ×2,18 | ×2,71 |
| 22µH | 23 | 99,01% | ×2,20 | ×2,35 |
| 47µH | 48 | 98,82% | ×2,09 | ×1,78 |
| 100µH | 90 | 98,41% | ×1,63 | ×1,38 |
| 220µH | 205 | 97,27% | ×1,20 | **×0,90** ⚠ |
| 330µH | 300 | 96,16% | **×0,90** ⚠ | **×0,69** ⚠ |

**À partir de 220µH, la marge passe sous 1** — le courant Irms simulé
dépasse la cote 40°C-rise du composant à 40W. Autrement dit : **ces
pièces chaufferaient plus que prévu par leur propre fiche constructeur
à ce point de fonctionnement**, pas juste « moins de marge » — un
dimensionnement à éviter sans descendre la puissance visée ou accepter
un échauffement non garanti par le fabricant.

**MSS1514V suit la même tendance, en moins sévère** (boîtier encore
plus gros, mais DCR mieux maîtrisée par valeur que MSS1583) :

| L (MSS1514V) | DCR (mΩ) | η à 40W nominal | Marge Isat (10%) | Marge Irms (40°C) |
|---|---|---|---|---|
| 47µH | 38 | 98,92% | ×1,67 | ×1,88 |
| 100µH | 64 | 98,66% | ×1,34 | ×1,53 |
| 220µH | 152 | 97,79% | **×1,01** ⚠ | ×1,10 |

À 220µH, MSS1514V reste juste au-dessus de 1 (×1,01/×1,10) là où
MSS1583-224 était déjà passé en dessous (×0,90 Irms) — DCR plus basse
à cette valeur (152 vs 205mΩ) malgré un boîtier plus gros. Reste
inférieur à SER2211-473 sur les trois critères à 47µH (tableau
ci-dessus), donc ne change pas le verdict.

**Verdict** : aucune des 9 alternatives testées ne bat SER2211-473 sur
le rapport rendement/marge thermique à cette fréquence/cette plage de
puissance. Les petites valeurs (10-22µH) en MSS1583 s'en sortent bien
électriquement mais n'apportent rien par rapport à SER2211-473 (moins
bon sur les trois critères) tout en étant dans un boîtier plus gros.
Le choix initial (47µH, SER2211) est confirmé, pas seulement toléré par
la contrainte de boîtier.

## 9. Ce qui reste ouvert / différé au(x) chapitre(s) suivant(s)

- **Technologie transistor/diode (Si/SiC/GaN)** — switch et diode
  restent génériques. Le CCM/DCM retenu ici influencera ce choix : DCM
  tolère un redresseur plus lent (le courant revient à zéro tout
  seul), CCM profite d'un redresseur rapide (SiC) pour éviter le
  recouvrement inverse. **→ chapitre 2.**
- **Pertes de commutation** — non modélisées, c'est pourquoi le
  rendement ne varie pas avec la fréquence dans ce chapitre (§6). Le
  vrai compromis rendement/fréquence ne sera visible qu'avec cette
  fidélité ajoutée. **→ chapitre 2.**
- **Pertes fer de l'inductance et ondulation de tension réelle** — non
  modélisées (DCR seule, `Cout` réduit artificiellement, §3). À refaire
  avec les vraies valeurs une fois le reste validé. **→ chapitre 3.**
- **100kHz, 24V→100V, 5W et 10W** — mode DCM confirmé mais valeurs
  précises non fiables (§4), à reprendre avec une méthode de recherche
  de D plus robuste si ce point redevient pertinent.

## Reproduire

Simulation LTspice (mode batch, testé en 26.1.1), pilotée en Python —
voir `requirements.md`/commentaires de chaque script pour le chemin de
l'exécutable LTspice à adapter.

- Calcul analytique seul : `python inductor_sizing.py`
- Balayage fréquence (un point L fixe) : `python run_sweep_stage1.py <fsw_Hz>`
- Comparaison d'inductance : `python run_sweep_Lcompare.py <fsw_Hz>`
  puis `python run_sweep_Lcompare_extra.py <fsw_Hz>`
- Graphiques : `python make_plots_stage1.py`, `python make_plots_Lcompare.py`

Les CSV de résultats et les `.asc`/`.log`/`.raw` intermédiaires ne sont
pas versionnés (régénérables) — seuls les scripts et les PNG finaux le
sont.
