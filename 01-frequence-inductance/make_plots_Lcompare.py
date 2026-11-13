"""Graphiques de comparaison d'inductance (doc/sim-stage1.md) a partir de
results/Lcompare_{100,200,300,400}khz.csv -- donnees reelles de
simulation, un graphique par frequence."""
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FAMILY_COLOR = {"SER2211": "C0", "MSS1583": "C1", "MSS1514V": "C2"}
FAMILY_MARKER = {"SER2211": "o", "MSS1583": "s", "MSS1514V": "^"}
FREQS_KHZ = [100, 200, 300, 400]


def family_of(part):
    return part.split("-")[0]


def make_figure(fsw_khz):
    rows = list(csv.DictReader(open(f"results/Lcompare_{fsw_khz}khz.csv", encoding="utf-8")))
    nominal_40w = [r for r in rows if r["pair"] == "20V_80V" and float(r["pout_target"]) == 40.0]

    fig, axs = plt.subplots(2, 2, figsize=(13, 10))
    fig.suptitle(f"Comparaison d'inductance -- {fsw_khz}kHz, point nominal "
                 "20V->80V/40W", fontsize=14)

    # --- Rendement vs L ---
    ax = axs[0, 0]
    seen = set()
    for r in sorted(nominal_40w, key=lambda r: float(r["l_uH"])):
        fam = family_of(r["part"])
        label = fam if fam not in seen else None
        seen.add(fam)
        ax.scatter(float(r["l_uH"]), float(r["eta_pct"]), color=FAMILY_COLOR[fam],
                   marker=FAMILY_MARKER[fam], s=80, label=label)
    ax.set_xscale("log")
    ax.set_xlabel("Inductance (uH)")
    ax.set_ylabel("Rendement a 40W (%)")
    ax.set_title("Rendement vs L")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    # --- Marge Isat vs L ---
    ax = axs[0, 1]
    seen = set()
    for r in sorted(nominal_40w, key=lambda r: float(r["l_uH"])):
        fam = family_of(r["part"])
        label = fam if fam not in seen else None
        seen.add(fam)
        ax.scatter(float(r["l_uH"]), float(r["isat_margin"]), color=FAMILY_COLOR[fam],
                   marker=FAMILY_MARKER[fam], s=80, label=label)
    ax.axhline(1.0, color="red", ls="--", label="marge = 1 (limite)")
    ax.axhline(1.5, color="orange", ls=":", label="marge = 1,5 (prudent)")
    ax.set_xscale("log")
    ax.set_xlabel("Inductance (uH)")
    ax.set_ylabel("Marge Isat (10% drop) a 40W")
    ax.set_title("Marge de saturation vs L")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    # --- Marge Irms (40C rise) vs L ---
    ax = axs[1, 0]
    seen = set()
    for r in sorted(nominal_40w, key=lambda r: float(r["l_uH"])):
        fam = family_of(r["part"])
        label = fam if fam not in seen else None
        seen.add(fam)
        ax.scatter(float(r["l_uH"]), float(r["irms_margin"]), color=FAMILY_COLOR[fam],
                   marker=FAMILY_MARKER[fam], s=80, label=label)
    ax.axhline(1.0, color="red", ls="--", label="marge = 1 (surchauffe)")
    ax.set_xscale("log")
    ax.set_xlabel("Inductance (uH)")
    ax.set_ylabel("Marge Irms (40C rise) a 40W")
    ax.set_title("Marge d'echauffement vs L")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    # --- DCR (donnee datasheet) vs L ---
    ax = axs[1, 1]
    seen = set()
    for r in sorted(nominal_40w, key=lambda r: float(r["l_uH"])):
        fam = family_of(r["part"])
        label = fam if fam not in seen else None
        seen.add(fam)
        ax.scatter(float(r["l_uH"]), float(r["dcr_ohm"]) * 1000, color=FAMILY_COLOR[fam],
                   marker=FAMILY_MARKER[fam], s=80, label=label)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Inductance (uH)")
    ax.set_ylabel("DCR (mOhm, donnee datasheet)")
    ax.set_title("DCR vs L par famille (pas une mesure)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    fig.tight_layout()
    out = f"plots/stage1_Lcompare_{fsw_khz}khz.png"
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"Ecrit {out}")


if __name__ == "__main__":
    for fsw_khz in FREQS_KHZ:
        make_figure(fsw_khz)
