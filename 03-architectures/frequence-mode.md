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

## 9. Révision du 2026-11-21 — contraintes réelles du concepteur

Trois apports qui changent la §8 : la transition est **assumée**, la
fiabilité impose de la **marge en tension**, et le stock existe.

### 9.1 Il n'y a pas une frontière, il y a une bande — facteur 3,5

$P_\text{lim} \propto V_{in}^2(1-V_{in}/V_{out})$. Sur 12–25 V, ce terme
passe de 122 à 430 : **la frontière se déplace d'un facteur 3,51**, à
inductance et fréquence fixes. Parler d'« une transition à 15 W » n'a de
sens qu'à une seule tension d'entrée.

**Bande de frontière à 200 kHz**, de $V_{in}$ = 12 V à 25 V :

| L | bande | couverture de la plage 5–50 W |
|---|---|---|
| SER2211-123 12 µH | 24,7 → 86,8 W | DCM presque partout |
| XAL1510-153 15 µH | 19,8 → 69,5 W | DCM sauf haut de plage à $V_{in}$ bas |
| **XAL1510-223 22 µH** | **13,5 → 47,4 W** | **la transition balaie toute la plage** |
| XAL1510-333 33 µH | 9,0 → 31,6 W | CCM au-dessus de 32 W à toute tension |
| SER2211-473 47 µH | 6,3 → 22,2 W | CCM dès 23 W à toute tension |

**Et les modes purs sont bien illusoires, les deux.** Le CCM permanent
demande 67 à 134 µH (§2). Le DCM permanent demande de rester sous la
frontière à **toute** tension, donc au coin bas : la 12 µH y donne 24,7 W
pour une puissance plafonnée à 25 W — **marginal de 1 %**. Ce n'est pas un
dimensionnement, c'est une coïncidence.

### 9.2 La moyenne géométrique, et pourquoi la borne basse a bougé

$\sqrt{4{,}7 \times 47} = 14{,}8\ \mu$H. Le raisonnement est juste : sur un
compromis à échelle logarithmique, le centre géométrique est le bon
premier candidat.

**Une réserve cependant** : les deux bornes n'étaient pas également
fondées. Le 4,7 µH venait du **DCM permanent**, stratégie abandonnée au
§9.1 ci-dessus. Si l'alternative réelle est « transition assumée », la
borne basse remonte à ~15 µH — celle qui garde encore un sens — et le
centre géométrique devient $\sqrt{15 \times 47} = 26{,}5\ \mu$H.

La fenêtre **22 à 33 µH** est donc celle à instruire, et elle recoupe le
haut de la fenêtre 10–22 proposée.

### 9.3 L'inductance : le XAL1510 règle la fiabilité

C'est le critère de fiabilité demandé, et l'écart est massif. Au **pire
coin, 19 V / 50 W, 200 kHz** :

| pièce | $I_{sat}$ | $I_{crête}$ | **$I_{sat}$ utilisé** | $I_{rms}$ utilisé | cuivre | surface |
|---|---|---|---|---|---|---|
| XAL1510-153 15 µH | 23,0 A | 5,13 A | **22 %** | 17 % | 85 mW | 225 mm² |
| **XAL1510-223 22 µH** | **18,7 A** | 4,36 A | **23 %** | 21 % | 120 mW | **225 mm²** |
| XAL1510-333 33 µH | 16,7 A | 3,81 A | **23 %** | 23 % | 145 mW | 225 mm² |
| SER2211-333 33 µH | 7,1 A | 3,81 A | 54 % | ? | 83 mW | 432 mm² |
| **SER2211-473 47 µH** *(stock)* | **4,4 A** | 3,48 A | **79 %** | ? | 81 mW | 432 mm² |

**La pièce en stock est la pire sur la fiabilité** : 79 % d'$I_{sat}$ en
régime nominal ne laisse rien pour un transitoire de charge ni pour la
dérive en température. Le XAL1510 descend à **22–23 %**, soit un facteur
3,4, pour **48 % de surface en moins**.

Le prix : **+37 à +64 mW de cuivre** à 50 W, soit 0,07 à 0,13 pt. Et à
5–10 W, là où la carte vit réellement, le cuivre tombe à **3 mW** : la
pénalité ne mord qu'à pleine charge, là où elle est indolore.

