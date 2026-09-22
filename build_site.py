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

REPO_URL = "https://github.com/dylantirandaz/radread-public"
HF_SPACE = "https://huggingface.co/spaces/tirandazdylan/radread-leaderboard"
HF_DATA = "https://huggingface.co/datasets/tirandazdylan/radread-public-results"
SITE_REPO = "https://github.com/dylantirandaz/radread-leaderboard"
STATIC_ASSETS = ("site_assets/space-grotesk-latin.woff2", "site_assets/OFL.txt")


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
    head = (
        "<thead><tr><th>Model</th>"
        + "".join(f"<th class='num'>@{k}</th>" for k in ks)
        + "</tr></thead>"
    )
    rows = []
    for model in models:
        cells = "".join(f"<td class='num'>{pct(model[f'pass@{k}'])}</td>" for k in ks)
        rows.append(
            f"<tr><td class='model'>{html.escape(model['name'])}</td>{cells}</tr>"
        )
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
            (
                f"<td class='num'>{pct(model['by_source'][s][f'pass@{max_k}'])}</td>"
                if s in model["by_source"]
                else "<td class='num mute'>—</td>"
            )
            for s in sources
        )
        rows.append(
            f"<tr><td class='model'>{html.escape(model['name'])}</td>{cells}</tr>"
        )
    return f"<div class='scroll'><table class='board tight'>{head}<tbody>{''.join(rows)}</tbody></table></div>"


PALETTE = ["#342d3a", "#7d506d", "#ac7041", "#547d74", "#80749c", "#8a858e"]


def passk_chart(models: list[dict[str, Any]], max_k: int) -> str:
    """pass@k for k = 1..max_k, one line per model, as inline SVG.

    Drawn by hand rather than with a chart library so the page stays script-free: a light
    grid, y axis from 0 to at least 60 %, circle markers, and a wrapping HTML legend.
    """
    width, height = 640, 360
    left, right, top, bottom = 56, 20, 26, 40
    plot_w, plot_h = width - left - right, height - top - bottom
    ys = [m[f"pass@{k}"] for m in models for k in range(1, max_k + 1)]
    y_min = 0.0
    y_max = max(
        0.6, min(1.0, (max(ys) * 100 // 10 + 1) * 10 / 100)
    )  # 0-60 %, more only if a line needs it

    def sx(k: int) -> float:
        return left + (k - 1) / (max_k - 1) * plot_w

    def sy(v: float) -> float:
        return top + (1 - (v - y_min) / (y_max - y_min)) * plot_h

    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="pass@k by model">'
    ]
    step = 0.1
    tick = y_min
    while tick <= y_max + 1e-9:
        y = sy(tick)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" class="grid"/>'
        )
        parts.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" class="tick" text-anchor="end">{tick * 100:.0f}%</text>'
        )
        tick += step
    for k in range(1, max_k + 1):
        x = sx(k)
        parts.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_h}" class="grid"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{top + plot_h + 18}" class="tick" text-anchor="middle">{k}</text>'
        )
    parts.append(
        f'<text x="{left + plot_w / 2:.1f}" y="{height - 6}" class="tick" text-anchor="middle">k attempts</text>'
    )
    parts.append(
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" class="frame"/>'
    )
    legend = []
    for index, model in enumerate(models):
        colour = PALETTE[index % len(PALETTE)]
        points = [(sx(k), sy(model[f"pass@{k}"])) for k in range(1, max_k + 1)]
        path = " ".join(
            f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}"
            for i, (x, y) in enumerate(points)
        )
        parts.append(
            f'<path d="{path}" fill="none" stroke="{colour}" stroke-width="1.6"/>'
        )
        for x, y in points:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{colour}"/>')
        legend.append(
            f'<li><span class="key-line" style="background:{colour}" aria-hidden="true"></span>'
            f'{html.escape(model["name"])}</li>'
        )
    parts.append("</svg>")
    parts.append(f'<ul class="chart-key" aria-label="Models">{"".join(legend)}</ul>')
    return "".join(parts)


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
            for klass, value in (
                ("always", always),
                ("sometimes", sometimes),
                ("never", never),
            )
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


def repeated_replies(audit: dict[str, Any] | None, models: list[dict[str, Any]]) -> str:
    if not audit:
        return ""
    pairs = sum(m["tasks_with_repeated_reply"] for m in audit["models"])
    total = sum(m["tasks"] for m in models)
    return f"A reply repeated verbatim in {pairs} of {total:,} model–study pairs."


