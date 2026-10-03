"""
Shade-correction engine: the whole "model" the pilot needs, in about 150 lines.

Input : spectrophotometer readings (L*, a*, b*, gloss) for each measured zone of
        - the master tile (or its stored digital target), and
        - the tiles fired in one round (base tile + one tile per ink channel nudged by +STEP (30 %)).
Output: a per-channel change to the ORIGINAL print file ("brown +6.5 %, yellow -3 %"),
        the colour difference it predicts per zone, and plain flags for anything the file
        cannot fix (gloss, an out-of-reach target, a noisy round).

The idea: the QC team already prints 6-7 variant tiles per lab round. If those variants
are chosen as "one channel at a time" instead of guessed, that same single round measures
how this batch responds to each ink (the local Jacobian). One least-squares solve then
gives the correction for all zones at once.

CLI:  python shade_tool.py example_round.csv
"""
from __future__ import annotations

import csv
import sys
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import lsq_linear

from shade_sim import INKS, N_INK, de2000

STEP = 0.30                      # +30 % relative on one channel per test tile (big enough to beat firing noise)
GAIN_BOUNDS = (-0.5, 0.8)        # never ask for more than -50 % / +80 % on a channel
TOL_DE00 = 1.0                   # pass mark per zone (placeholder until the client gives theirs)
GLOSS_TOL = 5.0                  # gloss units at 60 deg (placeholder)
RIDGE = 2.0                      # prefers small edits; in Lab units^2 per unit gain^2


def designed_round(g_now, step=STEP):
    """The 7 files to print: current file, then each channel nudged by +step."""
    files = [g_now.copy()]
    for i in range(N_INK):
        g = g_now.copy()
        g[i] += step
        files.append(g)
    return np.array(files)


def estimate_jacobian(lab_base, lab_pert, step=STEP):
    """lab_base (Z,3), lab_pert (6,Z,3) -> J (3Z, 6): change in Lab per unit of relative gain."""
    d = (lab_pert - lab_base[None]) / step              # (6, Z, 3)
    return d.reshape(N_INK, -1).T


def fit_local_linear(G, LAB, ridge=1e-3):
    """Fit Lab ~ a + J g by least squares over every tile fired so far near the current point.
    G (n,6), LAB (n,Z,3). Used from round 2 onward so no tile is wasted."""
    n = len(G)
    X = np.hstack([np.ones((n, 1)), G])
    Y = LAB.reshape(n, -1)
    A = X.T @ X + ridge * np.eye(X.shape[1])
    coef = np.linalg.solve(A, X.T @ Y)
    return coef[0], coef[1:].T                           # a (3Z,), J (3Z, 6)


def solve_correction(J, lab_now, lab_target, g_now, ridge=RIDGE, bounds=GAIN_BOUNDS, zone_w=None):
    """Smallest file change that moves every zone onto target, in least squares.
    Bounded so no channel goes past what the printer and the design team will accept."""
    err = (lab_target - lab_now).reshape(-1)             # what we need to move
    w = np.ones_like(err) if zone_w is None else np.repeat(zone_w, 3)
    A = np.vstack([J * w[:, None], np.sqrt(ridge) * np.eye(N_INK)])
    b = np.concatenate([err * w, np.zeros(N_INK)])
    lo = bounds[0] - g_now
    hi = bounds[1] - g_now
    res = lsq_linear(A, b, bounds=(lo, hi))
    dg = res.x
    pred = lab_now + (J @ dg).reshape(lab_now.shape)
    return dg, pred


@dataclass
class Recommendation:
    gain_change: np.ndarray
    predicted_lab: np.ndarray
    predicted_de: np.ndarray
    current_de: np.ndarray
    flags: list = field(default_factory=list)

    def text(self, zones=None):
        zones = zones or [f"zone {i + 1}" for i in range(len(self.current_de))]
        out = ["Recommended change to the ORIGINAL print file (relative, per ink channel):"]
        for ink, d in zip(INKS, self.gain_change):
            if abs(d) >= 0.005:
                out.append(f"  {ink:<7} {d * 100:+5.1f} %")
        out.append("Colour difference to master, dE2000 (now -> predicted after change):")
        for z, a, b in zip(zones, self.current_de, self.predicted_de):
            out.append(f"  {z:<10} {a:4.2f} -> {b:4.2f}")
        for f in self.flags:
            out.append(f"  ! {f}")
        out.append("Print the confirmation tile; QC signs off on the fired, measured result.")
        return "\n".join(out)


def recommend(lab_target, lab_base, lab_pert, g_now=None, gloss_target=None, gloss_base=None,
              repeat_de=None, tol=TOL_DE00):
    g_now = np.zeros(N_INK) if g_now is None else g_now
    J = estimate_jacobian(lab_base, lab_pert)
    dg, pred = solve_correction(J, lab_base, lab_target, g_now)
    rec = Recommendation(dg, pred, de2000(pred, lab_target), de2000(lab_base, lab_target))
    if np.any(rec.predicted_de > tol):
        rec.flags.append("Some zone stays out of tolerance even after the best file change: "
                         "check the ink limits or glaze; this one may not be fixable in the file.")
    if np.any(np.abs(dg + g_now - GAIN_BOUNDS[1]) < 1e-3) or np.any(np.abs(dg + g_now - GAIN_BOUNDS[0]) < 1e-3):
        rec.flags.append("A channel hit its allowed limit: the batch has drifted further than a file edit should cover.")
    if gloss_target is not None and gloss_base is not None and abs(gloss_base - gloss_target) > GLOSS_TOL:
        rec.flags.append(f"Gloss is off by {gloss_base - gloss_target:+.1f} GU. The print file can't fix gloss: "
                         "send to glaze/kiln.")
    if repeat_de is not None and repeat_de > 0.75 * tol:
        rec.flags.append("Two tiles from the same file differ by more than 0.75 x tolerance: the kiln, not the "
                         "file, is the problem today. Don't trust any file change until that is fixed.")
    return rec


# ----------------------------------------------------------------------------- CSV front end
def _read_round(path):
    """CSV columns: tile, zone, L, a, b, gloss. tile in {master, base, blue, brown, beige, yellow, pink, black}."""
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    zones = sorted({r["zone"] for r in rows}, key=lambda z: [r["zone"] for r in rows].index(z))
    def grab(tile):
        m = {r["zone"]: r for r in rows if r["tile"] == tile}
        lab = np.array([[float(m[z]["L"]), float(m[z]["a"]), float(m[z]["b"])] for z in zones])
        gl = np.mean([float(m[z]["gloss"]) for z in zones]) if all(m[z].get("gloss") for z in zones) else None
        return lab, gl
    tgt, gt = grab("master")
    base, gb = grab("base")
    pert = np.array([grab(ink)[0] for ink in INKS])
    return zones, tgt, gt, base, gb, pert


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "example_round.csv"
    zones, tgt, gt, base, gb, pert = _read_round(path)
    rec = recommend(tgt, base, pert, gloss_target=gt, gloss_base=gb)
    print(rec.text(zones))