### 9.4 Entre 22 et 33 µH, ce qui décide

| | 22 µH | 33 µH |
|---|---|---|
| ondulation à 50 W | 3,41 A | **2,27 A** → **−3,5 dB** |
| cuivre à 50 W | **120 mW** | 145 mW *(+0,05 pt)* |
| SRF publiée | **6,3 MHz** | 5,8 MHz |
| bande de frontière | 13,5–47,4 W | **9,0–31,6 W** |
| fiche téléchargée | — | **oui** |

**Retenu : XAL1510-223, 22 µH**, dans la fenêtre proposée. L'écart de
cuivre est de 0,05 pt, négligeable ; l'écart d'ondulation de 3,5 dB est
réel mais petit devant les 17–20 dB en jeu, et la SRF est meilleure. Le
**33 µH est le repli** si le spectre à 50 W passe mal.

> **Modélisation SPICE — à dire explicitement.** Coilcraft ne publie le
> modèle fréquentiel complet du XAL1510 que jusqu'au **10 µH**. Pour les
> 15, 22 et 33 µH, seuls **L, DCR et SRF** sont publiés. On en tire un
> modèle à trois éléments, $C_{par} = 1/((2\pi f_{SRF})^2 L)$, soit
> **29,0 pF** pour le 22 µH et 22,8 pF pour le 33 µH.
>
> **Ce n'est pas une fabrication** : les trois valeurs sortent de la
> fiche. C'est la différence exacte avec le modèle de `SER2013-472`
> (§7), dont $k_1$, $k_2$ et $C$ étaient **inventés**. Le modèle à trois
> éléments ne restitue pas le comportement au-delà de la SRF — il ne doit
> pas servir à conclure sur le contenu HF au-delà de ~6 MHz.
>
> À noter : le XAL1510 porte **29 pF contre 9,1 pF** pour le SER2211 à
> inductance égale, et une SRF de 6,3 contre 9,2 MHz. C'est le revers de
> sa compacité, et c'est à surveiller sur le spectre.

### 9.5 Marge en tension : le jeu de pièces rassemblé

$V_{out}$ nominal 80 V, mais déclaré **libre de 20 à 100 V** (chapitre 3
§1). Le transistor et la diode voient $V_{out}$ **plus la surtension**.

**Diodes Schottky Vishay TMBS disponibles :**

| réf | $V_{RRM}$ | $I_{F(AV)}$ | $V_F$ à 125 °C | boîtier |
|---|---|---|---|---|
| **V8PA22** | **200 V** | 8,0 A | 0,70 V à 8 A | SMPA DO-221BC |
| V5N3202 | 200 V | 5 A | **0,58 V** à 2,5 A | DFN33A, AEC-Q101 |
| V3N22 | 200 V | 3 A | 0,61 V à 1,5 A | DFN3820A |
| V8PA15 | 150 V | 8,0 A | 0,68 V à 8 A | SMPA |
| VSSAF515 | 150 V | 5,0 A | 0,66 V à 5 A | AEC-Q101 |

**Retenu : `V8PA22`, 200 V** — **2,0× de marge** même à $V_{out}$ = 100 V,
le plus gros boîtier donc la meilleure thermique, et la matrice du
chapitre 4 l'a déjà mesurée sur modèle constructeur. Le courant moyen de
diode vaut 0,625 A à 50 W : les 8 A sont surdimensionnés *exprès*.
Le `V5N3202` est l'alternative compacte et AEC-Q101, à $V_F$ plus bas mais
thermique plus serrée.

**Transistors 150 V en DPAK disponibles :**

| réf | $V_{DS}$ | $R_{ds(on)}$ | $I_D$ |
|---|---|---|---|
| **FDD770N15A** | 150 V | 61 mΩ typ / 77 max | 18 A |
| FDD86252 | 150 V | 52 mΩ max | 27 A |
| IPD200N15N3 | 150 V | **20 mΩ** max | 50 A |

