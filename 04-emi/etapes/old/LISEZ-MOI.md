# Courbes antérieures à la maille de routage

Ces figures ont été relevées **sans inductance de maille** : la diode était
branchée à même le drain du transistor.

**Elles portent toutes le même artefact.** À la fermeture du MOSFET, la
charge de `Cosn` et de la capacité de jonction de la diode était
court-circuitée à travers `Ron` = 53 mΩ, sans rien pour borner le `di/dt`.
Le courant crête n'était donc limité que par le **pas d'intégration** —
7,19 A relevés pour 0,27 nC seulement, une valeur qui dépend du pas choisi
et non de la physique.

Avec 10 nH de maille, la même pointe tombe à **0,88 A** : facteur 8.

Conservées pour l'historique du raisonnement, **à ne pas citer comme
résultats**. Les figures valides sont dans le dossier parent.
