# Fréquence, mode, et les quatre choix couplés — remise à plat

Établi le 2026-11-21, à la demande du concepteur : *« pour l'instant on
tourne en rond : pas de MOSFET choisi, pas d'inductance, pas de diode, pas
de mode de fonctionnement ni de fréquence. »*

Plage d'emploi retenue pour cet arbitrage : **5 à 50 W**, 20 V → 80 V.
Critères, dans cet ordre : **mode de fonctionnement**, puis **rendement sur
toute la plage**, puis CEM, volume, prix.

---

## 1. Pourquoi ça tournait en rond

### L'hypothèse de départ n'avait jamais été instruite

Les premiers prototypes, montés à la main, tournaient à **200 kHz avec
47 µH**. Ce n'était ni une simulation ni une étude : de l'expérience, de
l'intuition, et les composants disponibles.

Le chapitre 1 a ensuite « validé » 200 kHz. Mais il écrit, à son §5 :
*« l'hypothèse de départ (200 kHz) est confirmée »* — **il a confirmé son
propre point de départ**, c'est-à-dire l'intuition du prototype. Et il l'a
fait avec un **switch et une diode idéaux**, délibérément, comme son
en-tête l'annonce. Un banc idéal ne peut pas voir les pertes de
commutation — exactement la grandeur qui fixe l'optimum de fréquence.

**La fréquence n'a donc jamais été choisie sur un critère de rendement.**

### Et le choix mesuré a été écrasé par un paragraphe non simulé

Le §11.8 du chapitre 2 a bien fait le travail : 343 cellules exploitées,
240 en CCM et 103 en DCM, **zéro désaccord de mode**, $E_{oss}$ par
intégration de $C_{oss}(V)$ et charge de grille réelles. Il en sort **deux
configurations complètes**, et une recommandation.

Le §11.9 suivant les a écartées au profit du **DCM permanent à 4,7 µH /
400 kHz** — en portant lui-même l'avertissement :

> ⚠️ *Tout ce paragraphe est ANALYTIQUE, calculé sur les données de fiche.
> Rien n'en est simulé : le balayage ne contient ni le 4,7 µH, ni la
> détection d'anneau, ni l'inductance de boucle. À vérifier avant d'en
> faire une décision de conception.*

**C'est cette piste que les chapitres 3 et 4 ont suivie.** Le 4,7 µH a
depuis été abandonné ; les 400 kHz, venus du même paragraphe, sont restés.
Voilà la boucle : *un résultat mesuré écarté par un calcul de fiche, dont
la prémisse a ensuite été abandonnée sans rendre la décision au résultat
mesuré.*

---

## 2. Le résultat structurel qui ferme une branche

$$\Large P_\text{lim}=\frac{V_{in}^{2}\,D\,\eta}{2\,L\,f_{sw}}
\qquad\Longrightarrow\qquad P_\text{lim}=\frac{C}{L\,f_{sw}},
\quad C=133{,}6$$

Constante recoupée sur le tableau du §12.1 : 16,7 µH à 400 kHz → 20,0 W.

**Frontière DCM/CCM, en watts, sur toute la série SER2211** — le boîtier
déjà retenu au chapitre 1 :

| L | 150 kHz | 200 kHz | 250 kHz | 300 kHz | 400 kHz | 500 kHz |
|---|---|---|---|---|---|---|
| 5,3 µH | 168 | 126 | 101 | 84,0 | 63,0 | 50,4 |
| 8,2 µH | 109 | 81,5 | 65,2 | 54,3 | 40,7 | 32,6 |
| 12 µH | 74,2 | 55,7 | 44,5 | 37,1 | 27,8 | 22,3 |
| 27 µH | 33,0 | 24,7 | **19,8** | **16,5** | **12,4** | 9,9 |
| **33 µH** | 27,0 | **20,2** | **16,2** | **13,5** | **10,1** | 8,1 |
| 47 µH | **19,0** | **14,2** | **11,4** | 9,5 | 7,1 | 5,7 |

En gras, les combinaisons qui placent la frontière dans la cible 10–20 W.

### CCM sur toute la plage est hors de portée

Pour être en CCM dès 5 W, il faut $L > C/(5 f_{sw})$ :

| $f_{sw}$ | L nécessaire |
|---|---|
| 150 kHz | **178 µH** |
| 200 kHz | **134 µH** |
| 300 kHz | **89 µH** |
| 400 kHz | **67 µH** |
| 500 kHz | **53 µH** |

**La série SER2211 s'arrête à 47 µH.** Le CCM permanent — le mode
CEM-optimal — **n'est pas atteignable dans le boîtier choisi**, à aucune
fréquence utile. Il faudrait changer de boîtier, donc de contrainte de
volume.

**Conséquence : le choix n'a jamais été entre « DCM » et « CCM ». Il est
entre « frontière dans la plage » et « DCM partout ».** Cette alternative
n'était écrite nulle part, et c'est elle qui bloquait.