def render(
    data: dict[str, Any], built: str, audit: dict[str, Any] | None = None
) -> str:
    models = data["models"]
    max_k = data["rollouts_per_task"]
    protocol = data["protocol"]
    unsolved = data["unsolved_by_all"]
    best = models[0]
    best_one = max(models, key=lambda m: m["pass@1"])
    tasks = data["tasks"]
    rollouts = sum(m["rollouts"] for m in models)
    unsolved_sources = ", ".join(
        f"{count} {source}"
        for source, count in sorted(
            unsolved["by_source"].items(), key=lambda kv: -kv[1]
        )
    )
    repeats = repeated_replies(audit, models)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RadRead</title>
<meta name="description" content="RadRead: frontier models reading {tasks} radiographs. Findings, boxes, diagnosis and next step are scored against a fixed rubric.">
<link rel="preload" href="site_assets/space-grotesk-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="style.css">
</head>
<body>

<nav class="top">
  <div class="wrap">
    <a class="brand" href="index.html">RadRead</a>
    <span class="links"><a href="index.html">Leaderboard</a><a href="traces/index.html">Traces</a><a href="{HF_DATA}">Results</a><a class="btn" href="{REPO_URL}">Benchmark</a></span>
  </div>
</nav>

<header class="hero">
  <div class="wrap">
    <h1><span>Frontier models</span> <span>reading radiographs.</span></h1>
    <p>{tasks} studies. Findings, boxes, diagnosis and next step must all match the rubric.</p>
    <p class="meta">{max_k} attempts per study · {rollouts:,} reads · {built}</p>
  </div>
</header>

<main class="wrap">

<div class="grid three">
  <article class="card figure-card">
    <p class="figure">{pct(best[f'pass@{max_k}'])}<span>%</span></p>
    <p class="caption">best pass@{max_k} · <span>{html.escape(best['name'])}</span></p>
  </article>
  <article class="card figure-card">
    <p class="figure">{pct(best_one['pass@1'])}<span>%</span></p>
    <p class="caption">best pass@1 · <span>{html.escape(best_one['name'])}</span></p>
  </article>
  <article class="card figure-card">
    <p class="figure">{unsolved['count']}</p>
    <p class="caption">studies with no passing read</p>
  </article>
</div>

