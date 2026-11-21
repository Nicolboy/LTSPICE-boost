"""Extraire d'un modele ce qu'une fiche technique donnerait.

LE PROBLEME. Je simule avec l'IPD530N15N3, dont je n'ai PAS la fiche --
tout ce que j'en ai cite (53 mOhm, 10 V, Ls/Ld/Lg) vient de lignes
`.PARAM` du modele, c'est-a-dire d'un jeu d'ajustement et non d'une
specification. Le prototype, lui, sera monte avec le FDD770N15A, dont j'ai
la fiche mais dont le modele est inutilisable en pertes.

LA METHODE. La piece dont j'ai la fiche sert a VALIDER l'extraction :

    extraire Coss(V) et Qg du modele onsemi
        -> comparer a sa fiche : Coss 64 pF typ (85 max) a 75 V,
           Qg 8,4 nC typ (11 max) a 10 V, Qoss 14 nC a 37,5 V
    si l'ecart est acceptable, la methode est bonne
        -> l'appliquer au modele Infineon pour obtenir ce que sa fiche
           absente aurait donne

C'est un etalonnage, pas une supposition. Si l'extraction rate sur la
piece connue, elle ne vaut rien sur l'autre et il faudra aller chercher
la fiche Infineon.

UNE CORRECTION A PORTER. J'avais ecrit que les deux pieces avaient un
Rdson "comparable, 51,5 contre 53 mOhm". FAUX : les 51,5 etaient la somme
des resistances INTERNES du modele onsemi, comparee au MAXIMUM specifie de
l'Infineon. La fiche onsemi donne 61 mOhm typiques et 77 maximum. L'ecart
est de 45 %, pas de 3 %.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
RAC = ICI.parents[2]
for q in (ICI, RAC / ".claude/skills/sim-spice/scripts",
          RAC / ".claude/skills/sim-commun"):
    sys.path.insert(0, str(q))
from simcommun.lecture import lire                           # noqa: E402

EXE = r"C:\Program Files\ADI\LTspice\LTspice.exe"
LIB = RAC / "lib_spice_commun"

# ce que la fiche FDD770N15A donne, et qui sert d'etalon
FICHE_FDD = {
    "Rdson a 10 V, 12 A": (61.0, 77.0, "mohm   typ / max"),
    "Coss a 75 V": (64.0, 85.0, "pF     typ / max"),
    "Ciss a 75 V": (575.0, 765.0, "pF     typ / max"),
    "Qg total a 10 V": (8.4, 11.0, "nC     typ / max"),
    "Qoss a 37,5 V": (14.0, None, "nC     typ"),
    "Vgs seuil": (2.0, 4.0, "V      min / max"),
}

ENTETE = {
    "fdd770": ('X1 nd ng 0 FDD770N15A',
               (LIB / "onsemi" / "FDD770N15A.lib").read_text(
                   encoding="utf-8", errors="replace")),
    "ipd530": ('X1 nd ng 0 IPD530N15N3_L1',
               f'.inc "{(LIB / "Infineon" / "OptiMOS3_150V_LTSpice.lib").as_posix()}"'),
}


def lance(nom: str, corps: str) -> Path:
    f = ICI / f"x_{nom}.cir"
    f.write_text(corps, encoding="utf-8")
    subprocess.run([EXE, "-b", str(f)], capture_output=True, timeout=1200)
    return f.with_suffix(".raw")


def coss(modele: str) -> tuple[np.ndarray, np.ndarray]:
    """Coss(Vds) par la CHARGE, et non par une petite-signal.

    Grille a la masse, rampe lente sur le drain a travers une source de
    courant constante. Coss = I / (dV/dt), mesure point par point. Une
    rampe lente evite d'exciter les inductances de boitier, qui
    fausseraient une mesure en alternatif.
    """
    inst, bib = ENTETE[modele]
    n = "\n".join((
        f"* extraction Coss, {modele}",
        inst.replace("ng", "0"),
        "Ig   0    nd   PULSE(0 1m 0 1n 1n 1 2)",   # echelon, OP a 0
        "Rfuite nd 0    1g",
        ".options plotwinsize=0 cshunt=1e-15",
                ".tran 0 200u 0 20n",
        ".save V(nd) I(Ig)",
        bib, ".end"))
    r = lire(str(lance(f"coss_{modele}", n)))
    t = np.asarray(r.x)
    v = np.asarray(r.trace("V(nd)")).real
    m = (v >= 0.0) & (v < 149.0)
    t, v = t[m], v[m]
    dvdt = np.gradient(v, t)
    return v, 1e-3 / np.maximum(dvdt, 1e-9), t - t[0]


def qg(modele: str) -> tuple[np.ndarray, np.ndarray]:
    """Qg(Vgs) a courant de grille constant, drain tenu a 75 V.

    C'est exactement la manip de la fiche : 1 mA dans la grille, et
    Qg = I.t. Le palier Miller apparait tel quel.
    """
    inst, bib = ENTETE[modele]
    n = "\n".join((
        f"* extraction Qg, {modele}, Vds = 75 V",
        inst,
        "Vdd  nvd  0    DC 75",
        "Rd   nvd  nd   100",
        "Ig   0    ng   PULSE(0 1m 0 1n 1n 1 2)",
        "Rfg  ng   0    1g",
        ".options plotwinsize=0 cshunt=1e-15",
                ".tran 0 40u 0 4n",
        ".save V(ng) V(nd)",
        bib, ".end"))
    r = lire(str(lance(f"qg_{modele}", n)))
    t = np.asarray(r.x)
    return np.asarray(r.trace("V(ng)")).real, t * 1e-3


def main() -> int:
    print("  ETALONNAGE DE LA METHODE sur la piece dont j'ai la FICHE")
    print("  (FDD770N15A -- modele inutilisable en PERTES, mais ses")
    print("   capacites et charges restent extractibles)\n")
    res = {}
    for mod in ("fdd770", "ipd530"):
        try:
            v, c, tc = coss(mod)
            g, q = qg(mod)
            c75 = float(np.interp(75.0, v, c)) * 1e12
            # Qoss PAR LE TEMPS, pas par une integrale de Coss.
            #
            # Premiere version : integrer Coss(V) de 0,5 a 37,5 V. Deux
            # fautes. Elle manquait la zone sous 0,5 V, ou Coss est le
            # plus grand -- d'ou -48 % sur la piece etalon. Et sur le
            # modele Infineon elle rendait -2,3e13 nC, parce que
            # `dV/dt` passe par zero et que `1/dvdt` explose.
            #
            # Or la rampe est a COURANT CONSTANT : Qoss = I.t, point.
            # C'est la definition meme de la manip, et elle ne derive rien.
            qoss = {m: float(np.interp(u, v, tc)) * 1e-3 * 1e9
                    for m, u in (("37.5", 37.5), ("75", 75.0))}
            # Qg au PREMIER franchissement de 10 V. `np.interp` suppose
            # une abscisse croissante ; V(ng) ne l'est pas (palier Miller
            # puis sonnerie), et l'interpolation retombait sur 0,00 nC.
            k = np.argmax(g >= 10.0) if (g >= 10.0).any() else -1
            q10 = q[k] * 1e9 if k > 0 else float("nan")
            res[mod] = dict(c75=c75, qoss=qoss, q10=q10, v=v, c=c, g=g, q=q)
            print(f"  {mod} : Coss(75 V) = {c75:.1f} pF   "
                  f"Qoss = {qoss['37.5']:.1f} nC a 37,5 V et "
                  f"{qoss['75']:.1f} nC a 75 V   Qg(10 V) = {q10:.2f} nC")
        except Exception as e:
            print(f"  {mod} : extraction ECHOUEE -- {type(e).__name__}: {e}")
    if "fdd770" in res:
        f = res["fdd770"]
        print(f"\n  CONFRONTATION A LA FICHE FDD770N15A")
        print(f"    {'grandeur':22s} {'fiche':>18s} {'extrait':>10s} {'ecart':>9s}")
        for lib, ex, (ty, mx, u) in (
                ("Coss a 75 V", f["c75"], FICHE_FDD["Coss a 75 V"]),
                ("Qoss a 37,5 V", f["qoss"]["37.5"], FICHE_FDD["Qoss a 37,5 V"]),
                ("Qg total a 10 V", f["q10"], FICHE_FDD["Qg total a 10 V"])):
            mxs = f"{mx:g}" if mx else "--"
            print(f"    {lib:22s} {ty:8g} / {mxs:>6s} {ex:9.1f} "
                  f"{100*(ex-ty)/ty:+8.0f} %")
    for p in ICI.glob("x_*.*"):
        p.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
