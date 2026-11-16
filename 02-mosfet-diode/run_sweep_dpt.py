"""Chapitre 2 (extension) -- balayage 200-800 kHz en topologie double-pulse.

METHODE DU RAPPORT CYCLIQUE. La sortie raide rend le courant hypersensible
a D (voir en-tete de gen_boost2_dpt.py). Plutot qu'une secante
SEQUENTIELLE, on lance TROIS valeurs de D encadrantes par cellule et on
interpole toutes les grandeurs a Pout = 40 W :

  - I(D) est quasi-affine sur cet intervalle, donc l'interpolation est
    exacte a cet ordre ;
  - les 180 runs partent TOUS EN PARALLELE, au lieu de 3 tours sequentiels ;
  - la sensibilite dI/dD tombe gratuitement, et sert de controle (si elle
    s'ecarte de Vout/R_eff, c'est que la cellule n'est pas au regime
    suppose).

PARTAGE DES MECANISMES. SPICE donne les pertes de CONDUCTION et les
courants ; Coss et grille viennent du modele analytique datasheet
(switch_energy). Motif detaille en en-tete du generateur.
"""
from __future__ import annotations

import csv
import math
import os
import sys
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent.parent
sys.path[:0] = [str(ICI), str(RACINE / ".claude/skills/sim-spice/scripts"),
                str(RACINE / ".claude/skills/sim-commun")]

import gen_boost2_dpt as g                      # noqa: E402
import switch_energy as se                      # noqa: E402
from ngspice_run import lance_parallele          # noqa: E402
from simcommun.lecture import lire               # noqa: E402

SORTIE = ICI / "results"
TRAVAIL = Path(os.environ.get("TEMP", "/tmp")) / "ch2_dpt"
DELTA_D = 7e-4   # ~+/-30 % de courant : dI/dD ~ Vout/R_eff ~ 816 A par unite


def mesure(raw: Path, cell: dict, duty: float) -> dict | None:
    """Grandeurs integrales sur la fenetre, trapezes sur l'axe reel."""
    try:
        r = lire(raw)
    except Exception:
        return None
    t = r.x
    if t.size < 50:
        return None
    il = np.asarray(r.trace("I(L1)"))
    # Sonde 0 V : I(Vd) est DEJA dans le sens de conduction de la diode.
    # Signe verifie a l'essai, pas deduit d'une convention : avec le signe
    # oppose, min(I_switch) tombait a -15 A et Irms_switch passait de 1.77
    # a 2.69 A (le switch se voyait attribuer le courant de la diode).
    idio = np.asarray(r.trace("I(Vd)"))
    ivo = np.asarray(r.trace("I(Vo)"))
    iv1 = np.asarray(r.trace("I(V1)"))
    vsw = np.asarray(r.trace("V(nsw)"))
    T = t[-1] - t[0]
    if T <= 0:
        return None

    moy = lambda y: float(np.trapezoid(y, t) / T)
    eff = lambda y: float(np.sqrt(np.trapezoid(y * y, t) / T))

    isw = il - idio                       # KCL au noeud de commutation
    rds = se.fiche(cell["switch"])["rds_ohm"]
    from switch_diode_models import diode_vf_at

    pout = abs(moy(ivo)) * g.VOUT
    pin = abs(moy(iv1)) * g.VIN
    i_d_moy = abs(moy(idio))
    return dict(
        duty=duty,
        pout=pout, pin=pin,
        il_moy=moy(il), il_rms=eff(il), il_pk=float(il.max()), il_min=float(il.min()),
        isw_rms=eff(isw), id_moy=i_d_moy, id_rms=eff(idio),
        # conduction, les seuls mecanismes que CETTE netlist modelise
        p_cond_sw=eff(isw) ** 2 * rds,
        p_cond_diode=abs(moy(idio * (vsw - g.VOUT))),
        p_dcr=eff(il) ** 2 * cell["dcr"],
        vsw_max=float(vsw.max()),
        # FRACTION DE TEMPS MORT, et non le minimum du courant. Portage de
        # la methode du chapitre 1 : en DCM le noeud de commutation sonne,
        # donc un critere sur un ECHANTILLON UNIQUE (min du courant, ou
        # courant en fin de periode) se fait piéger par l'oscillation et
        # classe de travers. On integre donc le temps passe a courant
        # quasi nul sur toute la fenetre.
        frac_morte=float(np.trapezoid((np.abs(il) < 0.02 * max(float(il.max()), 1e-9)).astype(float), t) / T),
        # Controle de DERIVE. La condition initiale fait demarrer au point
        # vise, mais la sortie raide n'impose aucun rappel : le courant
        # integre lentement si D n'est pas exactement a l'equilibre. On
        # compare donc la moyenne sur la premiere et la seconde moitie de
        # la fenetre. Au-dela de quelques pour cent, le point mesure n'est
        # pas un regime mais un instantane de transitoire.
        derive_pct=100 * abs(
            float(np.trapezoid(il[t >= t[0] + (t[-1] - t[0]) / 2],
                               t[t >= t[0] + (t[-1] - t[0]) / 2]))
            / ((t[-1] - t[0]) / 2)
            - float(np.trapezoid(il[t <= t[0] + (t[-1] - t[0]) / 2],
                                 t[t <= t[0] + (t[-1] - t[0]) / 2]))
            / ((t[-1] - t[0]) / 2)
        ) / max(abs(moy(il)), 1e-9),
    )


