"""Render the passive browser shell for a progressive historical NCC display."""

from __future__ import annotations

from html import escape
from typing import Any

from .reconciliation import (
    HistoricalLineTopology,
    historical_line_topology_from_shared,
)
from .shared_topology import SharedTopology


def render_historical_display_html(shared: SharedTopology) -> str:
    """Return one self-contained observer page with no evidence-reduction logic."""

    historical = historical_line_topology_from_shared(shared)
    page = _PAGE_TEMPLATE
    replacements = {
        "__TOPOLOGY_ID__": _text(shared.id),
        "__MAP_SVG__": _map_svg(shared, historical),
        "__ENDPOINT_CARDS__": _endpoint_cards(historical),
        "__LINE_CARDS__": _line_cards(historical),
        "__CONFIGURED_LINKS__": _configured_links(shared, historical),
    }
    for marker, value in replacements.items():
        page = page.replace(marker, value)
    return page


def _map_svg(shared: SharedTopology, historical: HistoricalLineTopology) -> str:
    topology = shared.topology
    components = list(topology["components"])
    positions = {str(item["id"]): item["position"] for item in components}
    endpoint_owners = {
        str(endpoint["id"]): str(component["id"])
        for component in components
        for endpoint in component["endpoints"]
    }
    xs = [float(position["x"]) for position in positions.values()]
    ys = [float(position["y"]) for position in positions.values()]
    width, height = 940, 430
    margin_x, margin_y = 112, 92
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
        return (
            x,
            y,
        )

    line_by_link = {
        link_id: line_id for line_id, link_id in historical.line_link_ids.items()
    }
    nominal_by_id = {line.id: line for line in historical.nominal.lines}
    segments = []
    labels = []
    for link in topology["links"]:
        link_id = str(link["id"])
        first_endpoint, second_endpoint = (str(item) for item in link["endpoints"])
        first_owner = endpoint_owners[first_endpoint]
        second_owner = endpoint_owners[second_endpoint]
        x1, y1 = point(first_owner)
        x2, y2 = point(second_owner)
        middle_x, middle_y = (x1 + x2) / 2, (y1 + y2) / 2
        line_id = line_by_link.get(link_id)
        if line_id is None:
            segments.append(
                f'<line class="configured-link" data-link-id="{_attribute(link_id)}" '
                f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>'
            )
            labels.append(
                f'<text class="link-label configured-label" x="{middle_x:.1f}" '
                f'y="{middle_y - 11:.1f}">{_text(_link_label(link_id))}</text>'
            )
            continue

        nominal = nominal_by_id[line_id]
        normalized_to_subject = {
            normalized: subject
            for subject, normalized in historical.endpoint_subject_ids.items()
            if subject in {endpoint.subject for endpoint in nominal.endpoints}
        }
        first_subject = normalized_to_subject[first_endpoint]
        second_subject = normalized_to_subject[second_endpoint]
        direction_by_subject = {
            nominal.minus_endpoint.subject: "minus",
            nominal.plus_endpoint.subject: "plus",
        }
        segments.extend(
            (
                f'<line class="evidence-half state-unknown" '
                f'data-endpoint-subject="{_attribute(first_subject)}" '
                f'data-direction="{direction_by_subject[first_subject]}" '
                f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{middle_x - 19:.1f}" y2="{middle_y:.1f}"/>',
                f'<line class="evidence-half state-unknown" '
                f'data-endpoint-subject="{_attribute(second_subject)}" '
                f'data-direction="{direction_by_subject[second_subject]}" '
                f'x1="{middle_x + 19:.1f}" y1="{middle_y:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>',
                f'<g class="line-result state-unknown" data-reconciled-line="{_attribute(link_id)}" '
                f'transform="translate({middle_x:.1f} {middle_y:.1f})">'
                '<rect x="-34" y="-16" width="68" height="32" rx="2"/>'
                '<text data-line-state x="0" y="5">unknown</text></g>',
            )
        )
        for endpoint in nominal.endpoints:
            normalized = historical.endpoint_subject_ids[endpoint.subject]
            owner = endpoint_owners[normalized]
            x, y = point(owner)
            sign = "−" if endpoint == nominal.minus_endpoint else "+"
            labels.append(
                f'<text class="direction-label" x="{x:.1f}" y="{y + 53:.1f}">'
                f'{sign} {direction_by_subject[endpoint.subject]}</text>'
            )
        labels.append(
            f'<text class="link-label" x="{middle_x:.1f}" y="{middle_y - 29:.1f}">'
            "mapped direct line</text>"
        )

    nodes = []
    for component in components:
        component_id = str(component["id"])
        x, y = point(component_id)
        if component["kind"] == "imp":
            shape = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="35"/>'
            lamp = (
                f'<circle class="report-lamp state-unknown" '
                f'data-report-lamp="{_attribute(component_id)}" '
                f'cx="{x + 31:.1f}" cy="{y - 31:.1f}" r="8"/>'
            )
            description = (
                f'<title data-report-detail="{_attribute(component_id)}">'
                "No attributed trouble report observed.</title>"
            )
        else:
            shape = (
                f'<rect x="{x - 67:.1f}" y="{y - 27:.1f}" '
                'width="134" height="54" rx="2"/>'
            )
            lamp = ""
            description = ""
        nodes.append(
            f'<g class="map-node" data-component-id="{_attribute(component_id)}">'
            f'{description}{shape}{lamp}<text x="{x:.1f}" y="{y + 5:.1f}">'
            f'{_text(component["label"])}</text></g>'
        )
    return (
        f'<svg class="topology-map" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Fixed NCC receiver and IMP topology with separate endpoint and reconciled states">'
        + "".join(segments + nodes + labels)
        + "</svg>"
    )


