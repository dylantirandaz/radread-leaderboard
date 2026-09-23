"""Render the RadRead results site from results/leaderboard.json.

All results are baked into static HTML. Scores, tables and links work without
JavaScript, including from file://, Pages and static Spaces.

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
    "FracAtlas",
]

SOURCE_SHORT = {
    "ChestX-Det": "ChestX-Det",
    "NIH ChestX-ray14": "NIH CXR14",
    "VinDr-CXR": "VinDr",
    "GRAZPEDWRI-DX": "GRAZ",
    "RSNA Pneumonia": "RSNA",
    "FracAtlas": "FracAtlas",
}

REPO_URL = "https://github.com/dylantirandaz/radread-public"
HF_SPACE = "https://huggingface.co/spaces/tirandazdylan/radread-leaderboard"
HF_DATA = "https://huggingface.co/datasets/tirandazdylan/radread-public-results"
SITE_REPO = "https://github.com/dylantirandaz/radread-leaderboard"
STATIC_ASSETS = (
    "site_assets/source-serif-4-latin.woff2",
    "site_assets/OFL.txt",
)


def pct(value: float) -> str:
    return f"{value * 100:.1f}"


def bar(value: float, width: int = 120) -> str:
    """Render a static result bar; numerical scores remain the authoritative values."""
    filled = max(0, min(width, round(value * width)))
    return (
        f'<span class="bar" style="width:{width}px" aria-hidden="true">'
        f'<span class="fill" style="width:{filled}px"></span></span>'
    )


def leaderboard_table(models: list[dict[str, Any]], max_k: int) -> str:
    """Render shared ranks for models sorted by descending pass@k."""
    head = (
        "<thead><tr>"
        "<th class='rank'></th><th>Model</th><th class='lab'>Lab</th>"
        "<th class='num'>pass@1</th>"
        f"<th class='num'>pass@{max_k}</th>"
        "<th class='plot'></th>"
        "<th class='num'>Checks</th>"
        "<th class='num'>Never solved</th>"
        "</tr></thead>"
    )
    rows = []
    rank = 0
    previous_score = None
    for index, model in enumerate(models, 1):
        score = model[f"pass@{max_k}"]
        if score != previous_score:
            rank = index
        previous_score = score
        rows.append(
            "<tr>"
            f"<td class='rank'>{rank}</td>"
            f"<td class='model'>{html.escape(model['name'])}"
            f"<span class='model-lab'>{html.escape(model['lab'])}</span></td>"
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


LINE_STYLES = (
    ("#3A7097", "none"),
    ("#B06B37", "8 4"),
    ("#39745E", "3 4"),
    ("#896A89", "10 3 2 3"),
    ("#555555", "2 5"),
)


def passk_chart(models: list[dict[str, Any]], max_k: int) -> str:
    """pass@k for k = 1..max_k, one line per model, as inline SVG.

    Drawn without a chart library: a light grid, y axis from 0 to at least 60 %,
    distinct colors and dashes, and a wrapping model key.
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
        colour, dash = LINE_STYLES[index % len(LINE_STYLES)]
        points = [(sx(k), sy(model[f"pass@{k}"])) for k in range(1, max_k + 1)]
        path = " ".join(
            f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}"
            for i, (x, y) in enumerate(points)
        )
        parts.append(
            f'<path d="{path}" fill="none" stroke="{colour}" stroke-width="2" stroke-dasharray="{dash}">'
            f'<title>{html.escape(model["name"])}</title></path>'
        )
        for x, y in points:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{colour}"/>')
        legend.append(
            f'<li><svg class="key-line" viewBox="0 0 40 8" aria-hidden="true">'
            f'<line x1="0" y1="4" x2="40" y2="4" stroke="{colour}" stroke-width="2" stroke-dasharray="{dash}"/>'
            f"</svg>"
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


def render(data: dict[str, Any], built: str) -> str:
    models = data["models"]
    max_k = data["rollouts_per_task"]
    protocol = data["protocol"]
    unsolved = data["unsolved_by_all"]
    best = models[0]
    best_one = max(models, key=lambda m: m["pass@1"])
    best_count = sum(
        model[f"pass@{max_k}"] == best[f"pass@{max_k}"] for model in models
    )
    best_one_count = sum(model["pass@1"] == best_one["pass@1"] for model in models)
    best_label = best["name"] if best_count == 1 else f"{best_count} models tied"
    best_one_label = (
        best_one["name"] if best_one_count == 1 else f"{best_one_count} models tied"
    )
    tasks = data["tasks"]
    unsolved_sources = ", ".join(
        f"{count} {source}"
        for source, count in sorted(
            unsolved["by_source"].items(), key=lambda kv: -kv[1]
        )
    )
    study_dots = (
        '<span class="solved"></span>' * (tasks - unsolved["count"])
        + '<span class="unsolved"></span>' * unsolved["count"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RadRead</title>
<meta name="description" content="RadRead: frontier models reading {tasks} radiographs. Findings, boxes, diagnosis and next step are scored against a fixed rubric.">
<link rel="preload" href="site_assets/source-serif-4-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="style.css">
</head>
<body class="results-page">
<a class="skip-link" href="#leaderboard">Skip to results</a>

<nav class="top">
  <div class="wrap">
    <a class="brand" href="index.html">RadRead</a>
    <span class="links"><a href="#leaderboard">Leaderboard</a><a href="traces/index.html">Traces</a><a href="{HF_DATA}">Results</a><a href="{REPO_URL}">Benchmark</a></span>
  </div>
</nav>

<header class="hero">
  <div class="wrap">
    <div class="study-map" role="img"
      aria-label="{tasks} studies, {unsolved['count']} never solved. Each dot represents one study.
      Filled dots passed at least once across all models; outlined dots never passed.
      Dots are grouped by outcome, not source or task order.">
      {study_dots}
    </div>
    <h1><span>Can models read</span> <span>radiographs?</span></h1>
    <p class="hero-description">Findings, boxes, diagnosis, next step. All must pass.</p>
    <div class="action-links">
      <a href="#leaderboard">Results <span aria-hidden="true">↓</span></a>
      <a href="{REPO_URL}">Benchmark <span aria-hidden="true">↗</span></a>
    </div>
  </div>
</header>

<main class="wrap landing">

<section class="result-section" id="leaderboard" aria-labelledby="leaderboard-title">
  <div class="section-heading">
    <h2 id="leaderboard-title">Leaderboard</h2>
  </div>
  <div class="metric-grid">
    <div class="figure-card">
      <p class="figure">{pct(best[f'pass@{max_k}'])}<span>%</span></p>
      <p class="caption">best pass@{max_k} · <span>{html.escape(best_label)}</span></p>
    </div>
    <div class="figure-card">
      <p class="figure">{pct(best_one['pass@1'])}<span>%</span></p>
      <p class="caption">best pass@1 · <span>{html.escape(best_one_label)}</span></p>
    </div>
    <div class="figure-card">
      <p class="figure">{unsolved['count']}</p>
      <p class="caption">never solved by any model</p>
    </div>
  </div>
  <div class="readout">
  {leaderboard_table(models, max_k)}
  <p class="caption">pass@k estimates ≥1 pass in k attempts. Checks = mean checks passed. Never solved = 0/{max_k}.</p>
  </div>
</section>

<section class="result-section" aria-labelledby="attempts-title">
  <div class="section-heading">
    <h2 id="attempts-title">More attempts, more passes?</h2>
  </div>
  <div class="curve-layout">
    <figure class="chart-figure">{passk_chart(models, max_k)}</figure>
    {curve_table(models, max_k)}
  </div>
</section>

<section class="result-section" aria-labelledby="breakdown-title">
  <div class="section-heading"><h2 id="breakdown-title">Source &amp; consistency</h2></div>
  <div class="two even">
    <article class="panel">
      <h3>Passing attempts</h3>
      {reliability(models, max_k)}
    </article>
    <article class="panel">
      <h3>pass@{max_k} by source</h3>
      {source_table(models, max_k)}
    </article>
  </div>
</section>

<section class="result-section" id="method" aria-labelledby="method-title">
  <div class="section-heading">
    <h2 id="method-title">What counts as a pass?</h2>
    <p>One image. One response. Deterministic scoring.</p>
  </div>
  <div class="criteria-grid">
    <article>
      <h3>Findings</h3>
      <p>The model identifies which findings are present or absent and answers any questions about their location. Every checklist answer must match the reference answer for that image.</p>
    </article>
    <article>
      <h3>Localization</h3>
      <p>The model places a box around each required finding. Boxes are checked for overlap, position and size. Each case limits how many extra, unmatched boxes are allowed.</p>
    </article>
    <article>
      <h3>Diagnosis</h3>
      <p>The model names the condition. The grader checks for an accepted diagnosis and whether the answer affirms or denies it. Different wording can count; the free-text summary is not scored.</p>
    </article>
    <article>
      <h3>Next step</h3>
      <p>The model chooses emergency action, urgent review, routine follow-up or no further action. It must choose an option accepted for that case. A more urgent choice is not automatically correct.</p>
    </article>
  </div>
  <div class="two even protocol-grid">
    <article>
      <h3>Protocol</h3>
      <dl>
        <dt>Rollouts</dt><dd>{max_k} per study</dd>
        <dt>Sampling</dt><dd>temperature {protocol['temperature']}, {protocol['max_tokens']:,} max tokens</dd>
        <dt>Reasoning</dt><dd>{html.escape(protocol['reasoning_effort'])}</dd>
        <dt>Inference</dt><dd>{html.escape(protocol['provider'])}</dd>
        <dt>Images</dt><dd>1024 × 1024 px, one per study</dd>
      </dl>
    </article>
    <article>
      <h3>Never solved</h3>
      <p>{unsolved['count']}/{tasks} studies never passed: {unsolved_sources}.</p>
      <p class="caption"><a href="{REPO_URL}/blob/main/NOTICE.md">Source terms</a> · Images and gold are not distributed.</p>
    </article>
  </div>
  <p class="caption">These 164 cases were selected using all five models' outcomes to keep every model's pass@4 below 35%. The same four saved attempts per model and study are reused here. This is an outcome-selected challenge set, not an independent holdout or evidence of model deterioration.</p>
</section>

<section class="explore" aria-labelledby="explore-title">
  <h2 id="explore-title">Look closer.</h2>
  <div class="action-links">
    <a href="{REPO_URL}">Benchmark <span aria-hidden="true">↗</span></a>
    <a href="traces/index.html">Traces <span aria-hidden="true">↗</span></a>
    <a href="{HF_DATA}">Data <span aria-hidden="true">↗</span></a>
  </div>
</section>

</main>

<footer class="wrap">
  <p>RadRead · {built}</p>
  <p><a href="{HF_SPACE}">HF mirror</a> · <a href="{SITE_REPO}">Source</a></p>
</footer>

</body>
</html>
"""


CSS = """@font-face {
  font-family: "Source Serif 4";
  font-style: normal;
  font-weight: 400 600;
  font-display: swap;
  src: url("site_assets/source-serif-4-latin.woff2") format("woff2");
}

:root {
  --ink: #222725;
  --mute: #5e6562;
  --rule: #dce4df;
  --band: #f4f8f5;
  --mint: #98e6c5;
  --mint-ink: #216954;
  --mint-wash: #f8fcfa;
  --pink: #f3c5e5;
  --pink-ink: #ad358b;
  --pink-wash: #fdfafb;
  --lime: #dcea74;
  --lavender: #c5b8d9;
  --serif: "Source Serif 4", Georgia, serif;
  --sans: Arial, Helvetica, sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}

* { box-sizing: border-box; }
[hidden] { display: none !important; }
::selection { background: var(--mint); color: var(--ink); }

html {
  font-family: var(--serif);
  font-size: 17px;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

body { margin: 0; color: var(--ink); background: #fff; line-height: 1.5; }
.results-page { isolation: isolate; }
.results-page::before, .results-page::after { content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none; }
.results-page::before {
  background:
    radial-gradient(ellipse 55% 44% at 5% 18%, rgba(243, 190, 222, 0.16), rgba(244, 205, 232, 0.06) 48%, transparent 82%),
    radial-gradient(ellipse 40% 48% at 24% 18%, rgba(250, 216, 230, 0.1), transparent 78%),
    radial-gradient(ellipse 58% 64% at 100% 44%, rgba(144, 223, 193, 0.15), transparent 80%),
    radial-gradient(ellipse 45% 36% at 88% 64%, rgba(191, 238, 219, 0.09), transparent 80%),
    radial-gradient(ellipse 55% 48% at -5% 84%, rgba(192, 184, 220, 0.07), transparent 80%),
    radial-gradient(ellipse 46% 40% at 14% 103%, rgba(220, 234, 160, 0.09), transparent 82%);
}
.results-page::after {
  opacity: 0.018;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='paper'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='3' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23paper)'/%3E%3C/svg%3E");
}

.wrap { width: min(1100px, calc(100% - 3rem)); margin: 0 auto; }
.skip-link { position: absolute; top: -5rem; left: 1rem; z-index: 20; padding: 0.6rem 1rem; background: #fff; }
.skip-link:focus { top: 1rem; }

nav.top { position: sticky; top: 0; z-index: 10; background: #fff; }
nav.top .wrap {
  width: calc(100% - 3rem);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem 2rem;
  padding: 1rem 0;
}
nav.top .brand { font-size: 1.35rem; font-weight: 500; line-height: 1; letter-spacing: -0.04em; text-decoration: none; color: var(--ink); }
nav.top .links { display: flex; align-items: center; flex-wrap: wrap; gap: 0.5rem 1.6rem; font-family: var(--sans); font-size: 0.78rem; }
nav.top .links a { padding: 0.3rem 0; color: var(--ink); text-decoration: none; }
nav.top .links a:hover { color: var(--mint-ink); text-decoration: underline; }

header.hero {
  padding: 3.5rem 0 5rem;
  text-align: center;
}
.study-map {
  display: grid;
  grid-template-columns: repeat(81, minmax(0, 1fr));
  justify-items: center;
  row-gap: 10px;
  width: 100%;
  margin: 0 auto 2rem;
}
.study-map span { width: 5px; height: 5px; border: 1px solid var(--mint-ink); border-radius: 50%; }
.study-map .solved { background: var(--mint-ink); }
.study-map .unsolved { background: #fff; border-color: var(--pink-ink); }
header.hero .eyebrow { margin: 0 0 1rem; font-family: var(--sans); font-size: 0.75rem; color: var(--mute); }
header.hero h1 {
  margin: 0 auto 1.4rem;
  max-width: 44rem;
  font-size: clamp(1.8rem, 4vw, 3.2rem);
  font-weight: 400;
  line-height: 1.1;
  letter-spacing: -0.025em;
  text-wrap: balance;
}
header.hero h1 span { display: block; }
.hero-description { margin: 0 auto; max-width: 27rem; color: var(--mute); font-size: 1.05rem; line-height: 1.6; text-wrap: balance; }
header.hero .meta { margin: 1.8rem 0 0; font-size: 0.75rem; }
.action-links { display: flex; flex-wrap: wrap; justify-content: center; gap: 0.75rem 1.75rem; margin-top: 1.8rem; font-family: var(--sans); font-size: 0.84rem; }
.action-links a { padding: 0.35rem 0; text-decoration: none; border-bottom: 2px solid var(--mint); }
.action-links a:nth-child(2) { border-color: var(--pink); }
.action-links a:nth-child(3) { border-color: var(--lime); }
.action-links a:hover { color: var(--mint-ink); border-color: currentColor; }
.action-links span { margin-left: 0.3rem; }

.meta, .caption { font-family: var(--sans); color: var(--mute); font-size: 0.82rem; line-height: 1.55; }
.caption { margin: 1rem 0 0; }

main.wrap { padding-bottom: 2rem; }
.result-section { margin-bottom: 5rem; scroll-margin-top: 6rem; }
.section-heading { margin: 0 auto 2.5rem; text-align: center; }
.section-heading h2, .explore h2 { margin: 0 0 1rem; font-size: clamp(1.6rem, 2.8vw, 2rem); font-weight: 400; line-height: 1.25; letter-spacing: -0.025em; text-wrap: balance; }
.section-heading p { max-width: 34rem; margin: 0 auto; color: var(--mute); font-family: var(--sans); font-size: 0.9rem; text-wrap: balance; }
.metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; margin: 3rem 0; }
.curve-layout { max-width: 46rem; margin: 0 auto; display: grid; gap: 1.5rem; }
.two.even { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1.25rem; }
.two > *, .criteria-grid > * { min-width: 0; }
.panel { min-width: 0; padding: 1.5rem; background: var(--mint-wash); border-radius: 0.35rem; }
.panel:nth-child(2) { background: var(--pink-wash); }
.landing h3 { margin: 0 0 1rem; font-size: 1.2rem; font-weight: 400; line-height: 1.3; }
.panel th, .panel td { padding-left: 0.5rem; padding-right: 0.5rem; }
.panel table { font-size: 0.8rem; }
.criteria-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 2rem; }
.criteria-grid article { padding-top: 1rem; border-top: 3px solid var(--mint); }
.criteria-grid article:nth-child(2) { border-color: var(--pink); }
.criteria-grid article:nth-child(3) { border-color: var(--lime); }
.criteria-grid article:nth-child(4) { border-color: var(--lavender); }
.criteria-grid h3 { font-family: var(--sans); font-size: 0.9rem; font-weight: 500; }
.criteria-grid p { margin: 0; font-family: var(--sans); color: var(--mute); font-size: 0.85rem; line-height: 1.6; }
.method-note { margin: 2.5rem auto 0; max-width: 38rem; text-align: center; font-size: 0.95rem; color: var(--mute); text-wrap: balance; }
.protocol-grid { margin-top: 3rem; }
.protocol-grid p { margin: 0 0 1rem; }
.explore { padding: 1rem 0 5rem; text-align: center; }

.card {
  border-top: 1px solid var(--rule);
  padding: 1.65rem 0 0;
  min-width: 0;
}

.card h2 {
  margin: 0 0 1.25rem;
  font-size: 1.25rem;
  font-weight: 500;
  line-height: 1.25;
  letter-spacing: -0.02em;
}

.card p { margin: 0 0 0.8rem; }
.card ol, .card ul { margin: 0 0 0.8rem; padding-left: 1.2rem; }
.card li { margin-bottom: 0.3rem; }

.figure-card { padding: 0 1rem; border-top: 0; text-align: center; }
.figure { margin: 0; font-size: clamp(1.9rem, 3.2vw, 2.5rem); font-weight: 400; line-height: 1; letter-spacing: -0.045em; font-variant-numeric: lining-nums tabular-nums; }
.figure span { font-size: 1rem; margin-left: 0.1rem; }
.figure-card .caption { margin: 0.7rem 0 0; font-size: 0.75rem; }
.figure-card .caption span { white-space: nowrap; }
.figure-card:first-child .figure { color: var(--mint-ink); }
.figure-card:nth-child(2) .figure { color: var(--pink-ink); }

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
thead th { border-bottom: 1px solid #999; font-weight: 400; font-size: 0.75rem; color: var(--mute); }
tbody tr:last-child td { border-bottom: 1px solid #999; }
table.board tbody tr:hover { background: var(--band); }
th:first-child, td:first-child { padding-left: 0; }
th:last-child, td:last-child { padding-right: 0; }
.readout .board, .curve-layout .board { background: rgba(255, 255, 255, 0.9); }
.readout .board th, .readout .board td { padding-left: 0.6rem; padding-right: 0.6rem; }
.readout .board thead th, .curve-layout .board thead th { background: rgba(152, 230, 197, 0.035); color: var(--mint-ink); border-bottom-color: var(--rule); }
.readout .board th:nth-child(4), .readout .board td:nth-child(4) { background: rgba(243, 197, 229, 0.025); }
.readout .board th:nth-child(5), .readout .board td:nth-child(5),
.curve-layout .board th:last-child, .curve-layout .board td:last-child { background: rgba(152, 230, 197, 0.04); color: var(--mint-ink); }
.num { text-align: right; }
.rank { width: 1.5rem; color: var(--mute); }
.model { font-weight: 500; }
.model-lab { display: none; }
.lab { color: var(--mute); }
.strong { font-weight: 700; }
.plot { width: 130px; }
.mute { color: var(--mute); }
th .n { display: block; font-size: 0.68rem; color: var(--mute); }

.bar { display: inline-block; height: 7px; vertical-align: middle; background: #eee; overflow: hidden; }
.bar .fill { display: block; height: 100%; background: #222; }

.band { width: 46%; }
.stack { display: flex; width: 100%; height: 7px; background: var(--pink); }
.seg { display: block; height: 100%; }
.seg.always { background: var(--mint-ink); }
.seg.sometimes { background: var(--mint); }
.seg.never { background: var(--pink); }

dl { display: grid; grid-template-columns: 8rem 1fr; gap: 0.45rem 1rem; margin: 0; font-family: var(--sans); font-size: 0.86rem; }
dt { color: var(--mute); }
dd { margin: 0; }

a { color: var(--ink); text-decoration: underline; text-underline-offset: 0.18em; }
a:hover { color: var(--mint-ink); }
a:focus-visible, summary:focus-visible, button:focus-visible { outline: 2px solid var(--mint-ink); outline-offset: 4px; }

.chart-figure { min-width: 0; margin: 0; }
.chart { display: block; width: 100%; height: auto; margin: 0; font-family: var(--sans); }
.chart .grid { stroke: var(--rule); stroke-width: 1; }
.chart .frame { fill: none; stroke: #999; stroke-width: 1; }
.chart .tick { font-size: 12px; fill: var(--mute); }
.chart-key { display: flex; flex-wrap: wrap; justify-content: center; gap: 0.7rem 1.25rem; margin: 1rem 0 0; padding: 0; list-style: none; font-family: var(--sans); font-size: 0.82rem; }
.chart-key li { display: flex; align-items: center; gap: 0.5rem; margin: 0; }
.key-line { display: block; flex: 0 0 2.5rem; width: 2.5rem; height: 0.5rem; }

footer.wrap { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0 1rem; padding-top: 1rem; padding-bottom: 2rem; border-top: 1px solid var(--rule); font-family: var(--sans); font-size: 0.75rem; color: var(--mute); }

/* trace pages */

main.wide { padding-top: 3rem; }
.crumb { margin: 0 0 1.5rem; font-family: var(--sans); font-size: 0.82rem; color: var(--mute); overflow-wrap: anywhere; }
h1.study { margin: 0 0 0.5rem; font-size: clamp(1.5rem, 3.5vw, 2rem); font-weight: 400; letter-spacing: -0.025em; overflow-wrap: anywhere; }
.study-meta { margin: 0 0 2.5rem; }
.study-meta.lede { font-size: 1.05rem; color: var(--ink); }

.card.section { margin-bottom: 2.5rem; }
.card.section h2 .marks { font-family: var(--sans); font-size: 0.95rem; vertical-align: middle; }

pre.prompt, pre.reply {
  margin: 0;
  padding: 0.9rem 1rem;
  border: 1px solid var(--rule);
  background: var(--band);
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
.ok { color: var(--mint-ink); }
.ko { color: var(--pink-ink); }
table.traces td.model a { text-decoration: none; }
table.traces td.model a:hover { text-decoration: underline; }

details.attempt { margin: 0 0 0.6rem; border: 1px solid var(--rule); }
details.attempt summary { padding: 0.6rem 0.9rem; cursor: pointer; font-family: var(--sans); font-size: 0.86rem; list-style: none; }
details.attempt summary::-webkit-details-marker { display: none; }
details.attempt[open] summary { border-bottom: 1px solid var(--rule); }
details.attempt .body { padding: 0.7rem 0.9rem 1rem; }
.tag { display: inline-block; min-width: 2.6rem; margin-right: 0.6rem; padding: 0.05rem 0.4rem; font-size: 0.68rem; letter-spacing: 0.12em; text-transform: uppercase; text-align: center; border: 1px solid var(--ink); }
.tag.pass { background: var(--mint-wash); color: var(--mint-ink); border-color: var(--mint-ink); }
.tag.fail { background: var(--pink-wash); color: var(--pink-ink); border-color: var(--pink-ink); }
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
table.checks td.mark.ko { color: var(--pink-ink); }
p.nav { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 1rem; font-family: var(--sans); font-size: 0.85rem; overflow-wrap: anywhere; }

@media (max-width: 1100px) {
  .two.even { grid-template-columns: minmax(0, 1fr); }
}

@media (max-width: 1000px) {
  .criteria-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .plot, th.plot { display: none; }
}

@media (max-width: 800px) {
  .study-map { grid-template-columns: repeat(27, minmax(0, 1fr)); row-gap: 6px; }
}

@media (max-width: 600px) {
  .wrap { width: calc(100% - 2rem); }
  nav.top .wrap { width: calc(100% - 2rem); flex-wrap: wrap; padding: 1rem 0; gap: 0.85rem; }
  nav.top .links { gap: 0.5rem 1rem; font-size: 0.72rem; }
  .readout .board { font-size: 0.8rem; }
  .readout .board th, .readout .board td { padding: 0.75rem 0.3rem; }
  .readout .board th { font-size: 0.68rem; white-space: normal; }
  .readout .board .rank { width: 1.2rem; }
  .readout .board .model { white-space: normal; }
  .readout .board .lab { display: none; }
  .readout .model-lab { display: block; margin-top: 0.15rem; font-size: 0.7rem; font-weight: 400; color: var(--mute); }
  header.hero { padding: 2.5rem 0 4.5rem; }
  .study-map { margin-bottom: 1.5rem; }
  .hero-description { font-size: 1rem; }
  header.hero .meta { font-size: 0.72rem; }
  .result-section { margin-bottom: 4.5rem; scroll-margin-top: 7.5rem; }
  .section-heading { margin-bottom: 2rem; }
  .metric-grid { gap: 0; margin: 2.5rem 0; }
  .figure-card { padding: 0 0.4rem; }
  .panel { padding: 1.2rem; }
  .criteria-grid { gap: 1.75rem 1.25rem; }
  .protocol-grid { margin-top: 2.5rem; }
  .explore { padding-bottom: 3rem; }
  .figure { font-size: 1.7rem; }
  .figure span { font-size: 0.9rem; }
  .figure-card .caption { font-size: 0.7rem; line-height: 1.4; }
  .card h2 { font-size: 1.25rem; }
  .chart .tick { font-size: 20px; }
  dl { grid-template-columns: 6rem minmax(0, 1fr); gap: 0.6rem 0.8rem; }
  .meta-inline { display: block; margin: 0.4rem 0 0; }
  details.attempt summary, table.checks { overflow-wrap: anywhere; }
}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("results/leaderboard.json"))
    parser.add_argument("--out", type=Path, default=Path("site"))
    args = parser.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    built = dt.datetime.now(dt.timezone.utc).date().isoformat()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "index.html").write_text(
        render(data, built), encoding="utf-8", newline="\n"
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
