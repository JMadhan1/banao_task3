"""Stress tests on my own claims (results quoted in the case study, section 3 and 5).
  R1  What if the client's technicians pick the right channel more often than I assumed?
  R2  Can a 20-batch-change pilot tell a working method from a failing one? (binomial)
  R3  What if batch drift is half or double what I assumed?"""
import json, os
from functools import partial
import numpy as np
from scipy.stats import binom
import shade_sim
from experiments import manual, designed, prior_guess_and_learn, run, summarise

out = {}
# R1: manual technician skill (p_wrong = how often the wrong channel is picked)
out["R1_manual_skill"] = {}
for pw in (0.0, 0.1, 0.3):
    s = summarise(run(partial(manual, p_wrong=pw), seed=11, n=250))
    out["R1_manual_skill"][pw] = dict(in2=s["share_done_in_2"], mean_rounds=s["mean_rounds"], true_in_tol=s["share_truly_in_tol"])
    print("R1 p_wrong", pw, out["R1_manual_skill"][pw])
# R2: power of the 20-change paired test with the pass mark ">= 15 of 20 within 2 rounds"
out["R2_power"] = {f"true_rate_{p}": float(binom.sf(14, 20, p)) for p in (0.30, 0.50, 0.60, 0.70, 0.78, 0.90)}
print("R2 P(pass the >=15/20 bar | true success rate)", {k: round(v, 3) for k, v in out["R2_power"].items()})
# R3: drift scale
orig = shade_sim.Batch.__init__
out["R3_drift"] = {}
for sc in (0.5, 2.0):
    def patched(self, rng=None, scale=1.0, nominal=False, _sc=sc):
        orig(self, rng, scale * (_sc if not nominal else 1), nominal)
    shade_sim.Batch.__init__ = patched
    row = {}
    for name, pol in (("manual", manual), ("B", designed), ("C", prior_guess_and_learn)):
        s = summarise(run(pol, seed=11, n=200))
        row[name] = dict(in2=s["share_done_in_2"], m2=s["mean_offshade_m2"], needed=s["n_needed_correction"])
    out["R3_drift"][sc] = row
    print("R3 drift x", sc, row)
shade_sim.Batch.__init__ = orig
json.dump(out, open(os.path.join("out", "robustness.json"), "w"), indent=1)
