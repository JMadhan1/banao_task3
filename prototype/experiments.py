"""
Runs the experiments quoted in the case study and writes figures + results.json to out/.

  E1  Manual loop vs the two proposed methods, over 400 simulated batch changes
  E2  Firing-noise sweep: when does the method stop working? (the go/no-go gate)
  E3  Measuring one spot vs every colour zone of a patterned tile
  E4  Gloss: how much of it can the print file move?

  python experiments.py            (about 1-2 minutes)
"""
from __future__ import annotations

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from shade_sim import Batch, Kiln, N_INK, apply_file_gain, de2000, make_design
from shade_tool import STEP, designed_round, estimate_jacobian, fit_local_linear, solve_correction

OUT = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUT, exist_ok=True)

TOL = 1.0              # max dE2000 over zones to pass (placeholder for the client's tolerance)
MAX_ROUNDS = 6         # after this the team "lets it go" (the call described near-misses being accepted)
HOURS_PER_ROUND = 6.5  # client figure: 6-7 h per lab round
LINE_M2_PER_H = 8000 / 24   # one roller-kiln line at about 8,000 m2/day (assumption, see case study)
N_BATCH = 400
NOMINAL = Batch(nominal=True)


# ----------------------------------------------------------------------------- helpers
def score(lab, target):
    return de2000(lab, target).max()


def nominal_jacobian(c0, g):
    """Jacobian of the nominal (master-era) process. Stands in for the team's intuition
    (manual policy) and, with model error added, for a fleet model fitted on history (policy C)."""
    base = NOMINAL.fire(apply_file_gain(c0, g))
    cols = []
    for i in range(N_INK):
        gi = g.copy(); gi[i] += 0.02
        cols.append(((NOMINAL.fire(apply_file_gain(c0, gi)) - base) / 0.02).reshape(-1))
    return np.stack(cols, 1)


class Case:
    def __init__(self, rng, fire_sd=0.15):
        self.rng = rng
        self.c0 = make_design(rng)
        self.target = NOMINAL.fire(self.c0)                  # master tile, measured once and stored
        self.batch = Batch(rng)
        self.kiln = Kiln(self.batch, rng, fire_sd=fire_sd)

    def fire(self, g):
        return self.kiln.fire_and_measure(apply_file_gain(self.c0, g))

    def true_score(self, g):
        return score(self.batch.fire(apply_file_gain(self.c0, g)), self.target)


# ----------------------------------------------------------------------------- policies
def manual(case, p_wrong=0.3):
    """Today's loop as described on the call: pick ONE channel by eye/experience, print 6-7
    variants of different strength, fire, pick the best, repeat.
    Deliberately generous: the best variant is picked with the spectro, not by eye."""
    rng = case.rng
    g = np.zeros(N_INK)
    lab = case.fire(g)                                       # round 0: the first sample of the batch
    cur = score(lab, case.target)
    if cur <= TOL:
        return dict(rounds=0, tiles=1, final=case.true_score(g), passed=True)
    steps = np.array([0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15])
    for r in range(1, MAX_ROUNDS + 1):
        z = np.argmax(de2000(lab, case.target))
        need = (case.target - lab)[z]
        Jn = nominal_jacobian(case.c0, g).reshape(-1, 3, N_INK)[z]          # (3, 6)
        cos = (need @ Jn) / (np.linalg.norm(need) * np.linalg.norm(Jn, axis=0) + 1e-9)
        order = np.argsort(-np.abs(cos))
        ch = order[0] if rng.random() > p_wrong else rng.choice(order[1:4])
        sgn = np.sign(cos[ch]) or 1.0
        best = (cur, g, lab)
        for s in steps:
            gv = g.copy(); gv[ch] += sgn * s
            lv = case.fire(gv)
            sv = score(lv, case.target)
            if sv < best[0]:
                best = (sv, gv, lv)
        cur, g, lab = best
        if cur <= TOL:
            return dict(rounds=r, tiles=case.kiln.tiles_fired, final=case.true_score(g), passed=True)
    return dict(rounds=MAX_ROUNDS, tiles=case.kiln.tiles_fired, final=case.true_score(g), passed=False)


