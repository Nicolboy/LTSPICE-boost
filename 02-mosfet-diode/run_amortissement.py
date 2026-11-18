"""Execution du banc d'amortissement et production des figures.

Un seul point de fonctionnement, cinq variantes d'inductance, le MEME
rapport cyclique pour toutes : c'est la condition pour que l'ecart observe
soit imputable au modele d'inductance et a rien d'autre. Le rapport
cyclique est cale une fois sur la variante `constructeur`, qui est la
reference physique.
"""
from __future__ import annotations

import sys
import time
import numpy as np

import test_amortissement as ta
import analyse_amortissement as an

# waterfall : fourni par la skill `spectrogrammes`, utilise tel quel --
# c'est aussi la facon de verifier qu'elle sert hors de son cadre d'origine.
sys.path.insert(0, str(ta.RACINE / ".claude/skills/spectrogrammes/scripts"))
import spectres as sp                                           # noqa: E402

VARIANTES = ("ideal", "dcr_reelle", "pkz", "constructeur", "snubber")
DTMAX = 0.1e-9
SIG = ("V(nsw)", "I(Vl)", "V(nda)", "V(nd)")


def cale_duty(cible=ta.P_VISEE, tol=0.01):
    """Secante sur la puissance de sortie, variante `constructeur`."""
    d, hist = ta.duty_dcm(cible), []
    for _ in range(5):
        r = ta.run("cal", ta.netlist("constructeur", d, n_etab=2, n_mes=2,
                                     dtmax=0.25e-9))
        p = r["meas"]["pout"]
        hist.append((d, p))
        print(f"    calage : D = {d:.5f} -> {p:6.2f} W")
        if abs(p - cible) / cible < tol:
            return d
        if len(hist) >= 2 and abs(hist[-1][1] - hist[-2][1]) > 1e-9:
            (d0, p0), (d1, p1) = hist[-2], hist[-1]
            d = d1 + (cible - p1) * (d1 - d0) / (p1 - p0)
        else:
            d = d * np.sqrt(cible / max(p, 1e-3))
    return d


