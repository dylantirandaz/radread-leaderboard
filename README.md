# RadRead leaderboard

The published results page for [RadRead](https://github.com/dylantirandaz/radread), a radiology
reading benchmark: 243 studies, one model call each, deterministic scoring. A read passes only
if every finding, box, diagnosis and next step is correct.

- Page: https://dylantirandaz.com/radread-leaderboard/
- Mirror: https://huggingface.co/spaces/tirandazdylan/radread-leaderboard
- Rollout-level results: https://huggingface.co/datasets/tirandazdylan/radread-public-results

`index.html` is generated from `leaderboard.json` (`python build_site.py --data leaderboard.json --out .`);
`traces/` holds every model reply on every study with the grader's per-check verdict. Neither the
radiographs nor the gold are published.
