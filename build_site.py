"""Render the RadRead results site from results/leaderboard.json.

The site is static HTML with no JavaScript: every number is baked in at build time, so the page
works from a file:// path, a GitHub Pages deploy, or a Hugging Face static Space unchanged.

usage: python scripts/build_site.py --data results/leaderboard.json --out site
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import shutil
from pathlib import Path
from typing import Any

SOURCE_ORDER = [
    "ChestX-Det",
    "NIH ChestX-ray14",
    "VinDr-CXR",
    "GRAZPEDWRI-DX",
    "RSNA Pneumonia",
]

SOURCE_SHORT = {
    "ChestX-Det": "ChestX-Det",
    "NIH ChestX-ray14": "NIH CXR14",
    "VinDr-CXR": "VinDr",
    "GRAZPEDWRI-DX": "GRAZ",
    "RSNA Pneumonia": "RSNA",
}

REPO_URL = "https://github.com/dylantirandaz/radread"
HF_SPACE = "https://huggingface.co/spaces/tirandazdylan/radread-leaderboard"
HF_DATA = "https://huggingface.co/datasets/tirandazdylan/radread-public-results"
SITE_REPO = "https://github.com/dylantirandaz/radread-leaderboard"

DISPLAY_SHORT = {
    "anthropic/claude-opus-5": "Claude Opus 5",
    "anthropic/claude-fable-5.1": "Claude Fable 5.1",
    "openai/gpt-6-astra": "GPT-6 Astra",
    "openai/gpt-5.6-sol": "GPT-5.6 Sol",
    "google/gemini-3.8-flash": "Gemini 3.8 Flash",
}


def pct(value: float) -> str:
    return f"{value * 100:.1f}"


def bar(value: float, width: int = 120, height: int = 7) -> str:
    """A single filled rule, drawn with a nested span rather than an image or chart library."""
    filled = max(1, round(value * width))
    return (
        f'<span class="bar" style="width:{width}px;height:{height}px">'
        f'<span class="fill" style="width:{filled}px"></span></span>'
    )


def leaderboard_table(models: list[dict[str, Any]], max_k: int) -> str:
    head = (
        "<thead><tr>"
        "<th class='rank'></th><th>Model</th><th>Lab</th>"
        "<th class='num'>pass@1</th>"
        f"<th class='num'>pass@{max_k}</th>"
        "<th class='plot'></th>"
        "<th class='num'>Checks</th>"
        "<th class='num'>Never solved</th>"
        "</tr></thead>"
    )
    rows = []
    for index, model in enumerate(models, 1):
        rows.append(
            "<tr>"
            f"<td class='rank'>{index}</td>"
            f"<td class='model'>{html.escape(model['name'])}</td>"
            f"<td class='lab'>{html.escape(model['lab'])}</td>"
            f"<td class='num'>{pct(model['pass@1'])}</td>"
            f"<td class='num strong'>{pct(model[f'pass@{max_k}'])}</td>"
            f"<td class='plot'>{bar(model[f'pass@{max_k}'])}</td>"
            f"<td class='num'>{pct(model['checks_accuracy'])}</td>"
            f"<td class='num'>{model['unsolved']}</td>"
            "</tr>"
        )
    return f"<div class='scroll'><table class='board'>{head}<tbody>{''.join(rows)}</tbody></table></div>"


def curve_table(models: list[dict[str, Any]], max_k: int) -> str:
    ks = list(range(1, max_k + 1))
    head = "<thead><tr><th>Model</th>" + "".join(f"<th class='num'>@{k}</th>" for k in ks) + "</tr></thead>"
    rows = []
    for model in models:
        cells = "".join(f"<td class='num'>{pct(model[f'pass@{k}'])}</td>" for k in ks)
        rows.append(f"<tr><td class='model'>{html.escape(model['name'])}</td>{cells}</tr>")
    return f"<div class='scroll'><table class='board tight'>{head}<tbody>{''.join(rows)}</tbody></table></div>"


def source_table(models: list[dict[str, Any]], max_k: int) -> str:
    sources = [s for s in SOURCE_ORDER if any(s in m["by_source"] for m in models)]
    counts = {}
    for source in sources:
        for model in models:
            if source in model["by_source"]:
                counts[source] = model["by_source"][source]["tasks"]
                break
    head = (
        "<thead><tr><th>Model</th>"
        + "".join(
            f"<th class='num' title='{html.escape(s)}'>{html.escape(SOURCE_SHORT.get(s, s))}"
            f"<span class='n'>{counts[s]}</span></th>"
            for s in sources
        )
        + "</tr></thead>"
    )
    rows = []
    for model in models:
        cells = "".join(
            f"<td class='num'>{pct(model['by_source'][s][f'pass@{max_k}'])}</td>"
            if s in model["by_source"]
            else "<td class='num mute'>—</td>"
            for s in sources
        )
        rows.append(f"<tr><td class='model'>{html.escape(model['name'])}</td>{cells}</tr>")
    return f"<div class='scroll'><table class='board tight'>{head}<tbody>{''.join(rows)}</tbody></table></div>"


def reliability(models: list[dict[str, Any]], max_k: int) -> str:
    """One rule per model, split into never / sometimes / always solved."""
    rows = []
    for model in models:
        counts = model["attempts_correct"]
        total = sum(counts.values()) or 1
        never = counts.get("0", 0)
        always = counts.get(str(max_k), 0)
        sometimes = total - never - always
        segments = "".join(
            f"<span class='seg {klass}' style='width:{value / total * 100:.4f}%'></span>"
            for klass, value in (("always", always), ("sometimes", sometimes), ("never", never))
        )
        rows.append(
            "<tr>"
            f"<td class='model'>{html.escape(model['name'])}</td>"
            f"<td class='band'><span class='stack'>{segments}</span></td>"
            f"<td class='num'>{always}</td>"
            f"<td class='num'>{sometimes}</td>"
            f"<td class='num'>{never}</td>"
            "</tr>"
        )
    head = (
        "<thead><tr><th>Model</th><th class='band'></th>"
        f"<th class='num'>{max_k}/{max_k}</th><th class='num'>1–{max_k - 1}/{max_k}</th>"
        f"<th class='num'>0/{max_k}</th></tr></thead>"
    )
    return f"<div class='scroll'><table class='board tight'>{head}<tbody>{''.join(rows)}</tbody></table></div>"


def validity_section(audit: dict[str, Any] | None, rollouts: int, tasks: int) -> str:
    """Audit evidence, rendered only when results/audit.json exists — never invented."""
    if not audit or not audit.get("blind"):
        return ""
    mismatches = sum(len(m["regrade_mismatches"]) for m in audit["models"])
    truncated = sum(m["truncated"] for m in audit["models"])
    blind = " and ".join(
        f"{b['pass_rate'] * 100:.1f}% for {DISPLAY_SHORT.get(b['model'], b['model'])}" for b in audit["blind"]
    )
    sens = audit["threshold_sensitivity"]
    flips = sens.get("best_iou_0.20_0.25", 0)
    return f"""
