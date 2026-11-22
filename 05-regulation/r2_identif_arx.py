"""R2 -- limite du P depuis le plant identifie : modele parametrique.

La somme directe de h[n] (r2_identif.py) est inutilisable : le bruit de la
queue (ecart-type 0,027 en DCM sur 1500 echantillons, 0,76 en CCM) somme
dans H(e^j.theta) autant que le signal aux frequences utiles, et fabrique
des passages a -180 deg multiples.

Ici : modele discret B(z)/A(z) ajuste par moindres carres (ARX) sur la
reponse indicielle y[n] (entree u = echelon unite a n = 0), ordres
na/nb balayes ; on garde le plus petit qui reproduit y (erreur RMS
relative < 2 %). Puis la boucle du banc, d[n] = -Kp.s[n-2] :
    A(z).z^2 + Kp.B(z) = 0      (polynomes en z)
Kp limite = le plus petit Kp ou une racine atteint |z| = 1 (bissection),
et la frequence = argument de cette racine.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.signal import lfilter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
FSW = 200e3


def arx(y, na, nb, n_fit):
    """y[n] + a1 y[n-1] + ... = b0 u[n] + b1 u[n-1] + ..., u = 1 (n>=0)."""
    y = y[:n_fit]
    u = np.ones_like(y)
    rows, rhs = [], []
    for n in range(max(na, nb), len(y)):
        rows.append([-y[n - i] for i in range(1, na + 1)]
                    + [u[n - j] for j in range(0, nb + 1)])
        rhs.append(y[n])
    th, *_ = np.linalg.lstsq(np.array(rows), np.array(rhs), rcond=None)
    a = np.concatenate(([1.0], th[:na]))
    b = th[na:]
    ysim = lfilter(b, a, np.ones(len(y)))
    err = np.sqrt(np.mean((ysim - y) ** 2)) / np.sqrt(np.mean(y ** 2))
    return a, b, ysim, err


def rayon_max(a, b, kp):
    """Racines de A(z) + Kp.z^-2.B(z) = 0.

    A = 1 + a1 z^-1 + ... + a_na z^-na ; B = b0 + b1 z^-1 + ... + b_nb z^-nb.
    Multiplie par z^N, N = max(na, nb + 2) : coefficients en puissances
    DECROISSANTES de z, B decale de deux crans (le retard du banc).
    Premiere version : B n'etait pas decale -- erreur corrigee.
    """
    na, nb = len(a) - 1, len(b) - 1
    N = max(na, nb + 2)
    p = np.zeros(N + 1)
    p[:na + 1] += a
    p[2:2 + nb + 1] += kp * np.asarray(b, dtype=float)
    r = np.roots(p)
    i = int(np.argmax(np.abs(r)))
    return abs(r[i]), r[i]


def limite(a, b, k_hi):
    lo, hi = 0.0, k_hi
    if rayon_max(a, b, hi)[0] < 1:
        return None, None
    for _ in range(80):
        m = 0.5 * (lo + hi)
        if rayon_max(a, b, m)[0] < 1:
            lo = m
        else:
            hi = m
    rr, r = rayon_max(a, b, hi)
    return hi, abs(np.angle(r)) / (2 * np.pi) * FSW


def main():
    ref = {"ccm": (0.0207, 4.85e3, 0.5), "dcm": (1.345, 30.6e3, 20.0)}
    for mode in ("ccm", "dcm"):
        D = np.load(ICI / f"zi_{mode}.npz")
        y = D["y"]
        n_fit = 800 if mode == "ccm" else 1500
        print(f"  {mode.upper()}  (k-section : Kp {ref[mode][0]} a "
              f"{ref[mode][1]/1e3:.2f} kHz)")
        best = None
        for na in range(1, 7):
            for nb in range(1, 7):
                a, b, ysim, err = arx(y, na, nb, n_fit)
                if np.any(np.abs(np.roots(a)) >= 1):    # modele instable : rejet
                    continue
                kl, fl = limite(a, b, ref[mode][2])
                tag = f"na {na} nb {nb}"
                if err < 0.05:
                    print(f"     {tag}  erreur {err*100:5.2f} %  ->  Kp limite "
                          f"{kl if kl is None else round(kl, 4)}  a "
                          f"{'-' if fl is None else f'{fl/1e3:.2f} kHz'}")
                    if best is None or na + nb < best[0]:
                        best = (na + nb, na, nb, err, kl, fl)
        if best:
            _, na, nb, err, kl, fl = best
            print(f"     -> modele le plus simple sous 5 % : na {na} nb {nb}"
                  f" ({err*100:.2f} %), Kp limite {kl:.4f} a {fl/1e3:.2f} kHz\n")
        else:
            print("     aucun modele sous 5 % d'erreur\n")


if __name__ == "__main__":
    main()
