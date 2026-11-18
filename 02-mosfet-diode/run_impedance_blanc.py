"""Test a blanc du banc d'impedance, sur la SER1360-472.

POURQUOI CETTE PIECE. C'est la seule 4,7 uH de la gamme SER dont Coilcraft
publie A LA FOIS un datasheet et un modele SPICE. On dispose donc d'une
VERITE TERRAIN, ce qui est la condition d'un test a blanc : on peut verifier
que la methode retrouve ce qu'elle doit retrouver.

CE QUE LE TEST ETABLIT, dans l'ordre :

  1. Le datasheet donne TROIS des quatre parametres -- L, DCR, SRF -- et
     PAS le quatrieme. L'impedance de crete n'y figure pas.
  2. Sous la resonance propre, |Z| est INSENSIBLE a ce quatrieme parametre :
     un modele bati sur le seul datasheet y est juste.
  3. Au voisinage de la resonance, et pour tout ce qui est transitoire, ce
     meme parametre decide de TOUT. Un modele datasheet-seul ne dit rien de
     l'amortissement, et c'est exactement la que la faute precedente a ete
     commise.
  4. Le nuage des 5 071 modeles reels suffit a ECARTER une aberration, pas
     a FIXER une valeur. Les deux usages ne se confondent pas.
"""
from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                 # noqa: E402

import impedance_banc as ib                                     # noqa: E402

FIGURES = ib.ICI / "illustrations" / "impedance"
SORTIES = ib.ICI / "results" / "impedance"

FOND, PAPIER, ENCRE, TRAIT = "#14171b", "#1b1f25", "#e8eaed", "#9aa4b0"
C_REF, C_TEST, C_ALT = "#51cf66", "#ff6b6b", "#4dabf7"

# --- SER1360-472KL, datasheet Coilcraft doc 290-1 rev 09/30/24, page 1
DS = dict(L=4.7e-6,          # "Inductance ±10 % (µH)", mesuree a 100 kHz
          dcr=5.50e-3,       # "DCR (mOhm) typ"
          srf=32e6)          # "SRF typ (MHz)", au 4395A sur fixture 16193A

# --- SER2013-472MLD, fiche produit Coilcraft (serie SER2000).
# La piece RETENUE au chapitre 3, et celle dont j'avais fabrique un modele.
# Son datasheet donne bien une SRF : j'avais conclu le contraire depuis un
# export CSV du Power Inductor Finder, qui ne porte pas cette colonne.
# Conclure d'une source incomplete, deux fois la meme faute.
DS2013 = dict(L=4.7e-6,      # 4,7 uH +/-20 %  (et non +/-10 % comme SER1360)
              dcr=1.70e-3,   # DCR typ 1,7 mOhm (max 1,8)
              srf=30e6)      # SRF typ 30 MHz
BANDE = (1e4, 1e8)


def style():
    plt.rcParams.update({
        "figure.facecolor": FOND, "savefig.facecolor": FOND,
        "axes.facecolor": PAPIER, "axes.edgecolor": TRAIT,
        "axes.labelcolor": ENCRE, "axes.titlecolor": ENCRE,
        "text.color": ENCRE, "xtick.color": TRAIT, "ytick.color": TRAIT,
        "grid.color": TRAIT, "legend.facecolor": PAPIER,
        "legend.edgecolor": TRAIT, "legend.framealpha": .88,
        "legend.labelcolor": ENCRE, "font.size": 11, "axes.titlesize": 12,
    })


def _hab(ax):
    for a in np.atleast_1d(ax).ravel():
        a.grid(which="major", alpha=.4)
        a.grid(which="minor", alpha=.15)


# ----------------------------------------------------------------- Smith

