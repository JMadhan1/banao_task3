# Submission form: Task 3, Client A (Ceramic Tiles)

**Case study:** `case-study.pdf` (source: `case-study.md`) · **One-page client note:** `note-to-procurement-lead.pdf` · **Prototype:** `prototype/`

## In two sentences: what is the client's real problem, and how is it different from what they asked for?

The client's real problem is that they can't translate a measured colour difference into a print-file change that works for the *current* batch, so they guess one ink channel at a time, and every guess costs a 6–7 h kiln round and thousands of m² of off-shade tiles. They asked for a vision system that compares the master and production tiles within minutes, but their spectrophotometer already does that comparison, and one firing is unavoidable, so what they need is fewer kiln rounds per batch change, with corrections made from the original file against a stored numeric master.

## Who are the people in this deal, and what does each of them need to hear from you?

- **Special Projects Lead (procurement, the champion):** a proof on their own tiles within 3 weeks, a fixed price, and a clear stop point, so they can show internally that it can be done.
- **Head of IT & OT Procurement:** no new hardware for the pilot, nothing writes to the printer, it runs on-prem on a lab PC, and we can get people to the UAE plant.
- **Plant QC/lab team (the real users, absent from call 1):** fewer re-fires, they keep the sign-off, and the tool shows its working ("brown +9.6%"). It removes guesswork, not their judgement.
- **Design team:** original files are never overwritten, and every correction is versioned and can be undone.
- **Plant/production manager:** fewer off-shade m² and no extra kiln slots.
- **Printer OEM / ink supplier:** we stay vendor-neutral, touch files only, and never touch the machine.

## The five questions you would ask on the next call, ranked. For each one: why it matters, and what you assumed while you wait for the answer.

1. **If you print the same file on 5 tiles in one kiln pass, how far apart are they (ΔE)?** If the kiln can't repeat itself, no file correction can be judged, and the approach fails (this is my stop rule). *Assumed:* ≤ 0.5 ΔE2000 tile to tile, and a 1.5–3 ΔE shift at batch change.
2. **What exactly changes at a "batch change", and can the new material be sampled before the changeover?** It defines the drift. Early sampling would let the correction finish before the line switches, for near-zero off-shade m². *Assumed:* a new body/glaze lot when an SKU is re-run, with no early sampling today.
3. **Which printers and RIP, and how is the file edited (channels, global vs local edits)? Is there an unused colour-management module (EFI Fiery, ColorGATE)?** It decides the output format, and whether to configure what they already own before building. *Assumed:* 6-channel files edited with global per-channel changes, and no repeat-job colour management in use.
4. **What is the pass mark and who signs off (ΔE formula and limit, per zone, gloss limit, where they measure)?** It defines success. "Nearly matching" isn't a metric. *Assumed:* ≤ 1.0 ΔE2000 on each zone, ±5 GU gloss at 60°, a single spot measured per tile today.
5. **Do logs of past correction rounds exist, and what is an off-shade m² worth (downgrade, scrap, separate lot)?** Logs bring forward the stronger model-based method. The off-shade value *is* the business case. *Assumed:* partial Excel logs, and a 30% value loss on a ~$6/m² tile.

## Which options did you consider, and why did you pick the one you did? What did you rule out, and why?

- **Considered:**
  - an inline camera ("video analytics");
  - buying or enabling a commercial ceramic colour-management system (Durst/ColorGATE "Fingerprint", which claims 0–2 test runs; EFI Fiery proServer);
  - a spectral physics model;
  - machine learning on historical rounds;
  - a kiln/raw-material root-cause programme;
  - a **designed round plus solver** that grows into **model plus learn**.
- **Picked the designed round.** The team already prints 6–7 variants per kiln round, but all are guesses on one channel. If those same 7 tiles are the current file plus each of the 6 channels nudged by +30%, one round measures how this batch responds to every ink in every colour zone. A bounded least-squares solve then corrects all zones at once.
  - It needs no hardware, no printer integration and no history, and it works on day one.
  - Logged rounds then train a prior model (method C) that proposes a correction from the first sample in minutes.
  - In my simulator (400 batch changes), the share fixed within 2 rounds goes from 28% (manual) to 78% (B) and 92% (C). Off-shade output per batch change goes from about 8,900 m² to 5,300 m² (B) and 3,300 m² (C).
  - Stress-tested: even a technician who *always* picks the right channel only reaches 44%. The limit is one channel per round, not skill.
  - Honest limit: for small drifts the designed round costs more than it saves, so it runs only when the first sample is > 1.5 ΔE off. Method C beats manual at every drift size I tested.
  - The biggest win needs no software: if new batch material can be test-fired before the changeover, the correction is ready before the line switches.
