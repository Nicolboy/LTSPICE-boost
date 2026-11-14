"""Graphiques chapitre 2 (switch/diode) a partir de
results/stage1_tech_sweep.csv -- donnees reelles de simulation, memes
conventions de style que make_plots_Lcompare.py (ch.1)."""
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FREQS_KHZ = [100, 200, 300, 400]
L_VALUES = [12.0, 27.0, 47.0]
L_NAMES = {12.0: "SER2211-123 (12uH)", 27.0: "SER2211-273 (27uH)",
           47.0: "SER2211-473 (47uH)"}

SWITCH_COLOR = {"Si": "C0", "GaN": "C1"}
DIODE_COLOR = {"Schottky": "C0", "Ultrafast": "C1"}
COMBO_STYLE = {
    ("Si", "Schottky"): dict(color="C0", marker="o", ls="-"),
    ("Si", "Ultrafast"): dict(color="C0", marker="s", ls="--"),
    ("GaN", "Schottky"): dict(color="C1", marker="o", ls="-"),
    ("GaN", "Ultrafast"): dict(color="C1", marker="s", ls="--"),
}


def load(path="results/stage1_tech_sweep.csv"):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _f(r, k):
    v = r.get(k)
    return float(v) if v not in (None, "") else None


def make_switching_loss_figure(rows, out="plots/stage1_tech_switching_loss.png"):
    """Par L (3 lignes) x 2 colonnes : perte de commutation switch
    (Si vs GaN, diode Schottky fixee -- cas propre sans recouvrement) et
    perte de recouvrement diode (Schottky vs Ultrafast, switch Si fixe --
    l'incumbent) vs frequence, point nominal 20V->80V/40W."""
    nominal_40w = [r for r in rows if r["pair"] == "20V_80V"
                   and _f(r, "pout_target") == 40.0]

    fig, axs = plt.subplots(len(L_VALUES), 2, figsize=(12, 4 * len(L_VALUES)))
    fig.suptitle("Chapitre 2 -- pertes de commutation/recouvrement vs "
                  "frequence, point nominal 20V->80V/40W", fontsize=13)

    for i, l_uh in enumerate(L_VALUES):
        # --- switching loss switch : Si vs GaN, diode=Schottky fixee ---
        ax = axs[i, 0]
        for switch_tech in ("Si", "GaN"):
            pts = sorted(
                (r for r in nominal_40w
                 if r["switch_tech"] == switch_tech
                 and r["diode_tech"] == "Schottky"
                 and abs(_f(r, "l_uh") - l_uh) < 0.5),
                key=lambda r: _f(r, "fsw_khz"))
            xs = [_f(r, "fsw_khz") for r in pts]
            ys = [_f(r, "ploss_switch_sw_est") for r in pts]
            ax.plot(xs, ys, color=SWITCH_COLOR[switch_tech], marker="o",
                     label=f"switch={switch_tech}")
        ax.set_xlabel("fsw (kHz)")
        ax.set_ylabel("Ploss_switch_sw_est (W)")
        ax.set_title(f"{L_NAMES[l_uh]} -- commutation switch (diode=Schottky)")
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)

        # --- recovery loss diode : Schottky vs Ultrafast, switch=Si fixe ---
        ax = axs[i, 1]
        for diode_tech in ("Schottky", "Ultrafast"):
            pts = sorted(
                (r for r in nominal_40w
                 if r["diode_tech"] == diode_tech
                 and r["switch_tech"] == "Si"
                 and abs(_f(r, "l_uh") - l_uh) < 0.5),
                key=lambda r: _f(r, "fsw_khz"))
            xs = [_f(r, "fsw_khz") for r in pts]
            ys = [_f(r, "ploss_diode_recovery_est") for r in pts]
            ax.plot(xs, ys, color=DIODE_COLOR[diode_tech], marker="s",
                     label=f"diode={diode_tech}")
        ax.axhline(0.0, color="grey", lw=0.8)
        ax.set_xlabel("fsw (kHz)")
        ax.set_ylabel("Ploss_diode_recovery_est (W)")
        ax.set_title(f"{L_NAMES[l_uh]} -- recouvrement diode (switch=Si)")
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"Ecrit {out}")


def make_efficiency_figure(rows, out="plots/stage1_tech_efficiency.png",
                            l_uh=47.0):
    """Rendement vs Pout, un subplot par frequence, une ligne par
    combinaison switch x diode, a L=47uH (deja valide chapitre 1) et au
    couple nominal 20V->80V."""
    nominal = [r for r in rows if r["pair"] == "20V_80V"
               and abs(_f(r, "l_uh") - l_uh) < 0.5]

    fig, axs = plt.subplots(1, len(FREQS_KHZ), figsize=(5 * len(FREQS_KHZ), 4.5),
                             sharey=True)
    fig.suptitle(f"Chapitre 2 -- rendement vs puissance, {L_NAMES[l_uh]}, "
                  "couple nominal 20V->80V", fontsize=13)

    for ax, fsw_khz in zip(axs, FREQS_KHZ):
        for (switch_tech, diode_tech), style in COMBO_STYLE.items():
            pts = sorted(
                (r for r in nominal
                 if r["switch_tech"] == switch_tech
                 and r["diode_tech"] == diode_tech
                 and abs(_f(r, "fsw_khz") - fsw_khz) < 0.5),
                key=lambda r: _f(r, "pout_target"))
            xs = [_f(r, "pout_target") for r in pts]
            ys = [_f(r, "eta_pct") for r in pts]
            ax.plot(xs, ys, label=f"{switch_tech}+{diode_tech}", **style)
        ax.set_xlabel("Pout (W)")
        ax.set_title(f"{fsw_khz}kHz")
        ax.grid(alpha=0.3)
    axs[0].set_ylabel("Rendement (%)")
    axs[-1].legend(fontsize=8, loc="lower right")

    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"Ecrit {out}")


if __name__ == "__main__":
    rows = load()
    make_switching_loss_figure(rows)
    make_efficiency_figure(rows)