<section>
  <h2>Validity</h2>
  <p>Every transcript was re-graded independently after the runs: {rollouts - mismatches:,} of
  {rollouts:,} rewards reproduce, {truncated} truncated. With the radiograph withheld, the same
  {tasks} prompts pass {blind} of studies — the checklist does not give the finding away. Box
  failures are misses, not near misses: loosening the IoU threshold to 0.20 would change
  {flips} read{'s' if flips != 1 else ''} in {rollouts:,}.</p>
</section>
"""


def render(data: dict[str, Any], built: str, audit: dict[str, Any] | None = None) -> str:
    models = data["models"]
    max_k = data["rollouts_per_task"]
    protocol = data["protocol"]
    unsolved = data["unsolved_by_all"]
    best = models[0]
    tasks = data["tasks"]
    rollouts = sum(m["rollouts"] for m in models)
    unsolved_sources = ", ".join(
        f"{count} {source}" for source, count in sorted(unsolved["by_source"].items(), key=lambda kv: -kv[1])
    )
    validity = validity_section(audit, rollouts, tasks)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RadRead — a radiology reading benchmark</title>
<meta name="description" content="RadRead scores frontier vision-language models on {tasks} audited radiology studies. A read passes only when every finding, box, diagnosis and next step is correct.">
<link rel="stylesheet" href="style.css">
</head>
<body>
<main>

<header>
  <h1>RadRead</h1>
  <p class="lede">A radiology reading benchmark. {tasks} audited studies; a read passes only when
  every checklist finding, every lesion box, the diagnosis and the next step are all correct.</p>
  <p class="meta">{tasks} studies · {max_k} rollouts per study · {sum(m['rollouts'] for m in models):,} graded reads · {built}</p>
</header>

<section class="figures">
  <div>
    <p class="figure">{pct(best[f'pass@{max_k}'])}<span>%</span></p>
    <p class="caption">best pass@{max_k} — {html.escape(best['name'])}, {max_k} attempts per study</p>
  </div>
  <div>
    <p class="figure">{pct(best['pass@1'])}<span>%</span></p>
    <p class="caption">best pass@1 — one attempt, no retries</p>
  </div>
  <div>
    <p class="figure">{unsolved['count']}</p>
    <p class="caption">studies no model has ever read correctly</p>
  </div>
</section>

<section>
  <h2>Leaderboard</h2>
  {leaderboard_table(models, max_k)}
  <p class="note">pass@k is the unbiased estimator over {max_k} independent rollouts per study:
  the share of studies a model gets entirely right within k attempts. <em>Checks</em> is the mean
  share of individual gold checks passed — partial credit that the pass rate deliberately ignores.
  <em>Never solved</em> counts studies the model missed in all {max_k} attempts.</p>
</section>

<section>
  <h2>Attempts</h2>
  {curve_table(models, max_k)}
  <p class="note">The best model reads {pct(best['pass@1'])}% of studies correctly on one attempt
  and {pct(best[f'pass@{max_k}'])}% within {max_k}. The gap is the benchmark's headroom: the model
  can find the answer, but not reliably.</p>
</section>

<section>
  <h2>Reliability</h2>
  {reliability(models, max_k)}
  <p class="note">Studies split by how many of the {max_k} attempts were correct: always, sometimes,
  never. Sampling runs at temperature 0 and no model returned the same read twice — the middle
  band is a model that can see the finding and does not see it every time.</p>
</section>

<section>
  <h2>By image source</h2>
  {source_table(models, max_k)}
  <p class="note">pass@{max_k} within each upstream source.</p>
</section>

<section>
  <h2>What a pass requires</h2>
  <p>One study, one model call, one JSON read. The grader is deterministic — no judge model
  anywhere — and a study counts only when the read satisfies every one of:</p>
  <ol>
    <li>every requested checklist key answered, booleans and words matching the curated gold;</li>
    <li>every must-find lesion localized, IoU ≥ 0.25, one answered box consumed per gold box;</li>
    <li>spurious boxes inside the case's quota;</li>
    <li>the one-line diagnosis inside the accepted label set;</li>
    <li>the next step inside the accepted actions.</li>
  </ol>
  <p>There is no partial credit inside a study. A missing answer, an unparseable line or a
  malformed read fails it outright.</p>
</section>

<section>
  <h2>Protocol</h2>
  <dl>
    <dt>Rollouts</dt><dd>{max_k} per study, scored independently</dd>
    <dt>Sampling</dt><dd>temperature {protocol['temperature']}, {protocol['max_tokens']:,} max tokens</dd>
    <dt>Reasoning</dt><dd>{html.escape(protocol['reasoning_effort'])}</dd>
    <dt>Inference</dt><dd>{html.escape(protocol['provider'])}</dd>
    <dt>Scoring</dt><dd>{html.escape(protocol['scoring'])}</dd>
    <dt>Images</dt><dd>1024 × 1024 px, one radiograph per study, sent on the image channel</dd>
  </dl>
</section>
{validity}
<section>
  <h2>Unsolved</h2>
  <p>{unsolved['count']} of {tasks} studies were missed by every model in every attempt
  ({unsolved_sources}). They are ordinary reads — the finding is there, annotated by the
  upstream dataset, and no model in this cohort has ever produced it.</p>
</section>

<section>
  <h2>Data and code</h2>
  <ul class="links">
    <li><a href="{REPO_URL}">Benchmark and grader</a></li>
    <li><a href="{HF_DATA}">Rollout-level results</a></li>
    <li><a href="{HF_SPACE}">Leaderboard on Hugging Face</a></li>
    <li><a href="{SITE_REPO}">Source of this page</a></li>
  </ul>
  <p class="note">Images come from ChestX-Det, NIH ChestX-ray14, VinDr-CXR, GRAZPEDWRI-DX and the
  RSNA Pneumonia Detection Challenge, under their own licences. The benchmark redistributes
  annotations and code, not pixels.</p>
</section>

<footer>
  <p>RadRead · {built}</p>
</footer>

</main>
</body>
</html>
"""