<div class="grid">
  <article class="card span2" id="leaderboard">
    <h2>Leaderboard</h2>
    {leaderboard_table(models, max_k)}
    <p class="caption">pass@k: unbiased estimator over {max_k} rollouts. Checks: mean share of gold
    checks passed. Never solved: passed in 0 of {max_k} attempts.</p>
  </article>

  <article class="card span2">
    <h2>pass@k</h2>
    <div class="two">
      <figure class="chart-figure">{passk_chart(models, max_k)}</figure>
      <div>{curve_table(models, max_k)}</div>
    </div>
  </article>

  <article class="card">
    <h2>Attempts correct</h2>
    {reliability(models, max_k)}
    <p class="caption">Temperature 0. {repeats}</p>
  </article>

  <article class="card">
    <h2>pass@{max_k} by source</h2>
    {source_table(models, max_k)}
  </article>

  <article class="card">
    <h2>A pass</h2>
    <p>One study, one call, one JSON read. Deterministic grader, no judge model. All of:</p>
    <ol>
      <li>every checklist key answered and matching gold;</li>
      <li>every must-find lesion matched by one box (the grader's IoU / centre / containment test);</li>
      <li>extra boxes within the study's quota;</li>
      <li>diagnosis in the accepted set;</li>
      <li>next step in the accepted set.</li>
    </ol>
    <p>No partial credit. Missing or unparseable output fails. A failed read is not necessarily a clinical error.</p>
  </article>

  <article class="card">
    <h2>Protocol</h2>
    <dl>
      <dt>Rollouts</dt><dd>{max_k} per study</dd>
      <dt>Sampling</dt><dd>temperature {protocol['temperature']}, {protocol['max_tokens']:,} max tokens</dd>
      <dt>Reasoning</dt><dd>{html.escape(protocol['reasoning_effort'])}</dd>
      <dt>Inference</dt><dd>{html.escape(protocol['provider'])}</dd>
      <dt>Images</dt><dd>1024 × 1024 px, one per study</dd>
    </dl>
  </article>

  <article class="card span2">
    <div class="two even">
      <div>
        <h2>Unsolved</h2>
        <p>{unsolved['count']} of {tasks} studies: no model, no attempt. {unsolved_sources}.</p>
        <p class="caption">Images: ChestX-Det, NIH ChestX-ray14, VinDr-CXR, GRAZPEDWRI-DX, RSNA Pneumonia.
        Not redistributed. Gold not published.</p>
      </div>
      <div>
        <h2>Links</h2>
        <ul class="links-list">
          <li><a href="traces/index.html">Traces — every attempt, reply and verdict</a></li>
          <li><a href="{HF_DATA}">Rollout-level results</a></li>
          <li><a href="{HF_SPACE}">Hugging Face mirror</a></li>
          <li><a href="{REPO_URL}">Benchmark</a></li>
          <li><a href="{SITE_REPO}">This page</a></li>
        </ul>
      </div>
    </div>
  </article>
</div>

</main>

<footer class="wrap">
  <p>RadRead · {built}</p>
</footer>

</body>
</html>
"""


CSS = """@font-face {
  font-family: "Space Grotesk";
  font-style: normal;
  font-weight: 400 700;
  font-display: swap;
  src: url("site_assets/space-grotesk-latin.woff2") format("woff2");
}

:root {
  --ink: #29262e;
  --mute: #6d6672;
  --rule: #dfdbe2;
  --hair: #f0edf2;
  --band: #f4f0f5;
  --accent: #75465f;
  --fill: var(--accent);
  --display: "Space Grotesk", var(--sans);
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}

* { box-sizing: border-box; }

html {
  font-family: var(--sans);
  font-size: 17px;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

body { margin: 0; color: var(--ink); background: #fff; line-height: 1.5; }

.wrap { width: min(1100px, calc(100% - 3rem)); margin: 0 auto; }

/* centered masthead */

nav.top .wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.8rem;
  padding: 1.65rem 0 1.2rem;
  border-bottom: 1px solid var(--rule);
}
nav.top .brand { font-family: var(--display); font-size: 2.1rem; font-weight: 500; line-height: 1; letter-spacing: -0.055em; text-decoration: none; color: var(--ink); }
nav.top .links { display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 0.5rem 1.6rem; font-family: var(--sans); font-size: 0.82rem; }
nav.top .links a { color: var(--ink); text-decoration: none; }
nav.top .links a:hover { text-decoration: underline; }
nav.top .links .btn { border: 1px solid var(--accent); padding: 0.35rem 0.8rem; background: var(--accent); color: #fff; }
nav.top .links .btn:hover { background: var(--ink); border-color: var(--ink); text-decoration: none; }

/* editorial introduction */

header.hero { padding: 3.3rem 0 3.1rem; text-align: center; }
header.hero h1 {
  margin: 0 auto 1.5rem;
  max-width: 50rem;
  font-family: var(--display);
  font-size: clamp(2.05rem, 4.5vw, 3.55rem);
  font-weight: 500;
  line-height: 1.09;
  letter-spacing: -0.045em;
  text-wrap: balance;
}
header.hero h1 span { display: block; }
header.hero p { margin: 0 auto; max-width: 33rem; font-size: 1.05rem; line-height: 1.6; text-wrap: balance; }
header.hero .meta { margin-top: 1.4rem; font-size: 0.75rem; }

.meta, .caption { font-family: var(--sans); color: var(--mute); font-size: 0.82rem; line-height: 1.55; }
.caption { margin: 1rem 0 0; }

/* results and supporting sections */

main.wrap { padding-bottom: 2rem; }

.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 3.5rem 3rem; }
.grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0; padding: 2.1rem 0; margin-bottom: 3.5rem; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); }
.span2 { grid-column: 1 / -1; }
.two { display: grid; grid-template-columns: minmax(0, 1fr); gap: 1.75rem; max-width: 46rem; margin: 0 auto; }
.two.even { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 2.5rem; max-width: none; }
.two > div { min-width: 0; }

.card {
  border-top: 1px solid var(--rule);
  padding: 1.65rem 0 0;
  min-width: 0;
}

.card h2 {
  margin: 0 0 1.25rem;
  font-family: var(--display);
  font-size: 1.6rem;
  font-weight: 500;
  line-height: 1.25;
  letter-spacing: -0.02em;
}
.grid > .card:first-child { border-top: 0; padding-top: 0; }

.card p { margin: 0 0 0.8rem; }
.card ol, .card ul { margin: 0 0 0.8rem; padding-left: 1.2rem; }
.card li { margin-bottom: 0.3rem; }

.figure-card { padding: 0 1rem; border-top: 0; text-align: center; }
.figure-card + .figure-card { border-left: 1px solid var(--rule); }
.figure { margin: 0; font-family: var(--display); font-size: clamp(2.6rem, 4.4vw, 3.3rem); font-weight: 400; line-height: 1; letter-spacing: -0.06em; font-variant-numeric: lining-nums tabular-nums; }
.figure span { font-size: 1.25rem; margin-left: 0.1rem; }
.figure-card .caption { margin: 0.7rem 0 0; font-size: 0.75rem; }
.figure-card .caption span { white-space: nowrap; }