> ### ⚠ La marge en tension du transistor n'est pas acquise
>
> À $V_{out}$ = 100 V, un boîtier 150 V laisse **50 V** pour la
> surtension. La règle usuelle — $V_{ds}$ crête sous 80 % du calibre —
> donne un budget de **20 V seulement**. À $V_{out}$ = 80 V le budget
> remonte à 40 V, confortable.
>
> **Donc : soit $V_{out}$ est plafonné à 80 V et les 150 V suffisent, soit
> $V_{out}$ monte à 100 V et il faut du 200 V.** C'est une décision
> d'architecture qui remonte au partage de tension entre les deux étages,
> pas un choix de composant. **Non tranchée.**

**Et le classement de ces trois n'est pas celui du $R_{ds}$.** Le
chapitre 2 §11 a établi que **le $C_{oss}$ décide à charge partielle** :
le SuperSO8 à 7 mΩ est arrivé **dernier** des cinq à 8 W (95,83 %),
derrière un SOT-223 à 75 mΩ (98,60 %). L'`IPD200N15N3` à 20 mΩ est la
plus grosse puce des trois, donc *a priori* la pire à 5–10 W.

**À faire avant de trancher** : extraire $C_{oss}(V)$, $E_{oss}$ et $Q_g$
des trois fiches — le dépôt a l'outil,
`.claude/skills/sim-spice/scripts/extraction_composant.py`, et le
chapitre 2 §11.2 la méthode. **Je ne classe pas ces trois sans ces
chiffres** : c'est exactement la faute qui a fait retenir une pièce
thermiquement intenable au chapitre 3 §3.

### 9.6 État des cinq choix après révision

| | retenu | confiance |
|---|---|---|
| fréquence | **200 kHz** | **mesuré** — 343 cellules, optimum sur toute la plage |
| mode | **transition assumée**, bande 13,5–47,4 W selon $V_{in}$ | **acquis** — les deux modes purs sont hors de portée |
| inductance | **XAL1510-223 22 µH** | **fiche** — $I_{sat}$ à 23 %, modèle 3 éléments seulement |
| diode | **V8PA22 200 V** | **mesuré** — matrice chapitre 4, 2,0× de marge |
| transistor | **parmi les trois 150 V** | **non tranché** — $C_{oss}$ à extraire |

**Deux décisions d'architecture restent à toi** :

1. **$V_{out}$ plafonné à 80 V, ou libre jusqu'à 100 V ?** Il en découle
   150 V ou 200 V sur le transistor.
2. **Le 22 µH ou le 33 µH ?** 3,5 dB d'ondulation contre 0,05 pt de
   rendement — un spectre conduit le tranche.

---

## 10. Les zéros, et les deux plants de régulation

C'est la contrainte que le concepteur a retrouvée, et elle décide la
valeur d'inductance autant que les pertes.

### 10.1 Deux plants, pas un plant qui se déforme

En **CCM**, le boost présente au régulateur :

