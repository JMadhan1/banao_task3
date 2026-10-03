"""
Synthetic "print -> fire -> measure" simulator for a 6-ink ceramic inkjet line.

This is not a model of the client's line. It is a deliberately plausible stand-in
that has the properties that matter for the argument in the case study:

  * colour develops in the kiln, and each new batch (body / glaze / ink lot, kiln
    drift) changes how strongly each ink develops, so the SAME print file gives a
    DIFFERENT fired colour;
  * the response of fired colour to the file is non-linear (Kubelka-Munk mixing,
    dot gain) and the 6 inks interact;
  * a patterned tile has several colour zones, and one global edit to a channel
    moves all of them at once;
  * every fired tile carries firing noise, and the spectrophotometer adds a little more;
  * gloss is set by glaze and kiln, and the print file barely moves it.

Physics used (all textbook, all simplified):
  - spectral grid 400-700 nm, 10 nm steps
  - single-constant Kubelka-Munk: K/S of the mix = substrate K/S + sum of ink K/S
  - CIE 1931 2 deg observer from the Wyman-Sloan-Shirley (2013) analytic fit
  - illuminant: 6504 K Planckian (a stand-in for D65)
  - CIELAB and CIEDE2000
"""
from __future__ import annotations

import numpy as np

WL = np.arange(400, 701, 10, dtype=float)          # 31 bands
INKS = ["blue", "brown", "beige", "yellow", "pink", "black"]
N_INK = len(INKS)


# ----------------------------------------------------------------------------- colour science
def _g(x, mu, s1, s2):
    s = np.where(x < mu, s1, s2)
    return np.exp(-0.5 * ((x - mu) / s) ** 2)


def _cmf(wl):
    x = 1.056 * _g(wl, 599.8, 37.9, 31.0) + 0.362 * _g(wl, 442.0, 16.0, 26.7) - 0.065 * _g(wl, 501.1, 20.4, 26.2)
    y = 0.821 * _g(wl, 568.8, 46.9, 40.5) + 0.286 * _g(wl, 530.9, 16.3, 31.1)
    z = 1.217 * _g(wl, 437.0, 11.8, 36.0) + 0.681 * _g(wl, 459.0, 26.0, 13.8)
    return np.stack([x, y, z])


def _planck(wl_nm, T=6504.0):
    wl = wl_nm * 1e-9
    h, c, k = 6.626e-34, 2.998e8, 1.381e-23
    return 1.0 / (wl ** 5 * (np.exp(h * c / (wl * k * T)) - 1.0))


CMF = _cmf(WL)
ILL = _planck(WL)
ILL = ILL / ILL.max()
_NORM = 100.0 / (CMF[1] * ILL).sum()
WHITE = _NORM * (CMF * ILL).sum(axis=1)             # XYZ of the perfect diffuser


def refl_to_lab(R):
    """R: (..., 31) reflectance -> (..., 3) CIELAB."""
    XYZ = _NORM * np.einsum("...w,cw->...c", R * ILL, CMF)
    t = XYZ / WHITE
    d = 6 / 29
    f = np.where(t > d ** 3, np.cbrt(t), t / (3 * d * d) + 4 / 29)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def de2000(lab1, lab2):
    """CIEDE2000, vectorised over leading axes."""
    L1, a1, b1 = np.moveaxis(np.asarray(lab1, float), -1, 0)
    L2, a2, b2 = np.moveaxis(np.asarray(lab2, float), -1, 0)
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp = L2 - L1
    dCp = C2p - C1p
    dh = h2p - h1p
    dh = np.where(C1p * C2p == 0, 0, np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh)))
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh / 2))
    Lbp = (L1 + L2) / 2
    Cbp = (C1p + C2p) / 2
    hs = h1p + h2p
    hbp = np.where(C1p * C2p == 0, hs,
                   np.where(np.abs(h1p - h2p) <= 180, hs / 2,
                            np.where(hs < 360, (hs + 360) / 2, (hs - 360) / 2)))
    T = (1 - 0.17 * np.cos(np.radians(hbp - 30)) + 0.24 * np.cos(np.radians(2 * hbp))
         + 0.32 * np.cos(np.radians(3 * hbp + 6)) - 0.20 * np.cos(np.radians(4 * hbp - 63)))
    dtheta = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


# ----------------------------------------------------------------------------- ink set
def _ks_from_peak(mu, w, amp):
    return amp * np.exp(-0.5 * ((WL - mu) / w) ** 2)


