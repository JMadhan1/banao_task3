"""Writes example_round.csv: what the lab would export after one designed round on a simulated
batch change (master + base + one tile per channel, 4 zones, L a b gloss), then runs the tool."""
import csv
import numpy as np
from shade_sim import Batch, Kiln, INKS, apply_file_gain, make_design
from shade_tool import designed_round

rng = np.random.default_rng(7)
c0 = make_design(rng)
nominal, batch = Batch(nominal=True), Batch(rng)
kiln = Kiln(batch, rng)
zones = ["beige body", "brown vein", "grey light", "sand"]
rows = []
lab_m = nominal.fire(c0)
for z, (L, a, b) in enumerate(lab_m):
    rows.append(dict(tile="master", zone=zones[z], L=round(L, 2), a=round(a, 2), b=round(b, 2),
                     gloss=round(nominal.gloss_of(c0), 1)))
for name, g in zip(["base"] + INKS, designed_round(np.zeros(6))):
    cov = apply_file_gain(c0, g)
    lab = kiln.fire_and_measure(cov)
    gl = batch.gloss_of(cov) + rng.normal(0, 0.5)
    for z, (L, a, b) in enumerate(lab):
        rows.append(dict(tile=name, zone=zones[z], L=round(L, 2), a=round(a, 2), b=round(b, 2), gloss=round(gl, 1)))
with open("example_round.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
print("wrote example_round.csv,", len(rows), "rows")
