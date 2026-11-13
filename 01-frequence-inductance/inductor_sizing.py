"""Etape 1/2 : dimensionnement analytique de l'inductance par frequence
candidate, AVANT toute simulation SPICE -- pur calcul, formule boost
ideale.

Frontiere CCM/DCM d'un boost (conduction continue vs discontinue) :
l'ondulation crete-a-crete du courant d'inductance pendant Ton vaut
    dI = Vin * D / (L * fsw)
et le courant moyen d'inductance (= courant d'entree pour un boost
ideal sans pertes) vaut
    IL_avg = Pout / Vin
La frontiere (triangle 0 -> 2*IL_avg) correspond a dI = 2*IL_avg, d'ou
    L_crit = Vin^2 * D / (2 * fsw * Pout),  D = 1 - Vin/Vout
Pour un fsw et un (Vin,Vout) donnes, L >= L_crit(Pout) => CCM a cette
puissance ; L < L_crit(Pout) => DCM.
Reference : Erickson, "Fundamentals of Power Electronics" -- formule
standard du boost CCM/DCM, pas une derivation maison.

Cible retenue : choisir L, par frequence,
pour que la bascule DCM->CCM tombe a ~10W au point NOMINAL (20V/80V) --
DCM en dessous (redresseur favorise, insensible a la techno diode), CCM
au-dessus jusqu'a 40W. Le seuil de bascule aux deux autres couples
(12V/60V, 24V/100V) en DECOULE de ce choix de L, il n'est pas force a
10W egalement -- la frontiere scale en Vin^2*D, pas en Pout seul.
"""

FREQS_HZ = [100e3, 200e3, 300e3, 400e3]
PAIRS = [  # (label, Vin, Vout)
    ("12V_60V", 12.0, 60.0),
    ("20V_80V", 20.0, 80.0),  # point nominal
    ("24V_100V", 24.0, 100.0),
]
POWERS_W = [5.0, 10.0, 20.0, 40.0]
NOMINAL_PAIR = "20V_80V"
NOMINAL_CROSSOVER_W = 10.0

# Hypothese de depart (experience) a confronter au calcul puis a la
# simulation, pas a valider par confiance.
USER_HYPOTHESIS = {"fsw_hz": 200e3, "L_uH": 47.0}


def duty(vin, vout):
    return 1.0 - vin / vout


def l_crit(vin, vout, pout, fsw):
    """Henries. L >= l_crit(...) => CCM a ce point."""
    d = duty(vin, vout)
    return (vin ** 2) * d / (2.0 * fsw * pout)


def l_for_nominal_crossover(fsw):
    """L choisie pour cette frequence : bascule DCM->CCM a
    NOMINAL_CROSSOVER_W au point nominal (20V/80V)."""
    _, vin, vout = next(p for p in PAIRS if p[0] == NOMINAL_PAIR)
    return l_crit(vin, vout, NOMINAL_CROSSOVER_W, fsw)


def crossover_power(vin, vout, l_henries, fsw):
    """Puissance a laquelle CE L (fixe) croise la frontiere CCM/DCM a ce
    couple (Vin,Vout). Au-dessus => CCM, en dessous => DCM."""
    d = duty(vin, vout)
    return (vin ** 2) * d / (2.0 * fsw * l_henries)


def report():
    print("=" * 88)
    print("Dimensionnement L par frequence -- bascule DCM->CCM ciblee a "
          f"{NOMINAL_CROSSOVER_W}W au point nominal ({NOMINAL_PAIR})")
    print("=" * 88)
    rows = []
    for fsw in FREQS_HZ:
        l_chosen = l_for_nominal_crossover(fsw)
        print(f"\n--- fsw = {fsw/1e3:.0f}kHz -> L retenue = {l_chosen*1e6:.3f}uH "
              f"(bascule {NOMINAL_CROSSOVER_W}W au point nominal) ---")
        for label, vin, vout in PAIRS:
            pc = crossover_power(vin, vout, l_chosen, fsw)
            d = duty(vin, vout)
            print(f"  {label:10s} D={d:.4f}  bascule DCM->CCM a {pc:6.2f}W "
                  f"(DCM en dessous, CCM au-dessus)")
            for pout in POWERS_W:
                mode = "CCM" if pout >= pc else "DCM"
                lc = l_crit(vin, vout, pout, fsw)
                rows.append({
                    "fsw_hz": fsw, "pair": label, "vin": vin, "vout": vout,
                    "pout_w": pout, "duty": round(d, 4),
                    "l_chosen_uH": round(l_chosen * 1e6, 4),
                    "l_crit_uH": round(lc * 1e6, 4),
                    "mode_predicted": mode,
                    "crossover_w": round(pc, 4),
                })
    return rows


