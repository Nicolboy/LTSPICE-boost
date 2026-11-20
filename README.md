# LTSPICE-boost

Étude méthodique d'un étage boost (convertisseur élévateur de tension)
par simulation LTspice pilotée en Python, organisée en chapitres qui
ajoutent une dimension de réalisme à la fois — plutôt que de partir
directement sur un modèle complet "composants réels".

**Dépôt vivant, pas un dump final** : les chapitres sont publiés au fur
et à mesure, pas tous d'un coup. Les scripts génèrent le schéma LTspice
en texte brut (`.asc`), lancent la simulation en mode batch, parsent les
résultats `.meas`, et tracent les graphiques — tout est reproductible
depuis les scripts, aucun résultat n'est recopié à la main.

![Mode différentiel conduit — effet du choix d'inductance](04-emi/illustrations/cin_comparaison.png)

Spectre conduit en mode différentiel, étage 19 V → 80 V, 47 W, 400 kHz,
derrière un LISN CISPR 25 de 5 µH. Le passage de **4,7 µH en conduction
discontinue** à **47 µH en conduction continue** retire **17 à 20 dB** sur
tout le peigne d'harmoniques, sans ajouter un seul composant au filtre —
le courant d'entrée ne retombe plus à zéro à chaque cycle.

Deux choses que cette figure dit et qu'un gabarit continu masquerait :

- **le fondamental à 400 kHz ne tombe dans aucune bande.** CISPR 25 vise
  des bandes de service radio, séparées par des trous — ici 0,3 à
  0,53 MHz. Ce qui contraint, ce sont H2 à H4 en moyennes ondes ;
- **au-delà de 30 MHz le gain s'efface.** Là, ce n'est plus le mode de
  conduction qui domine mais la résonance de la maille de commutation, et
  aucun choix d'inductance d'entrée ne l'atteint.

> L'ESR et l'ESL des deux électrolytiques sont **posées, non relevées** :
> les références Panasonic exactes ne sont pas encore fixées. L'ESR du
> 220 µF commande la marge de stabilité du filtre, de −3,4 dB (polymère à
> 2 mΩ, instable sans la branche amortie) à +28,9 dB (100 mΩ). À remplacer
> dès que la référence est connue.

## Pourquoi ce dépôt

Montrer la démarche, pas seulement le résultat : hypothèses de départ
confrontées au calcul puis à la simulation, bugs trouvés et corrigés en
cours de route (voir chapitre 1 §3 — une erreur de constante de temps
qui donnait des rendements supérieurs à 100%), vérification croisée
systématique entre formule analytique et SPICE plutôt que la confiance
aveugle dans l'un ou l'autre.

## Chapitres

| # | Sujet | État |
|---|---|---|
| 1 | [Fréquence de découpage et choix d'inductance](01-frequence-inductance/) | ✅ fait |
| 2 | [Technologie switch/diode (Si vs GaN, Schottky vs ultrafast)](02-mosfet-diode/) | ✅ fait |
| 2b | [… étendu 200-800 kHz : calibre vs technologie](02-mosfet-diode/#11-extension-200-800-khz--le-calibre-avant-la-technologie) | ✅ fait |
| 3 | [Architectures (CCM/DCM) et inductance](03-architectures/) | ✅ fait |
| 4 | [EMI conduite](04-emi/) | 🚧 en cours (gabarit CISPR 25 obtenu, premiers spectres, architecture tranchée) |

## Méthode générale

- **Composants idéaux d'abord**, puis une seule dimension de réalisme
  ajoutée par chapitre (switch/diode idéaux + inductance réelle au
  chapitre 1, puis switch/diode réels au chapitre 2, etc.) — jamais un
  modèle entièrement réaliste dès le départ.
- **Vérification croisée** : chaque conclusion de simulation est
  recoupée avec une formule analytique connue (ici, le seuil CCM/DCM
  d'un boost, Erickson *Fundamentals of Power Electronics*) avant
  d'être retenue.
- **Les bugs de méthode sont documentés, pas effacés** : voir chapitre 1
  §3 pour un exemple (constante de temps de sortie bien plus longue que
  la fenêtre de simulation, donnant des rendements physiquement
  impossibles avant correction).

## Outils

LTspice (mode batch, ligne de commande), Python (génération de schéma,
pilotage des balayages, parsing des résultats, graphiques matplotlib).
Aucune dépendance Python exotique — `matplotlib` seul suffit en dehors
de la bibliothèque standard.
