"""Banc d'impedance pour composants passifs -- controler, exporter, ameliorer.

RAISON D'ETRE. Un modele SPICE fabrique a la main est entre dans un tableau
de choix de composant, et la "resonance propre de 27,1 MHz" qu'il portait a
servi d'argument. Rien, dans le fichier ni dans son emplacement, ne le
distinguait d'un modele constructeur. Ce module existe pour que cela ne
puisse plus arriver sans etre vu.

TOPOLOGIE. Wurth et Coilcraft convergent sur le meme schema a quatre
elements, releve sur 5 071 modeles de leurs bibliotheques :

        Rp                     Rp  pertes fer -- PORTE TOUT L'AMORTISSEMENT
    .---www---.                Cp  capacite propre -> resonance propre
    |         |                Rs  DCR
  --+---||----+--              L   inductance nominale
    |   Cp    |
    '-www-UUU-'
      Rs   L

Coilcraft raffine en ajoutant une resistance en SERIE avec Cp, ce qui etend
la validite au-dela de la resonance propre. Les deux variantes sont ici.

SYNTHESE EN FORME FERMEE. Les quatre parametres se deduisent de quatre
grandeurs de catalogue, sans ajustement :

    Rs = DCR          Cp = 1 / (L (2 pi f_SRF)^2)          Rp = |Z| crete

Verifie contre le modele constructeur SER1360-472 : ecart median 0,00 dB,
maximum 1,47 dB de 10 kHz a 100 MHz, le maximum etant AU-DESSUS de la
resonance propre, la ou le quatrieme element manque.

CE QUE LE DATASHEET NE DONNE PAS. Un datasheet d'inductance de puissance
publie L, DCR et la resonance propre -- mais PAS l'impedance de crete. Le
parametre qui gouverne l'amortissement n'y est donc pas. Un modele construit
sur le seul datasheet decrit correctement |Z| sous la resonance et ne dit
RIEN du facteur de qualite. C'est a dire, pas a masquer.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
LIB_COMMUN = RACINE / "lib_spice_commun"
Z0_SMITH = 50.0                      # normalisation de l'abaque de Smith


# ----------------------------------------------------------- modele direct

def z_localise(f, L, Rs, Cp, Rp, Rc=0.0):
    """Impedance complexe du modele a elements localises, en forme fermee.

    `Rc` : resistance en SERIE avec Cp (raffinement Coilcraft). A zero, on
    retrouve la topologie a quatre elements commune aux deux fournisseurs.

        Y = 1/Rp + 1/(Rc + 1/(j w Cp)) + 1/(Rs + j w L)
    """
    w = 2.0 * np.pi * np.asarray(f, dtype=float)
    y = 1.0 / Rp + 1.0 / (Rs + 1j * w * L)
    y = y + 1.0 / (Rc + 1.0 / (1j * w * Cp))
    return 1.0 / y


def synthese(L, dcr, srf, z_crete):
    """Quatre grandeurs de catalogue -> quatre parametres. Aucun ajustement."""
    return dict(L=float(L), Rs=float(dcr),
                Cp=1.0 / (L * (2.0 * math.pi * srf) ** 2),
                Rp=float(z_crete), Rc=0.0)


def z_depuis_spice(definitions, ligne_instance, fmin=1e3, fmax=3e8,
                   pts_par_decade=400, nom="z"):
    """Balayage `.ac` d'un sous-circuit : 1 A injecte, donc V = Z."""
    import sys
    sys.path.insert(0, str(RACINE / ".claude/skills/sim-spice/scripts"))
    from ltspice_run import lance
    from spicelib.raw.raw_read import RawRead

    trav = ICI / "results" / "impedance"
    trav.mkdir(parents=True, exist_ok=True)
    cir = trav / f"{nom}.cir"
    cir.write_text(f"""* impedance -- {nom}
I1   0    n1   AC 1
{ligne_instance}
{definitions}
.options plotwinsize=0
.ac dec {pts_par_decade} {fmin:.6e} {fmax:.6e}
.save V(n1)
.end
""", encoding="ascii")
    r = lance(cir)
    if not r["ok"]:
        raise RuntimeError(f"{nom} : {r['diagnostic']}")
    rr = RawRead(str(r["raw"]))
    ax = rr.get_trace(rr.get_trace_names()[0]).get_wave()
    f = np.abs(np.asarray(ax, dtype=float)) if not np.iscomplexobj(ax) \
        else np.abs(np.asarray(ax).real)
    return f, np.asarray(rr.get_trace("V(n1)").get_wave())


