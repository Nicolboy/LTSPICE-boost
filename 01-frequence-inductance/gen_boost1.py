"""Generateur de schema LTspice (.asc) pour un etage boost non
synchrone batterie -> 50-100V -- composants ideaux/generiques pour le
switch et la diode, inductance reelle sourcee (valeur/DCR passes en
parametre -- voir inductor_sizing.py ; valeur retenue dans ce chapitre :
SER2211-473 = 47uH/8,95mOhm typ, doc Coilcraft 1084-1).

Primitives Sheet/snap/flag/two_pin : generateur de schema LTspice en
texte brut, chaque patte de composant reliee par un FLAG place a sa
coordonnee exacte plutot que par un fil dessine -- un garde-fou
anti-collision leve une erreur si deux pattes de nets differents
atterrissent sur la meme coordonnee apres arrondi a la grille.

Topologie (boost non synchrone) :
  Vin -- Cin(ideal) -- L(reel, DCR serie) -- noeud de commutation n_sw
  -- switch bas-cote (NMOS ideal, source=GND) vers GND
  n_sw -- diode ideale (anode=n_sw, cathode=vout) -- Cout(ideal)+Rload

Idealisation deliberee (une seule variable reelle = l'inductance,
methode incrementale -- un seul parametre de fidelite a la fois) :
  - Switch : NMOS generique, RD tres faible, IS quasi nul (desactive la
    diode de corps interne -- jamais sollicitee dans le sens de
    conduction normal du boost de toute facon). PAS un candidat
    Si/SiC/GaN precis -- ce choix de technologie fait l'objet d'un
    chapitre separe.
  - Diode : modele generique simple (IS=100n N=1 RS=1m), Vf quasi nul.
  - Cin/Cout : ideaux (pas d'ESR), taille realiste (220uF) pour une
    ondulation de tension plausible sans introduire une perte non
    evaluee dans ce chapitre.
"""
import os

GRID = 16


def snap(v):
    return int(round(v / GRID) * GRID)