def grille_smith(ax, z0=ib.Z0_SMITH):
    """Cercles a R constant et arcs a X constant, normalises a z0."""
    th = np.linspace(0, 2 * np.pi, 721)
    ax.plot(np.cos(th), np.sin(th), color=TRAIT, lw=1.3, alpha=.9)
    ax.plot([-1, 1], [0, 0], color=TRAIT, lw=.9, alpha=.5)
    for r in (0.2, 0.5, 1, 2, 5, 10):
        c, rad = r / (1 + r), 1 / (1 + r)
        ax.plot(c + rad * np.cos(th), rad * np.sin(th), color=TRAIT,
                lw=.6, alpha=.30)
        # Au-dela de r = 2 les cercles se tassent contre le bord droit et
        # leurs etiquettes se chevauchent : on ne cote que les lisibles.
        if r <= 2:
            ax.text(c + rad, 0.018, f"{r:g}", color=TRAIT, fontsize=7.5,
                    ha="center", va="bottom", alpha=.8)
    for x in (0.2, 0.5, 1, 2, 5, 10):
        for s in (+1, -1):
            cy, rad = s / x, 1 / x
            g = (1 + 1j * cy) + rad * np.exp(1j * th)
            g = g[np.abs(g) <= 1.0]
            if len(g):
                ax.plot(g.real, g.imag, color=TRAIT, lw=.6, alpha=.30)
    ax.set_aspect("equal")
    ax.set_xlim(-1.56, 1.14)
    ax.set_ylim(-1.14, 1.14)
    ax.set_axis_off()

    # Nature du composant, en colonne a gauche et dans l'ordre vertical de
    # l'abaque : demi-plan haut inductif (reactance positive), axe median
    # purement resistif, demi-plan bas capacitif.
    for y, lettre, desc, col in ((0.50, "L", "inductif   + jX", "#ffd43b"),
                                 (0.00, "R", "résistif pur", "#ff9f68"),
                                 (-0.50, "C", "capacitif   − jX", "#4dabf7")):
        ax.text(-1.52, y, lettre, color=col, fontsize=23, ha="left",
                va="center", fontweight="bold")
        ax.text(-1.38, y, desc, color=col, fontsize=9.5, ha="left",
                va="center", alpha=.9)

    ax.text(-1.0, -1.10, "court-circuit", color=TRAIT, fontsize=8,
            ha="center", va="top")
    ax.text(1.0, -1.10, "circuit ouvert", color=TRAIT, fontsize=8,
            ha="center", va="top")
    ax.text(0, 1.10, f"normalisé {z0:.0f} Ω", color=TRAIT, fontsize=8.5,
            ha="center")


def trace_smith(ax, f, z, couleur, etiquette, style_trait="-", z0=ib.Z0_SMITH):
    g = (z / z0 - 1) / (z / z0 + 1)
    ax.plot(g.real, g.imag, color=couleur, lw=1.7, ls=style_trait,
            label=etiquette, zorder=5)
    for fx in (1e5, 1e6, 1e7, 1e8):
        if f[0] <= fx <= f[-1]:
            i = int(np.argmin(np.abs(f - fx)))
            ax.plot([g.real[i]], [g.imag[i]], "o", ms=5, color=couleur,
                    zorder=6)
            lab = f"{fx/1e6:g} MHz" if fx >= 1e6 else f"{fx/1e3:g} kHz"
            ax.annotate(lab, (g.real[i], g.imag[i]), fontsize=8,
                        color=couleur, xytext=(6, 5),
                        textcoords="offset points", zorder=7)


# ---------------------------------------------------------------- figures