/* tables */

.scroll { overflow-x: auto; }

table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--sans);
  font-variant-numeric: tabular-nums;
  font-size: 0.9rem;
}
th, td { padding: 0.75rem 0.6rem; text-align: left; border-bottom: 1px solid var(--rule); white-space: nowrap; }
thead th { border-bottom: 1px solid #938998; font-weight: 500; font-size: 0.68rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--mute); }
tbody tr:last-child td { border-bottom: 1px solid #938998; }
table.board tbody tr:hover { background: var(--band); }
th:first-child, td:first-child { padding-left: 0; }
th:last-child, td:last-child { padding-right: 0; }
.num { text-align: right; }
.rank { width: 1.5rem; color: var(--mute); }
.model { font-weight: 500; }
.lab { color: var(--mute); }
.strong { font-weight: 700; }
.plot { width: 130px; }
.mute { color: var(--mute); }
th .n { display: block; font-size: 0.68rem; color: #a9adb3; }

.bar { display: inline-block; vertical-align: middle; background: #e8e4e9; }
.bar .fill { display: block; height: 100%; background: var(--fill); }

.band { width: 46%; }
.stack { display: flex; width: 100%; height: 7px; background: #e8e4e9; }
.seg { display: block; height: 100%; }
.seg.always { background: var(--ink); }
.seg.sometimes { background: #a198a6; }
.seg.never { background: #e8e4e9; }

dl { display: grid; grid-template-columns: 8rem 1fr; gap: 0.45rem 1rem; margin: 0; font-family: var(--sans); font-size: 0.86rem; }
dt { color: var(--mute); }
dd { margin: 0; }

ul.links-list { list-style: none; padding-left: 0; }
ul.links-list li { margin-bottom: 0.4rem; }

a { color: var(--ink); text-decoration: underline; text-underline-offset: 0.18em; }
a:hover { color: var(--mute); }
a:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 4px; }

.chart-figure { min-width: 0; margin: 0; padding: 1.3rem; border: 1px solid var(--rule); background: #fff; }
.chart { display: block; width: 100%; height: auto; margin: 0; font-family: var(--sans); }
.chart .grid { stroke: var(--rule); stroke-width: 1; }
.chart .frame { fill: none; stroke: #938998; stroke-width: 1; }
.chart .tick { font-size: 12px; fill: var(--mute); }
.card .chart-key { display: flex; flex-wrap: wrap; justify-content: center; gap: 0.5rem 1.25rem; margin: 0.75rem 0 0; padding: 0; list-style: none; font-family: var(--sans); font-size: 0.82rem; }
.card .chart-key li { display: flex; align-items: center; gap: 0.45rem; margin: 0; }
.key-line { display: inline-block; width: 1.25rem; height: 2px; }

footer.wrap { padding-top: 1rem; padding-bottom: 3rem; border-top: 1px solid var(--rule); font-family: var(--sans); font-size: 0.78rem; color: var(--mute); }

/* trace pages */

main.wide { padding-top: 3rem; }
.crumb { margin: 0 0 1.5rem; font-family: var(--sans); font-size: 0.82rem; color: var(--mute); overflow-wrap: anywhere; }
h1.study { margin: 0 0 0.5rem; font-family: var(--display); font-size: clamp(1.6rem, 3.5vw, 2.3rem); font-weight: 500; letter-spacing: -0.035em; overflow-wrap: anywhere; }
.study-meta { margin: 0 0 2.5rem; }
.study-meta.lede { font-size: 1.05rem; color: var(--ink); }

.card.section { margin-bottom: 2.5rem; }
.card.section h2 .marks { font-family: var(--sans); font-size: 0.95rem; vertical-align: middle; }

pre.prompt, pre.reply {
  margin: 0;
  padding: 0.9rem 1rem;
  border: 1px solid var(--rule);
  background: #fafafa;
  font-family: var(--mono);
  font-size: 0.78rem;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
pre.reply { max-height: 34rem; overflow: auto; }
pre.reasoning { background: #fff; color: #555; }

.marks, .att { font-family: var(--sans); font-size: 0.85rem; letter-spacing: 0.06em; white-space: nowrap; }
.marks { margin-left: 0.6rem; }
th.att, td.att { text-align: center; }
.ok { color: var(--ink); }
.ko { color: #c4c7cc; }
table.traces td.model a { text-decoration: none; }
table.traces td.model a:hover { text-decoration: underline; }

details.attempt { margin: 0 0 0.6rem; border: 1px solid var(--rule); }
details.attempt summary { padding: 0.6rem 0.9rem; cursor: pointer; font-family: var(--sans); font-size: 0.86rem; list-style: none; }
details.attempt summary::-webkit-details-marker { display: none; }
details.attempt[open] summary { border-bottom: 1px solid var(--rule); }
details.attempt .body { padding: 0.7rem 0.9rem 1rem; }
.tag { display: inline-block; min-width: 2.6rem; margin-right: 0.6rem; padding: 0.05rem 0.4rem; font-size: 0.68rem; letter-spacing: 0.12em; text-transform: uppercase; text-align: center; border: 1px solid var(--ink); }
.tag.pass { background: var(--ink); color: #fff; }
.tag.fail { color: var(--mute); border-color: #c4c7cc; }
.why { color: var(--mute); }
.why code, table.checks code { font-family: var(--mono); font-size: 0.78rem; color: var(--ink); }
.meta-inline { color: var(--mute); font-size: 0.78rem; margin-left: 0.4rem; }
.label { margin: 0.9rem 0 0.3rem; font-family: var(--sans); font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--mute); }
details.inner { margin: 0.4rem 0 0; }
details.inner summary { cursor: pointer; font-family: var(--sans); font-size: 0.82rem; color: var(--mute); padding: 0.2rem 0; }
details.inner pre.prompt, details.inner pre.reply { margin-top: 0.4rem; }

table.checks { width: auto; font-size: 0.8rem; margin: 0.3rem 0 0.6rem; }
table.checks td { padding: 0.25rem 0.7rem 0.25rem 0; border-bottom: 0; white-space: normal; }
table.checks tbody tr:last-child td { border-bottom: 0; }
table.checks td.mark { width: 1rem; padding-right: 0.4rem; }
table.checks td.mark.ko { color: var(--ink); }
p.nav { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 1rem; font-family: var(--sans); font-size: 0.85rem; overflow-wrap: anywhere; }

@media (max-width: 1000px) {
  .grid:not(.three), .two.even { grid-template-columns: minmax(0, 1fr); }
  .plot, th.plot { display: none; }
}

@media (max-width: 600px) {
  .wrap { width: calc(100% - 2rem); }
  nav.top .wrap { padding-top: 1.5rem; gap: 0.8rem; }
  nav.top .brand { font-size: 2rem; }
  nav.top .links { gap: 0.5rem 1rem; font-size: 0.76rem; }
  nav.top .links .btn { padding: 0.3rem 0.6rem; }
  header.hero { padding: 2.6rem 0 2.3rem; }
  header.hero p { font-size: 1rem; }
  header.hero .meta { font-size: 0.72rem; }
  .grid.three { padding: 1.55rem 0; margin-bottom: 2.5rem; }
  .figure-card { padding: 0 0.4rem; }
  .figure { font-size: 1.85rem; }
  .figure span { font-size: 0.9rem; }
  .figure-card .caption { font-size: 0.7rem; line-height: 1.4; }
  .card h2 { font-size: 1.45rem; }
  .chart-figure { padding: 0.8rem 0.5rem; }
  .chart .tick { font-size: 20px; }
  dl { grid-template-columns: 6rem minmax(0, 1fr); gap: 0.6rem 0.8rem; }
  .meta-inline { display: block; margin: 0.4rem 0 0; }
  details.attempt summary, table.checks { overflow-wrap: anywhere; }
}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("results/leaderboard.json"))
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("results/audit.json"),
        help="audit output; the repeated-reply count is omitted when the file is absent",
    )
    parser.add_argument("--out", type=Path, default=Path("site"))
    args = parser.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    audit = (
        json.loads(args.audit.read_text(encoding="utf-8"))
        if args.audit.is_file()
        else None
    )
    built = dt.datetime.now(dt.timezone.utc).date().isoformat()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "index.html").write_text(
        render(data, built, audit), encoding="utf-8", newline="\n"
    )
    (args.out / "style.css").write_text(CSS, encoding="utf-8", newline="\n")
    if args.data.resolve() != (args.out / "leaderboard.json").resolve():
        shutil.copyfile(args.data, args.out / "leaderboard.json")
    for name in STATIC_ASSETS:
        source = Path(__file__).parent / name
        target = args.out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target.resolve():
            shutil.copyfile(source, target)
    print(f"wrote {args.out / 'index.html'}")


if __name__ == "__main__":
    main()
