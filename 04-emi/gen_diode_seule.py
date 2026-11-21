"""Rendement de la DIODE SEULE, tout le reste idéal.

POURQUOI CE BANC EXISTE. J'ai passé des heures à déboguer la convergence
d'un banc à pleine fidélité -- GaN comportemental, inductance à cinq
éléments, LISN, réseau d'entrée à trois branches -- pour répondre à une
question qui ne demande rien de tout cela : **que coûte la diode à
400 kHz ?**

La règle était pourtant écrite dans la skill `sim-spice` : modèle idéal
d'abord, parasites UN PAR UN, balayage exhaustif en dernier. Je ne l'ai pas
appliquée, et chaque échec de convergence venait d'un élément qui n'avait
rien à voir avec la question : nœud de retour à 1 µΩ, nœud interne de
modèle sans capacité vers la masse, conditions initiales impossibles.

CE BANC NE CONTIENT QUE CE QUI EST NÉCESSAIRE :

    interrupteur   `.model SW` idéal, Ron 5 mΩ
    inductance     L pure, plus une résistance série pour le DCR
    sortie         source de tension raide -- l'étage 2 régule derrière
    diode          **modèle constructeur, le seul élément réel**

Tout ce que la diode dissipe est alors à elle. Ce qui reste indéterminé est
nommé : l'inductance de maille est mise à zéro ici, donc AUCUNE surtension
de commutation -- ce banc mesure une PERTE, pas une contrainte. Les deux
études sont séparées exprès.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import gen_emi_dm as g                                    # noqa: E402

VOUT, FSW, ETA = 80.0, 400e3, 0.97
DCR = {"4u7": 5.5e-3, "10u": 3.3e-3, "47u": 10.7e-3}      # Coilcraft, datasheet

DIODES = {
    "inf": ("IDH04G65C6_L1", g.LIB / "Infineon" / "CoolSiC_G6_650V.lib",
            "Infineon CoolSiC G6 · 4 A / 650 V", 2),
    "c6d": ("C6D04065A", g.LIB / "Wolfspeed" / "C6D04065A.lib",
            "Wolfspeed C6D · 4 A / 650 V", 5),
    "c3d": ("C3D16065D1", g.LIB / "Wolfspeed" / "C3D16065D1.lib",
            "Wolfspeed C3D · 16 A / 650 V", 6),
    "si":  (None, None, "Vishay V8PA22 · 8 A / 200 V (Schottky Si)", 0),
}
L_VAL = {"4u7": 4.7e-6, "10u": 10e-6, "47u": 47e-6}


def mode_duty(l_h, pout, vin):
    d_ccm = 1.0 - vin / VOUT
    d_i = vin * d_ccm / (l_h * FSW)
    if pout / ETA / vin >= d_i / 2:
        return "CCM", d_ccm
    return "DCM", math.sqrt(2.0 * pout * l_h * FSW * (VOUT - vin)
                            / (ETA * vin ** 2 * VOUT))


def netlist(ind, dio, pout, vin=20.0, n_etab=20, n_mes=10, duty=None):
    nom_d, lib_d, libelle, broches = DIODES[dio]
    l_h = L_VAL[ind]
    m, d0 = mode_duty(l_h, pout, vin)
    duty = d0 if duty is None else duty
    tsw = 1.0 / FSW
    t0, t1 = n_etab * tsw, (n_etab + n_mes) * tsw
    i_in = pout / ETA / vin

    if dio == "si":
        bloc = f"D1   nd  nk  {g.DIODE[0]}"
        mod = f".model {g.DIODE[0]} {g.DIODE[1]}"
    elif broches == 2:
        bloc = f"XD1  nd  nk  {nom_d}"
        mod = g.texte_lib(lib_d)
    elif broches == 5:                                     # A K Case Tj Tc
        bloc = (f"XD1  nd  nk  ncase ntj 0 {nom_d}\n"
                f"Rcase ncase 0 1meg")
        mod = g.texte_lib(lib_d)
    else:                                                  # NC A K Case Tj Tc
        bloc = (f"XD1  nnc nd  nk  ncase ntj 0 {nom_d}\n"
                f"Rnc nnc 0 1meg\nRcase ncase 0 1meg")
        mod = g.texte_lib(lib_d)

    return f"""* Diode SEULE -- {libelle}
* {ind}, {m}, {vin:.0f} V -> {VOUT:.0f} V, {pout:.0f} W, {FSW/1e3:.0f} kHz
* Tout est ideal sauf la diode. genere par gen_diode_seule.py
.param TSW={tsw:.6e} duty={duty:.6f}
.temp 25

Vin  bin 0   DC {vin}
Cin  bin 0   100u

* --- inductance PURE + sa resistance continue au datasheet
L1   bin nl  {l_h:.4e}
Rl   nl  nsw {DCR[ind]:.4e}

* --- interrupteur ideal : 5 mOhm passant, 1 MOhm bloque. Pas de modele
* comportemental, pas de capacite de sortie, pas de charge de grille :
* ce banc ne mesure PAS le transistor.
S1   nsw 0   ng 0 SW
.model SW SW(Ron=5m Roff=1meg Vt=2.5 Vh=0 Lser=0)
Vg   ng  0   PULSE(0 5 0 1n 1n {{duty*TSW}} {{TSW}})

* --- diode, SEUL element reel. Aucune inductance de maille : ce banc
* mesure une PERTE, pas une surtension.
Vdm  nsw nd  DC 0
{bloc}
Vo   nk  0   DC {VOUT:.3f}

{mod}

.ic I(L1)={i_in:.4f}
.options reltol=1e-3 abstol=1e-12 vntol=1e-6 plotwinsize=0 cshunt=1e-15
.tran 0 {t1:.6e} {t0:.6e} 2n uic

.save I(Vdm) I(Vo) I(L1) V(nd) V(nk) V(nsw)
.meas TRAN pdio AVG (V(nd)-V(nk))*I(Vdm) FROM {t0:.6e} TO {t1:.6e}
.meas TRAN pout AVG {VOUT}*I(Vo)         FROM {t0:.6e} TO {t1:.6e}
.meas TRAN pin  AVG {vin}*I(L1)          FROM {t0:.6e} TO {t1:.6e}
.end
"""