def fig_module(f, zr, zt, srf_ref, sortie):
    fig, ax = plt.subplots(3, 1, figsize=(15, 11), sharex=True,
                           height_ratios=[3, 1.6, 1.6])
    ax[0].loglog(f, np.abs(zr), color=C_REF, lw=1.8,
                 label="RÉFÉRENCE — modèle constructeur SER1360-472_imp")
    ax[0].loglog(f, np.abs(zt), color=C_TEST, lw=1.5, ls="--",
                 label="TEST — synthétisé depuis 4 nombres de catalogue")
    ax[0].axvline(srf_ref, color=TRAIT, ls=":", lw=1.2)
    ax[0].text(srf_ref * 1.07, np.abs(zr).min() * 3, "résonance propre",
               color=TRAIT, fontsize=9, rotation=90)
    ax[0].set_ylabel("|Z|   [Ω]")
    ax[0].legend(loc="upper left", fontsize=10)
    ax[1].semilogx(f, np.angle(zr, deg=True), color=C_REF, lw=1.6)
    ax[1].semilogx(f, np.angle(zt, deg=True), color=C_TEST, lw=1.3, ls="--")
    ax[1].set_ylabel("phase   [°]")
    ax[1].set_yticks([-90, -45, 0, 45, 90])
    e = ib.ecart_db(zt, zr)
    ax[2].semilogx(f, e, color=C_ALT, lw=1.5)
    ax[2].axhspan(-1, 1, color=C_REF, alpha=.12)
    ax[2].axhline(0, color=TRAIT, lw=.8, ls=":")
    ax[2].set_ylabel("écart\n[dB]")
    ax[2].set_xlabel("fréquence   [Hz]")
    ax[2].set_ylim(-4, 4)
    ax[2].text(f[1], 1.25, "±1 dB", color=C_REF, fontsize=9)
    _hab(ax)
    ax[0].set_title("Impédance — référence contre modèle synthétisé\n"
                    "le modèle n'a vu que L, DCR, SRF et |Z| crête ; "
                    "jamais la courbe", fontsize=12)
    fig.tight_layout()
    fig.savefig(sortie, dpi=170)
    plt.close(fig)


def fig_rx(f, zr, zt, sortie):
    fig, ax = plt.subplots(1, 2, figsize=(16, 6))
    ax[0].loglog(f, np.abs(np.real(zr)), color=C_REF, lw=1.8, label="référence")
    ax[0].loglog(f, np.abs(np.real(zt)), color=C_TEST, lw=1.5, ls="--",
                 label="synthétisé")
    ax[0].set_ylabel("R = Re(Z)   [Ω]")
    ax[0].set_title("Partie résistive — c'est elle qui porte les pertes")
    ax[1].semilogx(f, np.real(ib.l_effective(f, zr)) * 1e6, color=C_REF, lw=1.8,
                   label="référence")
    ax[1].semilogx(f, np.real(ib.l_effective(f, zt)) * 1e6, color=C_TEST,
                   lw=1.5, ls="--", label="synthétisé")
    ax[1].axhline(DS["L"] * 1e6, color=TRAIT, ls=":", lw=1)
    ax[1].text(f[1], DS["L"] * 1e6 * 1.04, "4,7 µH catalogue", color=TRAIT,
               fontsize=9)
    ax[1].set_ylim(-20, 20)
    ax[1].set_ylabel("L effective = X / ω   [µH]")
    ax[1].set_title("Inductance effective — elle change de signe à la SRF")
    for a in ax:
        a.set_xlabel("fréquence   [Hz]")
        a.legend(loc="best", fontsize=10)
    _hab(ax)
    fig.tight_layout()
    fig.savefig(sortie, dpi=170)
    plt.close(fig)


def fig_smith(f, zr, zt, sortie):
    """SUPERPOSEES, et non juxtaposees : comparer deux trajectoires cote a
    cote ne permet pas de voir ou elles divergent.

    Contre toute attente, c'est ICI que le defaut du modele a quatre
    elements se voit le mieux. Au-dela de la resonance propre, la reference
    s'enroule vers l'interieur -- les pertes de la resistance en serie avec
    Cp eloignent du cercle unite -- alors que la synthese, qui n'a pas cet
    element, reste collee au bord. Sur le trace de module le meme ecart ne
    vaut que 1,7 dB et passe presque inapercu.
    """
    fig, ax = plt.subplots(1, 2, figsize=(17, 8))
    for a in ax:
        grille_smith(a)
        trace_smith(a, f, zr, C_REF, "RÉFÉRENCE — constructeur", "-")
        trace_smith(a, f, zt, C_TEST, "TEST — synthétisé", "--")
    ax[0].legend(loc="lower right", fontsize=10)
    ax[0].set_title("10 kHz → 300 MHz", fontsize=11)
    # zoom sur la zone de divergence, au-dela de la resonance propre
    ax[1].set_xlim(0.55, 1.03)
    ax[1].set_ylim(-0.55, 0.30)
    ax[1].set_title("zoom au-delà de la résonance propre — la référence "
                    "s'enroule,\nla synthèse reste sur le bord : "
                    "c'est l'élément manquant", fontsize=11)
    fig.suptitle("Abaque de Smith — référence et modèle superposés",
                 fontsize=12.5)
    fig.tight_layout()
    fig.savefig(sortie, dpi=170)
    plt.close(fig)


