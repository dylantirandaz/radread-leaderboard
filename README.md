# RadRead leaderboard

The published results page for [RadRead](https://github.com/dylantirandaz/radread), a radiology
reading benchmark: 243 studies, one model call each, deterministic scoring. A read passes
only when every checklist finding, every lesion box, the diagnosis and the next step are correct

- Page: https://dylantirandaz.com/radread-leaderboard/
- Mirror: https://huggingface.co/spaces/tirandazdylan/radread-leaderboard
- Rollout-level results: https://huggingface.co/datasets/tirandazdylan/radread-public-results

`index.html` is generated, never hand-edited:

```bash
python build_site.py --data leaderboard.json --out .
```

`leaderboard.json` holds the aggregate every number on the page is drawn from: pass@1..5 per
model, per-source breakdowns, attempt histograms, token and cost totals.
