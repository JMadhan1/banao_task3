# Task 3: Client A (ceramic tiles): right-first-time shade at batch change

| Deliverable | File |
|---|---|
| 1. Case study (6 pages + appendix) | [`case-study.pdf`](case-study.pdf) (source: `case-study.md`) |
| 2. One-page note to the procurement lead | [`note-to-procurement-lead.pdf`](note-to-procurement-lead.pdf) |
| 3. Submission form | [`submission-form.md`](submission-form.md) |
| Optional prototype | [`prototype/`](prototype/) |

## The idea in one paragraph
The client asked for a vision system that compares the master tile with a production tile. Their spectrophotometer already does the comparison. What's missing is the translation from a colour difference into a print-file change that works for *this* batch. The proposal turns the 6–7 variant tiles they already fire per lab round into a designed experiment: the current file plus each ink channel nudged once. A small solver then corrects every colour zone in one go. In simulation, batch changes fixed within two kiln rounds rise from 28% to 78% on day one, and to 92% once logged rounds train a prior model.

## Run the prototype (Python 3.10+, about 1 minute)
```bash
cd prototype
pip install numpy scipy matplotlib
python experiments.py          # E1-E4 -> out/*.png, out/results.json
python value_model.py          # value / price / cost arithmetic -> out/value_model.json
python robustness.py           # stress tests -> out/robustness.json (about 1 minute)
python make_example.py         # writes example_round.csv (one simulated lab round)
python shade_tool.py example_round.csv   # the tool itself: spectro CSV in, file correction out
```
| File | What it is |
|---|---|
| `shade_sim.py` | Spectral print-and-fire simulator: 6 inks, Kubelka–Munk, CIEDE2000, batch drift, firing and spectro noise, gloss |
| `shade_tool.py` | The pilot's core: designed round → Jacobian → bounded least-squares correction + flags (gloss, unreachable, noisy kiln) |
| `experiments.py` | Manual loop vs designed round vs model+learn; kiln-noise stop gate; one spot vs all zones; gloss |
| `value_model.py` | Every money number in the case study |
| `robustness.py` | Stress tests: technician skill, pilot test power, half/double drift |

Rebuild the PDFs: `pip install markdown` then `python build_pdf.py` (uses headless Edge/Chrome).

## Confidentiality
The discovery-call notes are confidential and are **not** in this repository (`.gitignore` excludes them). This public copy paraphrases every direct client quote. It has the same analysis, numbers and code as the submitted version.