- **Ruled out:**
  - **The camera:** it solves measurement, which already works, and is worse than a spectro on glossy, textured tile.
  - **Root cause:** the client said it's out of scope. We log batch metadata so it can be studied later.
  - **Pure ML now:** clean history probably doesn't exist yet.
  - **A commercial colour-management system:** not ruled out, but checked first. If they already license one, enabling it is cheaper, and I'd tell them so.

## How will the client know the pilot worked? Metric, baseline, threshold, how many runs, who measures, and what result would make you stop.

- **Metric:** share of batch changes approved within **2 kiln rounds** after the first sample. **Secondary metrics:**
  - true shade at sign-off (all zones within tolerance on 3 blind re-measured tiles);
  - off-shade m² per batch change;
  - test tiles used;
  - unprompted use by QC.
- **Baseline:** 4 weeks of logging the current process on the pilot lines, before the tool runs, plus any historical lab logs. Approved tiles are re-measured blind, because my simulation suggests many manual "passes" are false.
- **Threshold:**
  - ≥ 75% within 2 rounds (≥ 15 of 20);
  - true in-tolerance no worse than baseline;
  - off-shade m² down ≥ 35%.
- **Runs:**
  - kiln gate in week 2 (5 tiles × 2 passes);
  - bench test on 10 SKUs in weeks 5–7;
  - **20 real batch changes** across ≥ 6 SKUs in weeks 8–11. Each is a paired test: the manual variants and our designed round go through the same kiln pass, and tiles are coded so measurement is blind.
- **Who measures:** the client's lab technician measures, the QC head decides pass or fail, and we never touch the readings.
- **Stop if:**
  - (a) two tiles from the same file differ by more than 0.75 × tolerance. The kiln is the problem then, not the file, and the simulation shows the method's advantage disappears beyond that point;
  - (b) fewer than 50% of bench cases are in tolerance after one designed round;
  - (c) the tool wins fewer than 12 of 20 paired comparisons.
- **Is 20 enough?** A method that truly works 78% of the time clears the ≥ 15/20 bar 73% of the time, and a 50% method clears it 2% of the time (binomial). A 13–14/20 result means extend by 10 batch changes, not stop.

## What does this cost the client, and what does it cost us to deliver? Show the arithmetic and name the pricing structure. What value does the client get, in their money?

- **Our cost:**
  - Phase 0: FDE 12 days × $700 + advisor 4 days × $900 + $2,500 travel + $1,050 per diem = **$15,550**.
  - Phase 1: FDE 40 × $700 + ML/colour engineer 35 × $600 + full-stack 15 × $500 + advisor 4 × $900 + UAE partner 10 × $400 = $64,100, plus $5,000 travel, $2,700 per diem and $500 tools = **$72,300**.
  - **Total: $87,850.**
- **Price (fixed-fee phases with an outcome-weighted milestone, then a per-line subscription):**
  - Phase 0: **$25,000** fixed, half credited against phase 1.
  - Phase 1: **$110,000** fixed: 30% at kickoff, 30% at the week-7 bench readout, **40% only if the week-12 threshold is met**. If they continue: $25k + $110k − $12.5k credit = **$122.5k** against $87.85k of cost, a 28% margin.
  - Rollout: **$12k setup + $3k per line per month**. Our running cost is about $500 per line per month, an 83% margin. The client's running cost is ~$0 (their own lab PC and spectro).
  - Gain-share was rejected for the pilot, because the value of an off-shade m² is the least certain number.
- **Value:**
  - Base case for C: (8,867 − 3,316) m² saved per batch change × $6/m² × 30% value loss = **$9,992 per batch change**. At 3 batch changes a month per line, that is **≈ $360k per line per year**, or **$228k** with B alone.
  - Conservative case (2 a month, $5/m², 15% loss, half the simulated benefit): $32k–$50k per line per year.
  - I capped frequency at 4 a month, because more would imply over 15% of output is off-shade today, which isn't credible.
  - Payback of the $122.5k pilot: ≈ 6.4 months on one line with B ($19.0k a month), and ≈ 4.1 months with C ($30.0k a month), in the base case.

## Timeline. What is the first result the client sees, and when? Which steps depend on the client rather than on us?

- **Phase 0 (weeks 1–3):**
  - site visit and check for an existing colour-management licence;
  - measuring their master and variation tiles;
  - **week 2: kiln repeatability result (go/no-go)**;
  - **week 3: the first real SKU corrected in one designed round, confirmed by their own lab**. This is the first result they see.