def main():
    an.style_sombre()
    ta.FIGURES.mkdir(parents=True, exist_ok=True)

    print("== calage du rapport cyclique ==")
    duty = cale_duty()
    print(f"   retenu D = {duty:.5f}\n")

    # ------------------------------------------------- impedance (AC, rapide)
    print("== impedance propre de l'inductance ==")
    ac = {}
    for v in ("ideal", "dcr_reelle", "pkz", "constructeur"):
        txt = ta.netlist_ac(v).replace(".ac dec 400", ".ac dec 3000")
        r = ta.run(f"ac_{v}", txt)
        f, s = ta.lit_raw(r["raw"], ["V(n1)"])
        f = np.abs(np.asarray(f, dtype=float)) if not np.iscomplexobj(f) \
            else np.abs(f.real)
        ac[v] = (f, np.abs(s["V(n1)"]))
        z = ac[v][1]
        print(f"   {v:14s} SRF {f[np.argmax(z)]/1e6:6.2f} MHz   "
              f"|Z| crete {z.max():9.1f} ohm")

    # --------------------------------------------------------- transitoires
    print("\n== transitoires ==")
    don, mes = {}, {}
    tsw = 1.0 / ta.FSW
    for v in VARIANTES:
        t0 = time.time()
        r = ta.run(v, ta.netlist(v, duty, dtmax=DTMAX))
        t, s = ta.lit_raw(r["raw"], SIG)
        t = t - t[0]
        s = {k: np.asarray(w, dtype=float).real for k, w in s.items()}
        tu, yu, pas = an.uniforme(t, s["V(nsw)"])
        don[v] = dict(t=t, sig=s, tu=tu - tu[0], yu=yu, meas=r["meas"],
                      pas=pas)
        don[v]["fft"] = an.fft_amplitude(yu, an.DT_GRILLE)

        # --- decoupage d'une periode : coupure, annulation du courant
        t_off = duty * tsw
        t_i0 = an.fin_conduction(t, s["I(Vl)"], t_off)
        d_deb, d_fin = t_i0 + 20e-9, tsw - 30e-9

        # raie de temps mort, sur le seul intervalle a courant nul
        m = (tu - tu[0] >= d_deb) & (tu - tu[0] <= d_fin)
        spm = an.fft_amplitude(yu[m], an.DT_GRILLE, pad=8)
        don[v]["fft_mort"] = spm
        f_bf, _ = an.raie(*spm, 8e5, 2.5e7)
        q_bf, tau = an.facteur_qualite((tu[m] - tu[m][0]), yu[m], f_bf)

        # Raie de maille, sur les 120 ns qui suivent la coupure. La salve
        # est courte : sans completement par zeros le sommet s'accroche au
        # bin le plus proche et la "mesure" ne fait que rendre la grille
        # (une fenetre de 40 ns donnait 25,0 puis 100,0 MHz pile, soit les
        # bins 1 et 4 d'un pas de 25 MHz).
        mh = (tu - tu[0] >= t_off) & (tu - tu[0] <= t_off + 120e-9)
        f_hf, _ = an.raie(*an.fft_amplitude(yu[mh], an.DT_GRILLE, pad=16),
                          2e7, 6e8)

        mes[v] = dict(f_bf=f_bf, q_bf=q_bf, tau=tau, f_hf=f_hf,
                      t_i0=t_i0, d_deb=d_deb, d_fin=d_fin,
                      vpk=r["meas"]["vpk"], pout=r["meas"]["pout"],
                      psn=r["meas"].get("psn"))
        print(f"   {v:14s} {time.time()-t0:5.1f}s  Pout {r['meas']['pout']:5.2f} W"
              f"   pas moyen {pas*1e12:4.0f} ps"
              f"   f_BF {f_bf/1e6:5.2f} MHz  Q {q_bf:9.1f}"
              f"   f_HF {f_hf/1e6:6.1f} MHz", flush=True)

    # ------------------------------------------------------ sonnerie libre
    print("\n== sonnerie libre (mesure propre du facteur de qualite) ==")
    son = {}
    for v in ("ideal", "dcr_reelle", "pkz", "constructeur", "snubber"):
        r = ta.run(f"son_{v}", ta.netlist(v, duty, n_etab=6, dtmax=0.25e-9,
                                          sonnerie=30e-6))
        t, s = ta.lit_raw(r["raw"], ["V(nsw)"])
        t = t - t[0]
        tu, yu, _ = an.uniforme(t, np.asarray(s["V(nsw)"], float).real)
        tu = tu - tu[0]
        # on demarre 0,5 us apres la coupure : le temps que la diode cesse
        # de conduire et que le regime devienne une sonnerie libre.
        m = tu >= 0.5e-6
        tt, yy = tu[m] - tu[m][0], yu[m]
        f0, _ = an.raie(*an.fft_amplitude(yy, an.DT_GRILLE, pad=4), 8e5, 2.5e7)
        d = an.decroissance(tt, yy, f0)
        # `d` rend une base de temps RACCOURCIE (bords de convolution) :
        # on garde les deux, sans quoi le trace melange deux longueurs.
        son[v] = dict(t_plein=tt, y=yy, f0=f0, **d)
        mes[v]["q_son"], mes[v]["tau_son"] = d["q"], d["tau"]
        mes[v]["chute"] = d["chute"]
        print(f"   {v:14s} f0 {f0/1e6:5.2f} MHz   tau {d['tau']*1e6:7.2f} us"
              f"   Q {d['q']:7.0f}   chute observee x{d['chute']:.1f}",
              flush=True)

    # ----------------------------------------------------------- figures
    print("\n== figures ==")
    ref = mes["constructeur"]
    an.figure_mesuree(don, mes, duty, ta.FIGURES / "01-temps-plein.png")
    an.figure_zoom(don, mes, ref["d_deb"], ref["d_fin"],
                   ta.FIGURES / "02-zoom-temps-mort.png")
    an.figure_fft(don, mes, ta.FIGURES / "03-fft.png")
    an.figure_sonnerie(son, ta.FIGURES / "06-sonnerie-libre.png")
    an.figure_stft(don, duty, ta.FIGURES / "04-fft-court-terme.png")
    an.figure_impedance(ac, ta.FIGURES / "05-impedance-inductance.png")

    # --- waterfall : UNE periode de decoupage par tranche. C'est la seule
    # representation qui montre la reproductibilite d'une periode a la
    # suivante. La resonance de temps mort est a 3,73 MHz pour 400 kHz de
    # decoupage, soit un rapport de 9,33 : non entier, donc la phase a
    # l'allumage derive d'une periode a l'autre tant que rien ne l'amortit.
    # --- waterfall : DEUX periodes de trace, 14 tranches d'UNE periode
    # entiere chacune. La fenetre glisse donc a l'interieur de la periode
    # de decoupage, au lieu de sauter de periode en periode : on voit
    # quelle portion du cycle porte quel contenu, tout en gardant le
    # fondamental resolu. Le waterfall jointif sur 8 periodes, lui, ne
    # montrait qu'une chose -- que le regime est periodique -- ce que
    # l'allumage garantit en court-circuitant le noeud a chaque cycle.
    n_tr = 14
    for v in ("ideal", "constructeur"):
        yu = don[v]["yu"][:int(round(2.0 / ta.FSW / an.DT_GRILLE))]
        f, spx, duree, dep = sp.waterfall(yu, an.DT_GRILLE, ta.FSW,
                                          periodes=1, n_tranches=n_tr)
        sp.trace_waterfall(
            f, spx, ta.FIGURES / f"07-waterfall-{v}.png", duree=duree,
            bande=(3e5, 1.5e8), plage_db=75.0,
            titre=f"Waterfall — {an.ETIQ[v]}",
            bornes=(f"fenêtre à t = {dep[0]*1e9:.0f} ns",
                    f"t = {dep[-1]*1e9:.0f} ns"),
            # La 1re et la 14e tranche demarrent a la MEME phase du
            # decoupage (glissement total = une periode pile) : sur un
            # regime periodique elles doivent coincider. C'est un controle
            # de coherence gratuit, porte par la figure elle-meme.
            lecture="fenêtre d'une période entière glissant à l'intérieur "
                    "de la période de découpage\nla 1ʳᵉ et la 14ᵉ tranche "
                    "sont à la même phase : sur un régime périodique, "
                    "elles doivent coïncider")

    # -------------------------------------------------------- recapitulatif
    lignes = [f"Amortissement du temps mort -- {ta.VIN:.0f} V / {ta.VOUT:.0f} V, "
              f"{ta.FSW/1e3:.0f} kHz, D = {duty:.5f}",
              f"grille de reechantillonnage {an.DT_GRILLE*1e12:.0f} ps, "
              f"fenetre {ta.N_MES} periodes",
              "",
              f"{'variante':<14}{'Pout':>7}{'Vpk':>7}{'f_BF':>9}{'f_HF':>9}"
              f"{'tau(son)':>10}{'Q(son)':>9}{'chute':>8}{'Psnub':>8}",
              "Q et tau viennent de la SONNERIE LIBRE sur 30 us, pas de "
              "l'ajustement sur le seul temps mort.",
              "`chute` = rapport d'amplitude reellement observe sur la "
              "plage ajustee ; proche de 1, tau est extrapole."]
    for v in VARIANTES:
        m = mes[v]
        q = f"{m['q_son']:.0f}" if np.isfinite(m["q_son"]) else "inf"
        tau = f"{m['tau_son']*1e6:.2f} us" if np.isfinite(m["tau_son"]) else "-"
        psn = f"{m['psn']*1e3:.0f} mW" if m["psn"] is not None else "-"
        lignes.append(f"{v:<14}{m['pout']:6.2f}W{m['vpk']:6.1f}V"
                      f"{m['f_bf']/1e6:8.2f}M{m['f_hf']/1e6:8.1f}M"
                      f"{tau:>10}{q:>9}{'x%.1f' % m['chute']:>8}{psn:>8}")
    txt = "\n".join(lignes)
    (ta.TRAVAIL / "recapitulatif.txt").write_text(txt, encoding="utf-8")
    print("\n" + txt)
    print(f"\nfigures -> {ta.FIGURES}")


if __name__ == "__main__":
    main()