def fig_sensibilite(f, zr, srf_ref, sortie):
    """Le point central : |Z| sous la SRF ne dit RIEN de l'amortissement."""
    fig, ax = plt.subplots(1, 2, figsize=(16, 6.5))
    cmap = plt.get_cmap("plasma")
    essais = [(120.0, "120 Ω — le fichier fabriqué"),
              (1300.0, "1300 Ω — valeur réelle"),
              (5126.0, "5126 Ω — médiane du corpus"),
              (50000.0, "50 kΩ")]
    for k, (rp, lab) in enumerate(essais):
        p = ib.synthese(DS["L"], DS["dcr"], DS["srf"], rp)
        z = ib.z_localise(f, **p)
        c = cmap(.12 + .72 * k / (len(essais) - 1))
        ax[0].loglog(f, np.abs(z), lw=1.6, color=c, label=lab)
        m = f < 0.1 * srf_ref
        ax[1].semilogx(f[m], ib.ecart_db(z[m], zr[m]), lw=1.6, color=c,
                       label=lab)
    ax[0].loglog(f, np.abs(zr), color=C_REF, lw=2.4, alpha=.45,
                 label="référence constructeur")
    ax[0].axvline(srf_ref, color=TRAIT, ls=":", lw=1.2)
    ax[0].set_ylabel("|Z|   [Ω]")
    ax[0].set_title("Rp fait tout au voisinage de la résonance…")
    ax[1].axhspan(-1, 1, color=C_REF, alpha=.12)
    ax[1].set_ylim(-2, 2)
    ax[1].set_ylabel("écart contre la référence   [dB]")
    ax[1].set_title("…et RIEN en dessous : les quatre courbes s'y confondent")
    for a in ax:
        a.set_xlabel("fréquence   [Hz]")
        a.legend(loc="best", fontsize=9)
    _hab(ax)
    fig.suptitle("Un modèle bâti sur le seul datasheet est juste sous la "
                 "résonance — et muet sur l'amortissement", fontsize=12)
    fig.tight_layout()
    fig.savefig(sortie, dpi=170)
    plt.close(fig)


def fig_corpus(pts, sortie):
    fig, ax = plt.subplots(figsize=(14, 8))
    for nom, c in (("Würth", "#ffa94d"), ("Coilcraft", "#4dabf7")):
        xs = [l * 1e6 for l, r, v in pts if v == nom]
        ys = [r for l, r, v in pts if v == nom]
        ax.loglog(xs, ys, ".", ms=2.2, alpha=.30, color=c,
                  label=f"{nom} — {len(xs)} modèles")
    ax.loglog([4.7], [1300], "o", ms=13, mfc="none", mec=C_REF, mew=2.4,
              label="SER1360-472 réelle — 1300 Ω", zorder=5)
    ax.loglog([4.7], [120], "X", ms=14, color=C_TEST, mew=2.5,
              label="fichier fabriqué — 120 Ω  ⟵  ABERRANT", zorder=6)
    ax.loglog([4.7], [1.114e6], "X", ms=14, color="#cc8fff", mew=2.5,
              label="son |Z| crête mesurée — 1,1 MΩ  ⟵  ABERRANT", zorder=6)
    ax.set_xlabel("inductance nominale   [µH]")
    ax.set_ylabel("amortissement Rp / |Z| crête   [Ω]")
    ax.set_title(f"Nuage de vraisemblance — {len(pts)} modèles constructeur "
                 "réels du disque\nn'exige AUCUNE référence : une pièce hors "
                 "du nuage est suspecte en soi", fontsize=12)
    ax.legend(loc="upper left", fontsize=10)
    _hab(ax)
    fig.tight_layout()
    fig.savefig(sortie, dpi=170)
    plt.close(fig)


