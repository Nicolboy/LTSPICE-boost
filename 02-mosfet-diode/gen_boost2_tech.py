"""Chapitre 2 (switch/diode) -- generateur de schema LTspice (.asc) pour
l'etage 1 boost, derive de gen_boost1.py (chapitre 1, switch/diode
ideaux/generiques). Ajoute UNE dimension de realisme a la fois (methode
incrementale inchangee) par rapport au chapitre 1 :

  - switch et diode : modeles simples mais PARAMETRES sur des pieces
    reelles (Si vs GaN pour le switch, Schottky vs ultrafast PN Si pour
    la diode -- PAS de SiC ici, voir switch_diode_models.py) au lieu
    des modeles generiques MIDEAL_SW/DIDEAL du chapitre 1.
  - self parasite ESTIMEE au noeud de commutation (Lstray, voir
    switch_diode_models.LSTRAY_BY_L_H) -- sans elle, le recouvrement
    inverse de la diode ultrafast ne produit aucun depassement de tension
    observable, l'interet de la Schottky resterait invisible en
    simulation.
  - capacite au noeud de commutation : Coss REEL de la techno switch
    (remplace la capacite numerique non sourcee du chapitre 1 -- sert
    aussi a la convergence).

Inductance : meme principe qu'au chapitre 1 (valeur/DCR en parametre),
mais balayee sur 3 valeurs SER2211 (12/27/47uH) au lieu d'etre fixee a
47uH -- voir README de ce chapitre.

Topologie (boost non synchrone, inchangee) :
  Vin -- Cin(ideal) -- L(reel, DCR serie) -- n_pre_stray -- Lstray(estimee)
  -- noeud de commutation n_sw -- switch bas-cote (reel, techno
  parametree) vers GND
  n_sw -- diode (reelle, techno parametree, anode=n_sw, cathode=vout) --
  Cout(ideal)+Rload
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from switch_diode_models import (DIODES, LSTRAY_BY_L_H, SWITCHES,
                                  diode_spice_model, switch_spice_model)

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
          l_henries, dcr_ohm, switch_tech, diode_tech, lstray_h=None,
          rload=None, cin=220e-6, cout=0.22e-6,
          settle_periods=None, measure_periods=None, dtmax_s=1e-9,
          add_lisn=False):
    """cout reduit (0,22uF -- 10x plus petit qu'au chapitre 1, meme
    bug/justification que gen_boost1.build : fenetre de simulation trop
    courte face a la constante de temps Cout*Rload a faible puissance).
    Reduit ICI d'un facteur 10 de plus que le ch.1 (qui utilisait 2,2uF)
    car dtmax est resserre a 1ns pour resoudre les transitoires
    ns (voir plus bas) -- sans cette reduction supplementaire, le nombre
    de pas sur toute la fenetre de reglage devient impraticable (un
    balayage a dtmax=0,2ns sur les 4000 periodes/0,22uF du chapitre 1
    aurait pris plusieurs dizaines de secondes PAR POINT, constate a
    l'implementation).

    settle_periods/measure_periods par defaut (None) : calcules depuis
    `period` pour une duree ABSOLUE fixe (~3ms de reglage, ~0,3ms de
    mesure) quel que soit fsw -- le temps de reglage necessaire depend de
    Cout*Rload (constante de temps absolue, pas du nombre de periodes),
    donc une valeur FIXE de periodes ferait exploser le temps de calcul
    aux basses frequences (plus de temps absolu pour le meme nombre de
    periodes) sans necessite. Passer une valeur explicite pour
    outrepasser."""
    if settle_periods is None:
        settle_periods = max(200, round(3e-3 / period))
    if measure_periods is None:
        measure_periods = max(20, round(0.3e-3 / period))
    if lstray_h is None:
        lstray_h = LSTRAY_BY_L_H.get(l_henries)
        if lstray_h is None:
            raise ValueError(
                f"Pas de self parasite estimee pour L={l_henries*1e6}uH -- "
                f"ajouter une entree dans switch_diode_models.LSTRAY_BY_L_H "
                f"ou passer lstray_h explicitement.")

    sw = SWITCHES[switch_tech]
    ton = d * period
    s = Sheet(width=1600, height=900)
    s.comment(40, 20,
              f"Point {point_name} : Vin={vin}V Vout_cible={vout_target}V "
              f"Pout_cible={pout}W D={d:.4f} fsw={1/period/1e3:.0f}kHz -- "
              f"boost etage1 ch.2, switch={switch_tech}({sw['part']}) "
              f"diode={diode_tech}({DIODES[diode_tech]['part']}) "
              f"L={l_henries*1e6:.3f}uH DCR={dcr_ohm*1e3:.2f}mOhm "
              f"Lstray={lstray_h*1e9:.0f}nH")

    # --- switch et diode : modeles parametres sur la piece reelle
    # (switch_diode_models.py) -- PAS les modeles generiques du ch.1.
    s.directive(40, 560, switch_spice_model(switch_tech, "MTECH"))
    s.directive(40, 580, diode_spice_model(diode_tech, "DTECH"))

    # --- Vin + Cin ideal ---
    vin_node = "n_src" if add_lisn else "vin"
    two_pin(s, "voltage", 80, 160, "V1", str(vin), vin_node, "0")
    two_pin(s, "cap", 280, 160, "Cin", f"{cin*1e6:.1f}u", "vin", "0")

    # --- LISN simplifiee (une branche, PAS un reseau CISPR 16-1-2
    # complet a 2 branches) : separe la source ideale du DUT (le
    # convertisseur, en aval de "vin") pour mesurer la tension de bruit
    # conduit sur une impedance connue, comme le ferait un recepteur de
    # mesure. L_lisn=50uH (valeur standard CISPR), branche mesure
    # C=0,1uF + R=50Ohm (impedance de mesure), branche basse frequence
    # R=1k + C=1uF (deleste le continu/BF de la branche de mesure, meme
    # topologie qu'un LISN V-network standard, cote simple ligne). PAS
    # de retour/masse separee modelisee (0V = masse commune source/DUT
    # ici) -- limite documentee, voir README. ---
    if add_lisn:
        # R_lisn_esr (1 Ohm) : resistance serie realiste de l'inductance
        # LISN (DCR bobinage) -- sans elle, le filtre d'entree L_lisn/
        # Cin=220uF est quasi non amorti (R=0 ideale) et ne retombe pas
        # en regime periodique etabli dans la fenetre de simulation :
        # anneau basse frequence (~1,5kHz, L_lisn/Cin) toujours en
        # transitoire au debut de la fenetre de mesure, Pin_avg/Vds_max
        # mesures totalement faux (334W, 125V constate a l'implementation,
        # PAS une anomalie du convertisseur). 1 Ohm = proche de
        # l'amortissement critique pour L=50uH/C=220uF (R_crit=2*sqrt(L/C)
        # ~0,95 Ohm) -- valeur realiste pour un bobinage de LISN, pas
        # arbitraire pour masquer le probleme.
        two_pin(s, "ind", 160, 780, "L_lisn", "50.00u ic=0", "n_src", "n_lisn_r")
        two_pin(s, "res", 260, 780, "R_lisn_esr", "1", "n_lisn_r", "vin")
        two_pin(s, "cap", 360, 780, "C_lisn_meas", "0.1u", "vin", "n_lisn_meas")
        two_pin(s, "res", 560, 780, "R_lisn_meas", "50", "n_lisn_meas", "0")
        two_pin(s, "res", 760, 780, "R_lisn_lf", "1k", "vin", "n_lisn_lf")
        two_pin(s, "cap", 960, 780, "C_lisn_lf", "1u", "n_lisn_lf", "0")

    # --- L reelle (serie DCR) : vin -> n_pre_dcr -> Rdcr -> n_pre_stray ---
    two_pin(s, "ind", 480, 60, "L1", f"{l_henries*1e6:.4f}u ic=0", "vin", "n_pre_dcr")
    two_pin(s, "res", 480, 260, "Rdcr", f"{dcr_ohm:.5f}", "n_pre_dcr", "n_pre_stray")

    # --- self parasite ESTIMEE au noeud de commutation : n_pre_stray ->
    # Lstray -> n_sw. Sans elle, pas de depassement de tension au
    # recouvrement diode (voir docstring module). ---
    two_pin(s, "ind", 680, 260, "Lstray", f"{lstray_h*1e9:.2f}n ic=0",
            "n_pre_stray", "n_sw")

    # --- switch bas-cote : drain=n_sw, source=0, grille=g1 ---
    mx, my = s.symbol("nmos", 880, 460, rot="R0", inst="M1", value="MTECH")
    s.flag(mx + PIN["nmos"]["D"][0], my + PIN["nmos"]["D"][1], "n_sw")
    s.flag(mx + PIN["nmos"]["G"][0], my + PIN["nmos"]["G"][1], "g1")
    s.flag(mx + PIN["nmos"]["S"][0], my + PIN["nmos"]["S"][1], "0")

    # --- grille : PULSE reglee sur la techno (amplitude = VGS de drive
    # datasheet, fronts = tr/tf reels ou estimes -- voir
    # switch_diode_models.py, PAS 0-10V/2ns generique comme au ch.1). ---
    two_pin(s, "voltage", 680, 460, "Vg1",
            f"PULSE(0 {sw['vgs_drive']:.2f} 0 {sw['tr_ns']:.3f}n "
            f"{sw['tf_ns']:.3f}n {ton*1e6:.4f}u {period*1e6:.4f}u)",
            "g1", "0")

    # --- diode reelle (techno parametree) : anode=n_sw, cathode=vout ---
    two_pin(s, "diode", 1120, 260, "D1", "DTECH", "n_sw", "vout")

    # --- Cj diode EXPLICITE (candidats reels REAL_DIODES uniquement --
    # voir switch_diode_models.py) : participe au systeme resonant avec
    # Coss_TECH + Lstray. Les diodes generiques du ch.2 (DIODES["Schottky"]
    # / ["Ultrafast"]) n'ont PAS ce champ -- aucune capacite ajoutee pour
    # elles, comportement du ch.2 inchange. ---
    diode = DIODES[diode_tech]
    if diode.get("cj_f"):
        two_pin(s, "cap", 1120, 460, "Cj_DIODE", f"{diode['cj_f']*1e12:.2f}p",
                "n_sw", "vout")

    # --- Coss REEL de la techno switch, en shunt du noeud de commutation
    # -- remplace la capacite numerique non sourcee du chapitre 1 (sert
    # aussi a la convergence, mais a maintenant une valeur sourcee). ---
    two_pin(s, "cap", 880, 620, "Coss_TECH", f"{sw['coss_f']*1e12:.1f}p",
            "n_sw", "0")

    # --- Cout ideal + Rload ---
    two_pin(s, "cap", 1360, 160, "Cout", f"{cout*1e6:.1f}u ic={vout_target}", "vout", "0")
    if rload is None:
        rload = (vout_target ** 2) / pout
    two_pin(s, "res", 1480, 160, "Rload", f"{rload:.4f}", "vout", "0")

    tstop = settle_periods * period
    tstart = (settle_periods - measure_periods) * period
    # dtmax resserre a 1ns (contre 10ns au chapitre 1) : l'anneau LC
    # Lstray/Coss (~13-14ns de periode avec les valeurs de ce chapitre)
    # et le recouvrement diode (TT~16ns) sont plus courts que le pas du
    # chapitre 1 -- un pas trop grossier sous-echantillonne ces
    # transitoires et masque le depassement de tension au lieu de le
    # simuler (constate lors du premier essai a blanc de ce chapitre, avec
    # dtmax=10n herite du ch.1 : overshoot quasi identique Schottky vs
    # ultrafast alors que les pertes mesurees, elles, divergeaient
    # nettement). 1ns = compromis (~13 points/anneau), PAS 0,1-0,2ns
    # (force alors des dizaines de millions de pas sur toute la fenetre
    # de 4000 periodes du ch.1 -- bien trop lent). Voir aussi cout/
    # settle_periods reduits ci-dessus pour la meme raison de duree.
    # dtmax_s parametrable : la recherche de D par bissection
    # (find_duty2.py) utilise un dtmax plus grossier (rapide, Vout
    # approximatif suffit pour converger en direction) ; seul le point
    # FINAL retenu repasse par le dtmax fin par defaut (1ns) pour les
    # mesures de commutation/overshoot reellement exploitees.
    s.directive(40, 620, f".tran 0 {tstop*1e6:.3f}u {tstart*1e6:.3f}u {dtmax_s*1e9:.3f}n uic")

    f0, f1 = f"{tstart*1e6:.3f}u", f"{tstop*1e6:.3f}u"
    s.directive(40, 660, f".meas TRAN Vout_avg AVG V(vout) FROM {f0} TO {f1}")
    s.directive(40, 680, f".meas TRAN Iout_avg AVG I(Rload) FROM {f0} TO {f1}")
    s.directive(40, 700, f".meas TRAN Pout_avg AVG (V(vout)*I(Rload)) FROM {f0} TO {f1}")
    s.directive(40, 720, f".meas TRAN Pin_avg AVG (-V(vin)*I(V1)) FROM {f0} TO {f1}")
    s.directive(40, 740, f".meas TRAN Ploss_switch_total AVG (Id(M1)*V(n_sw)) FROM {f0} TO {f1}")
    s.directive(40, 760, f".meas TRAN Irms_switch RMS Id(M1) FROM {f0} TO {f1}")
    s.directive(40, 780, f".meas TRAN Ploss_diode_total AVG (I(D1)*(V(n_sw)-V(vout))) FROM {f0} TO {f1}")
    s.directive(40, 800, f".meas TRAN Ploss_L_dcr AVG (I(Rdcr)*I(Rdcr)*{dcr_ohm:.5f}) FROM {f0} TO {f1}")
    s.directive(40, 820, f".meas TRAN Vds_switch_max MAX V(n_sw) FROM {f0} TO {f1}")
    s.directive(40, 840, f".meas TRAN Ipk_L MAX I(L1) FROM {f0} TO {f1}")
    s.directive(40, 860, f".meas TRAN Irms_L RMS I(L1) FROM {f0} TO {f1}")
    t_end_check = tstop - 0.02 * period
    s.directive(40, 880, f".meas TRAN IL_end_of_period FIND I(L1) AT {t_end_check*1e6:.4f}u")

    s.write(out_path)
    print(f"Ecrit {out_path} (D={d:.4f}, Ton={ton*1e6:.4f}us, Rload={rload:.4f} Ohm, "
          f"switch={switch_tech}, diode={diode_tech}, Lstray={lstray_h*1e9:.0f}nH)")
    return rload


if __name__ == "__main__":
    fsw = 200e3
    T = 1 / fsw
    vin = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    vout_t = float(sys.argv[2]) if len(sys.argv) > 2 else 80.0
    pout = float(sys.argv[3]) if len(sys.argv) > 3 else 40.0
    d_val = float(sys.argv[4]) if len(sys.argv) > 4 else (1 - vin / vout_t)
    switch_tech = sys.argv[5] if len(sys.argv) > 5 else "Si"
    diode_tech = sys.argv[6] if len(sys.argv) > 6 else "Schottky"
    out = sys.argv[7] if len(sys.argv) > 7 else "test_point2.asc"
    build("test", vin, vout_t, pout, d_val, T, out,
          l_henries=47e-6, dcr_ohm=8.95e-3,
          switch_tech=switch_tech, diode_tech=diode_tech)