- **Phase 1 (weeks 4–12):** tool v1, then a bench test on 10 SKUs (readout in week 7), then the paired live test on 20 batch changes, then the **week-12 go/no-go**.
- **Phase 2 (months 4–9):** the prior model (method C), the India plant, and pre-changeover trials.
- **Depends on the client:**
  - shipping tiles in week 1;
  - site access;
  - a named QC champion;
  - kiln slots for test tiles;
  - original print files;
  - past lab logs;
  - lab-tech time (~6 h a week);
  - sharing the batch-change schedule (20 changes in 4 weeks needs ~5–6 lines in the pilot);
  - IT approval for a lab PC;
  - an introduction to the printer OEM for phase 2.

## Where did you push back on the client, narrow their ask, or tell them not to do something?

- **Not a vision system:** their spectro already measures better than a camera would. The gap is the inverse (ΔLab → file change), not measurement.
- **Not a few minutes end to end:** the decision takes minutes, but one kiln pass is physics. I reframed the goal as kiln rounds per batch change.
- **Stop editing edited files:** every correction is generated from the original file against a stored numeric master. This is the likely cause of the old reference drifting off.
- **Stop accepting near-misses:** sign-off is on a numeric per-zone tolerance, measured on several zones, not one spot.
- **Don't buy hardware, and don't wire anything into the printer, for the pilot.**
- **Gloss is not a file problem:** the tool flags it and routes it to glaze or kiln.
- **Check whether you already own a colour-management tool that does this before paying us.**
- **Move the loop off the critical path:** test-fire the new batch's material before the changeover where possible. This is a process change, not software.
- **The QC and design leads must be on the next call.** Procurement can't speak for the users.
- **A stop rule in week 2 if the kiln can't repeat itself.** In that case I'd tell them to fix the process, not buy software.

## What is most likely to go wrong with your plan, and what in these notes did you not trust?

- **Most likely to go wrong:**
  - Firing noise close to the tolerance, which is why there's a week-2 gate.
  - A share of drifts can't be fixed by global channel changes (~10% in simulation), so those get flagged and routed.
  - QC resistance, since the users weren't on the call.
  - Too few real batch changes in the pilot window.
  - Small drifts, where the designed round costs more than it saves (found in my own stress test), so it is gated at > 1.5 ΔE.
  - Discovering they already own a colour-management system that does this. That would be good for them, and it shrinks our scope.
  - Off-shade tiles keeping most of their value, which weakens the case.
- **Not trusted:**
  - **5,000–10,000 m²** (the audio was unclear). Cross-checked: it equals 2.3–4.6 rounds at ~8,000 m²/day and 6.5 h per round, and my simulated manual loop gives 4.1 rounds and 8,900 m², so it's consistent.
  - **That the print file is unchanged**: it isn't the same, it has been edited since 2021.
  - **That it is simply a printer for tiles**: it isn't, because the colour forms in the kiln.
  - **That firing is out of scope**: firing is the cause, even if the fix goes in the file.
  - **The six primary colours**: some channels may be effects or digital glaze.
  - **The 6–7 hours per round**: it's unclear how much is kiln time versus queueing.
  - **The video-analytics label**: a procurement label, not a requirement.
  - **The near-match acceptance**: not a metric.
  - **Procurement speaking for absent users.**

## What did you use AI for? Which tools, where they helped, where they misled you, and what you threw away.

- **Claude (Opus 5.5, in the Claude desktop app / Claude Code):**
  - **Web research:** colour-management products for ceramic printing, ISO 10545-16, kiln capacity, tile prices.
  - **Code:** the colour-science and simulator code (Kubelka–Munk, CIEDE2000, the policies).
  - **First drafts:** the case study, note and form.
- **Where it helped:**
  - It found that commercial "repeat job" systems exist (ColorGATE Fingerprint, EFI Fiery). That turned into a "check what they already own" recommendation and a sharper position.
  - It built a working simulator fast enough to *test* the idea instead of just asserting it.
- **Where it misled or wasted time:**
  - The first simulation used a +10% test nudge, which made the method look weak (51% fixed within 2 rounds). Comparing it with a noise-free optimum showed that firing noise was swamping the estimate, and +30% fixed it (78%). That became a real design point.
  - It proposed an "edit-on-edit drift" experiment that the simulator couldn't represent honestly, so I dropped it.
  - Some PDF sources couldn't be read by the fetch tool and had to be parsed locally.
- **Thrown away:**
  - the drift experiment;
  - a camera-based design;
  - a per-SKU prior (replaced by a fleet model);
  - early value numbers that implied 29% of line output was off-shade, which isn't credible, so I capped the batch-change frequency.
- Every number in the case study comes from `prototype/out/results.json` or `value_model.json`.

## Github Repo URL

https://github.com/JMadhan1/banao_task3 (public: code, prototype, case study, note and form. Client quotes are paraphrased and the discovery-call notes are not included.)
