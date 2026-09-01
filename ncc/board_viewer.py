"""Render the simple passive browser shell for the NCC network board."""

from __future__ import annotations

from html import escape

from .reconciliation import historical_line_topology_from_shared
from .shared_topology import SharedTopology


def render_ncc_board_html(shared: SharedTopology) -> str:
    """Return one restrained topology-first page with presentation-only logic."""

    page = _PAGE_TEMPLATE
    replacements = {
        "__TOPOLOGY_ID__": _text(shared.id),
        "__MAP_SVG__": _map_svg(shared),
    }
    for marker, value in replacements.items():
        page = page.replace(marker, value)
    return page


def _map_svg(shared: SharedTopology) -> str:
    topology = shared.topology
    historical = historical_line_topology_from_shared(shared)
    components = list(topology["components"])
    positions = {str(item["id"]): item["position"] for item in components}
    endpoint_owners = {
        str(endpoint["id"]): str(component["id"])
        for component in components
        for endpoint in component["endpoints"]
    }
    mapped_links = set(historical.line_link_ids.values())
    width, height = 1080, 500
    margin_x, margin_y = 105, 145
    xs = [float(position["x"]) for position in positions.values()]
    ys = [float(position["y"]) for position in positions.values()]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    x_span = x_max - x_min
    y_span = y_max - y_min

    def point(component_id: str) -> tuple[float, float]:
        position = positions[component_id]
        x = (
            width / 2
            if x_span == 0
            else margin_x
            + (float(position["x"]) - x_min) * (width - 2 * margin_x) / x_span
        )
        y = (
            height / 2
            if y_span == 0
            else margin_y
            + (float(position["y"]) - y_min) * (height - 2 * margin_y) / y_span
        )
        return x, y

    links = []
    for link in topology["links"]:
        link_id = str(link["id"])
        first_endpoint, second_endpoint = (str(item) for item in link["endpoints"])
        first_owner = endpoint_owners[first_endpoint]
        second_owner = endpoint_owners[second_endpoint]
        x1, y1 = point(first_owner)
        x2, y2 = point(second_owner)
        mapped = link_id in mapped_links
        links.append(
            f'<g class="link-group" data-link-group="{_attribute(link_id)}">'
            f'<title>{_text(link_id)} · '
            f'{"mapped report line" if mapped else "configured topology only"}</title>'
            f'<line class="network-link state-configured" '
            f'data-link-id="{_attribute(link_id)}" '
            f'data-mapped="{str(mapped).lower()}" '
            f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>'
            "</g>"
        )

    nodes = []
    for component in components:
        component_id = str(component["id"])
        kind = str(component["kind"])
        x, y = point(component_id)
        label = _board_label(component_id, str(component["label"]))
        if kind == "imp":
            shape = f'<circle class="node-shape" cx="{x:.1f}" cy="{y:.1f}" r="40"/>'
            lamp = (
                f'<circle class="node-lamp state-unknown" '
                f'data-component-lamp="{_attribute(component_id)}" '
                f'cx="{x + 31:.1f}" cy="{y - 31:.1f}" r="8"/>'
            )
        else:
            shape = (
                f'<rect class="node-shape" x="{x - 76:.1f}" y="{y - 31:.1f}" '
                'width="152" height="62" rx="2"/>'
            )
            lamp = ""
        nodes.append(
            f'<g class="network-node {_attribute(kind)}" '
            f'data-component-id="{_attribute(component_id)}">'
            f'<title>{_text(component["label"])} · configured shared topology</title>'
            f'{shape}{lamp}<text class="node-label" x="{x:.1f}" y="{y + 5:.1f}">'
            f'{_text(label)}</text><text class="node-id" x="{x:.1f}" y="{y + 61:.1f}">'
            f'{_text(component_id)}</text></g>'
        )

    return (
        f'<svg class="topology-map" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Configured seven-component ARPANET Redux topology with observed NCC state">'
        '<text class="lane-label" x="32" y="42">APPLICATION ROUTE</text>'
        '<text class="lane-label" x="32" y="482">NCC REPORT ROUTES</text>'
        + "".join(links + nodes)
        + "</svg>"
    )