def _confirm(case, g, dg, G, LAB):
    """A confirmation round: the solution plus two step sizes around it (3 tiles)."""
    best = None
    for a in (0.85, 1.0, 1.15):
        gv = g + a * dg
        lv = case.fire(gv)
        G.append(gv); LAB.append(lv)
        sv = score(lv, case.target)
        if best is None or sv < best[0]:
            best = (sv, gv, lv)
    return best


def designed(case):
    """Method B (pilot, day one, no history needed): the round's 7 tiles become a designed
    experiment (current file + each channel +30 %). One solve, then a confirmation round."""
    g = np.zeros(N_INK)
    lab0 = case.fire(g)
    if score(lab0, case.target) <= TOL:
        return dict(rounds=0, tiles=1, final=case.true_score(g), passed=True)
    G, LAB = [g.copy()], [lab0]
    for r in range(1, MAX_ROUNDS + 1):
        if r == 1:
            files = designed_round(g)
            labs = [case.fire(f) for f in files]
            G += list(files); LAB += labs
            base = (labs[0] + lab0) / 2                      # first sample + repeat: less noise
            J = estimate_jacobian(base, np.array(labs[1:]))
            dg, _ = solve_correction(J, base, case.target, g)
            continue                                         # round 1 is pure measurement
        # every later round: confirm, and learn from every tile fired so far
        sv, gv, lv = _confirm(case, g, dg, G, LAB)
        if sv <= TOL:
            return dict(rounds=r, tiles=case.kiln.tiles_fired, final=case.true_score(gv), passed=True)
        g = gv
        a, J = fit_local_linear(np.array(G[-10:]), np.array(LAB[-10:]))
        now = (a + J @ g).reshape(-1, 3)
        dg, _ = solve_correction(J, now, case.target, g)
    return dict(rounds=MAX_ROUNDS, tiles=case.kiln.tiles_fired, final=case.true_score(g), passed=False)


def prior_guess_and_learn(case, model_err=0.5):
    """Method C (after ~3 months of logged rounds): a fitted model of the process gives a
    correction straight from the first-sample reading (minutes, no kiln). Round 1 prints that
    guess AND one tile per channel around it, so a miss still teaches us the local response."""
    g = np.zeros(N_INK)
    lab0 = case.fire(g)
    if score(lab0, case.target) <= TOL:
        return dict(rounds=0, tiles=1, final=case.true_score(g), passed=True)
    # imperfect fleet model = nominal process with model error
    fleet = Batch(case.rng, scale=model_err)
    Jp = []
    base_m = fleet.fire(apply_file_gain(case.c0, g))
    for i in range(N_INK):
        gi = g.copy(); gi[i] += 0.02
        Jp.append(((fleet.fire(apply_file_gain(case.c0, gi)) - base_m) / 0.02).reshape(-1))
    Jp = np.stack(Jp, 1)
    dg, _ = solve_correction(Jp, lab0, case.target, g)
    G, LAB = [g.copy()], [lab0]
    for r in range(1, MAX_ROUNDS + 1):
        guess = g + dg
        if r == 1:
            files = designed_round(guess)
            labs = [case.fire(f) for f in files]
            G += list(files); LAB += labs
            sv = score(labs[0], case.target)
            if sv <= TOL:
                return dict(rounds=1, tiles=case.kiln.tiles_fired, final=case.true_score(guess), passed=True)
            g = guess
            J = estimate_jacobian(labs[0], np.array(labs[1:]))
            dg, _ = solve_correction(J, labs[0], case.target, g)
            continue
        sv, gv, lv = _confirm(case, g, dg, G, LAB)
        if sv <= TOL:
            return dict(rounds=r, tiles=case.kiln.tiles_fired, final=case.true_score(gv), passed=True)
        g = gv
        a, J = fit_local_linear(np.array(G[-10:]), np.array(LAB[-10:]))
        now = (a + J @ g).reshape(-1, 3)
        dg, _ = solve_correction(J, now, case.target, g)
    return dict(rounds=MAX_ROUNDS, tiles=case.kiln.tiles_fired, final=case.true_score(g), passed=False)


POLICIES = {"Manual (today)": manual, "B: designed round": designed, "C: model + learn": prior_guess_and_learn}