def interpole(pts: list[dict], cible: float) -> dict | None:
    """Interpole lineairement toutes les grandeurs a pout = cible.

    Rejette la cellule si la cible n'est pas encadree : extrapoler sur une
    grandeur aussi sensible que celle-ci n'aurait aucune valeur.
    """
    pts = sorted([p for p in pts if p], key=lambda p: p["pout"])
    if len(pts) < 2:
        return None
    ps = [p["pout"] for p in pts]
    if not (ps[0] <= cible <= ps[-1]):
        return None
    out = {}
    for k in pts[0]:
        out[k] = float(np.interp(cible, ps, [p[k] for p in pts]))
    # sensibilite dI/dD, controle de coherence du point de fonctionnement
    d0, d1 = pts[0]["duty"], pts[-1]["duty"]
    i0, i1 = pts[0]["il_moy"], pts[-1]["il_moy"]
    out["di_dd"] = (i1 - i0) / (d1 - d0) if d1 != d0 else float("nan")
    out["n_points"] = len(pts)
    return out


def tourne(cells: list[dict], plan: list[tuple[int, float]], etiq: str
           ) -> tuple[dict[int, list], int]:
    """Lance un lot (indice de cellule, rapport cyclique) et mesure."""
    taches, index = [], []
    for n, (ci, dd) in enumerate(plan):
        c = cells[ci]
        dossier = TRAVAIL / f"{etiq}_{n:04d}"
        dossier.mkdir(parents=True, exist_ok=True)
        f = dossier / "run.cir"
        f.write_text(g.netlist(c["switch"], c["diode"], c["fsw"], c["lh"],
                               c["dcr"], dd,
                               0.0 if c["mode_attendu"] == "DCM"
                               else c["pout"] / (0.99 * g.VIN)),
                     encoding="utf-8")
        taches.append(dict(netlist=f, dossier=dossier))
        index.append((ci, dd))

    res = lance_parallele(taches, n_coeurs=16)
    par_cell: dict[int, list] = {}
    echecs = 0
    for (ci, dd), r in zip(index, res):
        if not r["ok"]:
            echecs += 1
            continue
        m = mesure(Path(r["raw"]), cells[ci], dd)
        if m:
            par_cell.setdefault(ci, []).append(m)
    return par_cell, echecs