def fig_indetermination(f, bornes, p, ds, sortie):
    """Ce que le datasheet determine, et ce qu'il laisse ouvert."""
    fig, ax = plt.subplots(figsize=(14.5, 8))
    ax.fill_between(f, np.abs(bornes["p05"]), np.abs(bornes["p95"]),
                    color=C_TEST, alpha=.16,
                    label="indétermination sur Rp (p05–p95 du corpus)")
    for lab, c, lw in (("p05", "#ffa94d", 1.2), ("médiane", C_TEST, 2.0),
                       ("p95", "#cc8fff", 1.2)):
        ax.loglog(f, np.abs(bornes[lab]), color=c, lw=lw, label=f"Rp {lab}")
    ax.axvline(ds["srf"], color=TRAIT, ls=":", lw=1.2)
    ax.text(ds["srf"] * 1.07, 0.1, f"SRF {ds['srf']/1e6:.0f} MHz — datasheet",
            color=TRAIT, fontsize=9.5, rotation=90)
    for fx, lab in ((4e5, "400 kHz\ndécoupage"), (3.73e6, "3,73 MHz\nsonnerie")):
        ax.axvline(fx, color=C_REF, ls="--", lw=1.1, alpha=.8)
        ax.text(fx * 1.08, 2.2e3, lab, color=C_REF, fontsize=9.5)
    # LE point de la figure : a 3,73 MHz les trois courbes se confondent,
    # et pourtant le facteur de qualite y est indetermine d'un facteur 15.
    # |Z| y vaut omega*L a 0,5 % pres quel que soit Rp -- c'est precisement
    # pour cela qu'une courbe d'impedance ne controle PAS un amortissement.
    zl = 2 * np.pi * 3.73e6 * p["L"]
    q05, q95 = bornes_q = (1078.0 / zl, 15844.0 / zl)
    ax.annotate(f"à 3,73 MHz les trois courbes se confondent à 0,5 % près —\n"
                f"et pourtant Q y vaut entre {q05:.0f} et {q95:.0f}, "
                f"un facteur {q95/q05:.0f}.\n"
                f"Une courbe d'impédance ne contrôle PAS un amortissement.",
                xy=(3.73e6, 110), xytext=(2.2e4, 900), fontsize=11,
                color=C_REF,
                arrowprops=dict(arrowstyle="->", color=C_REF, lw=1.4),
                bbox=dict(boxstyle="round,pad=0.5", fc=PAPIER, ec=C_REF,
                          alpha=.92))
    ax.set_xlabel("fréquence   [Hz]")
    ax.set_ylabel("|Z|   [Ω]")
    ax.set_xlim(1e4, 3e8)
    ax.set_title("SER2013-472 — ce que le datasheet détermine, et ce qu'il "
                 "laisse ouvert\nL, DCR et SRF fixent |Z| partout sous "
                 "10 MHz ; l'amortissement n'est pas publié",
                 fontsize=12)
    ax.legend(loc="upper left", fontsize=10)
    _hab(ax)
    fig.tight_layout()
    fig.savefig(sortie, dpi=170)
    plt.close(fig)


# -------------------------------------------------------------------- main

