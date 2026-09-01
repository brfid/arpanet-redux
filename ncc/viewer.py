"""Render a deterministic, read-only local viewer for an NCC run summary."""

from __future__ import annotations

from html import escape
import json
from typing import Any

from .replay import replay_frames
from .run_summary import RunSummary


_STATE_CLASS = {
    "up": "state-up",
    "down": "state-down",
    "looped": "state-looped",
    "minus-down": "state-directional",
    "minus-looped": "state-directional",
    "plus-down": "state-directional",
    "plus-looped": "state-directional",
    "unknown": "state-unknown",
    "stale": "state-stale",
    "incomplete": "state-incomplete",
    "partitioned": "state-partitioned",
    "contradictory": "state-contradictory",
}


def render_summary_html(summary: RunSummary) -> str:
    """Return a self-contained local viewer for one validated summary."""

    document = summary.to_dict()
    frames = replay_frames(summary)
    topology = document["topology"]
    derived_states = {
        item["subject_id"]: item["state"] for item in document["derived_states"]
    }
    frame_data = [
        {
            "sequence": frame.sequence,
            "observed_at": frame.observed_at,
            "observation_id": frame.observation_id,
            "subject_id": frame.subject_id,
            "category": frame.category,
            "state": frame.state,
            "known_states": dict(frame.known_states),
        }
        for frame in frames
    ]
    frame_json = json.dumps(frame_data, separators=(",", ":"), sort_keys=True)
    frame_json = frame_json.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NCC run { _text(document['run']['id']) }</title>
<style>
:root {{
  --paper: #dbe6dd;
  --ink: #12242a;
  --blueprint: #2a5062;
  --signal: #087a62;
  --amber: #a06c12;
  --alert: #9b3f35;
  --quiet: #778783;
  --rule: #9aaba4;
  --panel: #f0f5ef;
  --mono: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  --display: Georgia, "Times New Roman", serif;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--paper); color: var(--ink); font: 15px/1.45 var(--mono); }}