def main() -> int:
    cells = g.cellules()
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    SORTIE.mkdir(parents=True, exist_ok=True)

    # --- ETAPE 1 : sonder. L'estimation analytique de R_eff s'est revelee
    # 41 % trop haute a l'essai a blanc (elle traite la chute de diode comme
    # une resistance, ce qu'elle n'est pas). Plutot que de raffiner
    # l'estimateur, on MESURE la loi Pout(D) sur deux points et on resout.
    # Elle est quasi-affine, donc deux points suffisent.
    plan1 = []
    for ci, c in enumerate(cells):
        ic = c["pout"] / (0.99 * g.VIN)
        if c["mode_attendu"] == "DCM":
            d0 = g.duty_estimee_dcm(c["pout"], c["lh"], c["fsw"])
            # en DCM la loi est quadratique : on sonde large, pas serre
            plan1 += [(ci, d0), (ci, d0 * 0.80)]
        else:
            r_eff = g.r_eff_estimee(c["switch"], c["diode"], c["dcr"], ic, 0.75)
            d0 = g.duty_estimee(g.VIN, g.VOUT, r_eff, ic)
            plan1 += [(ci, d0), (ci, d0 - 1.5e-3)]
    print(f"ETAPE 1 -- sondage : {len(cells)} cellules x 2 points"
          f" = {len(plan1)} runs")
    sonde, ech1 = tourne(cells, plan1, "s1")

    # --- ETAPE 2 : viser. D* resolu depuis la loi mesuree, puis trois
    # points serres autour pour l'interpolation finale.
    plan2, sans_loi = [], 0
    for ci in range(len(cells)):
        pts = sorted(sonde.get(ci, []), key=lambda p: p["duty"])
        if len(pts) < 2 or pts[-1]["duty"] == pts[0]["duty"]:
            sans_loi += 1
            continue
        (d_a, p_a), (d_b, p_b) = ((pts[0]["duty"], pts[0]["pout"]),
                                  (pts[-1]["duty"], pts[-1]["pout"]))
        if p_b == p_a:
            sans_loi += 1
            continue
        cible = cells[ci]["pout"]
        if cells[ci]["mode_attendu"] == "DCM" and p_a > 0 and p_b > 0:
            # Pout ~ D^2 : on resout sur D^2, pas sur D
            k = (p_b - p_a) / (d_b**2 - d_a**2) if d_b != d_a else 0.0
            d_star = math.sqrt(max(d_a**2 + (cible - p_a) / k, 1e-6)) if k else d_a
            pente = 2 * k * d_star if k else 1.0
        else:
            pente = (p_b - p_a) / (d_b - d_a)    # W par unite de D
            d_star = d_a + (cible - p_a) / pente
        # Largeur d'encadrement ADAPTATIVE : viser +/-35 % de la puissance
        # cible. Un ecart FIXE ne marche pas, parce que la pente varie d'un
        # facteur ~20 sur le balayage -- et surtout parce qu'en DCM la loi
        # Pout(D) est QUADRATIQUE, pas affine : le D* extrapole depuis deux
        # points y tombe a cote, et un encadrement trop etroit le rate.
        delta = min(max(0.35 * cible / abs(pente), 2e-4), 0.12)
        plan2 += [(ci, d_star - delta), (ci, d_star), (ci, d_star + delta)]
    print(f"\nETAPE 2 -- visee : {len(plan2)} runs"
          f" ({sans_loi} cellules sans loi exploitable)")
    par_cell, ech2 = tourne(cells, plan2, "s2")
    echecs = ech1 + ech2

    lignes, rejets = [], []
    for ci, c in enumerate(cells):
        it = interpole(par_cell.get(ci, []), c["pout"])
        if not it:
            continue

        # --- GARDE-FOU PHYSIQUE : conservation de l'energie.
        # En regime, le courant moyen d'inductance doit valoir
        #     I_L = (Pout + pertes) / Vin
        # Un ecart important ne signale pas une mesure imprecise mais un
        # point de fonctionnement qui n'a pas converge : le solveur de
        # rapport cyclique a extrapole de travers et le courant s'est
        # emballe. Observe sur les cellules a 500 kHz / 10 W, ou le seuil
        # DCM/CCM tombe a 11.11 W -- 10 % de marge seulement, de sorte que
        # ni la loi DCM ni la loi CCM n'y vaut : I_L y sortait a 22.7 A
        # contre 1.48 A attendus, soit un facteur 1436.
        #
        # Ce critere a ete prefere a un filtre sur la DERIVE du courant :
        # la derive discrimine mal (a 15 % elle rejetterait 25 cellules
        # dont la plupart sont saines), alors que le bilan d'energie isole
        # exactement les points divergents.
        pertes_spice = it["p_cond_sw"] + it["p_cond_diode"] + it["p_dcr"]
        il_attendu = (c["pout"] + pertes_spice) / g.VIN
        ecart = abs(it["il_moy"] - il_attendu) / max(il_attendu, 1e-9)
        if ecart > 0.25:
            rejets.append((c, ecart, it["il_moy"], il_attendu))
            continue
        an = g.pertes_analytiques(c["switch"], c["fsw"])
        p_tot = (it["p_cond_sw"] + it["p_cond_diode"] + it["p_dcr"]
                 + an["p_coss"] + an["p_gate"])
        lignes.append(dict(
            switch=c["switch"], diode=c["diode"],
            boitier=se.fiche(c["switch"]).get("boitier", "puce nue"),
            fsw_khz=c["fsw"] / 1e3, pout_w=c["pout"],
            l_uh=c["lh"] * 1e6, l_ref=c["l_ref"], mode_attendu=c["mode_attendu"],
            p_seuil_w=c["p_seuil"], duty=round(it["duty"], 6),
            di_dd=round(it["di_dd"], 1),
            il_moy=it["il_moy"], il_rms=it["il_rms"],
            il_pk=it["il_pk"], il_min=it["il_min"],
            # seuil a 2 % de temps mort : au-dela, la conduction est
            # discontinue de facon franche et mesurable
            mode="DCM" if it["frac_morte"] > 0.02 else "CCM",
            frac_morte=round(it["frac_morte"], 4),
            derive_pct=round(it["derive_pct"], 2),
            p_cond_sw=it["p_cond_sw"], p_cond_diode=it["p_cond_diode"],
            p_dcr=it["p_dcr"], p_coss=an["p_coss"], p_gate=an["p_gate"],
            p_total=p_tot, eta_pct=100 * c["pout"] / (c["pout"] + p_tot),
            vsw_max=it["vsw_max"],
        ))

    out = SORTIE / "stage1_dpt_sweep.csv"
    if lignes:
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(lignes[0]))
            w.writeheader()
            w.writerows(lignes)
    print(f"\n{len(lignes)}/{len(cells)} cellules exploitees"
          f" ({echecs} runs en echec)")
    if rejets:
        print(f"{len(rejets)} cellule(s) REJETEE(S) par le bilan d'energie "
              f"(point de fonctionnement non converge) :")
        for c, e, mes, att in rejets:
            print(f"   {c['switch']:13s} {c['diode']:10s} {c['fsw']/1e3:4.0f}k"
                  f" {c['pout']:4.0f}W  I_L {mes:7.3f} A contre {att:6.3f} attendus"
                  f"  (x{mes/max(att,1e-9):.0f})")
    print(f"-> {out}")
    return 0 if lignes else 1


if __name__ == "__main__":
    raise SystemExit(main())
