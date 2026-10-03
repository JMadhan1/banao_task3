"""Value, price and delivery-cost arithmetic used in the case study. Every input is an assumption, named."""
import json
r = json.load(open("out/results.json"))["E1"]
m2 = {k: v["mean_offshade_m2"] for k, v in r.items()}
man, B, C = m2["Manual (today)"], m2["B: designed round"], m2["C: model + learn"]
line_day = 8000
scen = {
    "conservative": dict(events=2, price=5.0, loss=0.15, benefit_share=0.5),
    "base":         dict(events=3, price=6.0, loss=0.30, benefit_share=1.0),
    "high":         dict(events=4, price=8.0, loss=0.40, benefit_share=1.0),
}
out = {"offshade_m2_per_event": dict(manual=man, B=B, C=C)}
for name, s in scen.items():
    row = {}
    for meth, m in (("B", B), ("C", C)):
        saved = (man - m) * s["benefit_share"]
        per_event = saved * s["price"] * s["loss"]
        row[meth] = dict(m2_saved_per_event=round(saved), usd_per_event=round(per_event),
                         usd_per_month=round(per_event * s["events"]), usd_per_year=round(per_event * s["events"] * 12))
    row["offshade_share_of_output_today"] = round(man * s["events"] / (line_day * 30), 3)
    out[name] = row
# delivery cost (internal)
rates = dict(fde=700, ml=600, fs=500, advisor=900, partner=400)
p0 = dict(fde=12, advisor=4)
p1 = dict(fde=40, ml=35, fs=15, advisor=4, partner=10)
cost = lambda d: sum(rates[k] * v for k, v in d.items())
p0_cost = cost(p0) + 1 * 2500 + 7 * 150
p1_cost = cost(p1) + 2 * 2500 + 18 * 150 + 500
out["delivery"] = dict(phase0_people=cost(p0), phase0_total=p0_cost, phase1_people=cost(p1), phase1_total=p1_cost,
                       total=p0_cost + p1_cost,
                       price_total=25000 + 110000 - 12500,          # half of phase 0 credited if they continue
                       margin=round(1 - (p0_cost + p1_cost) / 122500, 3))
out["rollout_per_line"] = dict(onboarding=12000, subscription_month=3000, our_running_cost_month=40 + 350 + 110,
                               margin=round(1 - 500 / 3000, 3))
print(json.dumps(out, indent=1))
json.dump(out, open("out/value_model.json", "w"), indent=1)
