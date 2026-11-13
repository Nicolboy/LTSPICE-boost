"""Graphiques etage1 (doc/sim-stage1.md) a partir de
results/stage1_{100,200,300,400}khz.csv -- donnees reelles de simulation,
pas de valeurs inventees."""
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FREQS = [100, 200, 300, 400]
PAIRS = ["12V_60V", "20V_80V", "24V_100V"]
PAIR_LABELS = {"12V_60V": "12V->60V", "20V_80V": "20V->80V (nominal)", "24V_100V": "24V->100V"}
COLORS = {"12V_60V": "C0", "20V_80V": "C1", "24V_100V": "C2"}

data = {}
for f in FREQS:
    with open(f"results/stage1_{f}khz.csv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            data[(f, row["pair"], float(row["pout_target"]))] = row

POWERS = [5.0, 10.0, 20.0, 40.0]

fig, axs = plt.subplots(2, 2, figsize=(13, 10))

# --- Rendement vs frequence, au point nominal 40W, par couple ---
ax = axs[0, 0]
for pair in PAIRS:
    etas = [float(data[(f, pair, 40.0)]["eta_pct"]) for f in FREQS]
    ax.plot(FREQS, etas, marker="o", color=COLORS[pair], label=PAIR_LABELS[pair])
ax.set_xlabel("Frequence (kHz)")
ax.set_ylabel("Rendement a 40W (%)")
ax.set_title("Rendement vs frequence (L=47uH fixe, switch/diode ideaux)")
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

# --- Courant crete a 40W vs frequence ---
ax = axs[0, 1]
for pair in PAIRS:
    ipks = [float(data[(f, pair, 40.0)]["ipk_l"]) for f in FREQS]
    ax.plot(FREQS, ipks, marker="s", color=COLORS[pair], label=PAIR_LABELS[pair])
ax.set_xlabel("Frequence (kHz)")
ax.set_ylabel("Ipk inductance a 40W (A)")
ax.set_title("Courant crete vs frequence -- baisse avec f (meme L)")
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

# --- Mode CCM/DCM par point (grille frequence x puissance), au couple nominal ---
ax = axs[1, 0]
pair = "20V_80V"
for i, f in enumerate(FREQS):
    for j, p in enumerate(POWERS):
        row = data.get((f, pair, p))
        if row is None:
            continue
        mode = row["mode_measured"]
        color = "C1" if mode == "CCM" else "C0"
        ax.scatter(p, f, s=300, color=color, marker="s" if mode == "CCM" else "o")
ax.set_xlabel("Puissance (W)")
ax.set_ylabel("Frequence (kHz)")
ax.set_title(f"Mode CCM (orange carre) / DCM (bleu rond) -- {PAIR_LABELS[pair]}")
ax.set_xticks(POWERS)
ax.set_yticks(FREQS)
ax.grid(alpha=0.3)

# --- Mode CCM/DCM au coin le plus dur (24V_100V) ---
ax = axs[1, 1]
pair = "24V_100V"
for i, f in enumerate(FREQS):
    for j, p in enumerate(POWERS):
        row = data.get((f, pair, p))
        if row is None:
            continue
        mode = row["mode_measured"]
        color = "C1" if mode == "CCM" else "C0"
        ax.scatter(p, f, s=300, color=color, marker="s" if mode == "CCM" else "o")
ax.set_xlabel("Puissance (W)")
ax.set_ylabel("Frequence (kHz)")
ax.set_title(f"Mode CCM (orange carre) / DCM (bleu rond) -- {PAIR_LABELS[pair]}")
ax.set_xticks(POWERS)
ax.set_yticks(FREQS)
ax.grid(alpha=0.3)

fig.tight_layout()
fig.savefig("plots/stage1_freq_comparison.png", dpi=140)
print("Ecrit plots/stage1_freq_comparison.png")

# --- Figure 2 : forme d'onde Vds au point nominal, comparaison frequences ---
# (valeurs deja mesurees : Vds_switch_max par frequence au point nominal 40W)
fig2, ax2 = plt.subplots(figsize=(7, 5))
etas_200 = [float(data[(f, "20V_80V", 40.0)]["vds_switch_max"]) for f in FREQS]
ax2.bar([str(f) for f in FREQS], etas_200, color="C1")
ax2.axhline(80, color="red", ls="--", label="Vout cible (80V)")
ax2.set_xlabel("Frequence (kHz)")
ax2.set_ylabel("Vds_switch max (V)")
ax2.set_title("Noeud chaud -- plafonne proprement a Vout (pas de parasite modelise)")
ax2.legend(fontsize=8)
ax2.grid(alpha=0.3, axis="y")
fig2.tight_layout()
fig2.savefig("plots/stage1_vds_hotnode.png", dpi=140)
print("Ecrit plots/stage1_vds_hotnode.png")
