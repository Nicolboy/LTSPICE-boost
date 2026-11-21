"""Oscillogrammes de verification de la configuration retenue.

19 V -> 80 V, 7,72 W, 200 kHz, DCM
SER2211-473 47 uH -- V8PA22 -- IPD530N15N3, Rg 10 ohms, Vgs 10 V
maille de routage 10 nH -- duty 0,588 -- .options cshunt=1e-15

TROIS FIGURES, et chacune repond a une question distincte.

  1  VUE D'ENSEMBLE, instrumentee. Est-ce que le convertisseur fait ce
     qu'on croit ? Rapport cyclique, crete de courant, annulation du
     courant (DCM), tension de drain, charge recue.

  2  LA COUPURE. C'est la que passe l'essentiel des 86,91 mW du
     transistor -- le bilan par regime l'a montre, la courbe doit le
     confirmer. On regarde le recouvrement tension-courant.

  3  LA FERMETURE ET LE TEMPS MORT. Deux resonances DIFFERENTES, pas
     deux harmoniques : la maille Lb-Cj pendant la conduction, et
     l'inductance principale contre les capacites de noeud pendant le
     temps mort. Leurs frequences different d'un facteur 60.

CE QUI EST MESURE ET NON ESTIME : le pas moyen reel, les deux frequences
de resonance par FFT, et le facteur de qualite de la sonnerie de temps
mort avec le rapport de chute REELLEMENT observe -- si la chute est
proche de 1, le tau annonce est une extrapolation et il faut le dire.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parents[2]
sys.path.insert(0, str(RAC / ".claude/skills/oscillogrammes/scripts"))
import oscillo as osc                                        # noqa: E402

FSW, DUTY, VIN, VOUT = 200e3, 0.588, 19.0, 80.0
SIG = ("V(nsw)", "V(ng)", "V(ngg)", "V(nda)", "V(nout)",
       "I(L1)", "I(Vd)", "I(Vbat)", "I(Vsl)", "I(Cosn)", "I(Rgx)")


def main() -> int:
    t, s = osc.charge(str(ICI / "s3.raw"), SIG)
    dmoy, dmax = osc.pas(t)
    print(f"  pas d'integration : moyen {dmoy*1e12:.0f} ps, "
          f"maximum {dmax*1e12:.0f} ps  (dtmax impose 500 ps)")
    print(f"  duree du fichier  : {(t[-1]-t[0])*1e6:.1f} us, "
          f"{len(t)} points")

    # FENETRE CALEE SUR UN EVENEMENT : un front montant de grille, jamais
    # l'origine du fichier ni l'argmax du courant d'inductance (qui tombe
    # PAR CONSTRUCTION sur la coupure dans un boost).
    vg = s["V(ng)"]
    mo = np.where((vg[:-1] < 5.0) & (vg[1:] >= 5.0))[0]
    t0 = t[mo[-3]]
    m = (t >= t0) & (t <= t0 + 2.0 / FSW)
    tw = t[m] - t0
    g = lambda n: s[n][m]
    il, idd, vs = g("I(L1)"), g("I(Vd)"), g("V(nsw)")

    # instants remarquables de la periode
    ph = osc.phases(tw, il, DUTY, FSW)
    print(f"  phases : coupure {ph['t_off']*1e6:.3f} us, "
          f"courant nul {ph['t_i0']*1e6:.3f} us, "
          f"temps mort {(ph['t_fin']-ph['t_i0'])*1e6:.3f} us "
          f"({100*(ph['t_fin']-ph['t_i0'])*FSW:.0f} % de la periode)")

    # --- LES DEUX RESONANCES, mesurees par FFT sur leur propre fenetre --
    mc = (tw > ph["t_on"] + 5e-9) & (tw < ph["t_off"] - 5e-9)   # conduction
    md = (tw > ph["t_i0"] + 50e-9) & (tw < ph["t_fin"] - 20e-9)  # temps mort
    f_hf = osc.frequence(tw[mc], idd[mc] - idd[mc].mean(), bande=(5e7, 9e8))
    duree = tw[md][-1] - tw[md][0]
    f_min = 3.0 / duree           # au moins 3 periodes
    f_tm = osc.frequence(tw[md], vs[md] - vs[md].mean(),
                         bande=(f_min, 2e7))
    dec = (osc.decroissance(tw[md], vs[md] - vs[md].mean(), f_tm)
           if duree * f_tm > 4 else {})
    print(f"  resonance pendant la CONDUCTION : {f_hf/1e6:7.1f} MHz "
          f"(maille Lb - Cj de la diode)")
    print(f"  resonance pendant le TEMPS MORT : {f_tm/1e6:7.2f} MHz "
          f"(L principale - capacites de noeud)")
    if dec.get("tau"):
        print(f"     Q = {dec['q']:.1f}, tau = {dec['tau']*1e9:.0f} ns, "
              f"chute observee {dec.get('chute', float('nan')):.2f}")
        if dec.get("chute", 0) > 0.7:
            print("     ATTENTION : chute proche de 1, le tau est EXTRAPOLE")
    print(f"  rapport des deux : {f_hf/f_tm:.0f}x -- ce ne sont PAS deux "
          f"harmoniques, ce sont deux circuits")

    # ================= FIGURE 1 : vue d'ensemble ======================
    pan = [("grille  [V]",
            [(tw, g("V(ng)"), "V(ng)  driver", dict(color=osc.CYCLE[3],
                                                    ls="--", lw=1.4)),
             (tw, g("V(ngg)"), "V(ngg)  grille du boîtier",
              dict(color=osc.CYCLE[1], lw=1.2))]),
           ("drain  [V]",
            [(tw, vs, "V(nsw)", dict(color=osc.CYCLE[0], lw=1.2)),
             (tw, g("V(nda)"), "V(nda)  après la maille",
              dict(color=osc.CYCLE[4], ls="--", lw=1.6))]),
           ("courant\ninductance  [A]",
            [(tw, il, "I(L1)", dict(color=osc.CYCLE[2], lw=1.3))]),
           ("courant\ndiode  [A]",
            [(tw, idd, "I(Vd)", dict(color=osc.CYCLE[5], lw=1.2))])]
    mes = [
        dict(n=1, panneau=2, libelle="courant crête", genre="point",
             t=tw[int(np.argmax(il))], y=float(il.max()),
             valeur=f"{il.max():.3f} A"),
        dict(n=2, panneau=2, libelle="courant minimum", genre="niveau",
             y=float(il.min()), valeur=f"{il.min():+.3f} A", repere=False),
        dict(n=3, panneau=2, libelle="conduction", genre="intervalle",
             t1=ph["t_on"], t2=ph["t_off"], y=float(il.max()) * .45,
             valeur=f"{ph['t_off']*1e9:.0f} ns   D = {ph['t_off']*FSW:.3f}"),
        dict(n=4, panneau=2, libelle="transfert", genre="intervalle",
             t1=ph["t_off"], t2=ph["t_i0"], y=float(il.max()) * .25,
             valeur=f"{(ph['t_i0']-ph['t_off'])*1e9:.0f} ns"),
        dict(n=5, panneau=2, libelle="temps mort  (DCM)", genre="intervalle",
             t1=ph["t_i0"], t2=ph["t_fin"], y=float(il.max()) * .12,
             valeur=f"{(ph['t_fin']-ph['t_i0'])*1e9:.0f} ns"),
        dict(n=6, panneau=1, libelle="drain, maximum", genre="point",
             t=tw[int(np.argmax(vs))], y=float(vs.max()),
             valeur=f"{vs.max():.1f} V"),
        dict(n=7, panneau=1, libelle="drain, minimum", genre="point",
             t=tw[int(np.argmin(vs))], y=float(vs.min()),
             valeur=f"{vs.min():+.2f} V   diode de corps"),
        dict(n=8, panneau=1, libelle="marge sur 150 V", genre="niveau",
             y=150.0, valeur=f"{100*(150-vs.max())/150:.0f} %"),
        dict(n=9, panneau=0, libelle="grille, maximum", genre="point",
             t=tw[int(np.argmax(g('V(ngg)')))], y=float(g("V(ngg)").max()),
             valeur=f"{g('V(ngg)').max():.2f} V   sur ±20 V"),
        dict(n=10, panneau=3, libelle="diode, crête", genre="point",
             t=tw[int(np.argmax(idd))], y=float(idd.max()),
             valeur=f"{idd.max():.3f} A"),
        dict(n=11, panneau=3, libelle="pointe à la fermeture",
             genre="point", t=tw[int(np.argmin(idd))], y=float(idd.min()),
             valeur=f"{idd.min():+.2f} A"),
    ]
    osc.trace_annote(
        pan, mes, ICI / "oscillo_1_ensemble.png",
        titre="VÉRIFICATION — boost 19 V → 80 V, 7,72 W, 200 kHz, DCM   ·   "
              "SER2211-473 · V8PA22 · IPD530N15N3 $R_g$ = 10 Ω",
        notes=(f"pas d'intégration : {dmoy*1e12:.0f} ps moyen, "
               f"{dmax*1e12:.0f} ps max",
               f"rendement 96,31 %   pertes 296,25 mW",
               f"bilan fermé à 0,02 %   régime établi à 0,000 %"))
    print("  oscillo_1_ensemble.png")

    # ================= FIGURE 2 : la coupure ==========================
    w = (tw > ph["t_off"] - 20e-9) & (tw < ph["t_off"] + 160e-9)
    tz = (tw[w] - ph["t_off"])
    isw = g("I(Vsl)")[w] - idd[w] - g("I(Cosn)")[w]
    pw = vs[w] * isw
    pan2 = [("drain  [V]", [(tz, vs[w], "V(nsw)",
                             dict(color=osc.CYCLE[0], lw=1.4))]),
            ("courants  [A]",
             [(tz, isw, "transistor", dict(color=osc.CYCLE[1], lw=1.4)),
              (tz, il[w], "inductance", dict(color=osc.CYCLE[2], lw=1.2)),
              (tz, idd[w], "diode", dict(color=osc.CYCLE[5], lw=1.2))]),
            ("puissance\ninstantanée  [W]",
             [(tz, pw, "V(nsw) × I(transistor)",
               dict(color=osc.CYCLE[4], lw=1.4))])]
    w60 = tz <= 60e-9
    e_off = float(np.trapezoid(pw[w60], tz[w60]))      # NET
    e_pos = float(np.trapezoid(np.maximum(pw[w60], 0), tz[w60]))
    mes2 = [
        dict(n=1, panneau=2, libelle="pic de recouvrement", genre="point",
             t=tz[int(np.argmax(pw))], y=float(pw.max()),
             valeur=f"{pw.max():.1f} W"),
        dict(n=2, panneau=2, libelle="énergie de la coupure",
             genre="intervalle", t1=0.0, t2=60e-9, y=float(pw.max()) * .45,
             valeur=f"{e_off*1e9:.0f} nJ net = {e_off*FSW*1e3:.1f} mW"),
        dict(n=3, panneau=0, libelle="pente de montée", genre="point",
             t=tz[int(np.argmax(np.gradient(vs[w], tz)))],
             y=float(vs[w][int(np.argmax(np.gradient(vs[w], tz)))]),
             valeur=f"{np.gradient(vs[w], tz).max()/1e9:.1f} V/ns"),
        dict(n=4, panneau=1, libelle="courant commuté", genre="point",
             t=0.0, y=float(np.interp(0.0, tz, il[w])),
             valeur=f"{np.interp(0.0, tz, il[w]):.3f} A"),
    ]
    osc.trace_annote(
        pan2, mes2, ICI / "oscillo_2_coupure.png",
        titre="LA COUPURE — où passe l'essentiel des 86,91 mW du transistor",
        xlabel="temps depuis la coupure  [µs]",
        notes=("le recouvrement tension-courant est le mécanisme,",
               "pas la conduction : 53 mΩ × 1,15 A² ne font que 8 mW",
               "",
               f"la coupure seule porte {e_off*FSW*1e3:.0f} mW NETS, pour "
               f"{86.91:.0f} mW",
               "sur la période entière : le reste du cycle en rend",
               f"({e_pos*FSW*1e3:.0f} mW si on ne compte que le positif,",
               "ce qui n'est pas une dissipation)"))
    print("  oscillo_2_coupure.png")

    # ========== FIGURE 3 : fermeture et temps mort ====================
    w3 = (tw > ph["t_i0"] - 100e-9) & (tw < ph["t_fin"] + 300e-9)
    tz3 = tw[w3] - ph["t_i0"]
    pan3 = [("drain  [V]", [(tz3, vs[w3], "V(nsw)",
                             dict(color=osc.CYCLE[0], lw=1.3))]),
            ("courant\ndiode  [A]", [(tz3, idd[w3], "I(Vd)",
                                      dict(color=osc.CYCLE[5], lw=1.2))]),
            ("courant\ninductance  [A]", [(tz3, il[w3], "I(L1)",
                                           dict(color=osc.CYCLE[2],
                                                lw=1.3))])]
    mes3 = [
        dict(n=1, panneau=0, libelle="résonance temps mort", genre="point",
             t=tz3[int(np.argmax(vs[w3]))], y=float(vs[w3].max()),
             valeur=f"{f_tm/1e6:.2f} MHz"),
        dict(n=2, panneau=0, libelle="  Q (sonnerie LIBRE)", genre="niveau",
             y=float(np.mean(vs[w3])), repere=False,
             valeur="23   1,027 MHz, chute ×50"),
        dict(n=12, panneau=0, libelle="  écrêtage diode de corps",
             genre="niveau", y=0.0, repere=False,
             valeur="~300 ns à 0 V"),
        dict(n=3, panneau=0, libelle="  amplitude crête-à-crête",
             genre="intervalle", t1=tz3[0], t2=tz3[-1],
             y=float(vs[w3].min()) + 3,
             valeur=f"{vs[w3].max()-vs[w3].min():.1f} V"),
        dict(n=4, panneau=0, libelle="écrêtée par la diode de corps",
             genre="point", t=tz3[int(np.argmin(vs[w3]))],
             y=float(vs[w3].min()), valeur=f"{vs[w3].min():+.2f} V"),
        dict(n=5, panneau=1, libelle="résonance conduction", genre="point",
             t=tz3[int(np.argmin(idd[w3]))], y=float(idd[w3].min()),
             valeur=f"{f_hf/1e6:.0f} MHz   maille $L_b$–$C_j$"),
        dict(n=6, panneau=2, libelle="courant nul : DCM confirmé",
             genre="niveau", y=0.0, valeur=f"min {il[w3].min():+.3f} A"),
    ]
    osc.trace_annote(
        pan3, mes3, ICI / "oscillo_3_tempsmort.png",
        titre="LE TEMPS MORT ET LA FERMETURE — deux résonances, deux circuits",
        xlabel="temps depuis l'annulation du courant  [µs]",
        notes=(f"{f_hf/1e6:.0f} MHz contre {f_tm/1e6:.2f} MHz, "
               f"soit un facteur {f_hf/f_tm:.0f} :",
               "ce ne sont pas deux harmoniques, ce sont deux circuits",
               "la maille de routage d'un côté, l'inductance principale "
               "de l'autre",
               "",
               "LE TEMPS MORT N'EST PAS UNE SONNERIE LIBRE : le drain reste",
               "plat à 0 V pendant ~300 ns, écrêté par la diode de corps.",
               "Le Q ne s'y mesure donc pas — il vient de la figure 4,",
               "où la commande est coupée et le circuit sonne seul."))
    print("  oscillo_3_tempsmort.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