def subckt_vendor(fichier, nom):
    """Extrait un bloc `.subckt ... .ends` VERBATIM d'un fichier fournisseur."""
    txt = Path(fichier).read_bytes().decode("utf-8", "replace")
    m = re.search(rf"^\.subckt\s+{re.escape(nom)}\b.*?^\.ends.*?$",
                  txt, re.S | re.M | re.I)
    if not m:
        raise LookupError(f"{nom} absent de {Path(fichier).name}")
    return m.group(0).strip()


# -------------------------------------------------------------- grandeurs

def mesures(f, z):
    """Grandeurs caracteristiques tirees d'une courbe d'impedance."""
    f = np.asarray(f, dtype=float)
    mod, re_z, im_z = np.abs(z), np.real(z), np.imag(z)
    i = int(np.argmax(mod))
    # resonance propre : passage de X par zero, plus precis que le sommet de
    # |Z| quand le balayage est grossier. On garde les deux.
    signe = np.sign(im_z)
    croise = np.where(np.diff(signe) < 0)[0]
    srf_x = float(np.interp(0.0, [im_z[croise[-1] + 1], im_z[croise[-1]]],
                            [f[croise[-1] + 1], f[croise[-1]]])) \
        if len(croise) else float("nan")
    bf = f < 0.05 * f[i]                       # loin sous la resonance
    l_bf = float(np.median(im_z[bf] / (2 * np.pi * f[bf]))) if bf.any() \
        else float("nan")
    # La DCR se lit au PLUS BAS point du balayage, pas en mediane : Re(Z)
    # croit avec la frequence parce que Rp charge la branche inductive --
    # Re(Z) = Rs + X^2/Rp. Une mediane sur la bande basse rendait 7,30 mOhm
    # pour une DCR de 5,50, soit +33 %.
    return dict(
        srf=float(f[i]), srf_x=srf_x, z_crete=float(mod[i]), l_bf=l_bf,
        r_bf=float(re_z[0]),
        q_srf=float(mod[i] / (2 * np.pi * f[i] * l_bf)) if bf.any()
        else float("nan"),
    )


def q_a(f, z, f_ref):
    """Facteur de qualite d'un circuit bouchon A UNE FREQUENCE DONNEE.

    Q = |Z|crete / (2 pi f_ref L). Il depend fortement de f_ref : la meme
    piece rend Q = 1,4 a sa resonance propre (32 MHz) et Q = 16 a 3,7 MHz,
    parce que la reactance omega*L y est 9 fois plus faible. Toujours
    annoncer la frequence avec le chiffre.
    """
    m = mesures(f, z)
    return float(m["z_crete"] / (2 * np.pi * f_ref * m["l_bf"]))


def l_effective(f, z):
    return np.imag(z) / (2.0 * np.pi * np.asarray(f, dtype=float))


def ecart_db(z_test, z_ref):
    return 20.0 * np.log10(np.abs(z_test) / np.abs(z_ref))


def verdict(f, z_test, z_ref, srf_ref, tol_sous=1.0, tol_sur=3.0,
            tol_srf=0.10, bande=(1e4, 1e8)):
    """Confrontation chiffree. Rend une liste de (critere, valeur, seuil, ok)."""
    m = (f >= bande[0]) & (f <= bande[1])
    e = ecart_db(z_test[m], z_ref[m])
    sous, sur = f[m] < srf_ref, f[m] >= srf_ref
    mt = mesures(f, z_test)
    lignes = []
    if sous.any():
        v = float(np.abs(e[sous]).max())
        lignes.append(("écart max sous la SRF", f"{v:.2f} dB",
                       f"≤ {tol_sous:.1f} dB", v <= tol_sous))
    if sur.any():
        v = float(np.abs(e[sur]).max())
        lignes.append(("écart max au-dessus de la SRF", f"{v:.2f} dB",
                       f"≤ {tol_sur:.1f} dB", v <= tol_sur))
    v = abs(mt["srf"] / srf_ref - 1.0)
    lignes.append(("écart de résonance propre", f"{v*100:.1f} %",
                   f"≤ {tol_srf*100:.0f} %", v <= tol_srf))
    lignes.append(("écart médian sur la bande",
                   f"{float(np.median(np.abs(e))):.2f} dB", "—", True))
    return lignes


# ------------------------------------------------- nuage de vraisemblance

