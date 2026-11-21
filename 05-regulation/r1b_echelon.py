"""Réaction de Vout à un échelon de charge, en BOUCLE OUVERTE.

C'est la mesure de ce que la régulation aura à corriger. Deux cas, et
ils ne sont pas symétriques du tout.

PRÉDIT AVANT DE LANCER, par les formules fermées :

  5 W -> 10 W, les deux en DCM, rapport cyclique figé à 0,4198
      Vout^2 - Vin.Vout = R.Vin^2.D^2 / (2.L.f)
      1280 -> 640 ohms  =>  80,0 -> 60,0 V, soit -25 %

  40 W -> 20 W, les deux en CCM, rapport cyclique figé à 0,7509
      Vout = (Vin - I.R_boucle) / (1-D)
      160 -> 320 ohms  =>  79,28 -> 79,49 V, soit +0,26 %

Un facteur CENT entre les deux. En DCM la boucle ouverte est une source
de courant déguisée ; en CCM elle est déjà presque une source de tension.
C'est la raison profonde du gain scheduling : ce ne sont pas deux
réglages d'une même machine, ce sont deux machines.

COUT NE CHANGE PAS CES VALEURS. En boucle ouverte, l'état final est fixé
par la topologie et la charge ; Cout ne règle que la vitesse d'y aller.
On mesure donc avec les 2,2 µF du banc et on lit les mêmes excursions
qu'avec 300 µF, en bien moins de temps.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parent
for q in (str(RAC / "04-emi/etapes"),
          str(RAC.parent / ".claude/skills/sim-commun")):
    sys.path.insert(0, q)
import etape                                                 # noqa: E402
from simcommun.lecture import lire                           # noqa: E402

EXE = r"C:\Program Files\ADI\LTspice\LTspice.exe"
FSW, VIN, VOUT, COUT = 200e3, 20.0, 80.0, 2.2e-6
plt.style.use("dark_background")
F, G, V = "#11141a", "#171b23", "#9aa4b5"
BL, VE, OR, RO, MA = "#4dabf7", "#51cf66", "#ffa94d", "#ff6b6b", "#cc8fff"

#      nom          R init  R fin  duty     n_etab  n_apres  prevu
CAS = (("5 W → 10 W   DCM", 1280.0, 640.0, 0.419820, 2500, 2000, (80.0, 60.0)),
       ("40 W → 20 W  CCM", 160.0, 320.0, 0.750929, 600, 1200, (79.28, 79.49)))


def lance(tag, r0, r1, duty, n_etab, n_ap):
    """Échelon de charge par interrupteur commandé sur une 2e résistance.

    La charge passe de r0 à r1 en MONTANT la résistance : on met donc r1
    en permanence et on PARALLÈLE ce qu'il faut pour obtenir r0, puis on
    ouvre. Pour descendre (5 -> 10 W, R qui baisse), c'est l'inverse.
    """
    n = etape.etape0(p=40.0, vin=VIN, charge=True, rl=r0, cout=COUT,
                     ser=True, v8pa22=True, mos="ipd530", n_etab=n_etab,
                     n_mes=n_ap, dtmax=200e-9, duty=duty)
    t_pas = n_etab / FSW + 0.2e-3          # 200 us après le début de mesure
    if r1 < r0:                             # charge qui AUGMENTE
        rpar = 1.0 / (1.0 / r1 - 1.0 / r0)
        bloc = (f"* echelon : on ajoute {rpar:.2f} ohms a t = {t_pas*1e3:.3f} ms"
                f"{chr(10)}Rstep nout nst {rpar:.4f}"
                f"{chr(10)}Sstep nst 0 nstep 0 MSTEP"
                f"{chr(10)}Vstep nstep 0 PULSE(0 5 {t_pas:.9e} 1n 1n 1 2)"
                f"{chr(10)}.model MSTEP SW(Ron=1m Roff=1g Vt=2.5)")
    else:                                   # charge qui DIMINUE
        rpar = 1.0 / (1.0 / r0 - 1.0 / r1)
        bloc = (f"* echelon : on retire {rpar:.2f} ohms a t = {t_pas*1e3:.3f} ms"
                f"{chr(10)}Rstep nout nst {rpar:.4f}"
                f"{chr(10)}Sstep nst 0 nstep 0 MSTEP"
                f"{chr(10)}Vstep nstep 0 PULSE(5 0 {t_pas:.9e} 1n 1n 1 2)"
                f"{chr(10)}.model MSTEP SW(Ron=1m Roff=1g Vt=2.5)")
    n = n.replace(".options plotwinsize=0", bloc + chr(10) * 2
                  + ".options plotwinsize=256" + chr(10)
                  + ".options cshunt=1e-15")
    n = re.sub(r"(?m)^\.save .*$", "", n).replace(chr(10) * 3, chr(10) * 2)
    n = n.replace(".end", ".save V(nout) V(nstep) I(L1)" + chr(10) + ".end")
    f = ICI / f"{tag}.cir"
    f.write_text(n, encoding="utf-8")
    return f, t_pas


def en_parallele(travaux):
    """Les CAS se parallelisent, le transitoire non.

    LTspice ne repartit pas une seule simulation transitoire sur
    plusieurs coeurs. La seule parallelisation possible est celle des
    cas -- et l'oublier laisse quinze processeurs sur seize inoccupes.
    """
    t0 = time.monotonic()
    procs = [subprocess.Popen([EXE, "-b", str(f)],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL) for f in travaux]
    for pr in procs:
        pr.wait(timeout=7200)
    return time.monotonic() - t0


def main() -> int:
    fig, ax = plt.subplots(2, 2, figsize=(14.6, 8.6), facecolor=F,
                           height_ratios=[1.5, 1])
    prep = [lance(f"st{k}", c[1], c[2], c[3], c[4], c[5])
            for k, c in enumerate(CAS)]
    dur = en_parallele([f for f, _ in prep])
    print(f"  deux cas EN PARALLELE : {dur:.0f} s au total")
    for k, (lib, r0, r1, duty, ne, na, prev) in enumerate(CAS):
        t_pas = prep[k][1]
        r = lire(str(prep[k][0].with_suffix(".raw")))
        t = np.asarray(r.x)
        vo = np.asarray(r.trace("V(nout)")).real
        il = np.asarray(r.trace("I(L1)")).real
        # MOYENNE GLISSANTE PAR SOMME CUMULEE, et non par convolution.
        #
        # `np.convolve` est une convolution DIRECTE, en O(n.m). Ici
        # n = 6,6 millions de points et m = 3293 (une periode de
        # decoupage) : 2.10^10 operations, soit des heures en mono-fil.
        # C'est ce qui laissait Python a 1 % de processeur pendant que
        # LTspice avait fini depuis longtemps -- le gouffre n'etait ni
        # dans la simulation ni dans la lecture du .raw, qui se fait a
        # 18 M points/s, mais dans mon propre code.
        #
        # Une somme cumulee rend la meme moyenne en O(n) : la difference
        # de deux cumuls distants de m points, divisee par m.
        np_ = max(int(round((1 / FSW) / np.median(np.diff(t)))), 3)
        cum = np.concatenate(([0.0], np.cumsum(vo)))
        vm = (cum[np_:] - cum[:-np_]) / np_
        tm = t[np_ // 2: np_ // 2 + len(vm)]
        m = (tm > t_pas - 0.3e-3) & (tm < t_pas + 6e-3)
        tz = (tm[m] - t_pas) * 1e3
        av = float(np.mean(vm[(tm > t_pas - .2e-3) & (tm < t_pas - .02e-3)]))
        ap = float(np.mean(vm[tm > tm[-1] - .3e-3]))
        print(f"\n  === {lib} ===")
        print(f"    avant {av:7.2f} V   apres {ap:7.2f} V   "
              f"ecart {ap-av:+7.2f} V ({100*(ap-av)/av:+.2f} %)")
        print(f"    prevu {prev[0]:7.2f} V         {prev[1]:7.2f} V   "
              f"{prev[1]-prev[0]:+7.2f} V")
        print(f"    ecart mesure / prevu : "
              f"{100*((ap-av)-(prev[1]-prev[0]))/abs(prev[1]-prev[0]):+.1f} %")
        # constante de temps de la reponse
        cible = av + 0.632 * (ap - av)
        idx = np.where((tm > t_pas) & ((vm - cible) * np.sign(ap - av) > 0))[0]
        tau = (tm[idx[0]] - t_pas) * 1e3 if len(idx) else float("nan")
        print(f"    constante de temps {tau:.3f} ms  "
              f"(R_fin.Cout = {r1*COUT*1e3:.3f} ms)")

        a = ax[0, k]
        a.set_facecolor(G); a.grid(alpha=.17, color=V, lw=.6)
        a.tick_params(colors=V, labelsize=9)
        for s in a.spines.values(): s.set_color("#2b3240")
        a.plot(tz, vm[m], color=(BL if k else OR), lw=1.8)
        a.axvline(0, color=VE, ls="--", lw=1.3)
        a.axhline(av, color=V, ls=":", lw=1.0)
        a.axhline(ap, color=V, ls=":", lw=1.0)
        a.text(.02, .5, f"échelon\nde charge", transform=a.transAxes,
               color=VE, fontsize=9, linespacing=1.5)
        a.annotate("", xy=(tz[-1] * .8, ap), xytext=(tz[-1] * .8, av),
                   arrowprops=dict(arrowstyle="<->", color=RO, lw=1.7))
        a.text(tz[-1] * .78, (av + ap) / 2, f"{ap-av:+.2f} V\n"
               f"{100*(ap-av)/av:+.2f} %", color=RO, fontsize=11,
               ha="right", va="center", weight="bold", linespacing=1.5)
        a.set_ylabel("V(nout)  [V]", color=V, fontsize=10.5)
        a.set_title(lib, color=(BL if k else OR), fontsize=12.5, pad=11,
                    weight="bold")
        if k == 0:
            a.set_ylim(55, 85)
        else:
            a.set_ylim(78.8, 79.9)

        a = ax[1, k]
        a.set_facecolor(G); a.grid(alpha=.17, color=V, lw=.6)
        a.tick_params(colors=V, labelsize=9)
        for s in a.spines.values(): s.set_color("#2b3240")
        mm = (t > t_pas - 0.3e-3) & (t < t_pas + 6e-3)
        a.plot((t[mm] - t_pas) * 1e3, il[mm], color=VE, lw=.5)
        a.axvline(0, color=VE, ls="--", lw=1.3)
        a.set_ylabel("I(L1)  [A]", color=V, fontsize=10.5)
        a.set_xlabel("temps depuis l'échelon  [ms]", color=V, fontsize=10.5)
        # on GARDE les .raw : effacer avant d'avoir compris le resultat
        # oblige a tout relancer pour une simple verification.

    fig.suptitle("RÉACTION DE $V_{out}$ À UN ÉCHELON DE CHARGE — "
                 "BOUCLE OUVERTE, rapport cyclique figé",
                 color="#e6e9ef", fontsize=13.5, weight="bold", y=.975)
    fig.text(.5, .018, "En DCM la boucle ouverte est une source de COURANT "
             "déguisée ; en CCM elle est déjà presque une source de tension. "
             "Un facteur CENT sépare les deux — c'est la raison profonde du "
             "gain scheduling.", ha="center", color=VE, fontsize=9.4)
    plt.tight_layout(rect=[0, .035, 1, .96])
    plt.savefig(ICI / "r1b_echelon.png", dpi=112, facecolor=F)
    print("\n  r1b_echelon.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
