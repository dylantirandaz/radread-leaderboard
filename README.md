# RadRead leaderboard

`public150-pass5-audit1`: frontier models reading 150 radiographs against a fixed
rubric. All checks must pass. These scores are not a clinical error rate.
This correction regrades the same five saved attempts per study and model:
750 reads per model, 3,750 across five models, with no new inference or cohort changes.

## Results

| Model | Lab | pass@1 (%) | 95% study-bootstrap CI | 5/5 cases | pass@5 (%) | Never solved |
|---|---|---:|---:|---:|---:|---:|
| GPT-6 Astra | OpenAI | 25.9 | 19.7–32.3 | 24 | 36.0 | 96 |
| Claude Opus 5 | Anthropic | 22.1 | 16.7–27.9 | 15 | 35.3 | 97 |
| Claude Fable 5.1 | Anthropic | 19.7 | 14.9–24.7 | 6 | 37.3 | 94 |
| Gemini 3.8 Flash | Google | 15.6 | 10.9–20.5 | 9 | 26.0 | 111 |
| GPT-5.6 Sol | OpenAI | 13.6 | 8.9–18.8 | 14 | 21.3 | 118 |

Rows follow pass@1 point estimates, not proven superiority. pass@1 is the mean
single-attempt pass rate across studies; 5/5 counts cases passing every attempt.
pass@5 is secondary and means at least one pass, not consistent reliability.
The page retains pass@k curves. Full paired pass@1 differences (percentage points)
remain available in `leaderboard.json`.
95% intervals use a paired percentile study bootstrap: 10,000 shared resamples of 150 studies, seed 42. All attempts within a study stay together; attempts are not independent resampling units. Descriptive intervals conditional on this outcome-selected challenge cohort and its saved responses, not an independent holdout or population/clinical validation. Studies, not individual attempts, are resampled. Intervals do not account for cohort selection, gold-label uncertainty, or future responses; pairwise intervals are not adjusted for multiple comparisons.
Pairwise intervals are not multiplicity-adjusted. Small-n source breakdowns are exploratory.

## Correction and limitations

NIH14 retains the original source right-lateral box and removes a contradictory
left-hilar alternative. ChestDet26 adds an omitted source calcification as optional;
both existing foci remain required. The laterality audit is corrected as well.
These are source-backed reference and audit corrections, not clinical validation.
Diagnosis grading remains lexical, not disease-level validation. `urgent_review`
is accepted on 148/150 keys; deterministic action-set membership is not clinical
adjudication and urgency discrimination remains weak.

The previous `public150-pass5` release used 3,725 cached reads and 25 new fifth
attempts. Immutable snapshots: [GitHub benchmark](https://github.com/dylantirandaz/radread-public/tree/773c85ab5bed5de68b4d069a3a8873ab8f7ed9f0)
and [HF results](https://huggingface.co/datasets/tirandazdylan/radread-public-results/tree/a6eb301d98852cdda41343a19ad7450036a002d5).

The parent 164-study cohort was selected using all five models' saved outcomes to keep
each model's pass@4 below 35%. The current cohort retains the 145 studies that already
had five cached attempts for every model, plus five of the remaining 19 sampled with
seed 42 before generating their new fifth attempts, one per model. The selection was
frozen in `results/pass5_150.selection.json` before those new outcomes. This correction
retains those studies, prompts, images and responses, with the reference and audit
changes described above.

This release inherits the parent's outcome selection: it is an outcome-selected
challenge subset, not an independent holdout or evidence of general model performance
deterioration.

- Page: https://dylantirandaz.com/radread-leaderboard/
- Mirror: https://huggingface.co/spaces/tirandazdylan/radread-leaderboard
- Rollout-level results: https://huggingface.co/datasets/tirandazdylan/radread-public-results

Rebuild: `python build_site.py --data leaderboard.json --out .`.

`traces/` contains every reply and check verdict. Images and gold are not published.
Results use static HTML and CSS, with no JavaScript required.
Source Serif 4 and its SIL Open Font License are in `site_assets/`.