def run(policy, seed, n=N_BATCH, fire_sd=0.15):
    rng = np.random.default_rng(seed)
    res = []
    for _ in range(n):
        case = Case(rng, fire_sd=fire_sd)
        res.append(policy(case))
    return res


def summarise(res):
    need = [r for r in res if r["rounds"] > 0]               # batch changes that needed correcting
    rounds = np.array([r["rounds"] for r in need])
    passed = np.array([r["passed"] for r in need])
    final = np.array([r["final"] for r in need])
    tiles = np.array([r["tiles"] for r in need])
    hours = rounds * HOURS_PER_ROUND
    return dict(
        n_batch=len(res), n_needed_correction=len(need),
        mean_rounds=float(rounds.mean()), median_rounds=float(np.median(rounds)),
        share_done_in_1=float((passed & (rounds <= 1)).mean()),
        share_done_in_2=float((passed & (rounds <= 2)).mean()),
        share_never=float((~passed).mean()),
        mean_hours=float(hours.mean()),
        mean_offshade_m2=float((hours * LINE_M2_PER_H).mean()),
        mean_tiles=float(tiles.mean()),
        true_final_de_median=float(np.median(final)),
        true_final_de_p90=float(np.percentile(final, 90)),
        share_truly_in_tol=float((final <= TOL).mean()),
        rounds_hist={int(k): int(v) for k, v in zip(*np.unique(rounds, return_counts=True))},
    )


# ----------------------------------------------------------------------------- E1
def e1():
    out = {}
    for name, pol in POLICIES.items():
        out[name] = summarise(run(pol, seed=11))
        print(f"{name:<22}", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out[name].items()})
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    cols = ["#9aa0a6", "#1a73e8", "#0b8043"]
    for k, (name, s) in enumerate(out.items()):
        h = s["rounds_hist"]; n = sum(h.values())
        xs = np.arange(1, MAX_ROUNDS + 1)
        ys = [100 * h.get(int(x), 0) / n for x in xs]
        ax[0].bar(xs + (k - 1) * 0.27, ys, width=0.27, color=cols[k], label=name)
    ax[0].set_xlabel("Kiln rounds after the first sample (6 = gave up)")
    ax[0].set_ylabel("% of batch changes")
    ax[0].set_title("Rounds to bring every zone within dE2000 1.0")
    ax[0].legend(frameon=False, fontsize=8)
    names = list(out)
    m2 = [out[n]["mean_offshade_m2"] for n in names]
    ax[1].barh(names, m2, color=cols)
    for i, v in enumerate(m2):
        ax[1].text(v, i, f" {v:,.0f} m²  ({out[names[i]]['mean_hours']:.1f} h)", va="center", fontsize=9)
    ax[1].set_xlim(0, max(m2) * 1.45)
    ax[1].set_title("Off-shade output per batch change (mean)")
    ax[1].invert_yaxis()
    for a in ax: a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e1_rounds.png"), dpi=160); plt.close(fig)
    return out


# ----------------------------------------------------------------------------- E2
def e2():
    sds = [0.05, 0.10, 0.15, 0.25, 0.35, 0.50, 0.70]
    rows = []
    for sd in sds:
        rng = np.random.default_rng(5)
        rep = []
        for _ in range(200):                                  # firing repeatability (same file twice)
            c = Case(rng, fire_sd=sd)
            rep.append(de2000(c.fire(np.zeros(N_INK)), c.fire(np.zeros(N_INK))).max())
        s = summarise(run(designed, seed=21, n=150, fire_sd=sd))
        m = summarise(run(manual, seed=21, n=150, fire_sd=sd))
        rows.append(dict(fire_sd=sd, repeat_de_median=float(np.median(rep)),
                         designed_in2=s["share_done_in_2"], designed_true_in_tol=s["share_truly_in_tol"],
                         manual_in2=m["share_done_in_2"], manual_true_in_tol=m["share_truly_in_tol"]))
        print("E2", rows[-1])
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    x = [r["repeat_de_median"] for r in rows]
    ax.plot(x, [100 * r["designed_in2"] for r in rows], "o-", color="#1a73e8", label="B: passes within 2 rounds")
    ax.plot(x, [100 * r["designed_true_in_tol"] for r in rows], "o--", color="#1a73e8", alpha=.5,
            label="B: truly within tolerance at sign-off")
    ax.plot(x, [100 * r["manual_in2"] for r in rows], "s-", color="#9aa0a6", label="Manual: passes within 2 rounds")
    ax.axvspan(0.75 * TOL, max(x) * 1.05, color="#d93025", alpha=.07)
    ax.text(0.75 * TOL + .02, 4, "stop zone: two tiles from the same file\ndiffer by more than 0.75 x tolerance",
            fontsize=8, color="#a50e0e")
    ax.set_xlabel("Firing repeatability: dE2000 between two tiles from the same file (median)")
    ax.set_ylabel("% of batch changes"); ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e2_noise_gate.png"), dpi=160); plt.close(fig)
    return rows