button {{ font: inherit; }}
button:focus-visible {{ outline: 3px solid var(--amber); outline-offset: 3px; }}
.shell {{ max-width: 1420px; margin: 0 auto; padding: 24px; }}
.masthead {{ border-bottom: 3px double var(--ink); display: flex; gap: 24px; justify-content: space-between; padding: 0 0 16px; }}
.eyebrow {{ color: var(--blueprint); font-size: 12px; letter-spacing: .1em; margin: 0 0 4px; text-transform: uppercase; }}
h1 {{ font: 700 clamp(30px, 5vw, 56px)/.95 var(--display); letter-spacing: -.035em; margin: 0; }}
.run-id {{ align-self: end; color: var(--blueprint); margin: 0; text-align: right; word-break: break-all; }}
.overview {{ display: grid; gap: 18px; grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr); margin-top: 20px; }}
.map-panel, .panel {{ background: var(--panel); border: 1px solid var(--rule); }}
.map-panel {{ min-height: 360px; padding: 16px; }}
.panel {{ padding: 16px; }}
.panel h2, .map-panel h2 {{ font-size: 13px; letter-spacing: .08em; margin: 0 0 12px; text-transform: uppercase; }}
.map-note {{ color: var(--blueprint); font-size: 12px; margin: -4px 0 10px; }}
.topology {{ display: block; height: auto; overflow: visible; width: 100%; }}
.link {{ stroke: var(--blueprint); stroke-width: 2; }}
.link.state-up {{ stroke: var(--signal); stroke-width: 5; }}
.link.state-down, .link.state-looped, .link.state-directional, .link.state-partitioned, .link.state-contradictory {{ stroke: var(--alert); stroke-width: 5; }}
.link.state-incomplete, .link.state-unknown, .link.state-stale {{ stroke: var(--amber); stroke-dasharray: 7 5; stroke-width: 4; }}
.node circle {{ fill: var(--panel); stroke: var(--blueprint); stroke-width: 2; }}
.node rect {{ fill: var(--panel); stroke: var(--blueprint); stroke-width: 2; }}
.node text {{ fill: var(--ink); font: 600 13px var(--mono); text-anchor: middle; }}
.node .state-dot {{ fill: var(--quiet); stroke: none; }}
.node.state-up .state-dot {{ fill: var(--signal); }}
.node.state-down .state-dot, .node.state-looped .state-dot, .node.state-directional .state-dot, .node.state-partitioned .state-dot, .node.state-contradictory .state-dot {{ fill: var(--alert); }}
.node.state-incomplete .state-dot, .node.state-unknown .state-dot, .node.state-stale .state-dot {{ fill: var(--amber); }}
.ribbon {{ stroke: var(--quiet); stroke-dasharray: 2 9; stroke-linecap: round; stroke-width: 5; }}
.ribbon.state-up {{ stroke: var(--signal); }}
.ribbon.state-down, .ribbon.state-looped, .ribbon.state-directional, .ribbon.state-partitioned, .ribbon.state-contradictory {{ stroke: var(--alert); }}
.ribbon.state-incomplete, .ribbon.state-unknown, .ribbon.state-stale {{ stroke: var(--amber); }}
.status-card {{ border-left: 8px solid var(--quiet); padding: 12px 0 12px 14px; }}
.status-card.passed {{ border-color: var(--signal); }}
.status-card.incomplete {{ border-color: var(--amber); }}
.status-card.failed {{ border-color: var(--alert); }}
.status {{ font: 700 28px/1 var(--display); margin: 0 0 6px; text-transform: capitalize; }}
.status-card p {{ margin: 0; }}
.divider {{ border: 0; border-top: 1px solid var(--rule); margin: 16px 0; }}
.legend {{ display: grid; gap: 8px; grid-template-columns: 1fr 1fr; font-size: 12px; }}
.key {{ align-items: center; display: flex; gap: 7px; }}
.dot {{ background: var(--quiet); border-radius: 50%; display: inline-block; height: 10px; width: 10px; }}
.dot.up {{ background: var(--signal); }} .dot.alert {{ background: var(--alert); }} .dot.unknown {{ background: var(--amber); }}
.replay {{ margin-top: 18px; }}
.replay-controls {{ align-items: center; display: flex; flex-wrap: wrap; gap: 8px; }}
.replay-controls button {{ background: var(--ink); border: 0; color: var(--panel); cursor: pointer; padding: 7px 10px; }}
.replay-controls button[disabled] {{ background: var(--quiet); cursor: not-allowed; }}
.replay-readout {{ color: var(--blueprint); margin: 10px 0 0; min-height: 2.9em; }}
.grid {{ display: grid; gap: 18px; grid-template-columns: minmax(0, 1.2fr) minmax(0, .8fr); margin-top: 18px; }}
table {{ border-collapse: collapse; width: 100%; }}
th {{ color: var(--blueprint); font-size: 11px; letter-spacing: .08em; text-align: left; text-transform: uppercase; }}
th, td {{ border-bottom: 1px solid var(--rule); padding: 8px 5px; vertical-align: top; }}
code {{ font: 12px/1.35 var(--mono); overflow-wrap: anywhere; }}
.verdict {{ font-weight: 700; text-transform: capitalize; }}
.verdict.passed {{ color: var(--signal); }} .verdict.failed {{ color: var(--alert); }} .verdict.inconclusive {{ color: var(--amber); }}
.event-row.future {{ color: var(--quiet); }}
.event-row.current {{ background: #c9ddd1; }}
.provenance, .evidence {{ list-style: none; margin: 0; padding: 0; }}
.provenance li, .evidence li {{ border-bottom: 1px solid var(--rule); padding: 7px 0; }}
.quiet {{ color: var(--blueprint); font-size: 12px; }}
.footnote {{ border-top: 3px double var(--ink); color: var(--blueprint); font-size: 12px; margin-top: 20px; padding-top: 12px; }}
@media (max-width: 760px) {{ .shell {{ padding: 14px; }} .masthead, .overview, .grid {{ display: block; }} .run-id {{ margin-top: 12px; text-align: left; }} .panel, .map-panel {{ margin-top: 14px; }} table {{ font-size: 12px; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior: auto !important; transition: none !important; }} }}
</style>
</head>
<body>
<main class="shell">
  <header class="masthead">
    <div><p class="eyebrow">Network Control Center · completed-run console</p><h1>Signal ribbon</h1></div>
    <p class="run-id">{_text(document['run']['id'])}</p>
  </header>
  <section class="overview" aria-label="Run overview">
    <section class="map-panel">
      <h2>Configured route</h2>
      <p class="map-note">Fixed logical positions are configured facts. Status dots show derived conclusions, not simulator controls.</p>
      {_topology_svg(topology, derived_states)}
    </section>
    <aside class="panel">
      <div class="status-card {_attribute(document['run']['outcome'])}">
        <p class="eyebrow">Completed run verdict</p>
        <p class="status">{_text(document['run']['outcome'])}</p>
        <p>{_text(document['run']['started_at'])} → {_text(document['run']['finished_at'])}</p>
      </div>
      <hr class="divider">
      <h2>State key</h2>
      <div class="legend"><span class="key"><i class="dot up"></i> derived up</span><span class="key"><i class="dot alert"></i> derived failure</span><span class="key"><i class="dot unknown"></i> incomplete / unknown</span><span class="key"><i class="dot"></i> configured only</span></div>
      <hr class="divider">
      <p class="quiet">This viewer is read-only. It cannot launch, stop, attach to, or modify any simulator process.</p>
    </aside>
  </section>
  <section class="panel replay" aria-label="Deterministic observation replay">
    <h2>Observation replay</h2>
    <div class="replay-controls"><button id="previous" type="button">Previous observation</button><button id="next" type="button">Next observation</button><button id="reset" type="button">Reset</button><span id="position" class="quiet"></span></div>
    <p id="replay-readout" class="replay-readout" aria-live="polite"></p>
  </section>
  <section class="grid">
    <section class="panel"><h2>Acceptance gates</h2>{_gates_table(document['gates'])}</section>
    <section class="panel"><h2>Derived conclusions</h2>{_derived_list(document['derived_states'])}</section>
  </section>
  <section class="grid">
    <section class="panel"><h2>Ordered observations</h2>{_observations_table(document['observations'])}</section>
    <section class="panel"><h2>Provenance</h2>{_provenance_list(document['run']['provenance'])}<h2 style="margin-top:18px">External evidence pointers</h2>{_evidence_list(document.get('external_evidence', []))}</section>
  </section>
  <p class="footnote">The timeline replays direct historical, harness, and application observations in stored sequence with their named sources. Derived conclusions retain their basis and supporting observation identifiers; the browser does not recalculate topology or acceptance results.</p>
</main>
<script>
const frames = {frame_json};
let index = frames.length ? 0 : -1;
const rows = [...document.querySelectorAll('.event-row')];
const position = document.querySelector('#position');
const readout = document.querySelector('#replay-readout');
const previous = document.querySelector('#previous');
const next = document.querySelector('#next');
function render() {{
  const frame = frames[index];
  position.textContent = frame ? `Observation ${{frame.sequence}} of ${{frames.length}}` : 'No observations';
  readout.textContent = frame ? `${{frame.observed_at}} · ${{frame.category}} · ${{frame.subject_id}} → ${{frame.state}}` : '';
  rows.forEach((row) => {{ const sequence = Number(row.dataset.sequence); row.classList.toggle('future', !frame || sequence > frame.sequence); row.classList.toggle('current', Boolean(frame) && sequence === frame.sequence); }});
  previous.disabled = index <= 0;
  next.disabled = index >= frames.length - 1;
}}
previous.addEventListener('click', () => {{ if (index > 0) {{ index -= 1; render(); }} }});
next.addEventListener('click', () => {{ if (index < frames.length - 1) {{ index += 1; render(); }} }});
document.querySelector('#reset').addEventListener('click', () => {{ index = frames.length ? 0 : -1; render(); }});
render();
</script>
</body>
</html>
"""


def _topology_svg(topology: dict[str, Any], states: dict[str, str]) -> str:
    components = topology["components"]
    positions = {item["id"]: item["position"] for item in components}
    endpoint_owners = {
        endpoint["id"]: component["id"]
        for component in components
        for endpoint in component["endpoints"]
    }
    xs = [position["x"] for position in positions.values()]
    ys = [position["y"] for position in positions.values()]
    width, height, margin = 760, 260, 74
    x_span = max(xs) - min(xs) or 1
    y_span = max(ys) - min(ys) or 1

    def point(component_id: str) -> tuple[float, float]:
        position = positions[component_id]
        return (
            margin + (position["x"] - min(xs)) * (width - 2 * margin) / x_span,
            margin + (position["y"] - min(ys)) * (height - 2 * margin) / y_span,
        )

    links = []
    for link in topology["links"]:
        first, second = (endpoint_owners[endpoint] for endpoint in link["endpoints"])
        x1, y1 = point(first)
        x2, y2 = point(second)
        state_class = _STATE_CLASS.get(states.get(link["id"], "configured"), "")
        classes = f"link {state_class}" if state_class else "link"
        links.append(
            f'<line class="{_attribute(classes)}" '
            f'data-subject="{_attribute(link["id"])}" '
            f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>'
        )
    route = topology["routes"][0] if topology["routes"] else None
    ribbon = []
    route_state = states.get(route["id"], "configured") if route else "configured"
    for first, second in zip(route["components"], route["components"][1:]) if route else ():
        x1, y1 = point(first)
        x2, y2 = point(second)
        ribbon.append(
            f'<line class="ribbon {_attribute(_STATE_CLASS.get(route_state, ""))}" '
            f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>'
        )
    nodes = []
    for component in components:
        component_id = component["id"]
        x, y = point(component_id)
        state = states.get(component_id, "configured")
        shape = (
            f'<rect x="{x - 40:.1f}" y="{y - 22:.1f}" width="80" height="44"/>'
            if component["kind"] == "host"
            else f'<circle cx="{x:.1f}" cy="{y:.1f}" r="24"/>'
        )
        nodes.append(
            f'<g class="node {_attribute(_STATE_CLASS.get(state, ""))}" data-subject="{_attribute(component_id)}">'
            f'{shape}<circle class="state-dot" cx="{x + 27:.1f}" cy="{y - 27:.1f}" r="6"/>'
            f'<text x="{x:.1f}" y="{y + 4:.1f}">{_text(component["label"])}</text></g>'
        )
    return (
        f'<svg class="topology" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Configured network route and derived component state">'
        + "".join(links + ribbon + nodes)
        + "</svg>"
    )


def _gates_table(gates: list[dict[str, Any]]) -> str:
    rows = "".join(
        "<tr>"
        f"<td><code>{_text(gate['id'])}</code></td>"
        f"<td>{_text(gate.get('kind', 'application'))}</td>"
        f"<td>{_text(gate['assertion'])}</td>"
        f"<td class=\"verdict {_attribute(gate['verdict'])}\">{_text(gate['verdict'])}</td>"
        f"<td><code>{_text(', '.join(gate['evidence_observation_ids']))}</code></td>"
        f"<td><code>{_text(', '.join(gate.get('evidence_derived_state_ids', [])))}</code></td>"
        "</tr>"
        for gate in gates
    )
    return "<table><thead><tr><th>Gate</th><th>Kind</th><th>Assertion</th><th>Verdict</th><th>Observations</th><th>Derived states</th></tr></thead><tbody>" + rows + "</tbody></table>"


def _derived_list(states: list[dict[str, Any]]) -> str:
    if not states:
        return "<p class=\"quiet\">No derived conclusions.</p>"
    items = "".join(
        "<li><strong class=\"verdict "
        + _attribute(_STATE_CLASS.get(item["state"], "").removeprefix("state-"))
        + "\">"
        + _text(item["state"])
        + "</strong> <code>"
        + _text(item["subject_id"])
        + "</code><br><span class=\"quiet\">"
        + _text(item["basis"])
        + " from "
        + _text(", ".join(item["supporting_observation_ids"]))
        + "</span></li>"
        for item in states
    )
    return f'<ul class="provenance">{items}</ul>'


def _observations_table(observations: list[dict[str, Any]]) -> str:
    rows = "".join(
        "<tr class=\"event-row\" data-sequence=\""
        + str(observation["sequence"])
        + "\"><td>"
        + str(observation["sequence"])
        + "</td><td>"
        + _text(observation["observed_at"])
        + "</td><td>"
        + _text(observation["category"])
        + "</td><td><code>"
        + _text(observation["subject_id"])
        + "</code></td><td>"
        + _text(observation["state"])
        + "</td><td><code>"
        + _text(observation["source"]["id"])
        + "</code><br><span class=\"quiet\">"
        + _text(observation["source"]["kind"])
        + "</span>"
        + "</td></tr>"
        for observation in observations
    )
    return "<table><thead><tr><th>#</th><th>Time</th><th>Authority</th><th>Subject</th><th>State</th><th>Source</th></tr></thead><tbody>" + rows + "</tbody></table>"


def _provenance_list(provenance: list[dict[str, Any]]) -> str:
    items = "".join(
        "<li><code>"
        + _text(item["id"])
        + "</code><br><span class=\"quiet\">"
        + _text(item["kind"])
        + (" · " + _text(item["revision"]) if "revision" in item else "")
        + "</span></li>"
        for item in provenance
    )
    return f'<ul class="provenance">{items}</ul>'


def _evidence_list(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return "<p class=\"quiet\">No external evidence pointers.</p>"
    items = "".join(
        "<li><code>"
        + _text(item["id"])
        + "</code><br><span class=\"quiet\">"
        + _text(item["kind"])
        + " · "
        + _text(item["locator"])
        + "</span></li>"
        for item in evidence
    )
    return f'<ul class="evidence">{items}</ul>'


def _text(value: object) -> str:
    return escape(str(value))


def _attribute(value: object) -> str:
    return escape(str(value), quote=True)