---

## 3. La fréquence : 200 kHz, et ce n'est pas la nostalgie du prototype

$E_{oss}\,f_{sw}$ est une perte **fixe** : indépendante de la charge. Son
poids relatif explose quand la charge baisse. Mesuré au §11.8, pour la
meilleure pièce, en passant de 200 à 800 kHz :

| charge | coût de la montée en fréquence |
|---|---|
| 50 W | **0,19 pt** |
| 8 W | **1,54 pt** — huit fois plus |

À 8 W / 800 kHz, le $C_{oss}$ pèse 55 % de la perte du SOT-223 et **88 %**
de celle de l'EPC2052.

Et le rendement mesuré décroît **monotonement** avec la fréquence, pour
les cinq pièces testées, à 40 W comme à 8 W. Il n'y a pas d'optimum
intérieur à aller chercher plus haut : **la fréquence la plus basse que les
autres contraintes autorisent est la bonne.**

> **Détail qui compte pour le dimensionnement** : le rendement culmine à
> **25 W**, pas à pleine charge. En dessous le $C_{oss}$ domine, au-dessus
> la conduction.

---

## 4. Le MOSFET : le calibre, pas la technologie

**L'écart de calibre vaut dix fois l'écart de technologie** — 2,0 points
entre la meilleure et la pire pièce, contre 0,2 point entre Si et GaN à
calibre optimal.

Classement mesuré **à 8 W / 200 kHz**, diode Schottky :

| pièce | $C_{oss}$ | rendement |
|---|---|---|
| **Si FDT86113LZ, SOT-223** | **46 pF** | **98,60** |
| GaN EPC2007C | 110 pF | 98,36 |
| Si TO-252 | 115 pF | 97,88 |
| GaN EPC2052 | 195 pF | 97,73 |
| Si BSC070N10NS5, SuperSO8 | 340 pF | 95,83 |

Le classement suit **exactement** l'ordre des $C_{oss}$. Deux pièces en
silicium occupent les deux extrêmes, et un GaN se retrouve entre deux Si.

L'avance du SOT-223 sur le meilleur GaN vaut 0,24 pt à 200 kHz, pour une
résolution de ±0,21 pt à cette charge : **favorable sans être tranché à
200 kHz**, net à 400 kHz (0,61 pt) et à 800 kHz (1,3 pt).

**Retenu : `FDT86113LZ`, onsemi, SOT-223.** Un silicium ordinaire, pour
une raison mesurée et non idéologique : à ces fréquences et à cette
charge, le $C_{oss}$ explique tout.

---

## 5. La diode : Schottky, et le calibre encore

La matrice du chapitre 4 — **44 cellules sur modèles constructeur**, pas
sur paramètres ajustés à la main :

| 47 µH, 400 kHz | 10 W | 20 W | 40 W |
|---|---|---|---|
| **V8PA22 Si 200 V** | 86 mW | 176 mW | 388 mW |
| **C3D16065D1 SiC 16 A** | 35 mW | 60 mW | 337 mW |
| C6D04065A SiC 4 A | 51 mW | 188 mW | — |
| CoolSiC G6 650 V 4 A | 195 mW | 317 mW | **809 mW** |

La Schottky silicium et le SiC de 16 A sont **à égalité** ; le SiC de 4 A
coûte **le double**. Même leçon que pour le transistor : **la surface de
puce décide, pas la technologie**. Et la Schottky bat l'ultrafast de +65 à
+81 % de perte sur toute la plage (§11.4).

**Retenu : `V8PA22` Schottky Si 200 V** — disponible, modèle constructeur
validé, et aucun gain mesurable à payer un SiC. Le `C3D16065D1` est le
remplaçant si la tenue en tension devait monter.

---

## 6. L'inductance : 33 µH, pas 47

Les deux tiennent la cible de frontière à 200 kHz. Ce qui les sépare est
une **anomalie de la table Coilcraft** : au sein de la même série,

| | $I_{sat}$ | frontière à 200 kHz | $I_{crête}$ à 50 W | $I_{sat}$ utilisé |
|---|---|---|---|---|
| SER2211-473, 47 µH | **4,4 A** | 14,2 W | 3,38 A | **77 %** |
| **SER2211-333, 33 µH** | **7,1 A** | 20,2 W | 3,71 A | **52 %** |

Le 33 µH ondule un peu plus — ~0,03 pt de conduction — pour **25 points de
marge de saturation gagnés**. À 77 % d'$I_{sat}$ en nominal, le 47 µH ne
laisse rien pour un transitoire de charge ni pour la dérive en température.

**Retenu : `SER2211-333MED`, 33 µH.** C'est la pièce du §11.8, dans le
boîtier du chapitre 1.

---

## 7. L'objection CEM, et sa réponse

