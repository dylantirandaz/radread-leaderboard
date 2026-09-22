# RadRead leaderboard

The published results page for [RadRead](https://github.com/dylantirandaz/radread-public):
frontier models reading 243 radiographs, one model call each, deterministic scoring. Findings,
boxes, diagnosis and next step must match the reference rubric; this is not a clinical error rate.

- Page: https://dylantirandaz.com/radread-leaderboard/
- Mirror: https://huggingface.co/spaces/tirandazdylan/radread-leaderboard
- Rollout-level results: https://huggingface.co/datasets/tirandazdylan/radread-public-results

`index.html` is generated from `leaderboard.json` (`python build_site.py --data leaderboard.json --out .`);
`traces/` holds every model reply on every study with the grader's per-check verdict. Neither the
radiographs nor the gold are published. `site_assets/` contains the self-hosted Newsreader font
and its SIL Open Font License.