$$\Large G_{vd}(s)=\frac{V_{out}}{D'}\cdot
\frac{1-s/\omega_z}{1+s/(Q\omega_0)+s^2/\omega_0^2}
\qquad \omega_z=\frac{D'^2R}{L},\quad \omega_0=\frac{D'}{\sqrt{LC}}$$

Un **second ordre**, et surtout un **zéro dans le demi-plan droit**.
Physiquement : pour délivrer plus de courant de sortie, il faut d'abord
allonger le temps de conduction, donc *fermer* la diode plus longtemps —
la sortie **baisse avant de monter**. Aucune compensation ne corrige ça ;
on ne peut que croiser bien en dessous.

En **DCM**, le courant repart de zéro à chaque cycle : l'inductance cesse
d'être une variable d'état. L'ordre **tombe à un**, et le zéro à droite
remonte d'environ une décade. Le plant devient docile.

**Ce ne sont pas deux points d'un même plant.** Ce sont deux fonctions de
transfert d'ordres différents, et le passage de l'une à l'autre est
**discontinu**. Un compensateur fixe voit deux objets ; au voisinage du
seuil, le gain de boucle effectif saute d'un cycle à l'autre et la boucle
**chasse** — un cycle limite qui alterne entre les deux modes.

### 10.2 Où tombe ce cycle limite — et la correction

Un cycle limite de ce type se place **dans la bande de la boucle**, soit
$f_{sw}/10$ à $f_{sw}/20$, et ses sous-harmoniques en dessous. À 200 kHz
cela donne **10 à 20 kHz, puis plus bas**.

> **Correction** : la bande audible est **sous 20 kHz**, pas 20–100 kHz.
> Le cycle limite y tombe donc **en plein**, et l'inductance chante. C'est
> plus gênant que ce que la mémoire du concepteur en gardait, pas moins.

### 10.3 Le zéro à droite, chiffré sur l'enveloppe réelle

$f_z = D'^2R/(2\pi L)$ avec $D' = V_{in}/V_{out}$ et $R = V_{out}^2/P$ —
donc $f_z$ **descend quand la charge monte** et quand $V_{in}$ baisse.
À 22 µH :

| $V_{in}$ | P | mode | $f_z$ | crossover max ($f_z/3$) |
|---|---|---|---|---|
| **12 V** | **25 W** | CCM | **41,7 kHz** | **13,9 kHz** ← le pire |
| 19 V | 50 W | CCM | 52,2 kHz | 17,4 kHz |
| 20 V | 50 W | CCM | 57,9 kHz | 19,3 kHz |
| 25 V | 50 W | CCM | 90,4 kHz | 30,1 kHz |
| 20 V | 8 W | **DCM** | 361,7 kHz | 120,6 kHz |

**Le pire cas est le coin bas en pleine charge, pas le point nominal** —
41,7 kHz à 12 V / 25 W. Et en DCM au point d'emploi, le zéro est à
361,7 kHz, **au-delà de la fréquence de découpage** : il ne contraint
rien.

**Conclusion de dimensionnement : croiser sous ~14 kHz**, ce qui tient
dans les deux modes sans rien commuter. Une alimentation de filament n'a
aucun besoin d'une réponse transitoire plus rapide.

### 10.4 Et il manque une pièce : $C_{out}$ n'est pas choisi

$f_0 = D'/(2\pi\sqrt{LC})$ — **le double pôle dépend de la capacité de
sortie, qui n'est pas arrêtée**. Le chapitre 1 l'a ramenée à 2,2 µF pour
la simulation et a explicitement différé la vraie valeur.

| $C_{out}$ | $f_0$ à 12 V | à 20 V | à 25 V |
|---|---|---|---|
| 10 µF | 1,61 kHz | 2,68 kHz | 3,35 kHz |
| **47 µF** | **0,74 kHz** | **1,24 kHz** | 1,55 kHz |
| 100 µF | 0,51 kHz | 0,85 kHz | 1,06 kHz |

Il faut $f_0 \ll f_c \ll f_z$. Avec $f_c \approx 14$ kHz, **47 µF suffit**
— une décade de marge sous le crossover. **À trancher**, et c'est le seul
chaînon manquant du plant.

### 10.5 Ce qui en découle pour l'inductance

Si la traversée est le point sensible, il faut **éloigner la frontière de
la zone d'emploi**. À 200 kHz, fourchette privilégiée 5–10 W :

| $V_{in}$ | 22 µH | 33 µH |
|---|---|---|
| 12 V | 13,5 W | **9,0 W ← dans la zone** |
| 16 V | 22,6 W | 15,0 W |
| 20 V | 33,1 W | 22,0 W |

**C'est l'argument qui tranche entre les deux**, et il va dans le sens de
la fenêtre 10–22 µH proposée par le concepteur : avec 33 µH la frontière
tombe à 9,0 W au coin bas, en plein dans la fourchette privilégiée. Avec
22 µH elle reste au-dessus à toute tension d'entrée.

> **Deux surfaces interactives**, qui ne disent pas la même chose :
>
> **[`zeros-3d.html`](zeros-3d.html)** — le plant lui-même. Axes
> $X = V_{in}$, $Y = P_{out}$, $Z$ au choix : zéro à droite, plafond de
> crossover, double pôle, $Q$ effectif. 882 points, $L$ et $C_{out}$
> sélectionnables. Les mailles **en DCM sont en orange** (la formule CCM y
> est une borne inférieure), celles dont le plafond tombe **sous 14 kHz**
> sont cerclées de rouge.
>
> **Et le résultat y est net** : $f_z = V_{in}^2/(2\pi L P)$ étant en
> $1/L$, **plus l'inductance est petite, plus le zéro est haut** —
> c'est-à-dire plus la boucle est facile :
>
> | L | $f_z$ minimum | mailles sous 14 kHz |
> |---|---|---|
> | 15 µH | 30,6 kHz | 3 / 49 |
> | **22 µH** | **20,8 kHz** | **6 / 49** |
> | 33 µH | 13,9 kHz | 13 / 49 |
> | 47 µH | **9,8 kHz** | **19 / 49** |
>
> **Deuxième argument indépendant** pour la fenêtre 10–22 µH, après celui
> du §10.5 : le 47 µH en stock dégrade le plant autant qu'il éloigne la
> frontière. À 22 µH il reste 6 mailles contraignantes, toutes au coin bas
> en pleine charge.
>
> **[`frontiere-3d.html`](frontiere-3d.html)** —
> $P_{lim}(V_{in}, L)$ à $V_{out}$ = 80 V, quatre fréquences, mailles
> à éviter cerclées de rouge. 168 points, analytiques, recoupés sur le
> tableau **mesuré** du chapitre 1 §5.
>
> Le décompte des mailles à risque y est parlant : **1 sur 42 à 150 kHz,
> 3 à 200 kHz, 6 à 300 kHz, 10 à 400 kHz.** Monter en fréquence ne coûte
> pas seulement du rendement à charge partielle — ça rapproche
> mécaniquement la frontière de la zone d'emploi.

### 10.6 Ce qui reste à vérifier

Les formes ci-dessus sont les modèles canoniques du boost (Erickson,
ch. 7 et 11) ; **les valeurs de $f_z$ sont calculées, pas mesurées**. À
confirmer par une réponse en fréquence du plant dans les deux modes, de
part et d'autre de la frontière, pour chiffrer l'écart réel et valider le
crossover de 14 kHz. C'est le travail qui manque, et il ne demande pas de
campagne : deux balayages AC.

---

## 11. Le transistor — relevé sur fiche, et le calibre décide

FOM $= E_{oss}\!\cdot\!R_{ds}$, la constante de technologie.
$E_{oss} = \tfrac12 C_{oss(er)}V^2$.

| pièce | $R_{ds}$ typ | $C_{oss}$(75 V) | $C_{oss(er)}$ | $E_{oss}$(80 V) | $Q_g$ | **FOM** |
|---|---|---|---|---|---|---|
| **FDD770N15A** | 61 mΩ | 64 pF | **113 pF** *(publié)* | 342 nJ | 8,4 nC | 20,9 |
| FDD86252 | 41 mΩ | 78 pF | 138 pF *(dérivé)* | 417 nJ | 11,3 nC | 17,1 |
| IPD200N15N3 | **16 mΩ** | **214 pF** | 378 pF *(dérivé)* | **1143 nJ** | 23 nC | 18,3 |
| *FDT86113LZ (ch. 2, SOT-223)* | *75 mΩ* | — | — | *176 nJ* | — | ***13,2*** |

> **Provenance.** Seul le `FDD770N15A` publie $C_{oss(er)}$. Comme il
> publie **aussi** $C_{oss}$ au même point, leur rapport **1,77** donne
> l'exposant réel de la famille, $C_{oss}\propto V^{-0{,}87}$ — et non le
> $V^{-0,5}$ qu'on suppose souvent. Ce rapport mesuré est appliqué aux
> deux autres, **et c'est marqué *dérivé***. Un $C_{oss(er)}$ constructeur
> ou l'intégration de la courbe le remplacerait ; l'ordre de grandeur ne
> bougera pas.

**Les trois FOM sont dans un mouchoir — 17 à 21 nJ·Ω.** Même génération
technologique. **Donc tout se joue sur la taille de puce**, et
$R^{*}=\sqrt{\mathrm{FOM}\cdot f_{sw}}/I_{rms}$ la donne :

| P | $I_{rms}$ | FDD770N15A | FDD86252 | IPD200N15N3 |
|---|---|---|---|---|
| **5 W** | 0,48 A | **0,5×** | 0,3× | **0,1×** |
| **8 W** | 0,68 A | **0,6×** | 0,5× | **0,2×** |
| 10 W | 0,80 A | **0,8×** | 0,6× | 0,2× |
| 25 W | 1,60 A | 1,5× | **1,1×** | 0,4× |
| 50 W | 2,76 A | 2,6× | 1,9× | **0,7×** |

*(rapport $R_{ds}$ réel / $R^{*}$ optimal ; 1,0 = juste, < 1 = puce trop
grosse, le $C_{oss}$ domine)*

**Sur la fourchette privilégiée 5–10 W, l'`IPD200N15N3` est 5 à 10 fois
trop grosse.** C'est exactement le piège du SuperSO8 à 7 mΩ, arrivé
**dernier des cinq** à 8 W au chapitre 2.

### 11.1 Révision — le `BSC900N20NS3 G` l'emporte, et le `FDT86113LZ` est écarté

**Le `FDT86113LZ` du chapitre 2 est disqualifié, pour deux raisons
indépendantes relevées sur sa fiche :**

1. **100 V, pas 150.** Sur un rail à 80 V, 80 % de 100 V font **exactement
   80 V** : budget de surtension **nul**.
2. **$I_D$ = 3,3 A** en continu, contre **4,28 A** de crête à 50 W avec
   22 µH.

> Cela remonte au chapitre 2 : **sa pièce gagnante était un 100 V simulé
> sur une sortie à 80 V**, et sa FOM flatteuse vient en partie de là — une
> pièce basse tension a intrinsèquement une meilleure FOM. À reprendre dans
> ce chapitre.

**Le `BSC900N20NS3 G` publie $C_{oss}$ ET $Q_{oss}$ au même point** — 52 pF
et 20 nC à 100 V — donc l'exposant se **déduit** au lieu d'être supposé :
$Q/(C\cdot V) = 3{,}85 \Rightarrow C_{oss}\propto V^{-0{,}74}$, d'où
$E_{oss}(80\ \mathrm{V})$ = **312 nJ**. Aucune valeur dérivée d'une autre famille.

| pièce | $V_{DS}$ | $R_{ds}$ | $E_{oss}$(80 V) | FOM | marge | boîtier |
|---|---|---|---|---|---|---|
| **BSC900N20NS3 G** | **200 V** | 77 mΩ | **312 nJ** | 24,0 | **2,5×** | SuperSO8 5×6 |
| FDD770N15A | 150 V | 61 mΩ | 342 nJ | 20,9 | 1,9× | DPAK |
| FDD86252 | 150 V | 41 mΩ | 417 nJ | 17,1 | 1,9× | DPAK |
| IPD200N15N3 | 150 V | 16 mΩ | 1143 nJ | 18,3 | 1,9× | DPAK |
| ~~FDT86113LZ~~ | ~~100 V~~ | ~~100 mΩ~~ | ~~176 nJ~~ | ~~17,6~~ | **1,2×** | **écarté** |

La FOM du 200 V est bien un peu moins bonne — **24,0 contre 20,9**, soit
le prix de l'épitaxie plus épaisse. **Mais ce n'est pas la FOM qui décide,
c'est le calibre**, et le bilan au point d'emploi les départage :

| pièce | conduction | $C_{oss}$ | grille | **total à 8 W** | total à 50 W |
|---|---|---|---|---|---|
| **BSC900N20NS3 G** | 14,2 mW | 62,3 mW | 18,0 mW | **94,5 mW** | 784 mW |
| FDD770N15A | 11,2 mW | 68,4 mW | 16,8 mW | **96,4 mW** | 642 mW |
| FDD86252 | 7,6 mW | 83,4 mW | 22,6 mW | 113,6 mW | 480 mW |
| IPD200N15N3 | 3,0 mW | 228,6 mW | 46,0 mW | **277,6 mW** | 421 mW |

**À 8 W les deux premiers sont à égalité** — 94,5 contre 96,4 mW, soit
2 %, sous la résolution. Le `BSC900N20NS3` gagne donc **2,5× de marge en
tension pour rien**, dans un boîtier plus petit. Il coûte 142 mW de plus à
50 W (0,28 pt), hors de la fourchette privilégiée.

Et l'`IPD200N15N3` confirme la règle : **trois fois la perte à 8 W**, dont
229 mW de seul $C_{oss}$. La plus grosse puce est la pire là où la carte
travaille.

**Retenu : `BSC900N20NS3 G`**, Infineon OptiMOS 3, 200 V, SuperSO8 5×6.
Modèle PSpice disponible
(`infineon-powermosfet-optimos-pspice-200v-n-channel-simulationmodels-en`).

---

## 12. Surtension drain mesurée — le 150 V passe

Campagne du 2026-11-21, double-pulse à **2,6 A coupés exactement**, quatre
modèles constructeur, $L_{pcb}$ balayée de 1 à 40 nH, $R_g$ = 10 Ω.
21 cas sur 24.

**$V_{ds}$ crête (V)**, budget = $V_{DS}	imes0{,}8 - 80$ :

| pièce | boîtier | calibre | 1 nH | 5 nH | 10 nH | 20 nH | 40 nH |
|---|---|---|---|---|---|---|---|
| **IPD530N15N3** | DPAK | **150 V** | 81 | 83 | 85 | 86 | **92** |
| IPD320N20N3 | DPAK | 200 V | 81 | — | 86 | — | — |
| BSC900N20NS3 | SuperSO8 | 200 V | 82 | 82 | 86 | 85 | **91** |
| FDD770N15A | DPAK | 150 V | 82 | 84 | **102** | **124** | **146** |

**Les trois pièces Infineon restent sous 92 V à 40 nH de routage**, pour un
plafond de 120 V sur un 150 V. **Le 150 V passe, avec de la marge, pour
tout routage réaliste** — la question de la tenue en tension du transistor
est donc close, et dans le sens favorable.

### 12.1 Pourquoi la loi de la diode ne s'y applique pas

Le chapitre 4 vérifie $\Delta V = L_\sigma\,di/dt$ **à 0,4 % près** sur la
diode. Sur le drain, le même contrôle donne **+9 % à +160 %** : la loi ne
se referme pas, et c'est physique.

| | diode | drain |
|---|---|---|
| événement | recouvrement, coupure **abrupte** et imposée | coupure **progressive** par le canal |
| ce qui la limite | rien, sinon $L_\sigma$ | le $C_{oss}$ absorbe, et $L_s$ **contre-réagit sur la grille** |

L'inductance de source est dans la boucle de grille : plus le courant
chute vite, plus elle s'oppose à la commande. **La coupure est
auto-limitée**, ce qu'une loi linéaire ne décrit pas.

> **Conséquence de méthode** : on ne transporte pas une loi d'un
> composant à l'autre, même quand la forme algébrique semble la même.
> C'était l'hypothèse de départ de cette campagne, et elle est fausse.

### 12.2 Une réserve que je ne masque pas

À 40 nH, le `FDD770N15A` monte à **146 V** là où les trois Infineon sont à
91-92 V. Deux modélisations de pièces comparables divergent de **54 V**.

Son $di/dt$ mesuré atteint **2,39 A/ns** contre 0,4 à 0,7 pour les
Infineon. Soit la pièce commute réellement bien plus vite, soit les deux
familles de modèles ne décrivent pas la coupure de la même façon — les
modèles Infineon portent un réseau thermique et parasite détaillé, celui
d'onsemi est plus simple.

**Je ne tranche pas**, et je ne retiens donc pas le `FDD770N15A` : à
calibre et boîtier équivalents, l'`IPD530N15N3` est modélisé dans la même
famille que les deux 200 V, ce qui rend la comparaison interne cohérente.
C'est la faute C4 — ne pas généraliser d'une famille de modèles à l'autre.

### 12.3 Spécification de routage

Puisque le 150 V passe à 40 nH, **l'inductance de maille n'est plus une
contrainte de tenue en tension**. Elle le reste pour la diode (80 V de
budget, loi vérifiée du chapitre 4 → $L_\sigma < 25$ nH) et pour le
contenu HF du spectre conduit.

**Retenu : `IPD530N15N3`**, Infineon OptiMOS 3, 150 V, 53 mΩ, DPAK — le
boîtier demandé pour les prototypes, un modèle constructeur disponible, et
92 V crête pour 120 V de plafond.

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
