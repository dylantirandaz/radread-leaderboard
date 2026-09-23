# RadRead leaderboard

Frontier models reading 150 radiographs against a fixed rubric. All checks must pass.
These scores are not a clinical error rate. The release uses five provider-successful
attempts per model and study: 750 reads per model, 3,750 across five models, comprising
3,725 cached reads and 25 newly generated, graded reads.

The parent 164-study cohort was selected using all five models' saved outcomes to keep
each model's pass@4 below 35%. The current cohort retains the 145 studies that already
had five cached attempts for every model, plus five of the remaining 19 sampled with
seed 42 before generating their new fifth attempts, one per model. The selection was
frozen in `results/pass5_150.selection.json` before those new outcomes. Prompts, images,
gold and grader are unchanged.

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