class Sheet:
    def __init__(self, width=1400, height=900):
        self.lines = ["Version 4", f"SHEET 1 {width} {height}"]
        self._flag_coords = {}

    def symbol(self, name, x, y, rot="R0", inst=None, value=None, prefix=None):
        x, y = snap(x), snap(y)
        self.lines.append(f"SYMBOL {name} {x} {y} {rot}")
        if inst:
            self.lines.append(f"SYMATTR InstName {inst}")
        if value is not None:
            self.lines.append(f"SYMATTR Value {value}")
        if prefix is not None:
            self.lines.append(f"SYMATTR Prefix {prefix}")
        return x, y

    def flag(self, x, y, net):
        x, y = snap(x), snap(y)
        prev = self._flag_coords.get((x, y))
        if prev is not None and prev != net:
            raise ValueError(
                f"Collision de coordonnees apres snap() : ({x},{y}) porte deja "
                f"le net '{prev}', tentative d'y placer '{net}' -- deux pattes "
                f"trop proches fusionneraient silencieusement dans LTspice. "
                f"Ecarter les composants concernes.")
        self._flag_coords[(x, y)] = net
        self.lines.append(f"FLAG {x} {y} {net}")

    def directive(self, x, y, text):
        x, y = snap(x), snap(y)
        self.lines.append(f"TEXT {x} {y} Left 2 !{text}")

    def comment(self, x, y, text):
        x, y = snap(x), snap(y)
        self.lines.append(f"TEXT {x} {y} Left 2 ;{text}")

    def write(self, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("\r\n".join(self.lines) + "\r\n")


PIN = {
    "res": {"A": (16, 16), "B": (16, 96)},
    "cap": {"A": (16, 0), "B": (16, 64)},
    "ind": {"A": (16, 16), "B": (16, 96)},
    "voltage": {"A": (0, 16), "B": (0, 96)},
    "nmos": {"D": (48, 0), "G": (0, 80), "S": (48, 96)},
    "diode": {"A": (16, 0), "B": (16, 64)},
}


def two_pin(sheet, symname, x, y, inst, value, net_a, net_b, rot="R0"):
    x, y = sheet.symbol(symname, x, y, rot=rot, inst=inst, value=value)
    pa = PIN[symname]["A"]
    pb = PIN[symname]["B"]
    sheet.flag(x + pa[0], y + pa[1], net_a)
    sheet.flag(x + pb[0], y + pb[1], net_b)
    return x, y


def build(point_name, vin, vout_target, pout, d, period, out_path,
          l_henries, dcr_ohm, rload=None, cin=220e-6, cout=2.2e-6,
          settle_periods=4000, measure_periods=100):
    """cout par defaut REDUIT (2,2uF, pas la vraie valeur 220uF retenue
    pour le rail de sortie) -- bug trouve en balayage : a
    faible puissance (Rload eleve, ex. 2kOhm a 5W/100V), la constante
    de temps Cout*Rload avec le vrai 220uF peut depasser 0,4s, bien
    au-dela de toute fenetre de simulation raisonnable -- les mesures
    de rendement tombaient sur un regime transitoire (cap encore en
    train de se charger/decharger), donnant des rendements >100% ou
    <<90% completement faux. Cout n'affecte QUE l'ondulation de
    tension et le temps d'etablissement, PAS la valeur moyenne de Vout
    ni le rendement en regime etabli -- le reduire ici est sans impact
    sur cette etude (CCM/DCM, pertes, rendement). La vraie valeur
    220uF sera reintroduite pour une etude d'ondulation/tenue dediee,
    pas pour celle-ci."""
    ton = d * period
    s = Sheet(width=1600, height=900)
    s.comment(40, 20,
              f"Point {point_name} : Vin={vin}V Vout_cible={vout_target}V "
              f"Pout_cible={pout}W D={d:.4f} fsw={1/period/1e3:.0f}kHz -- "
              f"boost etage1, switch/diode ideaux, L={l_henries*1e6:.3f}uH "
              f"DCR={dcr_ohm*1e3:.2f}mOhm")

    # --- switch idealise : RD domine la resistance a l'etat passant,
    # IS faible desactive la diode de corps interne du modele NMOS
    # (PAS un candidat Si/SiC/GaN precis -- voir le chapitre dedie).
    # RD/IS moins extremes qu'une premiere tentative (1mOhm/1e-15) :
    # ca faisait diverger LTspice (noeud de commutation sans aucune
    # capacite, transition en marche d'escalier pure -- voir README).
    s.directive(40, 560, ".model MIDEAL_SW NMOS(VTO=2 KP=200 RD=0.010 RS=0 IS=1e-12)")
    # --- diode idealisee, generique (pas un candidat Si/SiC precis) ---
    s.directive(40, 580, ".model DIDEAL D(IS=100n N=1 RS=10m)")

    # --- Vin + Cin ideal ---
    two_pin(s, "voltage", 80, 160, "V1", str(vin), "vin", "0")
    two_pin(s, "cap", 280, 160, "Cin", f"{cin*1e6:.1f}u", "vin", "0")

    # --- L reelle (serie DCR) : vin -> n_pre_dcr -> Rdcr -> n_sw ---
    two_pin(s, "ind", 520, 60, "L1", f"{l_henries*1e6:.4f}u ic=0", "vin", "n_pre_dcr")
    two_pin(s, "res", 520, 260, "Rdcr", f"{dcr_ohm:.5f}", "n_pre_dcr", "n_sw")

    # --- switch bas-cote : drain=n_sw, source=0, grille=g1 ---
    mx, my = s.symbol("nmos", 520, 460, rot="R0", inst="M1", value="MIDEAL_SW")
    s.flag(mx + PIN["nmos"]["D"][0], my + PIN["nmos"]["D"][1], "n_sw")
    s.flag(mx + PIN["nmos"]["G"][0], my + PIN["nmos"]["G"][1], "g1")
    s.flag(mx + PIN["nmos"]["S"][0], my + PIN["nmos"]["S"][1], "0")

    # --- grille : PULSE ideale, ON de t=0 a t=Ton, periode T ---
    two_pin(s, "voltage", 320, 460, "Vg1",
            f"PULSE(0 10 0 2n 2n {ton*1e6:.4f}u {period*1e6:.4f}u)",
            "g1", "0")

    # --- diode ideale : anode=n_sw, cathode=vout ---
    two_pin(s, "diode", 760, 260, "D1", "DIDEAL", "n_sw", "vout")

    # --- capacite parasite MINIME au noeud de commutation, aide a la
    # convergence (cf. gen_asc.py Cinter_ESTIME -- meme esprit : sans
    # elle, n_sw passe de 0 a Vout en marche d'escalier pure, aucune
    # derivee continue, LTspice ne converge pas). Valeur non sourcee,
    # juste assez grande pour lisser la transition sans influencer la
    # mesure -- PAS un Coss de switch reel. ---
    two_pin(s, "cap", 600, 460, "Cpar_sw_NUMERIQUE", "20p", "n_sw", "0")

    # --- Cout ideal + Rload ---
    two_pin(s, "cap", 1000, 160, "Cout", f"{cout*1e6:.1f}u ic={vout_target}", "vout", "0")
    if rload is None:
        rload = (vout_target ** 2) / pout
    two_pin(s, "res", 1200, 160, "Rload", f"{rload:.4f}", "vout", "0")

    tstop = settle_periods * period
    tstart = (settle_periods - measure_periods) * period
    s.directive(40, 620, f".tran 0 {tstop*1e6:.3f}u {tstart*1e6:.3f}u 10n uic")

    f0, f1 = f"{tstart*1e6:.3f}u", f"{tstop*1e6:.3f}u"
    s.directive(40, 660, f".meas TRAN Vout_avg AVG V(vout) FROM {f0} TO {f1}")
    s.directive(40, 680, f".meas TRAN Iout_avg AVG I(Rload) FROM {f0} TO {f1}")
    s.directive(40, 700, f".meas TRAN Pout_avg AVG (V(vout)*I(Rload)) FROM {f0} TO {f1}")
    s.directive(40, 720, f".meas TRAN Pin_avg AVG (-V(vin)*I(V1)) FROM {f0} TO {f1}")
    s.directive(40, 740, f".meas TRAN Ploss_switch AVG (Id(M1)*V(n_sw)) FROM {f0} TO {f1}")
    s.directive(40, 760, f".meas TRAN Ploss_diode AVG (I(D1)*(V(n_sw)-V(vout))) FROM {f0} TO {f1}")
    s.directive(40, 780, f".meas TRAN Ploss_L_dcr AVG (I(Rdcr)*I(Rdcr)*{dcr_ohm:.5f}) FROM {f0} TO {f1}")
    s.directive(40, 800, f".meas TRAN Vds_switch_max MAX V(n_sw) FROM {f0} TO {f1}")
    s.directive(40, 820, f".meas TRAN Ipk_L MAX I(L1) FROM {f0} TO {f1}")
    s.directive(40, 840, f".meas TRAN Irms_L RMS I(L1) FROM {f0} TO {f1}")
    # mode de conduction : I(L1) juste avant le rallumage du switch (fin
    # de periode) -- proche de 0 = DCM, significatif = CCM.
    t_end_check = tstop - 0.02 * period
    s.directive(40, 860, f".meas TRAN IL_end_of_period FIND I(L1) AT {t_end_check*1e6:.4f}u")

    s.write(out_path)
    print(f"Ecrit {out_path} (D={d:.4f}, Ton={ton*1e6:.4f}us, Rload={rload:.4f} Ohm)")
    return rload


if __name__ == "__main__":
    import sys
    fsw = 200e3
    T = 1 / fsw
    vin = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    vout_t = float(sys.argv[2]) if len(sys.argv) > 2 else 80.0
    pout = float(sys.argv[3]) if len(sys.argv) > 3 else 40.0
    d_val = float(sys.argv[4]) if len(sys.argv) > 4 else (1 - vin / vout_t)
    out = sys.argv[5] if len(sys.argv) > 5 else "test_point.asc"
    build("test", vin, vout_t, pout, d_val, T, out,
          l_henries=47e-6, dcr_ohm=8.95e-3)