def ink_ks(shift_nm=None):
    """Unit-coverage K/S spectra (6, 31) for a generic ceramic ink set."""
    s = np.zeros(N_INK) if shift_nm is None else shift_nm
    blue = _ks_from_peak(610 + s[0], 55, 2.2) + _ks_from_peak(540 + s[0], 40, 0.6)
    brown = 1.6 / (1 + np.exp((WL - (560 + s[1])) / 45)) + 0.25
    beige = 0.45 / (1 + np.exp((WL - (520 + s[2])) / 40)) + 0.04
    yellow = _ks_from_peak(430 + s[3], 30, 2.0) + _ks_from_peak(470 + s[3], 25, 0.8)
    pink = _ks_from_peak(530 + s[4], 35, 1.5) + _ks_from_peak(450 + s[4], 50, 0.3)
    black = np.full_like(WL, 3.0) + 0.3 * (700 - WL) / 300
    return np.stack([blue, brown, beige, yellow, pink, black])


SUB_KS0 = 0.025 + 0.06 / (1 + np.exp((WL - 440) / 25))     # off-white glaze/engobe
GAMMA = np.array([0.85, 0.80, 0.90, 0.85, 0.85, 0.75])       # dot-gain style non-linearity


class Batch:
    """Everything about one production batch that the print file does not control."""

    def __init__(self, rng=None, scale=1.0, nominal=False):
        rng = np.random.default_rng() if rng is None else rng
        if nominal:
            self.strength = np.ones(N_INK)
            self.shift = np.zeros(N_INK)
            self.sub = 1.0
            self.sub_tilt = 0.0
            self.gloss = 0.0
        else:
            # ink development strength per ink: kiln temperature/time, glaze chemistry, ink lot
            self.strength = 1 + scale * rng.normal(0, 0.14, N_INK)
            # small hue shifts in how the pigment develops
            self.shift = scale * rng.normal(0, 4.0, N_INK)
            # body/glaze whiteness and yellowing
            self.sub = 1 + scale * rng.normal(0, 0.35)
            self.sub_tilt = scale * rng.normal(0, 0.03)
            # gloss offset from glaze/kiln, in gloss units (60 deg)
            self.gloss = scale * rng.normal(0, 3.0)
        self.ks = ink_ks(self.shift)

    def fire(self, cov):
        """cov: (..., 6) ink coverage in [0, 1] -> (..., 3) fired Lab (noise-free)."""
        cov = np.clip(cov, 0, 1)
        sub = SUB_KS0 * self.sub + self.sub_tilt * np.clip((480 - WL) / 80, 0, None)
        ks = sub + np.einsum("...i,iw->...w", (cov ** GAMMA) * self.strength, self.ks)
        R = 1 + ks - np.sqrt(ks ** 2 + 2 * ks)
        return refl_to_lab(R)

    def gloss_of(self, cov):
        """60-degree gloss: set by glaze/kiln; heavier ink load knocks it down slightly."""
        return 85.0 + self.gloss - 4.0 * np.clip(cov, 0, 1).sum(axis=-1).mean()


# ----------------------------------------------------------------------------- tile design
def make_design(rng, n_zones=4):
    """A patterned tile = a few dominant colour zones, each with its own 6-ink recipe."""
    base = np.array([
        [0.05, 0.35, 0.40, 0.20, 0.05, 0.03],   # warm beige-brown (stone body colour)
        [0.03, 0.60, 0.20, 0.10, 0.10, 0.12],   # dark brown vein
        [0.15, 0.10, 0.25, 0.05, 0.02, 0.05],   # cool grey highlight
        [0.02, 0.20, 0.55, 0.35, 0.08, 0.01],   # sandy yellow
        [0.25, 0.15, 0.10, 0.02, 0.15, 0.20],   # blue-grey shadow
    ])
    pick = rng.choice(len(base), n_zones, replace=False)
    jitter = rng.normal(0, 0.03, (n_zones, N_INK))
    return np.clip(base[pick] + jitter, 0.0, 0.9)


def apply_file_gain(c0, gain):
    """What the QC team does in Photoshop: scale each ink channel of the ORIGINAL file by (1 + gain)."""
    return np.clip(c0 * (1 + gain), 0, 1)


class Kiln:
    """Fires tiles: true colour + firing noise (tile-level and zone-level) + spectro noise."""

    def __init__(self, batch, rng, fire_sd=0.15, zone_sd=0.08, meas_sd=0.05):
        self.b, self.rng = batch, rng
        self.fire_sd, self.zone_sd, self.meas_sd = fire_sd, zone_sd, meas_sd
        self.tiles_fired = 0

    def fire_and_measure(self, cov):
        """cov: (Z, 6) zone coverages for ONE tile -> measured (Z, 3) Lab."""
        self.tiles_fired += 1
        lab = self.b.fire(cov)
        lab = lab + self.rng.normal(0, self.fire_sd, 3)                  # whole tile shifted
        lab = lab + self.rng.normal(0, self.zone_sd, lab.shape)          # local variation
        lab = lab + self.rng.normal(0, self.meas_sd, lab.shape)          # instrument
        return lab
