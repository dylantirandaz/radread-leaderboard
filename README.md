# RadRead leaderboard

Frontier models reading 164 radiographs against a fixed rubric. All checks must pass.
These scores are not a clinical error rate.
The cohort was selected using all five models' outcomes to keep every model's pass@4
below 35%, reusing the same four saved attempts per model and study (3,280 reads).
This is an outcome-selected challenge set, not an independent holdout or evidence
of model deterioration.

- Page: https://dylantirandaz.com/radread-leaderboard/
- Mirror: https://huggingface.co/spaces/tirandazdylan/radread-leaderboard
- Rollout-level results: https://huggingface.co/datasets/tirandazdylan/radread-public-results

Rebuild: `python build_site.py --data leaderboard.json --out .`.

`traces/` contains every reply and check verdict. Images and gold are not published.
Results use static HTML and CSS, with no JavaScript required.
Source Serif 4 and its SIL Open Font License are in `site_assets/`.
