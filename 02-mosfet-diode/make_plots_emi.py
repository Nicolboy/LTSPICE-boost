"""Graphiques du volet EMI/resonance (doc/sim-stage2-emi.md) --
donnees reelles de estimate_switch_losses.py / run_resonance_check.py,
memes conventions de style que make_plots_tech.py."""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from estimate_switch_losses import estimate, load_nominal_points
from switch_diode_models import REAL_DIODES, REAL_SWITCHES

SWITCH_COLOR = {"IPD050N10N5": "C0", "SUD70090E": "C1", "NVD6824NL": "C2"}


def make_switch_losses_figure(out="plots/emi_switch_losses.png"):
    """Un sous-graphe par transistor -- 3 courbes (P_cond/P_sw/P_total)
    en fonction de fsw, pas un empilement -- pour voir directement
    lequel des deux termes domine et comment la somme evolue."""
    points = load_nominal_points()
    fsw_list = [p["fsw_khz"] for p in points]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharey=True)
    for ax, sw_name in zip(axes, REAL_SWITCHES):
        p_cond = [estimate(sw_name, p)["p_cond"] * 1e3 for p in points]
        p_sw = [estimate(sw_name, p)["p_sw"] * 1e3 for p in points]
        p_total = [c + s for c, s in zip(p_cond, p_sw)]
        ax.plot(fsw_list, p_cond, marker="o", label="P_cond",
                color=SWITCH_COLOR[sw_name], ls="--")
        ax.plot(fsw_list, p_sw, marker="s", label="P_sw",
                color=SWITCH_COLOR[sw_name], ls=":")
        ax.plot(fsw_list, p_total, marker="^", label="P_total",
                color=SWITCH_COLOR[sw_name], ls="-", lw=2)
        ax.set_xticks(fsw_list)
        ax.set_xticklabels([f"{f:.0f}k" for f in fsw_list])
        ax.set_title(sw_name)
        ax.set_xlabel("fsw (Hz)")
        ax.grid(alpha=0.3)
        if ax is axes[0]:
            ax.set_ylabel("Pertes switch (mW)")
        ax.legend(fontsize=8)
    fig.suptitle("Pertes switch a vitesse native -- conduction, "
                  "commutation et somme (20V->80V/40W, L=47uH)")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print(f"Ecrit {out}")


def make_resonance_figure(rows, out="plots/emi_resonance_overshoot.png"):
    labels = [f"{r['switch']}\n{r['diode']}" for r in rows]
    v_pic = [r["v_pic_calc"] for r in rows]
    v_sim = [r["vds_sim"] for r in rows]
    x = range(len(rows))
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar([i - 0.2 for i in x], v_pic, width=0.4, label="Vpic calcule "
           "(borne sup.)", color="C3", alpha=0.6)
    ax.bar([i + 0.2 for i in x], v_sim, width=0.4, label="Vds simule "
           "(SPICE)", color="C0")
    ax.axhline(80, color="k", ls=":", lw=1, label="Vout_avg nominal")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylim(75, 125)
    ax.set_ylabel("Tension (V)")
    ax.set_title("Dépassement de tension switch : calcul (borne sup.) "
                  "vs simulation, 9 combinaisons")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print(f"Ecrit {out}")


if __name__ == "__main__":
    make_switch_losses_figure()
    import run_resonance_check
    rows = run_resonance_check.main()
    make_resonance_figure(rows)