def report_hypothesis():
    fsw = USER_HYPOTHESIS["fsw_hz"]
    l_h = USER_HYPOTHESIS["L_uH"] * 1e-6
    print("\n" + "=" * 88)
    print(f"Hypothese utilisateur : {fsw/1e3:.0f}kHz / {l_h*1e6:.0f}uH "
          "(= valeur deja figee, SER2211-473) -- confrontee au calcul")
    print("=" * 88)
    l_calc = l_for_nominal_crossover(fsw)
    print(f"L calculee pour bascule a {NOMINAL_CROSSOVER_W}W au point nominal "
          f"a {fsw/1e3:.0f}kHz : {l_calc*1e6:.3f}uH -- "
          f"hypothese utilisateur : {l_h*1e6:.1f}uH "
          f"(ecart x{l_h/l_calc:.2f})")
    for label, vin, vout in PAIRS:
        pc = crossover_power(vin, vout, l_h, fsw)
        print(f"  Avec 47uH reelle, {label:10s} : bascule DCM->CCM a {pc:6.2f}W")


# SER2211 (Coilcraft, doc 1084-1) -- valeurs disponibles dans ce boitier,
# contrainte utilisateur : pas d'inductance plus GROSSE (physiquement)
# que ce boitier pour l'etage 1 -- le courant est la vraie limite, pas
# la compacite par frequence. 47uH = la plus grande valeur de la serie.
SER2211_MAX_L_uH = 47.0
SER2211_MAX_L_DCR_OHM = 8.95e-3  # typ, SER2211-473


def report_fixed_l_across_frequencies():
    """Reponse directe a la contrainte utilisateur : on fixe L au
    maximum disponible dans le boitier SER2211 (47uH, deja la piece
    reelle SER2211-473) et on regarde comment le point de bascule
    CCM/DCM et le courant evoluent avec la frequence -- PAS une
    inductance differente par frequence."""
    l_h = SER2211_MAX_L_uH * 1e-6
    print("\n" + "=" * 88)
    print(f"L FIXEE a {SER2211_MAX_L_uH}uH (SER2211-473, plus gros boitier "
          "accepte) -- bascule CCM/DCM et courant crete vs frequence")
    print("=" * 88)
    for fsw in FREQS_HZ:
        print(f"\n--- fsw = {fsw/1e3:.0f}kHz ---")
        for label, vin, vout in PAIRS:
            pc = crossover_power(vin, vout, l_h, fsw)
            d = duty(vin, vout)
            # Courant crete au point nominal de puissance le plus eleve
            # pertinent pour ce couple (40W au nominal, mais on rapporte
            # a 40W partout pour comparer -- Ipk = Iavg + dI/2,
            # Iavg=Pout/Vin (ideal), dI=Vin*D/(L*fsw).
            iavg_40 = 40.0 / vin
            di_40 = vin * d / (l_h * fsw)
            ipk_40 = iavg_40 + di_40 / 2
            mode_40 = "CCM" if 40.0 >= pc else "DCM"
            print(f"  {label:10s} D={d:.4f}  bascule a {pc:6.2f}W  "
                  f"-- a 40W : mode={mode_40}, Ipk_estime={ipk_40:.3f}A")


if __name__ == "__main__":
    import csv
    rows = report()
    report_hypothesis()
    report_fixed_l_across_frequencies()
    with open("results/inductor_sizing.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nEcrit results/inductor_sizing.csv ({len(rows)} lignes)")