# ----------------------------------------------------------------------------- E3
def e3():
    """Same designed round, but the solve only sees the zone a single spot reading would hit."""
    rng = np.random.default_rng(31)
    one, allz, before = [], [], []
    for _ in range(300):
        c = Case(rng)
        g = np.zeros(N_INK)
        files = designed_round(g)
        labs = np.array([c.fire(f) for f in files])
        if score(labs[0], c.target) <= TOL:
            continue
        before.append(c.true_score(g))
        J = estimate_jacobian(labs[0], labs[1:])
        dg, _ = solve_correction(J, labs[0], c.target, g)
        allz.append(c.true_score(g + dg))
        z = 0                                             # the spot the technician happens to measure
        J1 = J.reshape(-1, 3, N_INK)[z]
        dg1, _ = solve_correction(J1, labs[0][z:z + 1], c.target[z:z + 1], g)
        one.append(c.true_score(g + dg1))
    one, allz, before = map(np.array, (one, allz, before))
    r = dict(n=len(one), before_median=float(np.median(before)),
             one_spot_median=float(np.median(one)), one_spot_in_tol=float((one <= TOL).mean()),
             all_zone_median=float(np.median(allz)), all_zone_in_tol=float((allz <= TOL).mean()))
    print("E3", r)
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    bins = np.linspace(0, 4, 33)
    ax.hist(before, bins, color="#dadce0", label="before correction")
    ax.hist(one, bins, histtype="step", lw=2, color="#e37400", label="solve using one spot")
    ax.hist(allz, bins, histtype="step", lw=2, color="#1a73e8", label="solve using all 4 zones")
    ax.axvline(TOL, color="#d93025", ls=":", lw=1)
    ax.set_xlabel("Worst zone dE2000 after one correction (true, noise-free)")
    ax.set_ylabel("batch changes"); ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e3_zones.png"), dpi=160); plt.close(fig)
    return r


# ----------------------------------------------------------------------------- E4
def e4():
    rng = np.random.default_rng(41)
    off, reach = 0, []
    for _ in range(400):
        c = Case(rng)
        gl0 = c.batch.gloss_of(apply_file_gain(c.c0, np.zeros(N_INK)))
        tgt = NOMINAL.gloss_of(c.c0)
        if abs(gl0 - tgt) > 5:
            off += 1
        hi = c.batch.gloss_of(apply_file_gain(c.c0, np.full(N_INK, -0.3)))
        lo = c.batch.gloss_of(apply_file_gain(c.c0, np.full(N_INK, 0.3)))
        reach.append(hi - lo)
    r = dict(share_gloss_off_5GU=off / 400, file_gloss_range_GU_at_pm30pct=float(np.median(reach)))
    print("E4", r)
    return r


if __name__ == "__main__":
    results = dict(E1=e1(), E2=e2(), E3=e3(), E4=e4(),
                   settings=dict(TOL=TOL, MAX_ROUNDS=MAX_ROUNDS, HOURS_PER_ROUND=HOURS_PER_ROUND,
                                 LINE_M2_PER_H=LINE_M2_PER_H, N_BATCH=N_BATCH, STEP=STEP))
    json.dump(results, open(os.path.join(OUT, "results.json"), "w"), indent=2)
    print("wrote", OUT)