def _board_label(identifier: str, fallback: str) -> str:
    return {
        "host:176": "UNIX 176",
        "host:106": "ITS 106",
        "imp:62": "IMP 62",
        "imp:6": "IMP 6",
        "imp:7": "IMP 7",
        "imp:5": "IMP 5",
        "host:ncc": "NCC",
    }.get(identifier, fallback)


def _text(value: object) -> str:
    return escape(str(value))


def _attribute(value: object) -> str:
    return escape(str(value), quote=True)


_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ARPANET Redux · NCC network board</title>
<style>
:root {
  --cabinet: #d7dad4;
  --field: #172329;
  --field-raised: #22343b;
  --panel: #f2f3ef;
  --ink: #172329;
  --muted: #6d7774;
  --rule: #aeb5b0;
  --configured: #70807f;
  --signal: #69a89c;
  --attention: #d3a44b;
  --fault: #c76655;
  --looped: #9b83b6;
  --display: "DIN Condensed", "Avenir Next Condensed", "Arial Narrow", sans-serif;
  --body: "Helvetica Neue", Helvetica, Arial, sans-serif;
  --utility: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--cabinet); color: var(--ink); font: 14px/1.4 var(--body); }
button, a { font: inherit; }
a:focus-visible, summary:focus-visible { outline: 3px solid var(--attention); outline-offset: 3px; }
.shell { margin: 0 auto; max-width: 1540px; min-height: 100vh; padding: 18px; }
.masthead { align-items: center; display: flex; gap: 22px; justify-content: space-between; padding: 0 2px 14px; }
.identity { align-items: baseline; display: flex; flex-wrap: wrap; gap: 10px 18px; }
.identity p { color: var(--muted); font: 700 11px/1 var(--utility); letter-spacing: .1em; margin: 0; text-transform: uppercase; }
h1 { font: 800 30px/1 var(--display); letter-spacing: .02em; margin: 0; text-transform: uppercase; }
.run-head { align-items: center; display: flex; gap: 12px; min-width: 0; }
.mode-lamp { background: var(--configured); border: 3px solid var(--panel); box-shadow: 0 0 0 1px var(--muted); border-radius: 50%; flex: 0 0 auto; height: 13px; width: 13px; }
.mode-lamp.live, .mode-lamp.completed { background: var(--signal); }
.mode-lamp.attention { background: var(--attention); }
.mode-copy { min-width: 0; text-align: right; }
.mode-copy strong { display: block; font: 800 13px/1.1 var(--display); letter-spacing: .08em; text-transform: uppercase; }
.mode-copy code { color: var(--muted); display: block; font: 10px/1.4 var(--utility); max-width: 38vw; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.report-link { border: 1px solid var(--ink); color: var(--ink); font: 700 11px/1 var(--display); letter-spacing: .08em; padding: 9px 11px; text-decoration: none; text-transform: uppercase; }
.report-link:hover { background: var(--ink); color: var(--panel); }
.report-link[hidden] { display: none; }
.status-line { background: var(--field); color: #dce3df; display: grid; grid-template-columns: minmax(0, 1.4fr) repeat(3, minmax(120px, .55fr)); margin-bottom: 12px; }
.status-cell { border-right: 1px solid #3c4d52; min-width: 0; padding: 9px 12px; }
.status-cell:last-child { border-right: 0; }
.status-cell span { color: #93a19e; display: block; font: 700 9px/1.2 var(--utility); letter-spacing: .09em; margin-bottom: 3px; text-transform: uppercase; }
.status-cell strong { display: block; font: 11px/1.35 var(--utility); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.error { background: #f4ddd8; border-left: 5px solid var(--fault); color: #6e2820; margin: 0 0 12px; padding: 10px 12px; }
.error[hidden] { display: none; }
.workspace { display: grid; gap: 12px; grid-template-columns: minmax(0, 1fr) 310px; }
.board, .rail { border: 1px solid var(--rule); min-width: 0; }
.board { background: var(--field); }
.board-head { align-items: baseline; border-bottom: 1px solid #3c4d52; color: #dce3df; display: flex; gap: 16px; justify-content: space-between; padding: 11px 14px; }
.board-head h2, .rail h2 { font: 800 14px/1.2 var(--display); letter-spacing: .08em; margin: 0; text-transform: uppercase; }
.board-head p { color: #93a19e; font: 10px/1.3 var(--utility); margin: 0; text-align: right; }
.map-scroll { overflow: auto; }
.topology-map { display: block; height: auto; min-width: 720px; width: 100%; }
.network-link { stroke: var(--configured); stroke-dasharray: 5 8; stroke-linecap: square; stroke-width: 3; transition: stroke .18s ease, stroke-width .18s ease; }
.network-link[data-mapped="true"] { stroke-width: 5; }
.network-link.state-up, .network-link.state-observed { stroke: var(--signal); stroke-dasharray: none; }
.network-link.state-down, .network-link.state-cut, .network-link.state-contradictory, .network-link.state-minus-down, .network-link.state-plus-down { stroke: var(--fault); stroke-dasharray: 10 4; }
.network-link.state-stale { stroke: var(--attention); stroke-dasharray: 3 8; }
.network-link.state-looped, .network-link.state-minus-looped, .network-link.state-plus-looped { stroke: var(--looped); stroke-dasharray: 8 4 2 4; }
.node-shape { fill: var(--field-raised); stroke: #dce3df; stroke-width: 2; transition: stroke .18s ease, stroke-width .18s ease; }
.network-node.journey-observed .node-shape { stroke: var(--signal); stroke-width: 4; }
.network-node.journey-attention .node-shape { stroke: var(--attention); stroke-width: 4; }
.node-label { fill: #f0f3f0; font: 800 15px/1 var(--display); letter-spacing: .04em; text-anchor: middle; }
.node-id { fill: #93a19e; font: 10px/1 var(--utility); text-anchor: middle; }
.node-lamp { fill: var(--configured); stroke: var(--field); stroke-width: 3; }
.node-lamp.state-up, .node-lamp.state-recorded { fill: var(--signal); }
.node-lamp.state-stale { fill: var(--attention); }
.node-lamp.state-down, .node-lamp.state-contradictory { fill: var(--fault); }
.network-node.is-active .node-lamp { animation: report-pulse .7s ease-out; }
.lane-label { fill: #71817f; font: 700 10px/1 var(--utility); letter-spacing: .16em; }
.route-phase { align-items: center; border-bottom: 1px solid #3c4d52; color: #93a19e; display: flex; font: 800 11px/1 var(--display); gap: 9px; justify-content: center; letter-spacing: .08em; padding: 8px 12px; text-transform: uppercase; }
.route-phase[hidden] { display: none; }
.route-phase .cut { color: var(--fault); }
.route-phase .alternate { color: var(--signal); }
.route-phase b { color: #5e6e70; font: 400 12px/1 var(--utility); }
.map-foot { align-items: center; border-top: 1px solid #3c4d52; color: #93a19e; display: flex; font: 10px/1.45 var(--utility); gap: 18px; justify-content: space-between; margin: 0; padding: 9px 13px; }
.map-foot strong { color: #dce3df; }
.rail { background: var(--panel); display: flex; flex-direction: column; }
.rail > header { border-bottom: 1px solid var(--rule); padding: 11px 13px; }
.summary { display: grid; }
.summary-row { border-bottom: 1px solid #d3d7d3; padding: 11px 13px; }
.summary-row > span { color: var(--muted); display: block; font: 700 9px/1.2 var(--utility); letter-spacing: .09em; margin-bottom: 4px; text-transform: uppercase; }
.summary-row strong { display: block; font: 800 18px/1.05 var(--display); text-transform: uppercase; }
.summary-row p { color: var(--muted); font: 11px/1.4 var(--utility); margin: 4px 0 0; overflow-wrap: anywhere; }
.summary-row.state-passed strong, .summary-row.state-up strong, .summary-row.state-observed strong { color: #2e7168; }
.summary-row.state-missing strong, .summary-row.state-stale strong { color: #946c1b; }
.summary-row.state-down strong, .summary-row.state-cut strong, .summary-row.state-contradictory strong { color: #9a3d31; }
.activity { border-bottom: 1px solid var(--rule); padding: 11px 13px 7px; }
.activity-head { align-items: baseline; display: flex; justify-content: space-between; margin-bottom: 5px; }
.activity-head strong { font: 800 12px/1 var(--display); letter-spacing: .07em; text-transform: uppercase; }
.activity-head span { color: var(--muted); font: 9px/1 var(--utility); }
.activity-list { list-style: none; margin: 0; padding: 0; }
.activity-list li { border-top: 1px solid #daddd9; display: grid; gap: 5px; grid-template-columns: 34px minmax(0, 1fr); padding: 7px 0; }
.activity-list code { color: var(--muted); font: 9px/1.35 var(--utility); }
.activity-list span { font: 11px/1.35 var(--body); }
.activity-empty { color: var(--muted); font: 11px/1.4 var(--utility); margin: 8px 0 10px; }
.legend { display: grid; gap: 6px; margin-top: auto; padding: 11px 13px; }
.legend span { align-items: center; color: var(--muted); display: flex; font: 9px/1.3 var(--utility); gap: 8px; }
.legend i { background: var(--configured); display: inline-block; height: 4px; width: 20px; }
.legend i.observed { background: var(--signal); }
.legend i.attention { background: var(--attention); }
.legend i.fault { background: var(--fault); }
.footer { align-items: baseline; color: var(--muted); display: flex; font: 10px/1.45 var(--utility); gap: 18px; justify-content: space-between; padding: 11px 2px 0; }
.footer span:last-child { text-align: right; }
@keyframes report-pulse {
  0% { filter: drop-shadow(0 0 0 rgba(105, 168, 156, 0)); }
  35% { filter: drop-shadow(0 0 8px rgba(105, 168, 156, .95)); }
  100% { filter: drop-shadow(0 0 0 rgba(105, 168, 156, 0)); }
}
@media (max-width: 980px) {
  .workspace { grid-template-columns: 1fr; }
  .rail { display: grid; grid-template-columns: 1fr 1fr; }
  .rail > header { grid-column: 1 / -1; }
  .legend { margin-top: 0; }
}
@media (max-width: 680px) {
  .shell { padding: 10px; }
  .masthead { align-items: flex-start; flex-direction: column; gap: 12px; }
  .run-head { width: 100%; }
  .mode-copy { flex: 1; text-align: left; }
  .mode-copy code { max-width: 62vw; }
  .status-line { grid-template-columns: 1fr 1fr; }
  .status-cell:nth-child(2) { border-right: 0; }
  .status-cell:nth-child(-n+2) { border-bottom: 1px solid #3c4d52; }
  .rail { display: block; }
  .board-head { align-items: flex-start; flex-direction: column; gap: 5px; }
  .board-head p { text-align: left; }
  .map-foot, .footer { align-items: flex-start; flex-direction: column; gap: 5px; }
  .footer span:last-child { text-align: left; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; scroll-behavior: auto !important; transition: none !important; }
}
</style>
</head>
<body>
<main class="shell">
  <header class="masthead">
    <div class="identity"><p>ARPANET Redux / NCC</p><h1>Network board</h1></div>
    <div class="run-head">
      <span id="mode-lamp" class="mode-lamp" aria-hidden="true"></span>
      <div class="mode-copy" aria-live="polite"><strong id="mode">Waiting</strong><code id="run-id">no validated run header</code></div>
      <a id="report-link" class="report-link" href="/report" hidden>Run report</a>
    </div>
  </header>
  <section class="status-line" aria-label="Board status">
    <div class="status-cell"><span>Topology</span><strong>__TOPOLOGY_ID__</strong></div>
    <div class="status-cell"><span>Observed events</span><strong id="report-count">0</strong></div>
    <div class="status-cell"><span>Last observation</span><strong id="last-observed">—</strong></div>
    <div class="status-cell"><span>Stream</span><strong id="stream-state">waiting</strong></div>
  </section>
  <p id="error" class="error" role="alert" hidden></p>
  <div class="workspace">
    <section class="board">
      <header class="board-head"><h2>Configured network</h2><p>validated observations only</p></header>
      <div id="route-phase" class="route-phase" aria-label="Validated failover sequence" hidden><span>Direct</span><b aria-hidden="true">→</b><span class="cut">Cut</span><b aria-hidden="true">→</b><span class="alternate">Via IMP 7</span></div>
      <div class="map-scroll">__MAP_SVG__</div>
      <p class="map-foot"><span><strong>Node border:</strong> typed application boundary.</span><span><strong>IMP lamp:</strong> attributed report evidence.</span><span><strong>Link color:</strong> validated state; configured-only remains dashed.</span></p>
    </section>
    <aside class="rail" aria-label="Current evidence">
      <header><h2>Current evidence</h2></header>
      <div class="summary">
        <article id="application-card" class="summary-row state-unknown"><span>Application</span><strong id="application-state">pending</strong><p id="application-detail">No completed application evidence yet.</p></article>
        <article id="journey-card" class="summary-row state-unknown"><span>Typed journey</span><strong id="journey-state">pending</strong><p id="journey-detail">Journey evidence appears after the formal transaction.</p></article>
        <article id="line-card" class="summary-row state-unknown"><span id="line-label">Network state</span><strong id="line-state">unknown</strong><p id="line-detail">No reciprocal report support yet.</p></article>
      </div>
      <section class="activity">
        <div class="activity-head"><strong id="activity-title">Recent observations</strong><span id="activity-count">0 shown</span></div>
        <p id="activity-empty" class="activity-empty">Waiting for a complete validated record.</p>
        <ol id="activity-list" class="activity-list"></ol>
      </section>
      <div class="legend" aria-label="State legend"><span><i></i>configured only</span><span><i class="observed"></i>observed / reported</span><span><i class="attention"></i>stale or missing evidence</span><span><i class="fault"></i>reported down or contradiction</span></div>
    </aside>
  </div>
  <footer class="footer"><span>Passive board: GET/HEAD only. No simulator or controller authority.</span><span>Scenario start and stop remain in the launching terminal.</span></footer>
</main>
<script>
const stateNames = ["configured", "unknown", "recorded", "observed", "up", "cut", "down", "stale", "looped", "contradictory", "minus-down", "plus-down", "minus-looped", "plus-looped", "passed", "missing"];
let latestSequence = null;

function setText(id, value) {
  document.getElementById(id).textContent = String(value ?? "—");
}

function applyState(element, state) {
  if (!element) return;
  stateNames.forEach((name) => element.classList.remove(`state-${name}`));
  element.classList.add(`state-${stateNames.includes(state) ? state : "unknown"}`);
}

function matching(attribute, value) {
  return [...document.querySelectorAll(`[${attribute}]`)].filter((element) => element.getAttribute(attribute) === value);
}

function resetMap() {
  document.querySelectorAll(".network-link").forEach((link) => applyState(link, "configured"));
  document.querySelectorAll(".node-lamp").forEach((lamp) => applyState(lamp, "unknown"));
  document.querySelectorAll(".network-node").forEach((node) => node.classList.remove("journey-observed", "journey-attention", "is-active"));
  document.getElementById("route-phase").hidden = true;
  setText("line-label", "Network state");
}

function setMode(mode, runId) {
  setText("mode", mode);
  setText("run-id", runId);
  const lamp = document.getElementById("mode-lamp");
  lamp.className = "mode-lamp";
  if (mode === "completed" || mode === "live") lamp.classList.add(mode);
  if (mode !== "completed" && mode !== "live" && mode !== "waiting") lamp.classList.add("attention");
}

function setSummary(kind, state, detail, visualState = state) {
  setText(`${kind}-state`, state);
  setText(`${kind}-detail`, detail);
  applyState(document.getElementById(`${kind}-card`), visualState);
}

function renderActivity(events) {
  const visible = events.slice(-7).reverse();
  const list = document.getElementById("activity-list");
  list.replaceChildren();
  visible.forEach((event) => {
    const item = document.createElement("li");
    const sequence = document.createElement("code");
    sequence.textContent = `#${event.sequence}`;
    const label = document.createElement("span");
    label.textContent = event.label || `${event.subject} · ${event.state}`;
    item.append(sequence, label);
    item.title = `${event.observed_at} · ${event.authority}`;
    list.append(item);
  });
  document.getElementById("activity-empty").hidden = visible.length !== 0;
  setText("activity-count", `${visible.length} shown`);
  const newest = events.at(-1);
  if (newest && newest.sequence !== latestSequence) {
    latestSequence = newest.sequence;
    const sourceImp = newest.source && newest.source.imp;
    const node = sourceImp === undefined ? null : document.querySelector(`[data-component-id="imp:${sourceImp}"]`);
    if (node) {
      node.classList.remove("is-active");
      void node.getBoundingClientRect();
      node.classList.add("is-active");
    }
  }
}

function renderHistorical(snapshot) {
  resetMap();
  const completed = snapshot.mode === "completed";
  setMode(completed ? "completed" : "live", snapshot.run.id);
  setText("report-count", snapshot.stream.complete_event_count);
  setText("last-observed", snapshot.event_tape.at(-1)?.observed_at || snapshot.run.started_at);
  setText("stream-state", completed ? `${snapshot.completion.outcome} · completed v2 summary` : `generation ${snapshot.stream.generation} · ${snapshot.stream.change}`);
  setText("activity-title", "Recent observations");
  snapshot.direct.imps.forEach((imp) => matching("data-component-lamp", imp.subject_id).forEach((lamp) => {
    applyState(lamp, imp.state);
    lamp.parentElement.querySelector("title").textContent = `${imp.subject_id} · ${imp.meaning} · ${imp.state_authority}`;
  }));
  snapshot.reconciled.lines.forEach((line) => matching("data-link-id", line.subject_id).forEach((link) => applyState(link, line.state)));
  const line = completed ? snapshot.completion.summary_lines[0] : snapshot.reconciled.lines[0];
  const scope = completed ? "This completed network-behavior run makes no application claim." : "The progressive report stream does not make an application claim.";
  setSummary("application", "unknown", scope);
  setSummary("journey", "unknown", completed ? "This line-state run has no typed application journey." : "Typed journey evidence is validated separately after the formal transaction.");
  setText("line-label", "Mapped IMP 5 / IMP 6 line");
  setSummary("line", line?.state || "unknown", line?.supporting_observation_ids.length ? `${completed ? "Completed support" : "Current support"} ${line.supporting_observation_ids.join(" · ")}.` : "No reciprocal report support yet.");
  renderActivity(snapshot.event_tape);
  document.getElementById("report-link").hidden = true;
}

function renderCompleted(snapshot) {
  resetMap();
  setMode("completed", snapshot.run.id);
  setText("report-count", snapshot.historical.complete_event_count);
  setText("last-observed", snapshot.phases.markers.at(-1)?.observed_at || snapshot.run.finished_at);
  setText("stream-state", `${snapshot.run.outcome} · cleanup ${snapshot.lifecycle.outer_runtime_cleanup}`);
  setText("activity-title", "Mapped-line observations");
  Object.entries(snapshot.historical.report_counts_by_source_imp.trouble).forEach(([imp, count]) => {
    if (count > 0) matching("data-component-lamp", `imp:${imp}`).forEach((lamp) => applyState(lamp, "recorded"));
  });
  const finalLine = snapshot.historical.final_at_run_finish.line;
  matching("data-link-id", finalLine.normalized_link_id).forEach((link) => applyState(link, finalLine.state));
  const boundariesByComponent = new Map();
  snapshot.journey.assessment.boundaries.forEach((boundary) => {
    const entries = boundariesByComponent.get(boundary.component_id) || [];
    entries.push(boundary.state);
    boundariesByComponent.set(boundary.component_id, entries);
  });
  boundariesByComponent.forEach((states, componentId) => {
    const node = document.querySelector(`[data-component-id="${componentId}"]`);
    if (node) node.classList.add(states.includes("missing") ? "journey-attention" : "journey-observed");
  });
  setSummary("application", snapshot.application.state, `${snapshot.application.facts[0].label}: ${snapshot.application.facts[0].value}; ${snapshot.application.facts[3].label}: ${snapshot.application.facts[3].value}.`);
  const journey = snapshot.journey.assessment;
  setSummary("journey", journey.state, journey.first_boundary_id ? `First unresolved observation: ${journey.first_boundary_id}.` : "Every configured boundary is observed.", journey.state === "missing-boundary" ? "missing" : journey.state === "complete" ? "passed" : "unknown");
  const accepted = snapshot.historical.accepted_line;
  setText("line-label", "Mapped IMP 5 / IMP 6 line");
  setSummary("line", accepted.state, `Accepted support ${accepted.supporting_sequences.join(" / ")}; run-finish view ${finalLine.state}.`);
  renderActivity(snapshot.historical.evidence_tape);
  document.getElementById("report-link").hidden = false;
}

function renderFailover(snapshot) {
  resetMap();
  setMode("completed", snapshot.run.id);
  setText("report-count", snapshot.historical.complete_event_count);
  setText("last-observed", snapshot.historical.last_observed_at);
  setText("stream-state", `${snapshot.run.outcome} · cleanup ${snapshot.lifecycle.outer_runtime_cleanup}`);
  setText("activity-title", "Post-cut NCC reports");
  snapshot.historical.post_cut_report_sources.forEach((imp) => matching("data-component-lamp", `imp:${imp}`).forEach((lamp) => applyState(lamp, "recorded")));
  snapshot.journey.route.links.forEach((routeLink) => matching("data-link-id", routeLink.id).forEach((link) => applyState(link, "observed")));
  matching("data-link-id", snapshot.failover.direct_link.id).forEach((link) => {
    applyState(link, "cut");
    link.parentElement.querySelector("title").textContent = `${snapshot.failover.direct_link.id} · acknowledged harness cut`;
  });
  snapshot.failover.alternate_route.link_ids.forEach((linkId) => matching("data-link-id", linkId).forEach((link) => {
    applyState(link, "observed");
    link.parentElement.querySelector("title").textContent = `${linkId} · typed post-cut journey observation`;
  }));
  const boundariesByComponent = new Map();
  snapshot.journey.assessment.boundaries.forEach((boundary) => {
    const entries = boundariesByComponent.get(boundary.component_id) || [];
    entries.push(boundary.state);
    boundariesByComponent.set(boundary.component_id, entries);
  });
  boundariesByComponent.forEach((states, componentId) => {
    const node = document.querySelector(`[data-component-id="${componentId}"]`);
    if (node) node.classList.add(states.includes("missing") ? "journey-attention" : "journey-observed");
  });
  const application = snapshot.application;
  setSummary("application", application.state, "One TELNET session returned structured ITS :TIME before and after the acknowledged cut.");
  const journey = snapshot.journey.assessment;
  setSummary("journey", journey.state, `Alternate route observed through IMP 7; first unresolved host boundary ${journey.first_boundary_id}.`, "missing");
  setText("line-label", "Application route");
  setSummary("line", "via IMP 7", `Direct application link cut; ${snapshot.failover.alternate_route.link_ids.length} alternate links observed by the typed journey.`, "passed");
  document.getElementById("route-phase").hidden = false;
  renderActivity(snapshot.historical.evidence_tape);
  document.getElementById("report-link").hidden = true;
}

function renderWaiting(payload) {
  resetMap();
  setMode("waiting", payload.run_id);
  setText("report-count", 0);
  setText("last-observed", "—");
  setText("stream-state", "waiting for validated header");
  setText("activity-title", "Recent observations");
  setSummary("application", "unknown", "The scenario has not emitted completed application evidence.");
  setSummary("journey", "unknown", "The scenario has not emitted a typed journey.");
  setSummary("line", "unknown", "No reciprocal report support yet.");
  renderActivity([]);
  document.getElementById("report-link").hidden = true;
}

async function poll() {
  const error = document.getElementById("error");
  try {
    const response = await fetch("/api/snapshot", { cache: "no-store", credentials: "same-origin" });
    const payload = await response.json();
    if (response.status === 202) {
      renderWaiting(payload);
    } else if (!response.ok) {
      throw new Error(payload.error || `snapshot request failed (${response.status})`);
    } else if (payload.failover && payload.historical && payload.journey) {
      renderFailover(payload);
    } else if (payload.composition && payload.historical && payload.journey) {
      renderCompleted(payload);
    } else {
      renderHistorical(payload);
    }
    error.hidden = true;
    error.textContent = "";
  } catch (problem) {
    error.hidden = false;
    error.textContent = `Validated board snapshot unavailable: ${problem.message}`;
    setMode("attention", document.getElementById("run-id").textContent);
  }
  window.setTimeout(poll, 1000);
}

poll();
</script>
</body>
</html>
"""