def _endpoint_cards(historical: HistoricalLineTopology) -> str:
    cards = []
    for line in historical.nominal.lines:
        for endpoint in (line.minus_endpoint, line.plus_endpoint):
            direction = "minus" if endpoint == line.minus_endpoint else "plus"
            cards.append(
                f'<article class="endpoint-card state-unknown" '
                f'data-endpoint-card="{_attribute(endpoint.subject)}">'
                f'<div class="card-kicker"><span>{direction} direct end</span>'
                '<span data-endpoint-state>unknown</span></div>'
                f'<code>{_text(endpoint.subject)}</code>'
                '<p data-endpoint-detail>No complete observation yet.</p>'
                '<p class="state-authority" data-endpoint-authority>'
                "State authority: in-memory absence classification.</p>"
                '<p class="evidence-id" data-endpoint-event>no supporting event</p>'
                "</article>"
            )
    return "".join(cards)


def _line_cards(historical: HistoricalLineTopology) -> str:
    return "".join(
        f'<article class="conclusion-card state-unknown" '
        f'data-line-card="{_attribute(historical.line_link_ids[line.id])}">'
        '<div class="card-kicker"><span>paired line</span>'
        '<span data-conclusion-state>unknown</span></div>'
        f'<code>{_text(historical.line_link_ids[line.id])}</code>'
        '<p>In-memory reconciliation; not a direct report.</p>'
        '<p class="evidence-id" data-conclusion-support>no reciprocal support</p>'
        "</article>"
        for line in historical.nominal.lines
    )


def _configured_links(
    shared: SharedTopology,
    historical: HistoricalLineTopology,
) -> str:
    mapped = set(historical.line_link_ids.values())
    return "".join(
        f'<li><code>{_text(link["id"])}</code><span>configured only</span></li>'
        for link in shared.topology["links"]
        if str(link["id"]) not in mapped
    )


def _link_label(identifier: str) -> str:
    if identifier == "link:ncc-imp5":
        return "receiver attachment · configured"
    if "alternate" in identifier:
        return "alternate link · configured"
    return "configured link"


