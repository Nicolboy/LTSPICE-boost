"""Extraction de l'inductance de maille de commutation depuis un .kicad_pcb.

AUCUN EXPORT N'EST NECESSAIRE : le .kicad_pcb contient deja toute la
geometrie (segments avec depart/arrivee/largeur/couche, vias, pastilles,
zones) et, quand il est renseigne, l'empilage avec les epaisseurs
dielectriques. C'est le fichier source qu'on lit, pas un derive.

METHODE -- somme d'inductances partielles (PEEC allege) :

  L_boucle = somme(L_self,i) - 2 * somme(M_ij entre aller et retour)

  L_self d'un ruban plat de longueur l, largeur w, epaisseur t
  (Rosa / Grover, forme classique) :
      L = (mu0 l / 2pi) [ ln(2l/(w+t)) + 0.5 + 0.2235 (w+t)/l ]

  M entre deux filaments paralleles de meme longueur l, distants de d :
      M = (mu0 l / 2pi) [ ln(l/d + sqrt(1+(l/d)^2)) - sqrt(1+(d/l)^2) + d/l ]

Le terme mutuel est ce qui decide : deux conducteurs antiparalleles
colles s'annulent a 70-90 %, eloignes ils ne s'annulent pas du tout.
C'est pourquoi l'empilage et la proximite du retour comptent bien plus
que la longueur.

PRECISION ANNONCEE : +/- 30 %. Les formules sont exactes pour des
filaments droits, mais (a) les paires non paralleles sont traitees par
projection en cos(theta), (b) l'inductance des BOITIERS n'est pas dans
le PCB et vient des datasheets, (c) l'effet de peau redistribue le
courant a 100 MHz. Pour mieux, il faut un solveur de champs (FastHenry)
nourri par cette meme geometrie.

CE QUE L'OUTIL REFUSE DE FAIRE : inventer un chemin de retour. Si le
retour n'est pas route, il le signale et donne un encadrement sous
hypotheses explicites, plutot qu'un chiffre unique qui aurait l'air
mesure.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

MU0_2PI = 2.0e-7          # mu0 / 2pi, en H/m
EP_CUIVRE = 35e-6         # m, 1 oz par defaut si l'empilage ne dit rien


@dataclass
class Segment:
    x1: float; y1: float; x2: float; y2: float      # mm
    w: float                                         # mm
    couche: str
    net: str

    @property
    def longueur(self) -> float:
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)

    @property
    def milieu(self) -> tuple[float, float]:
        return (self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2

    @property
    def direction(self) -> tuple[float, float]:
        L = self.longueur
        return ((self.x2 - self.x1) / L, (self.y2 - self.y1) / L) if L else (0.0, 0.0)


def lit_pcb(chemin: Path) -> tuple[list[Segment], dict]:
    """Segments routes et metadonnees (empilage, epaisseur, zones)."""
    s = chemin.read_text(encoding="utf-8", errors="replace")
    plat = re.sub(r"\n\t+", " ", s)
    segs = [Segment(float(a), float(b), float(c), float(d), float(w), lay, n)
            for a, b, c, d, w, lay, n in re.findall(
                r'\(segment \(start ([\d.-]+) ([\d.-]+)\) \(end ([\d.-]+) ([\d.-]+)\)'
                r' \(width ([\d.]+)\) \(layer "([^"]+)"\) \(net "([^"]*)"\)', plat)]
    ep = re.search(r"\(general\s*\(thickness ([\d.]+)\)", plat)
    meta = dict(
        epaisseur=float(ep.group(1)) if ep else 1.6,
        n_zones=len(re.findall(r"\(zone", plat)),
        empilage=bool(re.search(r"\(stackup", plat)),
        couches=sorted({g.couche for g in segs}),
    )
    return segs, meta


def l_self(longueur_mm: float, largeur_mm: float,
           ep_m: float = EP_CUIVRE) -> float:
    """Inductance partielle propre d'un ruban droit, en H."""
    l = longueur_mm * 1e-3
    wt = largeur_mm * 1e-3 + ep_m
    if l <= 0:
        return 0.0
    return MU0_2PI * l * (math.log(2 * l / wt) + 0.5 + 0.2235 * wt / l)


def m_parallele(longueur_mm: float, distance_mm: float) -> float:
    """Mutuelle entre deux filaments paralleles de meme longueur, en H."""
    l, d = longueur_mm * 1e-3, max(distance_mm * 1e-3, 1e-6)
    r = l / d
    return MU0_2PI * l * (math.log(r + math.sqrt(1 + r * r))
                          - math.sqrt(1 + 1 / (r * r)) + 1 / r)


def l_sur_plan(longueur_mm: float, largeur_mm: float, h_mm: float) -> float:
    """Inductance d'une piste au-dessus d'un plan de retour, en H.

    L' = mu0 h / w_eff, avec w_eff = w + h en correction grossiere de
    franges. Vaut tant que w est du meme ordre que h ou plus grand.
    """
    return 4e-7 * math.pi * (h_mm / (largeur_mm + h_mm)) * longueur_mm * 1e-3


