"""Render the passive browser shell for the completed coexistence desk."""

from __future__ import annotations


def render_coexistence_display_html() -> str:
    """Return one self-contained page with presentation logic only."""

    return _PAGE


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ARPANET Redux · NCC coexistence desk</title>
<style>
:root {
  --panel: #16252d;
  --panel-2: #20343d;
  --paper: #eee9da;
  --paper-2: #dcd7c9;
  --ink: #14252b;
  --verified: #4ea9ae;
  --verdict: #e0a64b;
  --tail: #c65d58;
  --steel: #74878d;
  --display: "Avenir Next Condensed", "Arial Narrow", sans-serif;
  --body: "Avenir Next", "Segoe UI", system-ui, sans-serif;
  --mono: "SFMono-Regular", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
html { background: var(--panel); color-scheme: dark; }
body { background: var(--panel); color: var(--paper); font: 15px/1.48 var(--body); margin: 0; }
button { color: inherit; font: inherit; }
code, time, .mono { font-family: var(--mono); }
.desk { margin: 0 auto; max-width: 1720px; padding: 24px; }
.masthead { align-items: end; border-bottom: 2px solid var(--paper); display: grid; gap: 22px; grid-template-columns: minmax(0, 1fr) auto; padding: 4px 2px 16px; }
.eyebrow, .section-label, dt, th, .chip, .marker-kind { font: 800 10px/1.2 var(--display); letter-spacing: .14em; text-transform: uppercase; }
.eyebrow { color: var(--verified); margin: 0 0 7px; }
h1 { font: 900 clamp(38px, 6vw, 78px)/.84 var(--display); letter-spacing: -.025em; margin: 0; text-transform: uppercase; }
.outcome-seal { border: 2px solid var(--verdict); color: var(--verdict); min-width: 178px; padding: 10px 12px; text-align: right; }
.outcome-seal span { display: block; font: 800 10px var(--display); letter-spacing: .14em; text-transform: uppercase; }
.outcome-seal strong { display: block; font: 900 29px/1 var(--display); margin-top: 4px; text-transform: uppercase; }
.status-strip { border-bottom: 1px solid rgba(238, 233, 218, .33); display: grid; grid-template-columns: 1.5fr 1fr 1fr 1.25fr; }
.status-cell { border-right: 1px solid rgba(238, 233, 218, .22); min-width: 0; padding: 11px 12px; }
.status-cell:last-child { border-right: 0; }
.status-cell span { color: rgba(238, 233, 218, .62); display: block; font: 800 9px var(--display); letter-spacing: .12em; margin-bottom: 3px; text-transform: uppercase; }
.status-cell strong { display: block; font: 650 11px/1.4 var(--mono); overflow-wrap: anywhere; }
.error { background: var(--tail); border: 2px solid var(--paper); color: var(--paper); margin-top: 16px; padding: 12px 14px; }
.error[hidden] { display: none; }
.panel { background: var(--paper); border: 1px solid rgba(238, 233, 218, .34); color: var(--ink); min-width: 0; }
.panel-head { align-items: baseline; border-bottom: 1px solid rgba(20, 37, 43, .3); display: flex; gap: 16px; justify-content: space-between; padding: 12px 14px; }
.panel-head h2 { font: 900 18px/1 var(--display); letter-spacing: .075em; margin: 0; text-transform: uppercase; }
.panel-head p { color: rgba(20, 37, 43, .68); font: 10px/1.35 var(--mono); margin: 0; text-align: right; }
.phase-panel { background: var(--panel-2); border: 1px solid rgba(238, 233, 218, .38); margin-top: 18px; }
.phase-panel .panel-head { border-color: rgba(238, 233, 218, .25); color: var(--paper); }
.phase-panel .panel-head p { color: rgba(238, 233, 218, .66); }
.phase-scroll { overflow-x: auto; padding: 18px 18px 8px; }
.phase-stage { min-width: 980px; padding: 42px 24px 54px; position: relative; }
.phase-track { background: rgba(238, 233, 218, .24); height: 3px; position: relative; }
.phase-support-span, .phase-tail-span { height: 9px; position: absolute; top: -3px; }
.phase-support-span { background: var(--verdict); }
.phase-tail-span { background: linear-gradient(90deg, rgba(198, 93, 88, .35), var(--tail)); }
.phase-marker { background: transparent; border: 0; cursor: pointer; height: 52px; margin-left: -18px; padding: 0; position: absolute; top: -25px; width: 36px; }
.phase-marker::before { background: var(--steel); border: 3px solid var(--panel-2); border-radius: 50%; content: ""; display: block; height: 17px; margin: 17px auto 0; width: 17px; }
.phase-marker.accepted-support::before { background: var(--verdict); }
.phase-marker.receiver-tail::before { background: var(--tail); }
.phase-marker[aria-pressed="true"]::before { box-shadow: 0 0 0 4px var(--paper); }
.phase-marker:focus-visible { outline: 3px solid var(--verified); outline-offset: 5px; }
.phase-label { color: var(--paper); font: 9px/1.25 var(--mono); left: 50%; min-width: 130px; position: absolute; text-align: center; top: 48px; transform: translateX(-50%); }
.phase-marker:nth-child(even) .phase-label { bottom: 49px; top: auto; }
.phase-marker.edge-start { margin-left: 0; }
.phase-marker.edge-start .phase-label { left: 0; text-align: left; transform: none; }
.phase-marker.edge-end { margin-left: -36px; }
.phase-marker.edge-end .phase-label { left: auto; right: 0; text-align: right; transform: none; }
.phase-sequence { color: var(--verdict); display: block; font-weight: 800; }
.phase-inspector { border-top: 1px solid rgba(238, 233, 218, .22); display: grid; gap: 12px 22px; grid-template-columns: 1.2fr 1fr 1fr; padding: 13px 18px; }
.phase-inspector strong { display: block; font: 850 14px var(--display); letter-spacing: .045em; text-transform: uppercase; }
.phase-inspector span { color: rgba(238, 233, 218, .72); display: block; font: 10px/1.45 var(--mono); margin-top: 3px; overflow-wrap: anywhere; }
.judgment-ledger { background: var(--paper); border: 1px solid rgba(238, 233, 218, .34); color: var(--ink); display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin-top: 16px; }
.judgment { border-left: 8px solid var(--verified); min-height: 164px; padding: 16px 18px; }
.judgment + .judgment { border-top: 0; }
.judgment.journey { border-left-color: var(--tail); }
.judgment.line { border-left-color: var(--verdict); }
.judgment .section-label { color: rgba(20, 37, 43, .62); margin: 0; }
.judgment h2 { font: 900 clamp(27px, 3vw, 43px)/.9 var(--display); margin: 12px 0 7px; text-transform: uppercase; }
.judgment p { margin: 0; }
.judgment .authority { color: rgba(20, 37, 43, .66); font: 9px/1.4 var(--mono); margin-top: 11px; }
.main-grid { display: grid; gap: 16px; grid-template-columns: minmax(0, 1.65fr) minmax(300px, .65fr); margin-top: 16px; }
.map-wrap { background: var(--paper); overflow-x: auto; padding: 8px 10px 2px; }
.topology-map { display: block; min-width: 760px; width: 100%; }
.topology-map .configured-link { stroke: rgba(20, 37, 43, .38); stroke-dasharray: 7 7; stroke-width: 3; }
.topology-map .mapped-link { stroke: rgba(224, 166, 75, .72); stroke-dasharray: 3 5; stroke-width: 5; }
.topology-map .tail-half { stroke-width: 7; }
.topology-map .tail-half.state-down { stroke: var(--tail); }
.topology-map .tail-half.state-stale { stroke: var(--steel); stroke-dasharray: 4 5; }
.topology-map .tail-half.state-up { stroke: var(--verified); }
.topology-map .tail-half.state-unknown { stroke: rgba(20, 37, 43, .28); stroke-dasharray: 3 6; }
.topology-map .node-shape { fill: var(--paper); stroke: var(--ink); stroke-width: 3; }
.topology-map .observer .node-shape { fill: var(--panel-2); stroke: var(--verified); }
.topology-map .observer text { fill: var(--paper); }
.topology-map text { fill: var(--ink); font: 800 13px var(--display); pointer-events: none; text-anchor: middle; }
.topology-map .component-id { fill: rgba(20, 37, 43, .62); font: 9px var(--mono); }
.topology-map .observer .component-id { fill: rgba(238, 233, 218, .7); }
.topology-map .link-label { fill: rgba(20, 37, 43, .65); font: 8px var(--mono); }
.topology-map .accepted-plate { fill: var(--verdict); stroke: var(--ink); stroke-width: 2; }
.topology-map .accepted-label { fill: var(--ink); font: 900 9px var(--display); letter-spacing: .06em; }
.map-caption { border-top: 1px solid rgba(20, 37, 43, .24); color: rgba(20, 37, 43, .74); display: flex; flex-wrap: wrap; font: 10px/1.45 var(--mono); gap: 10px 22px; margin: 0; padding: 10px 14px 13px; }
.authority-body { padding: 6px 14px 14px; }
.authority-list { list-style: none; margin: 0; padding: 0; }
.authority-list li { border-bottom: 1px solid rgba(20, 37, 43, .21); padding: 10px 0; }
.authority-list strong { display: block; font: 850 11px var(--display); letter-spacing: .055em; text-transform: uppercase; }
.authority-list span { color: rgba(20, 37, 43, .7); display: block; font: 9px/1.42 var(--mono); margin-top: 3px; }
.journey-panel { margin-top: 16px; }
.journey-route { align-items: center; border-bottom: 1px solid rgba(20, 37, 43, .25); display: flex; gap: 8px; overflow-x: auto; padding: 12px 14px; }
.journey-route .route-node { border: 2px solid var(--ink); flex: 0 0 auto; font: 800 10px/1.2 var(--display); min-width: 120px; padding: 8px 10px; text-align: center; text-transform: uppercase; }
.journey-route .route-node.imp { border-radius: 50%; min-width: 78px; padding: 26px 7px; }
.journey-route .route-conductor { color: rgba(20, 37, 43, .58); flex: 1 0 70px; font: 8px/1.2 var(--mono); text-align: center; }
.journey-route .route-conductor::before { border-top: 2px dashed rgba(20, 37, 43, .38); content: ""; display: block; margin-bottom: 4px; }
.journey-body { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(280px, .55fr); }
.journey-lanes { border-right: 1px solid rgba(20, 37, 43, .25); padding: 14px; }
.lane + .lane { margin-top: 13px; }
.lane-head { align-items: baseline; display: flex; justify-content: space-between; margin-bottom: 6px; }
.lane-head strong { font: 900 14px var(--display); letter-spacing: .09em; text-transform: uppercase; }
.lane-head span { color: rgba(20, 37, 43, .62); font: 9px var(--mono); }
.boundary-grid { display: grid; gap: 6px; grid-template-columns: repeat(6, minmax(112px, 1fr)); min-width: 720px; }
.boundary-scroll { overflow-x: auto; }
.boundary { background: transparent; border: 2px dashed rgba(20, 37, 43, .38); cursor: pointer; min-height: 82px; padding: 7px 8px; text-align: left; }
.boundary.observed.direct { background: var(--verified); border-color: var(--verified); color: var(--paper); }
.boundary.observed.harness-derived { background: var(--verdict); border-color: var(--verdict); color: var(--ink); }
.boundary.missing { border-color: var(--tail); color: var(--tail); }
.boundary[aria-pressed="true"] { box-shadow: inset 0 0 0 3px var(--ink); }
.boundary:focus-visible { outline: 4px solid var(--tail); outline-offset: 2px; }
.boundary small { display: flex; font: 800 8px var(--display); justify-content: space-between; letter-spacing: .08em; text-transform: uppercase; }
.boundary strong { display: block; font: 900 16px/1 var(--display); margin: 9px 0 6px; text-transform: uppercase; }
.boundary code { display: block; font-size: 8px; overflow-wrap: anywhere; }
.boundary-inspector { padding: 14px; }
.boundary-inspector h3 { font: 900 28px/1 var(--display); margin: 7px 0; text-transform: uppercase; }
.boundary-inspector p { color: rgba(20, 37, 43, .72); margin: 0 0 10px; }
.fact-grid { display: grid; grid-template-columns: 100px minmax(0, 1fr); margin: 0; }
.fact-grid dt, .fact-grid dd { border-top: 1px solid rgba(20, 37, 43, .2); margin: 0; padding: 6px 0; }
.fact-grid dd { font: 9px/1.45 var(--mono); overflow-wrap: anywhere; }
.lower-grid { display: grid; gap: 16px; grid-template-columns: .72fr 1.25fr .9fr; margin-top: 16px; }
.body-pad { padding: 12px 14px 14px; }
table { border-collapse: collapse; font: 9px/1.4 var(--mono); width: 100%; }
th { background: var(--paper-2); color: rgba(20, 37, 43, .72); position: sticky; text-align: left; top: 0; }
th, td { border-bottom: 1px solid rgba(20, 37, 43, .2); padding: 8px 9px; vertical-align: top; }
td:first-child { color: var(--verified); font-weight: 800; }
.tape-wrap { max-height: 430px; overflow: auto; }
.tape-row.support td { background: rgba(224, 166, 75, .13); }
.tape-row.tail td:first-child, .state-down-text { color: var(--tail); }
.report-matrix td:not(:first-child), .report-matrix th:not(:first-child) { text-align: right; }
.report-matrix td { font-size: 12px; }
.lifecycle-stamp { border: 2px solid var(--verified); display: grid; gap: 6px; grid-template-columns: 1fr auto; margin-bottom: 13px; padding: 10px; }
.lifecycle-stamp strong { font: 900 17px var(--display); text-transform: uppercase; }
.lifecycle-stamp code { font-size: 10px; }
.artifact-list { list-style: none; margin: 0; padding: 0; }
.artifact-list li { border-top: 1px solid rgba(20, 37, 43, .2); padding: 8px 0; }
.artifact-list strong, .artifact-list code, .artifact-list span { display: block; overflow-wrap: anywhere; }
.artifact-list strong { font: 850 10px var(--display); letter-spacing: .04em; text-transform: uppercase; }
.artifact-list code { color: rgba(20, 37, 43, .72); font-size: 8px; margin-top: 2px; }
.artifact-list span { color: rgba(20, 37, 43, .7); font-size: 9px; margin-top: 2px; }
.footer { border-top: 1px solid rgba(238, 233, 218, .3); color: rgba(238, 233, 218, .68); font: 9px/1.5 var(--mono); margin-top: 17px; padding: 12px 2px 0; }
@media (max-width: 1100px) {
  .main-grid, .lower-grid { grid-template-columns: 1fr; }
  .judgment-ledger { grid-template-columns: 1fr; }
  .judgment + .judgment { border-top: 1px solid rgba(20, 37, 43, .22); }
  .journey-body { grid-template-columns: 1fr; }
  .journey-lanes { border-bottom: 1px solid rgba(20, 37, 43, .25); border-right: 0; }
}
@media (max-width: 720px) {
  .desk { padding: 12px; }
  .masthead { align-items: start; grid-template-columns: 1fr; }
  .outcome-seal { justify-self: start; text-align: left; }
  .status-strip { grid-template-columns: 1fr 1fr; }
  .status-cell:nth-child(2) { border-right: 0; }
  .status-cell:nth-child(-n+2) { border-bottom: 1px solid rgba(238, 233, 218, .22); }
  .phase-inspector { grid-template-columns: 1fr; }
  .panel-head { align-items: start; flex-direction: column; }
  .panel-head p { text-align: left; }
}
@media (prefers-reduced-motion: reduce) {
  * { scroll-behavior: auto !important; transition: none !important; }
}
</style>
</head>
<body>
<main class="desk">
  <header class="masthead">
    <div><p class="eyebrow">ARPANET Redux · evidence-composed operator view</p><h1>NCC coexistence desk</h1></div>
    <div class="outcome-seal"><span>Composition verdict</span><strong id="composition-state">validating</strong></div>
  </header>
  <section class="status-strip" aria-label="Completed run identity">
    <div class="status-cell"><span>Run</span><strong id="run-id">waiting for validated artifacts</strong></div>
    <div class="status-cell"><span>Observation span</span><strong id="run-span">—</strong></div>
    <div class="status-cell"><span>Repository</span><strong id="revision">—</strong></div>
    <div class="status-cell"><span>Desk boundary</span><strong>read-only · structured artifacts only</strong></div>
  </section>
  <div id="error" class="error" role="alert" hidden></div>

  <section class="phase-panel" aria-labelledby="phase-heading">
    <header class="panel-head"><h2 id="phase-heading">Evidence phase rail</h2><p>historical-event sequence · never a shared simulator clock</p></header>
    <div class="phase-scroll"><div class="phase-stage"><div id="phase-track" class="phase-track"><div id="support-span" class="phase-support-span"></div><div id="tail-span" class="phase-tail-span"></div></div></div></div>
    <div id="phase-inspector" class="phase-inspector" aria-live="polite"></div>
  </section>

  <section class="judgment-ledger" aria-label="Independent evidence conclusions">
    <article class="judgment application"><p class="section-label">Application plane</p><h2 id="application-state">—</h2><p id="application-summary">Awaiting Gate 4H evidence.</p><p id="application-authority" class="authority"></p></article>
    <article class="judgment journey"><p class="section-label">Typed journey</p><h2 id="journey-state">—</h2><p id="journey-summary">Awaiting reducer diagnosis.</p><p id="journey-authority" class="authority"></p></article>
    <article class="judgment line"><p class="section-label">Mapped direct line</p><h2 id="line-state">—</h2><p id="line-summary">Awaiting composition support.</p><p id="line-authority" class="authority"></p></article>
  </section>

  <section class="main-grid">
    <section class="panel">
      <header class="panel-head"><h2>One configured composition</h2><p id="topology-id">waiting for shared topology</p></header>
      <div id="map" class="map-wrap"></div>
      <p class="map-caption"><span><strong>Dashed:</strong> configured link only.</span><span><strong>Amber plate:</strong> accepted reciprocal support.</span><span><strong>Colored halves:</strong> run-finish tail endpoint classification.</span><span>Neither route configuration nor application success assigns historical traffic to a link.</span></p>
    </section>
    <aside class="panel">
      <header class="panel-head"><h2>Authority ledger</h2><p>keep planes separate</p></header>
      <div id="authorities" class="authority-body"></div>
    </aside>
  </section>

  <section class="panel journey-panel">
    <header class="panel-head"><h2>Typed application journey</h2><p id="journey-id">twelve configured crossings · ten typed observations</p></header>
    <div id="journey-route" class="journey-route"></div>
    <div class="journey-body">
      <div class="journey-lanes">
        <section class="lane"><div class="lane-head"><strong>Request →</strong><span>host 176 toward ITS 106</span></div><div class="boundary-scroll"><div id="request-lane" class="boundary-grid"></div></div></section>
        <section class="lane"><div class="lane-head"><strong>← Reply</strong><span>ITS 106 toward host 176</span></div><div class="boundary-scroll"><div id="reply-lane" class="boundary-grid"></div></div></section>
      </div>
      <aside id="boundary-inspector" class="boundary-inspector" aria-live="polite"></aside>
    </div>
  </section>

  <section class="lower-grid">
    <section class="panel">
      <header class="panel-head"><h2>Report coverage</h2><p>direct stream = verdict counts</p></header>
      <div class="body-pad"><table class="report-matrix"><thead><tr><th>Source IMP</th><th>Type 303</th><th>Type 302</th></tr></thead><tbody id="report-counts"></tbody></table><div id="application-facts"></div></div>
    </section>
    <section class="panel">
      <header class="panel-head"><h2>Mapped-line evidence tape</h2><p>accepted support before later receiver tail</p></header>
      <div class="tape-wrap"><table><thead><tr><th>Seq</th><th>Phase</th><th>Observed</th><th>Direct fact</th><th>Authority</th></tr></thead><tbody id="evidence-tape"></tbody></table></div>
    </section>
    <aside class="panel">
      <header class="panel-head"><h2>Lifecycle & artifacts</h2><p>fail-closed inputs</p></header>
      <div class="body-pad"><div id="lifecycle"></div><ul id="artifacts" class="artifact-list"></ul></div>
    </aside>
  </section>
  <p id="footer" class="footer">Passive loopback desk.</p>
</main>
<script>
const NS = "http://www.w3.org/2000/svg";
const desk = { snapshot: null, selectedPhaseId: null, selectedBoundaryId: null };

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

function svgElement(tag, attributes = {}, text) {
  const node = document.createElementNS(NS, tag);
  Object.entries(attributes).forEach(([name, value]) => node.setAttribute(name, String(value)));
  if (text !== undefined) node.textContent = String(text);
  return node;
}

function replace(id, ...children) {
  document.getElementById(id).replaceChildren(...children);
}

function setText(id, value) {
  document.getElementById(id).textContent = String(value);
}

function factGrid(items) {
  const grid = element("dl", "fact-grid");
  items.forEach(([term, value]) => {
    grid.append(element("dt", "", term));
    grid.append(element("dd", "", value === null || value === undefined || value === "" ? "—" : value));
  });
  return grid;
}

function phasePercent(sequence, phases) {
  const span = Math.max(1, phases.last_sequence - phases.first_sequence);
  return ((sequence - phases.first_sequence) / span) * 100;
}

function renderPhase(snapshot) {
  const phases = snapshot.phases;
  const track = document.getElementById("phase-track");
  [...track.querySelectorAll("button")].forEach((button) => button.remove());
  const support = phases.accepted_support_sequences;
  const supportStart = phasePercent(Math.min(...support), phases);
  const supportEnd = phasePercent(Math.max(...support), phases);
  const tailStart = phasePercent(phases.post_support_starts_after, phases);
  const supportSpan = document.getElementById("support-span");
  supportSpan.style.left = `${supportStart}%`;
  supportSpan.style.width = `${Math.max(1.2, supportEnd - supportStart)}%`;
  const tailSpan = document.getElementById("tail-span");
  tailSpan.style.left = `${tailStart}%`;
  tailSpan.style.width = `${Math.max(0, 100 - tailStart)}%`;
  if (!desk.selectedPhaseId) desk.selectedPhaseId = "accepted-support-2";
  phases.markers.forEach((marker) => {
    const position = phasePercent(marker.sequence, phases);
    const edge = position <= 1 ? "edge-start" : position >= 99 ? "edge-end" : "";
    const button = element("button", `phase-marker ${marker.kind} ${edge}`);
    button.type = "button";
    button.style.left = `${position}%`;
    button.setAttribute("aria-pressed", String(marker.id === desk.selectedPhaseId));
    button.setAttribute("aria-label", `${marker.label}, sequence ${marker.sequence}, ${marker.authority}`);
    const label = element("span", "phase-label", marker.label);
    label.prepend(element("span", "phase-sequence", `SEQ ${marker.sequence}`));
    button.append(label);
    button.addEventListener("click", () => {
      desk.selectedPhaseId = marker.id;
      renderPhase(snapshot);
    });
    track.append(button);
  });
  const selected = track.querySelector('.phase-marker[aria-pressed="true"]');
  const scroller = document.querySelector(".phase-scroll");
  if (selected && scroller.scrollWidth > scroller.clientWidth) {
    scroller.scrollLeft = Math.max(0, selected.offsetLeft - scroller.clientWidth / 2);
  }
  renderPhaseInspector(snapshot);
}

function renderPhaseInspector(snapshot) {
  const marker = snapshot.phases.markers.find((item) => item.id === desk.selectedPhaseId) || snapshot.phases.markers[0];
  if (!marker) {
    replace("phase-inspector", element("span", "", "No historical phase marker."));
    return;
  }
  const event = snapshot.historical.evidence_tape.find((item) => item.sequence === marker.sequence);
  const first = element("div", "");
  first.append(element("span", "marker-kind", marker.kind.replaceAll("-", " ")));
  first.append(element("strong", "", marker.label));
  first.append(element("span", "", `sequence ${marker.sequence} · ${marker.observed_at}`));
  const second = element("div", "");
  second.append(element("strong", "", "Authority"));
  second.append(element("span", "", marker.authority));
  const third = element("div", "");
  third.append(element("strong", "", event ? `${event.subject} · ${event.state}` : "Phase boundary"));
  third.append(element("span", "", event ? `${event.id} · source IMP ${event.source.imp}` : snapshot.phases.note));
  replace("phase-inspector", first, second, third);
}

function renderJudgments(snapshot) {
  const application = snapshot.application;
  const journey = snapshot.journey.assessment;
  const accepted = snapshot.historical.accepted_line;
  const final = snapshot.historical.final_at_run_finish;
  setText("application-state", application.state);
  setText("application-summary", `${application.facts[0].label}: ${application.facts[0].value}; ${application.facts[3].label}: ${application.facts[3].value}.`);
  setText("application-authority", `Authority: ${application.authority}.`);
  setText("journey-state", journey.state);
  setText("journey-summary", `First unresolved ${journey.first_boundary_id}; application success does not fill it.`);
  setText("journey-authority", `Authority: ${journey.authority}.`);
  setText("line-state", `accepted ${accepted.state}`);
  setText("line-summary", `Verdict support ${accepted.supporting_sequences.join(" / ")}; run-finish tail reduces ${final.line.state}.`);
  setText("line-authority", `Accepted: ${accepted.authority}. Tail: ${final.line.authority}.`);
}

function point(position) {
  return { x: 100 + Number(position.x) * 280, y: 105 + Number(position.y) * 215 };
}

function mapLabel(component) {
  return ({
    "host:176": "Network UNIX 176",
    "host:106": "ITS 106",
    "imp:7": "IMP 7 · alternate",
    "host:ncc": "NCC receiver",
  })[component.id] || component.label;
}

function renderTopology(snapshot) {
  const topology = snapshot.topology;
  const svg = svgElement("svg", { class: "topology-map", viewBox: "0 0 1040 425", role: "img", "aria-label": "Configured seven-component application and NCC topology with accepted line support and later endpoint classifications" });
  const componentById = new Map(topology.components.map((item) => [item.id, item]));
  const endpointOwner = new Map();
  topology.components.forEach((component) => component.endpoints.forEach((endpoint) => endpointOwner.set(endpoint.id, component.id)));
  const finalEndpointByComponent = new Map(snapshot.historical.final_at_run_finish.endpoints.map((item) => [item.component_id, item]));
  topology.links.forEach((link) => {
    const firstId = endpointOwner.get(link.endpoints[0]);
    const secondId = endpointOwner.get(link.endpoints[1]);
    const first = point(componentById.get(firstId).position);
    const second = point(componentById.get(secondId).position);
    const lineClass = link.report_mapping ? "configured-link mapped-link" : "configured-link";
    svg.append(svgElement("line", { class: lineClass, x1: first.x, y1: first.y, x2: second.x, y2: second.y }));
    const midX = (first.x + second.x) / 2;
    const midY = (first.y + second.y) / 2;
    if (link.report_mapping) {
      const firstTail = finalEndpointByComponent.get(firstId);
      const secondTail = finalEndpointByComponent.get(secondId);
      const split = 34;
      const dx = second.x - first.x;
      const dy = second.y - first.y;
      const length = Math.max(1, Math.hypot(dx, dy));
      const ux = dx / length;
      const uy = dy / length;
      svg.append(svgElement("line", { class: `tail-half state-${firstTail?.state || "unknown"}`, x1: first.x, y1: first.y, x2: midX - ux * split, y2: midY - uy * split }));
      svg.append(svgElement("line", { class: `tail-half state-${secondTail?.state || "unknown"}`, x1: midX + ux * split, y1: midY + uy * split, x2: second.x, y2: second.y }));
      svg.append(svgElement("rect", { class: "accepted-plate", x: midX - 36, y: midY - 15, width: 72, height: 30, rx: 1 }));
      svg.append(svgElement("text", { class: "accepted-label", x: midX, y: midY + 3 }, "ACCEPTED UP"));
    } else {
      svg.append(svgElement("text", { class: "link-label", x: midX, y: midY - 9 }, link.id.replace("link:", "")));
    }
  });
  topology.components.forEach((component) => {
    const at = point(component.position);
    const group = svgElement("g", { class: `node ${component.kind}` });
    group.append(svgElement("title", {}, `${component.label} · ${component.id} · configured topology`));
    if (component.kind === "imp") {
      group.append(svgElement("circle", { class: "node-shape", cx: at.x, cy: at.y, r: 42 }));
    } else {
      group.append(svgElement("rect", { class: "node-shape", x: at.x - 74, y: at.y - 31, width: 148, height: 62, rx: 1 }));
    }
    group.append(svgElement("text", { x: at.x, y: at.y + 2 }, mapLabel(component)));
    group.append(svgElement("text", { class: "component-id", x: at.x, y: at.y + 18 }, component.id));
    svg.append(group);
  });
  replace("map", svg);
  setText("topology-id", `${topology.id} · ${topology.configured_only_link_ids.length} configured-only links`);
}

function renderAuthorities(snapshot) {
  const list = element("ul", "authority-list");
  snapshot.authority_legend.forEach((authority) => {
    const item = element("li", "");
    item.append(element("strong", "", authority.label));
    item.append(element("span", "", authority.meaning));
    list.append(item);
  });
  replace("authorities", list);
}

function sourceAuthority(boundary) {
  const classes = boundary.source_authority_classes;
  if (classes.includes("direct")) return "direct";
  if (classes.includes("harness-derived")) return "harness-derived";
  return "configured";
}

function renderJourneyRoute(snapshot) {
  const children = [];
  snapshot.journey.route.components.forEach((component, index) => {
    const node = element("div", `route-node ${component.kind}`, component.label);
    node.title = `${component.id} · configured shared topology`;
    children.push(node);
    const link = snapshot.journey.route.links[index];
    if (link) {
      const conductor = element("div", "route-conductor", link.id);
      conductor.title = link.authority;
      children.push(conductor);
    }
  });
  replace("journey-route", ...children);
}

function renderJourneyLane(id, boundaries, reverse) {
  const ordered = reverse ? [...boundaries].reverse() : boundaries;
  const buttons = ordered.map((boundary) => {
    const authority = sourceAuthority(boundary);
    const button = element("button", `boundary ${boundary.state} ${authority}`);
    button.type = "button";
    button.setAttribute("aria-pressed", String(boundary.id === desk.selectedBoundaryId));
    button.setAttribute("aria-label", `${boundary.id}, ${boundary.state}, ${boundary.component_label}, ${authority}`);
    const small = element("small", "");
    small.append(element("span", "", String(boundary.position).padStart(2, "0")));
    small.append(element("span", "", boundary.direction));
    button.append(small);
    button.append(element("strong", "", boundary.state));
    button.append(element("code", "", `${boundary.component_id} · ${boundary.interface_label}`));
    button.addEventListener("click", () => {
      desk.selectedBoundaryId = boundary.id;
      renderJourney(desk.snapshot);
    });
    return button;
  });
  replace(id, ...buttons);
}

function renderBoundaryInspector(snapshot) {
  const assessment = snapshot.journey.assessment;
  let boundary = assessment.boundaries.find((item) => item.id === desk.selectedBoundaryId);
  if (!boundary) {
    boundary = assessment.boundaries.find((item) => item.id === assessment.first_boundary_id) || assessment.boundaries[0];
    desk.selectedBoundaryId = boundary?.id || null;
  }
  if (!boundary) {
    replace("boundary-inspector", element("p", "", "No configured boundary."));
    return;
  }
  const observations = boundary.evidence_observation_ids.map((id) => snapshot.journey.observations.find((item) => item.id === id)).filter(Boolean);
  const container = element("div", "");
  container.append(element("span", "section-label", `${boundary.leg} crossing ${boundary.position}`));
  container.append(element("h3", "", boundary.state));
  container.append(element("p", "", `${boundary.component_label} · ${boundary.direction} through ${boundary.interface_label}`));
  container.append(factGrid([
    ["Boundary", boundary.id],
    ["State authority", boundary.state_authority],
    ["Source class", boundary.source_authority_classes.join(" + ") || "configured only"],
    ["Direct evidence", boundary.evidence_observation_ids.join(", ") || "none at this boundary"],
    ["Reducer context", boundary.context_supporting_observation_ids.join(", ") || "none"],
    ["Observation source", observations.map((item) => `${item.provenance.id} · local ${item.source_local_sequence}`).join("; ") || "not observed"],
  ]));
  replace("boundary-inspector", container);
}

function renderJourney(snapshot) {
  const boundaries = snapshot.journey.assessment.boundaries;
  if (!desk.selectedBoundaryId) {
    desk.selectedBoundaryId = snapshot.journey.assessment.first_boundary_id || boundaries[0]?.id || null;
  }
  renderJourneyRoute(snapshot);
  renderJourneyLane("request-lane", boundaries.filter((item) => item.leg === "request"), false);
  renderJourneyLane("reply-lane", boundaries.filter((item) => item.leg === "reply"), true);
  renderBoundaryInspector(snapshot);
  setText("journey-id", `${snapshot.journey.route.journey_id} · ${snapshot.journey.assessment.authority}`);
}

function renderReports(snapshot) {
  const counts = snapshot.historical.report_counts_by_source_imp;
  const rows = [5, 6, 7, 62].map((imp) => {
    const row = element("tr", "");
    [imp, counts.trouble[String(imp)], counts.throughput[String(imp)]].forEach((value) => row.append(element("td", "", value)));
    return row;
  });
  replace("report-counts", ...rows);
  const facts = factGrid(snapshot.application.facts.map((fact) => [fact.label, fact.value]));
  facts.style.marginTop = "14px";
  replace("application-facts", facts);
}

function renderTape(snapshot) {
  const rows = snapshot.historical.evidence_tape.map((event) => {
    const row = element("tr", `tape-row ${event.phase === "accepted-support" ? "support" : "tail"}`);
    const values = [event.sequence, event.phase.replaceAll("-", " "), event.observed_at, `${event.subject} · ${event.state} · neighbor ${event.details.neighbor_imp ?? "not retained"}`, event.phase === "accepted-support" ? "direct + reducer + verdict" : event.authority];
    values.forEach((value, index) => row.append(element("td", index === 3 && event.state === "down" ? "state-down-text" : "", value)));
    row.title = event.id;
    return row;
  });
  replace("evidence-tape", ...rows);
}

function renderLifecycle(snapshot) {
  const life = snapshot.lifecycle;
  const stamp = element("div", "lifecycle-stamp");
  stamp.append(element("strong", "", "Cleanup passed"));
  stamp.append(element("code", "", `${life.application_controller_exit_status} / ${life.receiver_exit_status}`));
  stamp.append(element("span", "", "surviving owned processes"));
  stamp.append(element("code", "", life.application_surviving_owned_processes));
  replace("lifecycle", stamp);
  const artifacts = snapshot.artifact_validation.artifacts.map((artifact) => {
    const item = element("li", "");
    item.append(element("strong", "", `${artifact.name} · ${artifact.kind}`));
    item.append(element("code", "", artifact.sha256 ? `sha256 ${artifact.sha256}` : "no manifest digest"));
    item.append(element("span", "", artifact.binding));
    return item;
  });
  replace("artifacts", ...artifacts);
}

function render(snapshot) {
  desk.snapshot = snapshot;
  setText("composition-state", snapshot.composition.state);
  setText("run-id", snapshot.run.id);
  setText("run-span", `${snapshot.run.started_at} → ${snapshot.run.finished_at}`);
  setText("revision", snapshot.run.repository_revision);
  setText("footer", snapshot.passive_boundary);
  renderPhase(snapshot);
  renderJudgments(snapshot);
  renderTopology(snapshot);
  renderAuthorities(snapshot);
  renderJourney(snapshot);
  renderReports(snapshot);
  renderTape(snapshot);
  renderLifecycle(snapshot);
  document.getElementById("error").hidden = true;
}

async function loadSnapshot() {
  try {
    const response = await fetch("/api/snapshot", { cache: "no-store", credentials: "same-origin" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `snapshot request failed (${response.status})`);
    render(payload);
  } catch (error) {
    const banner = document.getElementById("error");
    banner.textContent = `Validated coexistence desk unavailable: ${error.message}`;
    banner.hidden = false;
  }
}

loadSnapshot();
</script>
</body>
</html>
"""
