"""R2 DCM -- resserrer le debut de la bifurcation fsw/2 (verdict du gendarme).

Banc complet (r2_ziegler_dcm.py : FDD770, Wurth 10 uF + MLCC, echantillon
0,998 T + retard d'une periode), echelon 5 -> 10 W a 1 ms.

Le gendarme a refuse la limite "1,3 par enveloppe constante" : toutes les
enveloppes sont constantes (regime etabli), et 0,0013 a Kp 1,32 est au
niveau du bruit des cas stables. L'alternance croit CONTINUMENT avec Kp
(bifurcation supercritique) : l'estimateur est l'amplitude AU CARRE contre
Kp, extrapolee a zero. Il demandait :
  - des points entre 1,33 et 1,38 ;
  - un horizon long (1500 periodes apres l'echelon) pour confirmer r ~ 1
    et exclure une croissance lente.

Amplitude = valeur EFFICACE de la composante alternee de D,
d[k] - (d[k-1] + d[k+1]) / 2, sur les 1000 dernieres periodes (une
moyenne quadratique, plus stable qu'un crete-a-crete par fenetre).
Tendance = pente de l'efficace par tranches de 250 periodes.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import r2_ziegler_dcm as d                                   # noqa: E402
import r2_ziegler as z                                       # noqa: E402
import ltspice_run                                           # noqa: E402

KPS = (1.33, 1.35, 1.37, 1.40)
N_APRES_LONG = 1500


def alternance(D, n_dern=1000, tranche=250):
    ts = d.N_AVANT / z.FSW
    m = D["tb"] > ts + 0.5e-3
    dd = D["db"][m]
    alt = dd[1:-1] - 0.5 * (dd[:-2] + dd[2:])
    eff = float(np.sqrt(np.mean(alt[-n_dern:] ** 2)))
    nb = len(alt) // tranche
    tr = [float(np.sqrt(np.mean(alt[i * tranche:(i + 1) * tranche] ** 2)))
          for i in range(nb)]
    # signe alterne ? correlation k / k+1 de alt (-1 = periode 2 pure)
    c = float(np.corrcoef(alt[-n_dern:-1], alt[-n_dern + 1:])[0, 1])
    return eff, tr, c


def main() -> int:
    fs = [d.prepare(f"zs_{int(round(k*100))}", k,
                    n_mes=d.N_AVANT + N_APRES_LONG) for k in KPS]
    t0 = time.monotonic()
    res = ltspice_run.lance_lot(fs, procs=len(fs))
    print(f"  {len(fs)} cas, {d.N_AVANT}+{N_APRES_LONG} periodes, en "
          f"parallele : {time.monotonic()-t0:.0f} s\n")
    pts = []
    for k, f in zip(KPS, fs):
        r = res[f.stem]
        if not r["ok"]:
            print(f"  Kp {k:.2f}  ECHEC  {r['diagnostic'][:90]}")
            continue
        D = z.par_periode(f)
        np.savez(f.with_suffix(".npz"), **D)
        f.with_suffix(".raw").unlink()
        eff, tr, c = alternance(D)
        pts.append((k, eff))
        print(f"  Kp {k:.2f}  efficace {eff:.5f}  corr(k,k+1) {c:+.2f}  "
              f"par tranches de 250 : {[round(x, 5) for x in tr]}")
    # points anterieurs (horizon court) relus avec le MEME estimateur
    print("\n  points de la k-section (horizon 600 periodes), meme estimateur :")
    for f in sorted(ICI.glob("zr[0-9]_*.npz")):
        cir = f.with_suffix(".cir").read_text(encoding="utf-8")
        k = float(cir.split("Bctrl")[1].split("+ ")[1].split("*")[0])
        if 1.1 < k < 1.7:
            eff, tr, c = alternance(dict(np.load(f)), n_dern=400, tranche=100)
            pts.append((k, eff))
            print(f"  Kp {k:.4f}  efficace {eff:.5f}  corr {c:+.2f}  "
                  f"tranches {[round(x, 5) for x in tr]}")
    pts.sort()
    kp = np.array([p[0] for p in pts])
    a2 = np.array([p[1] for p in pts]) ** 2
    print("\n  Kp      efficace^2")
    for k, a in zip(kp, a2):
        print(f"  {k:.4f}  {a:.3e}")
    # ajustement lineaire a2 = s.(Kp - Kc) sur les points au-dessus du
    # bruit (efficace > 3 x celui du cas le plus bas)
    plancher = np.sqrt(a2.min())
    sel = np.sqrt(a2) > 3 * plancher
    if sel.sum() >= 2:
        s, b = np.polyfit(kp[sel], a2[sel], 1)
        kc = -b / s
        res_ = a2[sel] - (s * kp[sel] + b)
        print(f"\n  plancher (efficace le plus bas) : {plancher:.5f}")
        print(f"  ajustement sur {sel.sum()} points au-dessus de 3 x plancher :"
              f" Kc = {kc:.3f}  (residus relatifs max "
              f"{np.max(np.abs(res_) / a2[sel])*100:.0f} %)")
    np.save(ICI / "r2_dcm_resserre.npy", dict(kp=kp, a2=a2), allow_pickle=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
