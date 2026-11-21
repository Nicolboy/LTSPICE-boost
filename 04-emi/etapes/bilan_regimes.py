"""Le bilan de puissance, décomposé selon les TROIS régimes.

L'analyse de la résonance HF prédit une chose vérifiable : l'énergie
injectée dans la maille à chaque fermeture vaut 1/2.Cj.deltaV^2, et elle
finit intégralement en chaleur dans la résistance de la maille (canal du
MOSFET + Rs de la diode), puisque la sonnerie s'amortit complètement avant
l'ouverture suivante.

Si c'est vrai, alors :

    P_resonance = 1/2.Cj.deltaV^2.f   DOIT être retrouvée, à quelques
                                      pour cent près, par l'intégration
                                      directe de I_rms^2.R sur la fenêtre
                                      de conduction du MOSFET.

Deux chemins indépendants vers le même nombre. C'est le recoupement W3 du
gendarme, appliqué à la conclusion qu'on vient de tirer.

DÉCOUPAGE DE LA PÉRIODE
  1 TRANSFERT   grille basse, diode conductrice  -- le courant décroît
  2 TEMPS MORT  grille basse, diode bloquée      -- sonnerie ~3 MHz
  3 CONDUCTION  grille haute                     -- sonnerie HF Lb-Cj
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parents[2]
for q in (ICI, RAC / ".claude/skills/sim-spice/scripts",
          RAC / ".claude/skills/sim-commun"):
    sys.path.insert(0, str(q))
from gendarme import recoupe, REFUS                          # noqa: E402
from simcommun.lecture import lire                           # noqa: E402

FSW, LB, RON = 200e3, 10e-9, 0.053
# (fichier, libellé, modèle d'inductance, Cj déduite de la fréquence)
CAS = (("s0", "ÉTAPE 0  tout idéal", False, 11.67e-12, 0.020),
       ("s1", "ÉTAPE 1  + SER2211", True, 11.67e-12, 0.020),
       ("s2", "ÉTAPE 2  + V8PA22", True, 45.19e-12, None),
       ("s3", "ÉTAPE 3  + IPD530N15N3", True, 45.19e-12, None))


def decoupe(r, sl, tt):
    """Les trois régimes, par des critères DISJOINTS et exhaustifs.

    PREMIÈRE VERSION FAUSSE, et instructive. Elle cherchait le premier
    bloc continu où la diode conduit, en partant du premier point à
    grille basse. Or la fenêtre est calée sur `np.where(vg[:-1] < 2.5 &
    vg[1:] >= 2.5)`, qui rend l'indice AVANT le franchissement : le point
    0 est donc le dernier point bas d'avant le front, pas une retombée.
    La boucle démarrait là, n'y trouvait aucun courant de diode, et
    cassait aussitôt. Résultat : une colonne TRANSFERT à 0,00 mW sur les
    trois étapes -- un zéro parfaitement net, qui ressemblait à un
    résultat.

    CRITÈRE JUSTE, et exact en DCM : le transfert va de chaque RETOMBÉE
    de grille au premier passage par zéro de I(L1). C'est la définition
    même du mode, pas un seuil ajusté.
    """
    g = lambda n: np.asarray(r.trace(n)).real[sl]
    on = g("V(ng)") > 2.5
    il = g("I(L1)")
    tr = np.zeros_like(on)
    for d in np.where(on[:-1] & ~on[1:])[0] + 1:        # retombées vraies
        k = d
        while k < len(on) and not on[k] and il[k] > 0.0:
            tr[k] = True
            k += 1
    mort = (~on) & (~tr)
    return on, tr, mort


def main() -> int:
    print("  BILAN DE PUISSANCE DÉCOMPOSÉ PAR RÉGIME")
    print("  fenêtre de 4 périodes entières, calée sur les fronts de grille")
    griefs = []
    for f, lib, ser, cj, rs_d in CAS:
        r = lire(str(ICI / f"{f}.raw"))
        t = np.asarray(r.x)
        vg = np.asarray(r.trace("V(ng)")).real
        mo = np.where((vg[:-1] < 2.5) & (vg[1:] >= 2.5))[0]
        sl = slice(mo[-5], mo[-1] + 1)
        tt = t[sl]
        T = tt[-1] - tt[0]
        g = lambda n: np.asarray(r.trace(n)).real[sl]
        moy = lambda y: float(np.trapezoid(y, tt) / T)

        vs, vo, vda = g("V(nsw)"), g("V(nout)"), g("V(nda)")
        idd, icos, il = g("I(Vd)"), g("I(Cosn)"), g("I(L1)")
        isw = g("I(Vsl)") - idd - icos
        on, tr, mort = decoupe(r, sl, tt)

        pert = {}
        if ser:
            pert["L.Rp"] = (g("I(Rp_l)") ** 2) * 7315.89
            pert["L.Rs"] = (g("I(Rs_l)") ** 2) * 0.0107
            pert["L.Rc"] = (g("I(Cp_l)") ** 2) * 140.0
        else:
            pert["L.DCR"] = (il ** 2) * 0.0107
        pert["S1"] = vs * isw
        pert["D1"] = (vda - vo) * idd

        print(f"\n  === {lib} ===")
        print(f"    {'élément':10s} {'1 TRANSFERT':>13s} {'2 TEMPS MORT':>14s} "
              f"{'3 CONDUCTION':>14s} {'TOTAL':>11s}")
        print("    " + "-" * 66)
        col = np.zeros(3)
        tot = 0.0
        for k, p in pert.items():
            v = [float(np.trapezoid(np.where(m, p, 0.0), tt) / T)
                 for m in (tr, mort, on)]
            col += np.array(v)
            tot += sum(v)
            print(f"    {k:10s} {v[0]*1e3:10.2f} mW {v[1]*1e3:11.2f} mW "
                  f"{v[2]*1e3:11.2f} mW {sum(v)*1e3:8.2f} mW")
        print("    " + "-" * 66)
        print(f"    {'TOTAL':10s} {col[0]*1e3:10.2f} mW {col[1]*1e3:11.2f} mW "
              f"{col[2]*1e3:11.2f} mW {tot*1e3:8.2f} mW")
        part = 100 * col / tot
        print(f"    {'part':10s} {part[0]:11.1f} % {part[1]:12.1f} % "
              f"{part[2]:12.1f} %")
        duree = [100 * float(np.trapezoid(m.astype(float), tt)) / T
                 for m in (tr, mort, on)]
        print(f"    {'durée':10s} {duree[0]:11.1f} % {duree[1]:12.1f} % "
              f"{duree[2]:12.1f} %")

        # --- LE RECOUPEMENT ---------------------------------------------
        # voie A : l'énergie stockée dans Cj au moment de la fermeture,
        #          restituée fsw fois par seconde
        j = int(mo[-2])
        vav = float(np.mean(np.asarray(r.trace("V(nsw)")).real[j - 6:j - 1]))
        dv = abs(vav)
        pa = 0.5 * cj * dv ** 2 * FSW
        # voie B : l'intégration directe de r.i^2 sur la maille, pendant
        #          la seule conduction du MOSFET
        iring = idd[on]
        tring = tt[on]
        irms2 = float(np.trapezoid((iring - iring.mean()) ** 2, tring)
                      / (tring[-1] - tring[0]))
        # LA RÉSISTANCE DE LA MAILLE SE MESURE, ELLE NE SE DEVINE PAS.
        # Première version : Ron du `.model` plus le RS déclaré de la
        # diode. Les deux voies divergeaient de 43 à 48 %. La maille
        # contient aussi la résistance dynamique de la jonction et ce que
        # le modèle encapsulé ajoute -- rien de tout cela n'est lisible
        # dans la netlist. Mais l'amortissement mesuré le donne :
        #     Q = pi.f0.tau   et   R = Z0 / Q
        # C'est une grandeur relevée sur la courbe, pas un paramètre.
        w = (tt > tt[on][0] + 2e-9) & (tt < tt[on][0] + 80e-9)
        iz = idd[w] - idd[w].mean()
        zc = np.where((iz[:-1] < 0) & (iz[1:] >= 0))[0]
        f0 = (len(zc) - 1) / (tt[w][zc[-1]] - tt[w][zc[0]])
        pk = np.where((iz[1:-1] > iz[:-2]) & (iz[1:-1] > iz[2:]))[0] + 1
        pk = pk[iz[pk] > 0]
        co = np.polyfit(tt[w][pk] - tt[w][pk[0]],
                        np.log(np.maximum(iz[pk], 1e-9)), 1)
        tau = -1 / co[0]
        z0 = np.sqrt(LB / cj)
        rb = z0 / (np.pi * f0 * tau)
        pb = irms2 * rb * (tring[-1] - tring[0]) / T
        print(f"\n    RÉSONANCE HF — deux voies indépendantes")
        print(f"      A  1/2.Cj.dV^2.f   avec Cj = {cj*1e12:.1f} pF, "
              f"dV = {dv:.1f} V   -> {pa*1e3:7.3f} mW")
        print(f"      B  I_rms^2.R       avec I_rms = {np.sqrt(irms2)*1e3:.0f} mA, "
              f"R = {rb*1e3:.0f} mohm -> {pb*1e3:7.3f} mW")
        print(f"         R mesuree par l'amortissement : f0 = {f0/1e6:.0f} MHz, "
              f"tau = {tau*1e9:.0f} ns, Q = {np.pi*f0*tau:.0f}, Z0 = {z0:.1f} ohm")
        gr = recoupe(pa, pb, "résonance HF", tol=0.20)
        griefs += gr
        for x in gr:
            print(f"      [{x.rang}] {x.texte[:84]}")
        if not gr:
            print(f"      les deux voies concordent "
                  f"({100*abs(pa-pb)/max(pa, pb):.0f} % d'écart)")
        print(f"      soit {100*pa/tot:.2f} % des pertes totales")
    return 1 if any(x.rang == REFUS for x in griefs) else 0


if __name__ == "__main__":
    raise SystemExit(main())