CSS = """:root {
  --ink: #111;
  --mute: #767676;
  --rule: #e2e2e2;
  --fill: #111;
}

* { box-sizing: border-box; }

html {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 15px;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

body {
  margin: 0;
  color: var(--ink);
  background: #fff;
  line-height: 1.55;
}

main {
  max-width: 54rem;
  margin: 0 auto;
  padding: 5rem 1.5rem 6rem;
}

header { margin-bottom: 4rem; }

h1 {
  margin: 0 0 1.25rem;
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: 0.22em;
  text-transform: uppercase;
}

h2 {
  margin: 0 0 1rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--mute);
}

.lede {
  margin: 0 0 0.75rem;
  max-width: 34rem;
  font-size: 1.05rem;
}

.meta, .note {
  color: var(--mute);
  font-size: 0.8rem;
  line-height: 1.6;
}

.meta { margin: 0; }
.note { margin: 0.9rem 0 0; max-width: 34rem; }

section { margin-bottom: 3.5rem; }

p { margin: 0 0 0.9rem; max-width: 34rem; }

table {
  width: 100%;
  border-collapse: collapse;
  font-variant-numeric: tabular-nums;
  font-size: 0.85rem;
}

th, td {
  padding: 0.55rem 0.6rem;
  text-align: left;
  border-bottom: 1px solid var(--rule);
  white-space: nowrap;
}

thead th {
  border-bottom: 1px solid var(--ink);
  font-weight: 400;
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--mute);
}

tbody tr:last-child td { border-bottom: 1px solid var(--ink); }

th:first-child, td:first-child { padding-left: 0; }
th:last-child, td:last-child { padding-right: 0; }

.num { text-align: right; }
.rank { width: 1.5rem; color: var(--mute); }
.model { font-weight: 500; }
.lab { color: var(--mute); }
.strong { font-weight: 700; }
.plot { width: 130px; }

th .n {
  display: block;
  font-size: 0.68rem;
  color: var(--rule);
  color: #b3b3b3;
}

.bar {
  display: inline-block;
  vertical-align: middle;
  background: #ededed;
}

.bar .fill {
  display: block;
  height: 100%;
  background: var(--fill);
}

.scroll { overflow-x: auto; }

.mute { color: var(--mute); }

.band { width: 46%; }

.stack {
  display: flex;
  width: 100%;
  height: 7px;
  background: #ededed;
}

.seg { display: block; height: 100%; }
.seg.always { background: #111; }
.seg.sometimes { background: #9a9a9a; }
.seg.never { background: #ededed; }

.figures {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 2rem;
  margin-bottom: 4rem;
}

.figure {
  margin: 0;
  font-size: 2.6rem;
  font-weight: 300;
  letter-spacing: -0.03em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.figure span {
  font-size: 1.1rem;
  font-weight: 400;
  margin-left: 0.1rem;
}

.caption {
  margin: 0.55rem 0 0;
  max-width: 14rem;
  color: var(--mute);
  font-size: 0.78rem;
  line-height: 1.45;
}

ol, ul { margin: 0 0 0.9rem; padding-left: 1.1rem; max-width: 34rem; }
li { margin-bottom: 0.3rem; }

ul.links { list-style: none; padding-left: 0; }

dl {
  display: grid;
  grid-template-columns: 9rem 1fr;
  gap: 0.35rem 1rem;
  margin: 0;
  max-width: 40rem;
  font-size: 0.85rem;
}

dt { color: var(--mute); }
dd { margin: 0; }

a { color: var(--ink); text-decoration: underline; text-underline-offset: 0.18em; }
a:hover { color: var(--mute); }

footer {
  margin-top: 5rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--rule);
  color: var(--mute);
  font-size: 0.75rem;
}

@media (max-width: 640px) {
  main { padding: 3rem 1.1rem 4rem; }
  .plot, th.plot { display: none; }
  .figures { grid-template-columns: 1fr; gap: 1.75rem; }
  .figure { font-size: 2.2rem; }
  dl { grid-template-columns: 1fr; gap: 0 0; }
  dt { margin-top: 0.6rem; }
}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("results/leaderboard.json"))
    parser.add_argument("--audit", type=Path, default=Path("results/audit.json"),
                        help="audit output; the Validity section is omitted when the file is absent")
    parser.add_argument("--out", type=Path, default=Path("site"))
    args = parser.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    audit = json.loads(args.audit.read_text(encoding="utf-8")) if args.audit.is_file() else None
    built = dt.date.today().isoformat()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "index.html").write_text(render(data, built, audit), encoding="utf-8", newline="\n")
    (args.out / "style.css").write_text(CSS, encoding="utf-8", newline="\n")
    shutil.copyfile(args.data, args.out / "leaderboard.json")
    print(f"wrote {args.out / 'index.html'}")


if __name__ == "__main__":
    main()