def corpus(cache=None, force=False):
    """(L, Rp, fournisseur) de tous les modeles d'inductance sur le disque.

    Sert de reference de VRAISEMBLANCE : un modele dont l'amortissement
    sort de ce nuage est suspect sans qu'aucune courbe de reference ne soit
    necessaire. C'est le controle qui aurait arrete le fichier fabrique.
    """
    cache = Path(cache or ICI / "results" / "impedance" / "corpus.json")
    if cache.exists() and not force:
        d = json.loads(cache.read_text())
        return [tuple(x) for x in d]
    pts = []
    for f in (LIB_COMMUN / "WurthElektronik").rglob("*.lib"):
        d = f.read_bytes().decode("utf-8", "replace")
        for m in re.finditer(r"\.subckt\s+\S+.*?\.ends", d, re.S | re.I):
            b = m.group(0)
            rp = re.search(r"^Rp\s+\S+\s+\S+\s+([0-9.eE+-]+)", b, re.M | re.I)
            l1 = re.search(r"^L1?\s+\S+\s+\S+\s+([0-9.eE+-]+)u", b, re.M | re.I)
            if rp and l1:
                pts.append((float(l1.group(1)) * 1e-6, float(rp.group(1)),
                            "Würth"))
    for f in (LIB_COMMUN / "Coilcraft").glob("*.lib"):
        d = f.read_bytes().decode("utf-8", "replace")
        for m in re.finditer(r"\.subckt\s+\S+_imp.*?\.ends", d, re.S | re.I):
            b = m.group(0)
            pk = re.search(r"PkZ\s*=\s*([0-9.eE+-]+)", b, re.I)
            ind = re.search(r"Ind\s*=\s*([0-9.eE+-]+)(u|n)H", b, re.I)
            if pk and ind:
                L = float(ind.group(1)) * (1e-6 if ind.group(2).lower() == "u"
                                           else 1e-9)
                pts.append((L, float(pk.group(1)), "Coilcraft"))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(pts))
    return pts


def vraisemblance(L, rp, pts=None, largeur=0.3):
    """Position de (L, Rp) dans le nuage. Rend percentile et verdict.

    `largeur` : demi-largeur de la fenetre en decades autour de L.
    """
    pts = pts or corpus()
    voisins = sorted(r for l, r, _ in pts
                     if abs(math.log10(l / L)) <= largeur)
    if len(voisins) < 20:
        return dict(n=len(voisins), percentile=float("nan"), ok=None,
                    mediane=float("nan"), p05=float("nan"), p95=float("nan"))
    a = np.asarray(voisins)
    pc = float((a < rp).mean() * 100.0)
    return dict(n=len(a), percentile=pc, mediane=float(np.median(a)),
                p05=float(np.percentile(a, 5)),
                p95=float(np.percentile(a, 95)),
                ok=bool(np.percentile(a, 5) <= rp <= np.percentile(a, 95)))


# ------------------------------------------------------------- export

def export_lib(nom, p, meta, sortie):
    """Emet un `.lib` dont l'EN-TETE porte la provenance de chaque nombre.

    `meta` : dict avec `statut`, `bande`, `sources` (liste de chaines),
    `controle` (liste de chaines). Rien n'est ecrit sans ces champs : c'est
    leur absence qui a permis au fichier fabrique de passer pour un modele
    constructeur.
    """
    for champ in ("statut", "bande", "sources", "controle"):
        if not meta.get(champ):
            raise ValueError(f"export refuse : champ `{champ}` absent. "
                             "Un modele sans provenance ne doit pas exister.")
    src = "\n".join(f"*   {s}" for s in meta["sources"])
    ctl = "\n".join(f"*   {s}" for s in meta["controle"])
    rc = (f"Rc     n1    nc   {p['Rc']:.6g}\nCp     nc    port2 {p['Cp']:.6e}"
          if p.get("Rc") else f"Cp     port1 port2 {p['Cp']:.6e}")
    txt = f"""* =====================================================================
* {nom}
* STATUT : {meta['statut'].upper()}
* =====================================================================
* Genere par impedance_banc.py -- ne pas editer a la main.
* Topologie : Rp // Cp // (Rs + L){' , Rc en serie avec Cp' if p.get('Rc') else ''}
* Validite declaree : {meta['bande']}
*
* PROVENANCE DE CHAQUE NOMBRE
{src}
*
* CONTROLE
{ctl}
* =====================================================================
.subckt {nom} port1 port2
Rp     port1 port2 {p['Rp']:.6g}
{rc}
Rs     port1 n2    {p['Rs']:.6e}
L1     n2    port2 {p['L']:.6e}
.ends {nom}
"""
    Path(sortie).write_text(txt, encoding="ascii", errors="replace")
    return txt
