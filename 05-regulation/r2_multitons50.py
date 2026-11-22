"""R2 -- plant CCM a 50 W (pire point) par injection multi-tons, 2-20 kHz.

Meme methode que r2_multitons.py (validee : CCM 30 W a -5 % de la
k-section), elargie : une derivee fait monter le croisement, il faut H
au-dela de 7 kHz. 19 tons de 2 a 20 kHz, amplitude reduite par ton
(0,0003) pour garder la somme petite. D0 relu dans le regime etabli de la
k-section Ki a 50 W (z50Ki*). Sortie : zm_ccm50.npz, r2_multitons50.npy.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import r2_identif as idf                                     # noqa: E402
import r2_multitons as mt                                    # noqa: E402
import ltspice_run                                           # noqa: E402

idf.MODES["ccm50"] = dict(p=50.0, rl=80.0 ** 2 / 50.0,
                          src=("z50Ki[0-9]_*.npz", 0.00558), dd=0.001)
BANDE = "haute" if "haute" in sys.argv else "basse"
# bande basse 2-20 kHz ; bande haute 20-60 kHz : la derivee fait remonter
# le gain vers fsw/2, la marge de gain se lit au-dela de 20 kHz.
mt.TONS["ccm50"] = (dict(f=np.arange(2000, 20001, 1000), amp=0.0003)
                    if BANDE == "basse" else
                    dict(f=np.arange(20000, 60001, 2500), amp=0.0005))
mt.REF["ccm50"] = (0.0135, 4.0e3)


def main() -> int:
    blanc = "blanc" in sys.argv
    n_tot = 6 if blanc else mt.N_ETAB + mt.N_FEN + 2
    f = mt.prepare("ccm50", n_tot)
    r = ltspice_run.lance(f)
    print(f"  ccm50 ({n_tot} periodes) : {'OK' if r['ok'] else 'ECHEC'}"
          f"  D0 {idf.MODES['ccm50']['d0']:.4f}  {r['diagnostic'][:80]}")
    if not r["ok"] or blanc:
        if r["ok"]:
            f.with_suffix(".raw").unlink()
        return 0 if r["ok"] else 1
    d, s = mt.sequences(f, "ccm50", n_tot)
    np.savez(ICI / f"zm_ccm50_{BANDE}.npz", d=d, s=s)
    f.with_suffix(".raw").unlink()
    rows = mt.analyse("ccm50", d, s)
    lim = mt.lecture("ccm50", rows)
    np.save(ICI / ("r2_multitons50.npy" if BANDE == "basse" else "r2_multitons50_haute.npy"), dict(rows=rows, lim=lim),
            allow_pickle=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