Avec 33 µH à 200 kHz, la frontière tombe à 20,2 W : **la carte tourne en
DCM à son point d'emploi réel de 5–10 W**, c'est-à-dire dans le mode que
le chapitre 4 dit défavorable de 17 à 20 dB.

**Mais cette pénalité a été mesurée sur une tout autre ondulation.**

| configuration | P | mode | ondulation crête |
|---|---|---|---|
| 4,7 µH / 400 kHz — *la figure CEM* | 47 W | DCM | **6,22 A** |
| 47 µH / 400 kHz — *la figure CEM* | 47 W | CCM | 0,80 A |
| **33 µH / 200 kHz — proposé** | 8 W | DCM | **1,37 A** |
| 33 µH / 200 kHz — proposé | 50 W | CCM | 2,27 A |
| 12 µH / 200 kHz — *DCM partout* | 50 W | DCM | 5,68 A |

Le DCM proposé ondule **4,5 fois moins** que le DCM qui a produit la
pénalité. L'énergie par cycle, qui fixe l'amplitude des raies, varie en
$I^2$ : **rapport 21, soit environ 26 dB de moins avant tout filtrage.**

> **Ce chiffre est une mise à l'échelle, pas un spectre.** Il ne tient
> compte ni de la forme de l'impulsion ni du décalage du peigne de 400 à
> 200 kHz. **Une seule simulation le trancherait** : spectre conduit de la
> configuration proposée à 8 W et à 50 W, à $R_g = 10\ \Omega$. C'est le
> seul vrai trou de cet arbitrage, et il est bon marché.

Noter aussi que le **DCM partout** — la piste du §11.9 — exigerait 12 µH à
200 kHz, soit **5,68 A d'ondulation à 50 W** : quatre fois celle de la
configuration proposée. La stratégie « une seule signature à qualifier »
se paie en amplitude, précisément sur la priorité n°1.

---

## 8. Décision

| | retenu | d'où ça vient |
|---|---|---|
| **fréquence** | **200 kHz** | rendement monotone décroissant en $f$, et coût 8× pire à charge partielle, là où la carte vit (§11.4, §11.8) |
| **inductance** | **SER2211-333, 33 µH** | $I_{sat}$ 7,1 A contre 4,4 ; 52 % utilisés à 50 W ; frontière 20,2 W |
| **mode** | **DCM sous 20 W, CCM au-dessus** | le CCM permanent est hors de portée du boîtier ; le DCM partout coûte 4× l'ondulation |
| **transistor** | **onsemi FDT86113LZ, SOT-223** | $C_{oss}$ 46 pF, meilleur des cinq à 8 W ; le calibre vaut 10× la technologie |
| **diode** | **Vishay V8PA22, Schottky Si 200 V** | à égalité avec le SiC 16 A, moitié des pertes du SiC 4 A |

**Le prototype avait raison sur la fréquence.** 200 kHz sort du balayage
comme l'optimum de rendement sur toute la plage — pas par nostalgie, mais
parce que $E_{oss}f$ est une perte fixe et que la carte travaille à charge
partielle. La seule correction que l'instruction justifie est
**47 → 33 µH**, sur la marge de saturation.

### Ce qui reste à faire, et dans cet ordre

1. **Spectre conduit de la configuration retenue**, à 8 W et 50 W,
   $R_g = 10\ \Omega$. Seul trou réel. Confirme ou renverse le §7.
2. **Rendement sur modèles constructeur** aux cinq points 5 / 8 / 25 / 40 /
   50 W. Le balayage du §11 utilisait des modèles paramétrés à la main ; la
   matrice diode du chapitre 4 montre qu'un substitut peut mentir.
3. Reprendre les figures HF publiées, toutes relevées à 385 V/ns.

### Ce qui ferait changer d'avis

- **un spectre DCM à 8 W qui dépasse le gabarit** → remonter en fréquence
  pour descendre la frontière (33 µH à 400 kHz donne 10,1 W), au prix
  mesuré de ~0,5 pt à charge partielle ;
- **un besoin de CCM permanent** → changer de boîtier, 67 à 134 µH selon la
  fréquence, et rouvrir la contrainte de volume du chapitre 1 ;
- **une tenue en tension au-delà de 200 V** → `C3D16065D1` à la place de la
  `V8PA22`, sans pénalité de pertes.

---

## Reproduire

Les chiffres de frontière, d'ondulation et de courant crête de ce document
viennent d'un calcul direct, recoupé sur deux sources indépendantes du
dépôt : le tableau **mesuré** du chapitre 1 §5 et la formule du chapitre 3
§12.1, concordantes à **10,9 % près, écart systématique sur quatre
fréquences**. Les rendements sont ceux du balayage de 343 cellules du
chapitre 2 §11, et les pertes diode celles de la matrice du chapitre 4.

Prémisses courantes du banc : [`../banc.toml`](../banc.toml) — à mettre à
jour quand cette décision est actée.