def partielles(segs: list[Segment], nets: tuple[str, ...],
               zone: tuple[float, float, float, float] | None = None) -> dict:
    """Somme des inductances propres des segments retenus, par net."""
    out = {}
    for net in nets:
        pris = [g for g in segs if g.net == net]
        if zone:
            x0, x1, y0, y1 = zone
            pris = [g for g in pris
                    if x0 < g.milieu[0] < x1 and y0 < g.milieu[1] < y1]
        out[net] = dict(
            n=len(pris),
            longueur=sum(g.longueur for g in pris),
            l_nh=sum(l_self(g.longueur, g.w) for g in pris) * 1e9,
            largeurs=sorted({g.w for g in pris}),
            couches=sorted({g.couche for g in pris}),
        )
    return out


# ---------------------------------------------------------------- graphe
def graphe(segs: list[Segment], net: str, tol: float = 0.08):
    """Connectivite des segments d'un net. Noeuds = extremites fusionnees."""
    import collections
    noeuds: list[tuple[float, float, str]] = []

    def cle(x, y, couche):
        for i, (nx, ny, nc) in enumerate(noeuds):
            if nc == couche and math.hypot(nx - x, ny - y) <= tol:
                return i
        noeuds.append((x, y, couche))
        return len(noeuds) - 1

    adj = collections.defaultdict(list)
    for g in segs:
        if g.net != net:
            continue
        a = cle(g.x1, g.y1, g.couche)
        b = cle(g.x2, g.y2, g.couche)
        adj[a].append((b, g.longueur, g))
        adj[b].append((a, g.longueur, g))
    return noeuds, adj


def relie_vias(noeuds, adj, vias, net, tol: float = 0.3):
    """Un via relie les noeuds de meme position sur des couches differentes."""
    for vx, vy, vnet in vias:
        if vnet != net:
            continue
        proches = [i for i, (nx, ny, _) in enumerate(noeuds)
                   if math.hypot(nx - vx, ny - vy) <= tol]
        for i in proches:
            for j in proches:
                if i < j and noeuds[i][2] != noeuds[j][2]:
                    adj[i].append((j, 0.0, None))
                    adj[j].append((i, 0.0, None))


def chemin(noeuds, adj, depart: tuple[float, float],
           arrivee: tuple[float, float]):
    """Dijkstra entre les noeuds les plus proches de deux points."""
    import heapq
    if not noeuds:
        return None, float("inf")
    d0 = min(range(len(noeuds)),
             key=lambda i: math.hypot(noeuds[i][0] - depart[0], noeuds[i][1] - depart[1]))
    a0 = min(range(len(noeuds)),
             key=lambda i: math.hypot(noeuds[i][0] - arrivee[0], noeuds[i][1] - arrivee[1]))
    dist = {d0: 0.0}
    prec: dict[int, tuple[int, Segment | None]] = {}
    tas = [(0.0, d0)]
    vus = set()
    while tas:
        d, u = heapq.heappop(tas)
        if u in vus:
            continue
        vus.add(u)
        if u == a0:
            break
        for v, w, g in adj[u]:
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prec[v] = (u, g)
                heapq.heappush(tas, (nd, v))
    if a0 not in dist:
        return None, float("inf")
    route, u = [], a0
    while u != d0:
        p, g = prec[u]
        if g is not None:
            route.append(g)
        u = p
    return list(reversed(route)), dist[a0]


def inductance_boucle(aller: list[Segment], retour: list[Segment],
                      h_mm: float = 1.5) -> dict:
    """L = somme(L_propres) - 2 somme(M aller-retour).

    Les paires non paralleles sont ponderees par |cos(theta)| : une
    mutuelle ne couple que les composantes colineaires des courants.
    """
    propres = sum(l_self(g.longueur, g.w) for g in aller + retour)
    mut = 0.0
    for a in aller:
        for r in retour:
            ax, ay = a.direction
            rx, ry = r.direction
            cos = abs(ax * rx + ay * ry)
            if cos < 1e-3:
                continue
            (mx, my), (nx, ny) = a.milieu, r.milieu
            # la separation VERTICALE compte : sans elle, deux segments
            # superposes F.Cu/B.Cu ressortent a distance ~0, donc avec une
            # mutuelle enorme qui annule trop et sous-estime la boucle.
            dz = 0.0 if a.couche == r.couche else h_mm
            d = math.hypot(math.hypot(mx - nx, my - ny), dz)
            if d < 1e-6:
                continue
            lc = math.sqrt(a.longueur * r.longueur)     # longueur commune
            mut += m_parallele(lc, d) * cos
    return dict(propres_nh=propres * 1e9, mutuelles_nh=mut * 1e9,
                boucle_nh=max(propres - 2 * mut, 0.0) * 1e9,
                lg_aller=sum(g.longueur for g in aller),
                lg_retour=sum(g.longueur for g in retour))


def lit_vias(chemin_pcb: Path):
    plat = re.sub(r"\n\t+", " ", chemin_pcb.read_text(encoding="utf-8", errors="replace"))
    return [(float(x), float(y), n) for x, y, n in re.findall(
        r'\(via \(at ([\d.-]+) ([\d.-]+)\).*?\(net "([^"]*)"\)', plat)]