def _text(value: object) -> str:
    return escape(str(value))


def _attribute(value: object) -> str:
    return escape(str(value), quote=True)


_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ARPANET Redux · passive NCC line desk</title>
<style>
:root {
  --cabinet: #cfd5d1;
  --paper: #f7f7f2;
  --ink: #16272d;
  --blueprint: #336c72;
  --amber: #b66c12;
  --fault: #a43d35;
  --loop: #665281;
  --quiet: #74817e;
  --rule: #98a49f;
  --shadow: rgba(22, 39, 45, .14);
  --display: "Avenir Next Condensed", "Arial Narrow", sans-serif;
  --body: Charter, "Iowan Old Style", Georgia, serif;
  --mono: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--cabinet); color: var(--ink); font: 16px/1.45 var(--body); }
code, time, .utility { font-family: var(--mono); }
.desk { margin: 0 auto; max-width: 1560px; padding: 22px; }
.masthead { align-items: end; border-bottom: 2px solid var(--ink); display: grid; gap: 18px; grid-template-columns: minmax(0, 1fr) auto; padding: 4px 2px 14px; }
.eyebrow, .section-label, .card-kicker, th { font: 700 12px/1.2 var(--display); letter-spacing: .12em; text-transform: uppercase; }
.eyebrow { color: var(--blueprint); margin: 0 0 5px; }
h1 { font: 800 clamp(34px, 5vw, 64px)/.88 var(--display); letter-spacing: -.025em; margin: 0; text-transform: uppercase; }
.passive-seal { align-items: center; border: 2px solid var(--blueprint); display: flex; font: 800 12px var(--display); gap: 8px; letter-spacing: .1em; padding: 8px 10px; text-transform: uppercase; }
.passive-seal::before { background: var(--blueprint); border-radius: 50%; content: ""; height: 9px; width: 9px; }
.status-strip { background: var(--ink); color: var(--paper); display: grid; font: 12px/1.35 var(--mono); gap: 1px; grid-template-columns: 1.5fr 1fr 1fr 1fr; margin-top: 12px; }
.status-cell { border-right: 1px solid #506066; min-width: 0; padding: 10px 12px; }
.status-cell:last-child { border-right: 0; }
.status-cell span { color: #b7c6c3; display: block; font: 700 10px var(--display); letter-spacing: .11em; margin-bottom: 3px; text-transform: uppercase; }
.status-cell strong { display: block; overflow-wrap: anywhere; }
.alert-banner { background: #f4d9d5; border: 2px solid var(--fault); color: #6d201b; margin-top: 12px; padding: 10px 12px; }
.alert-banner[hidden] { display: none; }
.main-grid { display: grid; gap: 16px; grid-template-columns: minmax(0, 1.72fr) minmax(330px, .78fr); margin-top: 16px; }
.panel { background: var(--paper); border: 1px solid var(--rule); box-shadow: 0 3px 12px var(--shadow); min-width: 0; }
.panel-head { align-items: baseline; border-bottom: 1px solid var(--rule); display: flex; gap: 14px; justify-content: space-between; padding: 12px 14px; }
.panel-head h2 { font: 800 17px var(--display); letter-spacing: .06em; margin: 0; text-transform: uppercase; }
.panel-head p { color: var(--quiet); font: 11px var(--mono); margin: 0; text-align: right; }
.map-wrap { padding: 10px 12px 3px; }
.topology-map { display: block; height: auto; width: 100%; }
.configured-link { stroke: var(--quiet); stroke-dasharray: 4 8; stroke-width: 2; }
.evidence-half { stroke: var(--quiet); stroke-linecap: square; stroke-width: 8; }
.evidence-half.state-up { stroke: var(--blueprint); }
.evidence-half.state-down { stroke: var(--fault); }
.evidence-half.state-looped { stroke: var(--loop); stroke-dasharray: 5 3; }
.evidence-half.state-stale { stroke: var(--amber); stroke-dasharray: 2 7; }
.evidence-half.state-contradictory { stroke: var(--fault); stroke-dasharray: 10 3 2 3; }
.evidence-half.state-unknown { stroke: var(--quiet); stroke-dasharray: 2 8; }
.line-result rect { fill: var(--paper); stroke: var(--quiet); stroke-width: 2; }
.line-result text { fill: var(--ink); font: 700 10px var(--mono); text-anchor: middle; text-transform: uppercase; }
.line-result.state-up rect { stroke: var(--blueprint); }
.line-result.state-down rect, .line-result.state-contradictory rect { stroke: var(--fault); stroke-width: 3; }
.line-result.state-minus-down rect, .line-result.state-plus-down rect { stroke: var(--fault); stroke-width: 3; }
.line-result.state-looped rect { stroke: var(--loop); stroke-width: 3; }
.line-result.state-minus-looped rect, .line-result.state-plus-looped rect { stroke: var(--loop); stroke-width: 3; }
.line-result.state-stale rect { stroke: var(--amber); }
.map-node > circle, .map-node > rect { fill: var(--paper); stroke: var(--ink); stroke-width: 2; }
.map-node > text { fill: var(--ink); font: 800 13px var(--display); text-anchor: middle; }
.report-lamp { fill: var(--quiet) !important; stroke: var(--paper) !important; stroke-width: 3 !important; }
.report-lamp.state-up { fill: var(--blueprint) !important; }
.report-lamp.state-stale { fill: var(--amber) !important; }
.report-lamp.state-unknown { fill: var(--quiet) !important; }
.link-label, .direction-label { fill: var(--ink); font: 700 11px var(--display); letter-spacing: .04em; text-anchor: middle; text-transform: uppercase; }
.configured-label { fill: var(--quiet); }
.direction-label { fill: var(--blueprint); }
.map-caption { border-top: 1px solid var(--rule); color: var(--quiet); display: flex; font: 11px/1.45 var(--mono); gap: 18px; justify-content: space-between; margin: 0; padding: 10px 14px; }
.map-caption strong { color: var(--ink); }
.evidence-rack { display: flex; flex-direction: column; gap: 12px; padding: 13px; }
.endpoint-card, .conclusion-card { border-left: 7px solid var(--quiet); padding: 8px 10px 9px; }
.endpoint-card.state-up, .conclusion-card.state-up { border-color: var(--blueprint); }
.endpoint-card.state-down, .endpoint-card.state-contradictory, .conclusion-card.state-down, .conclusion-card.state-contradictory { border-color: var(--fault); }
.conclusion-card.state-minus-down, .conclusion-card.state-plus-down { border-color: var(--fault); }
.endpoint-card.state-looped, .conclusion-card.state-looped { border-color: var(--loop); }
.conclusion-card.state-minus-looped, .conclusion-card.state-plus-looped { border-color: var(--loop); }
.endpoint-card.state-stale, .conclusion-card.state-stale { border-color: var(--amber); }
.card-kicker { align-items: center; display: flex; justify-content: space-between; }
.card-kicker span:last-child { font-family: var(--mono); }
.endpoint-card code, .conclusion-card code { display: block; font-size: 12px; margin: 5px 0; overflow-wrap: anywhere; }
.endpoint-card p, .conclusion-card p { color: #405156; font-size: 13px; margin: 3px 0 0; }
.endpoint-card .state-authority { color: var(--blueprint); font-family: var(--mono); font-size: 10px; }
.evidence-id { color: var(--quiet) !important; font-family: var(--mono); font-size: 10px !important; overflow-wrap: anywhere; }
.authority-key { border-top: 1px solid var(--rule); display: grid; gap: 7px; grid-template-columns: 1fr 1fr; padding-top: 11px; }
.authority-key span { align-items: center; display: flex; font: 10px/1.3 var(--mono); gap: 6px; }
.authority-key i { border: 2px solid var(--quiet); display: inline-block; height: 11px; width: 11px; }
.authority-key .direct { background: var(--blueprint); border-color: var(--blueprint); }
.authority-key .reconciled { background: var(--paper); border-color: var(--fault); }
.authority-key .configured { border-style: dashed; }
.authority-key .harness { background: var(--amber); border-color: var(--amber); }
.lower-grid { display: grid; gap: 16px; grid-template-columns: minmax(0, 1.6fr) minmax(300px, .65fr); margin-top: 16px; }
.tape-wrap { max-height: 430px; overflow: auto; }
table { border-collapse: collapse; font: 11px/1.35 var(--mono); width: 100%; }
th { background: #e5e9e5; color: #43565b; position: sticky; text-align: left; top: 0; z-index: 1; }
th, td { border-bottom: 1px solid #d1d7d3; padding: 8px 9px; vertical-align: top; }
td:first-child { color: var(--blueprint); font-weight: 700; }
.tape-empty { color: var(--quiet); margin: 0; padding: 18px; }
.side-list { list-style: none; margin: 0; padding: 5px 14px 13px; }
.side-list li { align-items: baseline; border-bottom: 1px solid #d7dcd8; display: flex; gap: 9px; justify-content: space-between; padding: 9px 0; }
.side-list code { font-size: 11px; overflow-wrap: anywhere; }
.side-list span { color: var(--quiet); flex: 0 0 auto; font: 10px var(--display); letter-spacing: .08em; text-transform: uppercase; }
.completion { border-top: 3px double var(--ink); margin: 2px 14px 14px; padding-top: 12px; }
.completion strong { display: block; font: 800 17px var(--display); letter-spacing: .04em; text-transform: uppercase; }
.completion p { color: #405156; font-size: 13px; margin: 4px 0 0; }
.footer { color: #53625f; font: 11px/1.45 var(--mono); margin: 14px 2px 0; }
@media (max-width: 920px) {
  .main-grid, .lower-grid { grid-template-columns: 1fr; }
  .status-strip { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 560px) {
  .desk { padding: 10px; }
  .masthead { grid-template-columns: 1fr; }
  .passive-seal { justify-self: start; }
  .status-strip { grid-template-columns: 1fr; }
  .status-cell { border-bottom: 1px solid #506066; border-right: 0; }
  .map-caption { display: block; }
  .authority-key { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
  * { scroll-behavior: auto !important; transition: none !important; }
}
</style>
</head>
<body>
<main class="desk">
  <header class="masthead">
    <div><p class="eyebrow">ARPANET Redux · historical report observer</p><h1>Passive NCC line desk</h1></div>
    <div class="passive-seal">Read only</div>
  </header>
  <section class="status-strip" aria-label="Observation status">
    <div class="status-cell"><span>Run</span><strong id="run-id">waiting for validated header</strong></div>
    <div class="status-cell"><span>Mode</span><strong id="mode">live observation</strong></div>
    <div class="status-cell"><span>Complete records</span><strong id="record-count">0</strong></div>
    <div class="status-cell"><span>Observation clock</span><strong id="observation-clock">—</strong></div>
  </section>
  <div id="error-banner" class="alert-banner" role="alert" hidden></div>
  <section class="main-grid">
    <section class="panel">
      <header class="panel-head"><h2>Fixed logical map</h2><p>__TOPOLOGY_ID__</p></header>
      <div class="map-wrap">__MAP_SVG__</div>
      <p class="map-caption"><span><strong>Split conductor:</strong> each half is one direct endpoint report; the center plate is the paired conclusion.</span><span id="tail-status">Complete JSONL prefix only.</span></p>
    </section>
    <aside class="panel evidence-rack">
      <p class="section-label">Endpoint evidence</p>
      __ENDPOINT_CARDS__
      <p class="section-label">Paired conclusion</p>
      __LINE_CARDS__
      <div class="authority-key" aria-label="Authority key"><span><i class="direct"></i>direct historical report</span><span><i class="reconciled"></i>in-memory reconciliation</span><span><i class="configured"></i>configured only</span><span><i class="harness"></i>terminal harness fact</span></div>
    </aside>
  </section>
  <section class="lower-grid">
    <section class="panel">
      <header class="panel-head"><h2>Report tape</h2><p id="stream-change">waiting for first snapshot</p></header>
      <div class="tape-wrap"><p id="tape-empty" class="tape-empty">No complete report events yet.</p><table id="event-table" hidden><thead><tr><th>#</th><th>Observed</th><th>Direct fact</th><th>Source</th><th>ID</th></tr></thead><tbody id="event-tape"></tbody></table></div>
    </section>
    <aside class="panel">
      <header class="panel-head"><h2>Configured-only paths</h2><p>never activity</p></header>
      <ul class="side-list">__CONFIGURED_LINKS__</ul>
      <div class="completion"><strong id="completion-title">Live reconciliation</strong><p id="completion-detail">No completed-summary authority is active.</p></div>
    </aside>
  </section>
  <p class="footer">This page issues read-only requests to a loopback server. It cannot launch, stop, attach to, or modify a simulator, controller, receiver, relay, reflector, result artifact, or external network endpoint.</p>
</main>
<script>
const stateClasses = ['state-up', 'state-down', 'state-looped', 'state-stale', 'state-unknown', 'state-contradictory', 'state-minus-down', 'state-plus-down', 'state-minus-looped', 'state-plus-looped'];
let handoffStarted = false;

function applyState(element, state) {
  if (!element) return;
  stateClasses.forEach((name) => element.classList.remove(name));
  const allowed = new Set(['up', 'down', 'looped', 'stale', 'unknown', 'contradictory', 'minus-down', 'plus-down', 'minus-looped', 'plus-looped']);
  element.classList.add(`state-${allowed.has(state) ? state : 'unknown'}`);
}

function matchingElements(attribute, value) {
  return [...document.querySelectorAll(`[${attribute}]`)].filter((element) => element.getAttribute(attribute) === value);
}

function renderEndpoint(endpoint) {
  matchingElements('data-endpoint-subject', endpoint.subject).forEach((segment) => applyState(segment, endpoint.state));
  matchingElements('data-endpoint-card', endpoint.subject).forEach((card) => {
    applyState(card, endpoint.state);
    card.querySelector('[data-endpoint-state]').textContent = endpoint.state;
    const neighbor = endpoint.details.neighbor_imp;
    const match = endpoint.topology_match;
    card.querySelector('[data-endpoint-detail]').textContent = endpoint.event_id
      ? `Last report: ${endpoint.last_known_state}; neighbor ${neighbor === null || neighbor === undefined ? 'not retained' : `IMP ${neighbor}`}; topology ${match ? 'matches' : 'contradicts'}.`
      : 'No complete observation yet.';
    card.querySelector('[data-endpoint-authority]').textContent = `State authority: ${endpoint.state_authority}.`;
    card.querySelector('[data-endpoint-event]').textContent = endpoint.event_id
      ? `${endpoint.event_id} · ${endpoint.observed_at} · ${endpoint.source.kind}`
      : 'no supporting event';
  });
}

function renderLine(line) {
  matchingElements('data-reconciled-line', line.subject_id).forEach((result) => {
    applyState(result, line.state);
    result.querySelector('[data-line-state]').textContent = line.state;
  });
  matchingElements('data-line-card', line.subject_id).forEach((card) => {
    applyState(card, line.state);
    card.querySelector('[data-conclusion-state]').textContent = line.state;
    card.querySelector('[data-conclusion-support]').textContent = line.supporting_observation_ids.length
      ? line.supporting_observation_ids.join(' · ')
      : 'no reciprocal support';
  });
}

function renderTape(events) {
  const body = document.querySelector('#event-tape');
  body.replaceChildren();
  const visible = events.slice(-48).reverse();
  visible.forEach((event) => {
    const row = document.createElement('tr');
    const values = [event.sequence, event.observed_at, event.label, `IMP ${event.source.imp} · ${event.source.kind}`, event.id];
    values.forEach((value) => { const cell = document.createElement('td'); cell.textContent = value; row.appendChild(cell); });
    row.title = `${event.authority}\n${JSON.stringify(event.details)}`;
    body.appendChild(row);
  });
  document.querySelector('#event-table').hidden = visible.length === 0;
  document.querySelector('#tape-empty').hidden = visible.length !== 0;
}

function renderCompletion(completion) {
  const title = document.querySelector('#completion-title');
  const detail = document.querySelector('#completion-detail');
  if (completion.status === 'matched') {
    title.textContent = 'Validated v2 handoff';
    detail.textContent = `Final live state and support agree. Opening the accepted completed-run summary (${completion.outcome}).`;
    if (!handoffStarted) {
      handoffStarted = true;
      window.setTimeout(() => window.location.replace(completion.handoff_url), 650);
    }
  } else if (completion.status === 'mismatch' || completion.status === 'invalid') {
    title.textContent = completion.status === 'mismatch' ? 'Completion mismatch' : 'Invalid completion';
    detail.textContent = (completion.issues || [completion.message]).filter(Boolean).join(' ');
  } else if (completion.status === 'pending') {
    title.textContent = 'Awaiting formal completion';
    detail.textContent = completion.message;
  } else {
    title.textContent = 'Live reconciliation';
    detail.textContent = 'This stream has no supported completed-summary handoff configured.';
  }
}

function render(snapshot) {
  document.querySelector('#run-id').textContent = snapshot.run.id;
  document.querySelector('#mode').textContent = snapshot.mode.replaceAll('-', ' ');
  document.querySelector('#record-count').textContent = String(snapshot.stream.complete_event_count);
  document.querySelector('#observation-clock').textContent = snapshot.observed_at;
  document.querySelector('#stream-change').textContent = `generation ${snapshot.stream.generation} · ${snapshot.stream.change}`;
  document.querySelector('#tail-status').textContent = snapshot.stream.incomplete_final_record
    ? 'Incomplete final JSONL record ignored.'
    : 'Complete JSONL prefix only.';
  snapshot.direct.endpoints.forEach(renderEndpoint);
  snapshot.direct.imps.forEach((imp) => matchingElements('data-report-lamp', imp.subject_id).forEach((lamp) => {
    applyState(lamp, imp.state);
    const source = imp.source ? `${imp.event_id} · ${imp.source.kind}` : 'no supporting event';
    const detail = `${imp.subject_id}: ${imp.meaning}. State authority: ${imp.state_authority}. ${source}.`;
    lamp.setAttribute('aria-label', detail);
    matchingElements('data-report-detail', imp.subject_id).forEach((title) => { title.textContent = detail; });
  }));
  snapshot.reconciled.lines.forEach(renderLine);
  renderTape(snapshot.event_tape);
  renderCompletion(snapshot.completion);
  const error = document.querySelector('#error-banner');
  if (snapshot.mode === 'completion-mismatch' || snapshot.mode === 'completion-invalid') {
    error.hidden = false;
    error.textContent = document.querySelector('#completion-detail').textContent;
  } else {
    error.hidden = true;
    error.textContent = '';
  }
}

async function poll() {
  try {
    const response = await fetch('/api/snapshot', { cache: 'no-store', credentials: 'same-origin' });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Snapshot request failed (${response.status}).`);
    render(payload);
  } catch (error) {
    const banner = document.querySelector('#error-banner');
    banner.hidden = false;
    banner.textContent = `Validated observation unavailable: ${error.message}`;
  }
  if (!handoffStarted) window.setTimeout(poll, 1000);
}

poll();
</script>
</body>
</html>
"""