def main():
    # La console Windows est en cp1252 : un simple « Ω » y leve une
    # UnicodeEncodeError et tue le run apres la simulation, pas avant.
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                      # noqa: BLE001
        pass
    style()
    FIGURES.mkdir(parents=True, exist_ok=True)
    SORTIES.mkdir(parents=True, exist_ok=True)
    dsf = "Coilcraft doc 290-1 rev 09/30/24, p. 1"

    print("== 1. RÉFÉRENCE : modèle constructeur, balayage .ac ==")
    defs = (ib.subckt_vendor(ib.LIB_COMMUN / "Coilcraft/CoilcraftTemplates.lib",
                             "Model1D") + "\n"
            + ib.subckt_vendor(ib.LIB_COMMUN / "Coilcraft/SER1360.lib",
                               "SER1360-472_imp"))
    f, zr = ib.z_depuis_spice(defs, "XL n1 0 SER1360-472_imp", nom="ref")
    mr = ib.mesures(f, zr)
    print(f"   SRF {mr['srf']/1e6:6.2f} MHz (sommet de |Z|) ; X=0 à "
          f"{mr['srf_x']/1e6:.2f} MHz — DEUX définitions, 8 % d'écart")
    print(f"   |Z| crête {mr['z_crete']:7.1f} Ω   L_BF {mr['l_bf']*1e6:.3f} µH"
          f"   R(f min) {mr['r_bf']*1e3:.2f} mΩ")
    print(f"   datasheet : SRF {DS['srf']/1e6:.0f} MHz, L {DS['L']*1e6:.1f} µH,"
          f" DCR {DS['dcr']*1e3:.2f} mΩ   ({dsf})")
    print(f"   écart datasheet / modèle sur la SRF : "
          f"{abs(mr['srf']/DS['srf']-1)*100:.1f} %")

    print("\n== 2. SYNTHÈSE depuis le catalogue ==")
    z_crete = mr["z_crete"]          # <- ABSENT du datasheet, cf. §3
    p = ib.synthese(DS["L"], DS["dcr"], DS["srf"], z_crete)
    print(f"   L {p['L']*1e6:.2f} µH | Rs {p['Rs']*1e3:.2f} mΩ | "
          f"Cp {p['Cp']*1e12:.3f} pF | Rp {p['Rp']:.0f} Ω")
    zt = ib.z_localise(f, **p)
    lignes = ib.verdict(f, zt, zr, mr["srf"], bande=BANDE)
    print(f"\n   {'critère':<34}{'mesuré':>12}{'seuil':>12}   verdict")
    for crit, val, seuil, ok in lignes:
        print(f"   {crit:<34}{val:>12}{seuil:>12}   "
              f"{'OK' if ok else 'ÉCHEC'}")

    print("\n== 3. SENSIBILITÉ au paramètre ABSENT du datasheet ==")
    for rp in (120.0, 1300.0, 5126.0, 50000.0):
        zz = ib.z_localise(f, **ib.synthese(DS["L"], DS["dcr"], DS["srf"], rp))
        m = f < 0.1 * mr["srf"]
        print(f"   Rp {rp:8.0f} Ω  →  écart sous SRF/10 : "
              f"{np.abs(ib.ecart_db(zz[m], zr[m])).max():5.2f} dB   |   "
              f"|Z| crête {np.abs(zz).max():9.1f} Ω   "
              f"Q@SRF {ib.mesures(f, zz)['q_srf']:5.1f}   "
              f"Q@3,73MHz {ib.q_a(f, zz, 3.73e6):6.1f}")

    print("\n== 4. VRAISEMBLANCE dans le corpus ==")
    pts = ib.corpus()
    for nom, rp in (("SER1360-472 réelle", z_crete),
                    ("fichier fabriqué (Rp)", 120.0),
                    ("fichier fabriqué (|Z| crête mesurée)", 1.114e6)):
        v = ib.vraisemblance(DS["L"], rp, pts)
        etat = "dans le nuage" if v["ok"] else "HORS NUAGE"
        print(f"   {nom:<38} {rp:11.0f} Ω → percentile {v['percentile']:5.1f} "
              f"   {etat}")
    v = ib.vraisemblance(DS["L"], z_crete, pts)
    print(f"   corpus à 4,7 µH : n={v['n']}, p05 {v['p05']:.0f} Ω, "
          f"médiane {v['mediane']:.0f} Ω, p95 {v['p95']:.0f} Ω")

    print("\n== 5. EXPORT + ALLER-RETOUR ==")
    nom_lib = "SER1360-472_synth"
    chemin = SORTIES / f"{nom_lib}.lib"
    ib.export_lib(nom_lib, p, dict(
        statut="synthétisé",
        bande="10 kHz – 100 MHz (contrôlé) ; au-delà, extrapolation",
        sources=[
            f"L   = 4,7 uH +/-10 %, a 100 kHz  -- {dsf}",
            f"Rs  = DCR typ 5,50 mOhm          -- {dsf}",
            f"Cp  = deduit de SRF typ 32 MHz   -- {dsf}",
            f"Rp  = {z_crete:.0f} Ohm -- ABSENT DU DATASHEET, releve sur le",
            "      modele constructeur SER1360-472_imp (SER1360.lib).",
            "      Sans ce modele, ce parametre serait INCONNU.",
        ],
        controle=[
            "Confronte au modele constructeur par balayage .ac 1 kHz-300 MHz.",
            "Les ecarts mesures sont reportes ci-dessous par le banc.",
        ]), chemin)
    f2, z2 = ib.z_depuis_spice(chemin.read_text(), f"XL n1 0 {nom_lib}",
                               nom="aller_retour")
    # Comparer sur la MEME bande que le verdict. Sur le balayage entier
    # (1 kHz - 300 MHz) l'ecart monte a 7 dB, mais tout est au-dessus de
    # 100 MHz, hors de la validite declaree : l'annoncer brut serait un
    # faux echec.
    mb = (f2 >= BANDE[0]) & (f2 <= BANDE[1])
    e_ar = np.abs(ib.ecart_db(z2[mb], ib.z_localise(f2[mb], **p))).max()
    e_ref = np.abs(ib.ecart_db(z2[mb], zr[mb])).max()
    e_tot = np.abs(ib.ecart_db(z2, zr)).max()
    print(f"   fichier écrit : {chemin.name}")
    print(f"   aller-retour (fichier vs forme fermée)   : {e_ar:.3f} dB")
    print(f"   fichier vs référence, bande déclarée     : {e_ref:.2f} dB")
    print(f"   fichier vs référence, balayage entier    : {e_tot:.2f} dB "
          f"(hors validité au-delà de 100 MHz)")

    print("\n== 6. APPLICATION : SER2013-472, la pièce RETENUE ==")
    # Trois parametres sur quatre viennent du datasheet. Le quatrieme,
    # l'amortissement, n'y est pas -- et c'est le trou qu'un modele
    # fabrique avait comble par une invention.
    p13 = ib.synthese(DS2013["L"], DS2013["dcr"], DS2013["srf"], float("nan"))
    print(f"   depuis le datasheet : L {DS2013['L']*1e6:.1f} µH ±20 %, "
          f"DCR {DS2013['dcr']*1e3:.2f} mΩ, SRF {DS2013['srf']/1e6:.0f} MHz")
    print(f"   -> Cp déduite = {p13['Cp']*1e12:.2f} pF")
    print(f"   -> Rp : ABSENTE du datasheet")
    print(f"   le fichier fabriqué portait Cp = 7,40 pF, soit "
          f"{(7.40/(p13['Cp']*1e12)-1)*100:+.0f} % et une SRF de 27,0 MHz "
          f"au lieu de 30")
    v13 = ib.vraisemblance(DS2013["L"], 1300.0, pts)
    print(f"   encadrement de Rp par le corpus à 4,7 µH : "
          f"{v13['p05']:.0f} – {v13['p95']:.0f} Ω (médiane {v13['mediane']:.0f})")
    f13 = np.logspace(3, np.log10(3e8), 2400)
    bornes = {}
    for lab, rp in (("p05", v13["p05"]), ("médiane", v13["mediane"]),
                    ("p95", v13["p95"])):
        bornes[lab] = ib.z_localise(f13, **{**p13, "Rp": rp})
    m400 = f13 < 1e6
    etendue = max(np.abs(ib.ecart_db(bornes["p95"][m400], bornes["p05"][m400])))
    print(f"   indétermination qui en résulte sur |Z| : "
          f"{etendue:.2f} dB sous 1 MHz, "
          f"{max(np.abs(ib.ecart_db(bornes['p95'], bornes['p05']))):.1f} dB "
          f"au sommet")
    fig_indetermination(f13, bornes, p13, DS2013,
                        FIGURES / "06-ser2013-indetermination.png")

    print("\n== 7. FIGURES ==")
    fig_module(f, zr, zt, mr["srf"], FIGURES / "01-module-phase-ecart.png")
    fig_rx(f, zr, zt, FIGURES / "02-resistance-inductance.png")
    fig_smith(f, zr, zt, FIGURES / "03-smith.png")
    fig_sensibilite(f, zr, mr["srf"], FIGURES / "04-sensibilite-Rp.png")
    fig_corpus(pts, FIGURES / "05-nuage-vraisemblance.png")
    print(f"   -> {FIGURES}")
    return dict(f=f, zr=zr, zt=zt, p=p, mr=mr, lignes=lignes,
                e_ar=e_ar, e_ref=e_ref, lib=chemin.read_text(), pts=pts)


if __name__ == "__main__":
    main()
