# Régulation — la montée pas à pas

Même méthode que les étapes 0 à 5 sur les composants : le plus simple
d'abord, un seul changement à la fois, et on ne passe au suivant que si
les tests sont bons.

## Ce que le plant impose, avant tout correcteur

$$\Large f_{RHP} = \frac{R(1-D)^2}{2\pi L} \qquad f_{p} = \frac{1-D}{2\pi\sqrt{LC_{out}}}$$

| | $f_{RHP}$ | croisement max ($f_{RHP}/5$) |
|---|---|---|
| 20 W | 67,7 kHz | 13,5 kHz |
| 40 W | 33,9 kHz | 6,8 kHz |
| **50 W** | **27,1 kHz** | **5,4 kHz** |

Le zéro à partie réelle positive est une **limite dure** : pour monter
$V_{out}$ il faut fermer plus longtemps, donc couper la diode — et
$V_{out}$ commence par baisser. Aucun correcteur ne le supprime.

> **À vérifier avant de s'engager.** La cible de 6,5 kHz inscrite dans
> `04-emi/banc.toml` dépasse la règle $f_{RHP}/5$ à 50 W. Ce n'est pas
> forcément rédhibitoire, mais ça se mesure.

## L'ascension

| | étape | ce qui change | ce qui la valide |
|---|---|---|---|
| **R0** | boucle ouverte | *(fait)* | l'étalon, rapport cyclique fixe |
| **R1** | **mesurer le plant** | rien au circuit | $f_{RHP}$ et $f_{p}$ mesurés = formule fermée |
| **R2** | intégrateur pur | **un** paramètre : le gain | $V_{out}$ rejoint la consigne, marge mesurée |
| **R3** | PI | + un zéro | marge de phase ≥ 45° |
| **R4** | type II | + un pôle HF | le bruit de commutation ne remonte pas dans la commande |
| **R5** | **retard numérique** | 1,5 période | c'est lui qui décide |
| **R6** | gain scheduling | DCM ↔ CCM | les deux modes avec un seul jeu |
| **R7** | quantification | ADC, résolution PWM | cycle limite, bruit de quantification |

**R1 est le cœur.** Le plant se **mesure** par injection, il ne s'écrit
pas — exactement comme l'étape 0 validait le câblage avant toute question
de fidélité. Si le banc ne rend pas les 33,9 kHz de $f_{RHP}$ à 40 W, rien
de ce qui suit n'a de sens.

**R5 n'est pas un détail de fin.** À 6,5 kHz avec 1,5 période de retard,
la phase perdue vaut **17,6°** : une marge de 60° calculée en continu n'en
laisse que **42**. Le placer tard, c'est concevoir deux fois.

| retard | phase perdue à 6,5 kHz |
|---|---|
| échantillonnage seul | 5,8° |
| + calcul (1 période) | 11,7° |
| + PWM (1,5 période) | **17,6°** |

## Un point qui joue en notre faveur

Le banc en boucle ouverte demandait **600 périodes** d'établissement, parce
qu'il dépendait de $R\!\cdot\!C$. En boucle fermée c'est la bande passante
qui gouverne : à 6,5 kHz l'établissement tient en ~25 périodes.

**Fermer la boucle rend le banc 25 fois plus rapide**, et permet enfin
d'utiliser le vrai $C_{out}$ — dont dépend tout le plant : $f_{p}$ passe de
3,91 kHz à 0,335 kHz entre 2,2 et 300 µF.

## Et ce que la boucle décidera en aval

Le condensateur d'**entrée** attend ce résultat. Un convertisseur régulé
est une charge à puissance constante : son impédance d'entrée
différentielle vaut $-V_{in}^2/P_{in}$ = **−9,76 Ω** à 40 W, et le filtre
d'entrée doit rester nettement dessous (critère de Middlebrook).

Mais **cette résistance négative n'existe que boucle fermée**. À rapport
cyclique fixe, l'impédance d'entrée est positive et le critère ne mord pas.
Dimensionner l'amortisseur avant d'avoir la boucle, ce serait amortir
contre quelque chose que le banc ne produit pas.

Pour mémoire, le dimensionnement qui en découlera :

| | mesuré / calculé |
|---|---|
| charge à absorber $\Delta Q$ | 859 nC à 8 W, **996 nC à 40 W** |
| C pour 0,1 V d'ondulation | **10 µF** |
| pic $\lvert Z_{out}\rvert$ non amorti, 10 µF + 2 µH | **10,0 Ω** — à la limite |
| $C_d$ d'amortissement | **220 µF** suffisent ($n = 22$) |
| $R_d$ optimal | **0,54 Ω** |
| pic amorti | 0,661 Ω, soit 14,8× de marge |

Le pic plafonne à $Z_0\sqrt2$ : au-delà de $n \approx 20$, ajouter de la
capacité n'apporte plus rien — les 1000 µF ne gagneraient que 3 % sur les
220 µF. Et **une ESR élevée est ici une qualité** : un polymère à très
basse ESR serait un défaut.

## Deux fautes corrigées en écrivant ce plan

**La formule du pic amorti.** Ma première version mélangeait l'expression
du $R_d$ optimal et celle du pic, ce qui faisait croire qu'augmenter $C_d$
**dégradait** le pic — l'inverse du vrai. Reprise sur la formulation
d'Erickson, ch. 10.

**La lecture du besoin en capacité d'entrée.** J'avais annoncé que le point
8 W en DCM dimensionnait, en lisant le *rapport* ondulation/moyen (0,92
contre 0,22). C'est la **charge** qui compte, et c'est le point nominal qui
gagne — de 16 %.
