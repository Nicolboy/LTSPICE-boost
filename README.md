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
| 4 | [EMI conduite](04-emi/) | 🚧 en cours (plan posé, pas encore de mesure spectrale) |

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
