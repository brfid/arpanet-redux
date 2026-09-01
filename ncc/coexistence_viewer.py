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
  --desk: #5d594f;
  --cover: #aa8d4d;
  --cover-deep: #7e662f;
  --paper: #f1efe4;
  --paper-2: #e5e1d1;
  --ink: #27251f;
  --graphite: #686258;
  --faint: #b9b1a0;
  --observed: #42666a;
  --verdict: #8b632b;
  --tail: #91483f;
  --binding: #171611;
  --display: "Helvetica Neue", Helvetica, Arial, sans-serif;
  --mono: "Courier New", Courier, ui-monospace, monospace;
}
* { box-sizing: border-box; }
html { background: var(--desk); color-scheme: light; }
body {
  background:
    linear-gradient(90deg, rgba(255, 255, 255, .035), transparent 24%, transparent 76%, rgba(0, 0, 0, .05)),
    var(--desk);
  color: var(--ink);
  font: 14px/1.5 var(--mono);
  margin: 0;
}
button { color: inherit; font: inherit; }
code, time, .mono { font-family: var(--mono); }
.desk {
  background:
    linear-gradient(90deg, rgba(39, 37, 31, .018) 1px, transparent 1px),
    var(--paper);
  background-size: 34px 100%;
  box-shadow: 0 22px 55px rgba(20, 18, 14, .34);
  margin: 34px auto;
  max-width: 1500px;
  min-height: calc(100vh - 68px);
  padding: 0 42px 30px 62px;
  position: relative;
}
.desk::before {
  background: repeating-linear-gradient(
    to bottom,
    transparent 0 10px,
    var(--binding) 10px 27px,
    transparent 27px 39px
  );
  bottom: 24px;
  content: "";
  left: -15px;
  position: absolute;
  top: 24px;
  width: 34px;
  z-index: 4;
}
.desk::after {
  border-left: 1px solid rgba(39, 37, 31, .22);
  bottom: 0;
  content: "";
  left: 28px;
  position: absolute;
  top: 0;
}
.masthead {
  background: var(--cover);
  border-bottom: 1px solid var(--cover-deep);
  margin: 0 -42px 0 -62px;
  min-height: 246px;
  padding: 26px 54px 28px 74px;
  position: relative;
  text-align: center;
}
.cover-title { margin: 0 auto; max-width: 800px; }
.eyebrow, .section-label, dt, th, .chip, .marker-kind {
  font: 700 10px/1.2 var(--mono);
  letter-spacing: .08em;
  text-transform: uppercase;
}
.eyebrow {
  display: flex;
  justify-content: space-between;
  margin: 0 0 22px;
  text-align: left;
}
.cover-kicker {
  font: 700 clamp(18px, 2.2vw, 29px)/1 var(--display);
  letter-spacing: .13em;
  margin: 0;
  text-transform: uppercase;
}
.cover-for {
  font: 600 15px/1 var(--display);
  letter-spacing: .08em;
  margin: 13px 0 8px;
}
h1 {
  font: 700 clamp(33px, 4.7vw, 62px)/.95 var(--display);
  letter-spacing: .15em;
  margin: 0;
  text-indent: .15em;
  text-transform: uppercase;
}
.cover-subject {
  border-top: 1px solid rgba(39, 37, 31, .45);
  display: inline-block;
  font: 700 13px/1.3 var(--mono);
  letter-spacing: .08em;
  margin: 18px 0 0;
  padding-top: 9px;
  text-transform: uppercase;
}
.outcome-seal {
  border: 3px double var(--ink);
  color: var(--ink);
  min-width: 154px;
  padding: 8px 10px;
  position: absolute;
  right: 40px;
  text-align: center;
  top: 56px;
  transform: rotate(-.6deg);
}
.outcome-seal span { display: block; font: 700 9px var(--mono); letter-spacing: .08em; text-transform: uppercase; }
.outcome-seal strong { display: block; font: 700 22px/1 var(--display); letter-spacing: .08em; margin-top: 5px; text-transform: uppercase; }
.status-strip {
  border-bottom: 3px double var(--ink);
  display: grid;
  grid-template-columns: 1.5fr 1fr 1fr 1.25fr;
}
.status-cell {
  border-right: 1px dotted var(--graphite);
  min-width: 0;
  padding: 14px 12px 13px;
}
.status-cell:last-child { border-right: 0; }
.status-cell span { color: var(--graphite); display: block; font: 700 9px var(--mono); letter-spacing: .07em; margin-bottom: 5px; text-transform: uppercase; }
.status-cell strong { display: block; font: 700 10px/1.45 var(--mono); overflow-wrap: anywhere; }
.error { border: 3px double var(--tail); color: var(--tail); margin-top: 18px; padding: 12px 14px; }
.error[hidden] { display: none; }
.panel { color: var(--ink); min-width: 0; }
.panel-head {
  align-items: baseline;
  border-bottom: 1px dashed var(--graphite);
  border-top: 1px solid var(--ink);
  display: flex;
  gap: 18px;
  justify-content: space-between;
  padding: 12px 8px 10px;
}
.panel-head h2 { font: 700 14px/1.1 var(--mono); letter-spacing: .06em; margin: 0; text-transform: uppercase; }
.panel-head p { color: var(--graphite); font: italic 11px/1.4 var(--mono); margin: 0; text-align: right; }
.phase-panel { border-bottom: 1px solid var(--ink); margin-top: 22px; }
.phase-scroll { overflow-x: auto; padding: 18px 8px 6px; }
.phase-stage { min-width: 980px; padding: 48px 24px 58px; position: relative; }
.phase-track { border-top: 2px dashed var(--graphite); height: 0; position: relative; }
.phase-support-span, .phase-tail-span { height: 5px; position: absolute; top: -3px; }
.phase-support-span { background: var(--verdict); }
.phase-tail-span { background: repeating-linear-gradient(90deg, rgba(145, 72, 63, .25) 0 8px, var(--tail) 8px 12px); }
.phase-marker { background: transparent; border: 0; cursor: pointer; height: 52px; margin-left: -18px; padding: 0; position: absolute; top: -27px; width: 36px; }
.phase-marker::before {
  background: var(--paper);
  border: 2px solid var(--graphite);
  content: "";
  display: block;
  height: 17px;
  margin: 17px auto 0;
  width: 17px;
}
.phase-marker.accepted-support::before { background: var(--cover); border-color: var(--verdict); }
.phase-marker.receiver-tail::before { border-color: var(--tail); }
.phase-marker[aria-pressed="true"]::before { box-shadow: 0 0 0 3px var(--paper), 0 0 0 5px var(--ink); }
.phase-marker:focus-visible, .boundary:focus-visible { outline: 3px double var(--observed); outline-offset: 5px; }
.phase-label { color: var(--ink); font: 9px/1.3 var(--mono); left: 50%; min-width: 138px; position: absolute; text-align: center; top: 49px; transform: translateX(-50%); }
.phase-marker:nth-child(even) .phase-label { bottom: 49px; top: auto; }
.phase-marker.edge-start { margin-left: 0; }
.phase-marker.edge-start .phase-label { left: 0; text-align: left; transform: none; }
.phase-marker.edge-end { margin-left: -36px; }
.phase-marker.edge-end .phase-label { left: auto; right: 0; text-align: right; transform: none; }
.phase-sequence { color: var(--verdict); display: block; font-weight: 800; }
.phase-inspector { border-top: 1px dashed var(--graphite); display: grid; gap: 12px 30px; grid-template-columns: 1.2fr 1fr 1fr; padding: 14px 8px 16px; }
.phase-inspector > div + div { border-left: 1px dotted var(--graphite); padding-left: 18px; }
.phase-inspector strong { display: block; font: 700 12px/1.35 var(--mono); text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px; text-transform: uppercase; }
.phase-inspector span { color: var(--graphite); display: block; font: 9px/1.5 var(--mono); margin-top: 4px; overflow-wrap: anywhere; }
.judgment-ledger {
  border-bottom: 3px double var(--ink);
  border-top: 3px double var(--ink);
  counter-reset: result;
  margin-top: 22px;
}
.manual-heading {
  font: 700 14px/1 var(--mono);
  letter-spacing: .08em;
  margin: 28px 0 -10px;
  text-align: center;
  text-transform: uppercase;
}
.judgment {
  align-items: baseline;
  border-bottom: 1px dotted var(--graphite);
  counter-increment: result;
  display: grid;
  gap: 5px 18px;
  grid-template-columns: 30px 150px 210px minmax(0, 1fr);
  min-height: 0;
  padding: 12px 8px;
}
.judgment:last-child { border-bottom: 0; }
.judgment::before { content: counter(result) "."; font-weight: 700; grid-column: 1; grid-row: 1 / span 2; }
.judgment .section-label { color: var(--graphite); grid-column: 2; margin: 0; }
.judgment h2 { font: 700 19px/1 var(--mono); grid-column: 3; margin: 0; text-transform: uppercase; }
.judgment.application h2 { color: var(--observed); }
.judgment.journey h2 { color: var(--tail); }
.judgment.line h2 { color: var(--verdict); }
.judgment p { grid-column: 4; margin: 0; }
.judgment .authority { color: var(--graphite); font: italic 9px/1.45 var(--mono); grid-column: 4; margin: 0; }
.main-grid { display: grid; gap: 28px; grid-template-columns: minmax(0, 1.65fr) minmax(300px, .65fr); margin-top: 28px; }
.main-grid > aside { border-left: 3px double var(--ink); padding-left: 22px; }
.map-wrap { overflow-x: auto; padding: 12px 4px 3px; }
.topology-map { display: block; min-width: 760px; width: 100%; }
.topology-map .configured-link { stroke: var(--graphite); stroke-dasharray: 7 7; stroke-width: 2; }
.topology-map .mapped-link { stroke: var(--verdict); stroke-dasharray: 3 5; stroke-width: 4; }
.topology-map .tail-half { stroke-width: 5; }
.topology-map .tail-half.state-down { stroke: var(--tail); }
.topology-map .tail-half.state-stale { stroke: var(--graphite); stroke-dasharray: 4 5; }
.topology-map .tail-half.state-up { stroke: var(--observed); }
.topology-map .tail-half.state-unknown { stroke: var(--faint); stroke-dasharray: 3 6; }
.topology-map .node-shape { fill: var(--paper); stroke: var(--ink); stroke-width: 2; }
.topology-map .observer .node-shape { fill: var(--paper); stroke: var(--observed); stroke-width: 4; }
.topology-map .observer text { fill: var(--ink); }
.topology-map text { fill: var(--ink); font: 700 12px var(--mono); pointer-events: none; text-anchor: middle; }
.topology-map .component-id { fill: var(--graphite); font: 9px var(--mono); }
.topology-map .observer .component-id { fill: var(--observed); }
.topology-map .link-label { fill: var(--graphite); font: 8px var(--mono); }
.topology-map .accepted-plate { fill: var(--paper); stroke: var(--verdict); stroke-width: 3; }
.topology-map .accepted-label { fill: var(--verdict); font: 700 9px var(--mono); letter-spacing: .03em; }
.map-caption { border-top: 1px dashed var(--graphite); color: var(--graphite); display: flex; flex-wrap: wrap; font: italic 10px/1.5 var(--mono); gap: 10px 22px; margin: 0; padding: 11px 8px 0; }
.authority-body { padding: 4px 8px 0; }
.authority-list { list-style: none; margin: 0; padding: 0; }
.authority-list li { border-bottom: 1px dotted var(--graphite); padding: 10px 0; }
.authority-list strong { display: block; font: 700 10px var(--mono); letter-spacing: .04em; text-decoration: underline; text-underline-offset: 3px; text-transform: uppercase; }
.authority-list span { color: var(--graphite); display: block; font: italic 9px/1.5 var(--mono); margin-top: 4px; }
.journey-panel { margin-top: 30px; }
.journey-route { align-items: center; border-bottom: 1px dashed var(--graphite); display: flex; gap: 8px; overflow-x: auto; padding: 14px 8px; }
.journey-route .route-node { border: 1px solid var(--ink); flex: 0 0 auto; font: 700 9px/1.25 var(--mono); min-width: 120px; padding: 8px 10px; text-align: center; text-transform: uppercase; }
.journey-route .route-node.imp { border-radius: 50%; min-width: 78px; padding: 26px 7px; }
.journey-route .route-conductor { color: var(--graphite); flex: 1 0 70px; font: 8px/1.2 var(--mono); text-align: center; }
.journey-route .route-conductor::before { border-top: 1px dotted var(--graphite); content: ""; display: block; margin-bottom: 4px; }
.journey-body { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(280px, .55fr); }
.journey-body > * { min-width: 0; }
.journey-lanes { border-right: 1px dashed var(--graphite); min-width: 0; padding: 16px 16px 16px 8px; }
.lane + .lane { margin-top: 13px; }
.lane-head { align-items: baseline; display: flex; justify-content: space-between; margin-bottom: 6px; }
.lane-head strong { font: 700 12px var(--mono); letter-spacing: .06em; text-decoration: underline; text-underline-offset: 3px; text-transform: uppercase; }
.lane-head span { color: var(--graphite); font: italic 9px var(--mono); }
.boundary-grid { display: grid; gap: 6px; grid-template-columns: repeat(6, minmax(112px, 1fr)); min-width: 720px; }
.boundary-scroll { max-width: 100%; min-width: 0; overflow-x: auto; }
.boundary { background: transparent; border: 1px solid var(--graphite); border-top-width: 4px; cursor: pointer; min-height: 88px; padding: 7px 8px; text-align: left; }
.boundary.observed.direct { background: rgba(66, 102, 106, .07); border-color: var(--observed); }
.boundary.observed.harness-derived { background: rgba(170, 141, 77, .13); border-color: var(--verdict); }
.boundary.missing { border-color: var(--tail); border-style: dashed; color: var(--tail); }
.boundary[aria-pressed="true"] { box-shadow: inset 0 0 0 2px var(--paper), inset 0 0 0 4px var(--ink); }
.boundary small { display: flex; font: 700 8px var(--mono); justify-content: space-between; letter-spacing: .05em; text-transform: uppercase; }
.boundary strong { display: block; font: 700 14px/1 var(--mono); margin: 10px 0 7px; text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px; text-transform: uppercase; }
.boundary code { display: block; font-size: 8px; overflow-wrap: anywhere; }
.boundary-inspector { padding: 16px; }
.boundary-inspector h3 { font: 700 23px/1 var(--mono); margin: 8px 0; text-decoration: underline; text-underline-offset: 4px; text-transform: uppercase; }
.boundary-inspector p { color: var(--graphite); font-style: italic; margin: 0 0 11px; }
.fact-grid { display: grid; grid-template-columns: 100px minmax(0, 1fr); margin: 0; }
.fact-grid dt, .fact-grid dd { border-top: 1px dotted var(--graphite); margin: 0; padding: 6px 0; }
.fact-grid dd { font: 9px/1.45 var(--mono); overflow-wrap: anywhere; }
.lower-grid { display: grid; gap: 28px; grid-template-columns: .72fr 1.25fr .9fr; margin-top: 30px; }
.lower-grid > * + * { border-left: 1px dotted var(--graphite); padding-left: 22px; }
.body-pad { padding: 12px 8px 0; }
table { border-collapse: collapse; font: 9px/1.4 var(--mono); width: 100%; }
th { background: var(--paper); color: var(--graphite); position: sticky; text-align: left; top: 0; }
th, td { border-bottom: 1px dotted var(--graphite); padding: 8px 9px; vertical-align: top; }
th { border-bottom: 2px dashed var(--ink); }
td:first-child { color: var(--observed); font-weight: 700; }
.tape-wrap { max-height: 430px; overflow: auto; }
.tape-row.support td { background: rgba(170, 141, 77, .12); }
.tape-row.tail td:first-child, .state-down-text { color: var(--tail); }
.report-matrix td:not(:first-child), .report-matrix th:not(:first-child) { text-align: right; }
.report-matrix td { font-size: 12px; }
.lifecycle-stamp { border: 3px double var(--observed); display: grid; gap: 6px; grid-template-columns: 1fr auto; margin-bottom: 13px; padding: 10px; }
.lifecycle-stamp strong { color: var(--observed); font: 700 15px var(--mono); text-transform: uppercase; }
.lifecycle-stamp code { font-size: 10px; }
.artifact-list { list-style: none; margin: 0; padding: 0; }
.artifact-list li { border-top: 1px dotted var(--graphite); padding: 8px 0; }
.artifact-list strong, .artifact-list code, .artifact-list span { display: block; overflow-wrap: anywhere; }
.artifact-list strong { font: 700 9px var(--mono); letter-spacing: .03em; text-decoration: underline; text-underline-offset: 3px; text-transform: uppercase; }
.artifact-list code { color: var(--graphite); font-size: 8px; margin-top: 3px; }
.artifact-list span { color: var(--graphite); font-size: 9px; margin-top: 2px; }
.footer {
  border-top: 3px double var(--ink);
  color: var(--graphite);
  display: grid;
  font: 9px/1.5 var(--mono);
  gap: 14px;
  grid-template-columns: 1fr auto 1fr;
  margin-top: 30px;
  padding: 14px 2px 0;
}
.footer .folio-number { color: var(--ink); font-weight: 700; text-align: center; }
.footer .source-note { font-style: italic; text-align: right; }
@media (max-width: 1100px) {
  .main-grid, .lower-grid { grid-template-columns: 1fr; }
  .main-grid > aside, .lower-grid > * + * { border-left: 0; padding-left: 0; }
  .journey-body { grid-template-columns: 1fr; }
  .journey-lanes { border-bottom: 1px dashed var(--graphite); border-right: 0; padding-right: 8px; }
}
@media (max-width: 720px) {
  .desk { margin: 12px; min-height: calc(100vh - 24px); padding: 0 16px 24px 38px; }
  .desk::before { left: -11px; width: 26px; }
  .desk::after { left: 21px; }
  .masthead { margin: 0 -16px 0 -38px; min-height: 0; padding: 22px 20px 24px 44px; }
  .eyebrow { display: block; line-height: 1.5; }
  .eyebrow span { display: block; }
  .outcome-seal { margin: 19px auto 0; position: static; width: 154px; }
  .status-strip { grid-template-columns: 1fr 1fr; }
  .status-cell:nth-child(2) { border-right: 0; }
  .status-cell:nth-child(-n+2) { border-bottom: 1px dotted var(--graphite); }
  .phase-inspector { grid-template-columns: 1fr; }
  .phase-inspector > div + div { border-left: 0; border-top: 1px dotted var(--graphite); padding-left: 0; padding-top: 9px; }
  .judgment { align-items: start; gap: 5px 10px; grid-template-columns: 25px minmax(0, 1fr); }
  .judgment::before { grid-column: 1; }
  .judgment .section-label, .judgment h2, .judgment p, .judgment .authority { grid-column: 2; }
  .footer { grid-template-columns: 1fr; }
  .footer .folio-number, .footer .source-note { text-align: left; }
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
    <div class="cover-title">
      <p class="eyebrow"><span>ARPANET Redux</span><span>Observation folio NCC / 01</span></p>
      <p class="cover-kicker">Scenarios</p>
      <p class="cover-for">for diagnosing the</p>
      <h1>ARPANET</h1>
      <p class="cover-subject">NCC coexistence desk · completed result</p>
    </div>
    <div class="outcome-seal"><span>Composition verdict</span><strong id="composition-state">validating</strong></div>
  </header>
  <section class="status-strip" aria-label="Completed run identity">
    <div class="status-cell"><span>Run identification</span><strong id="run-id">waiting for validated artifacts</strong></div>
    <div class="status-cell"><span>Observation span</span><strong id="run-span">—</strong></div>
    <div class="status-cell"><span>Source revision</span><strong id="revision">—</strong></div>
    <div class="status-cell"><span>Observation boundary</span><strong>read-only · structured artifacts only</strong></div>
  </section>
  <div id="error" class="error" role="alert" hidden></div>

  <section class="phase-panel" aria-labelledby="phase-heading">
    <header class="panel-head"><h2 id="phase-heading">Scenario register / evidence phase rail</h2><p>historical-event sequence · never a shared simulator clock</p></header>
    <div class="phase-scroll"><div class="phase-stage"><div id="phase-track" class="phase-track"><div id="support-span" class="phase-support-span"></div><div id="tail-span" class="phase-tail-span"></div></div></div></div>
    <div id="phase-inspector" class="phase-inspector" aria-live="polite"></div>
  </section>

  <h2 class="manual-heading">Result summary</h2>
  <section class="judgment-ledger" aria-label="Independent evidence conclusions">
    <article class="judgment application"><p class="section-label">Application plane</p><h2 id="application-state">—</h2><p id="application-summary">Awaiting Gate 4H evidence.</p><p id="application-authority" class="authority"></p></article>
    <article class="judgment journey"><p class="section-label">Typed journey</p><h2 id="journey-state">—</h2><p id="journey-summary">Awaiting reducer diagnosis.</p><p id="journey-authority" class="authority"></p></article>
    <article class="judgment line"><p class="section-label">Mapped direct line</p><h2 id="line-state">—</h2><p id="line-summary">Awaiting composition support.</p><p id="line-authority" class="authority"></p></article>
  </section>

  <section class="main-grid">
    <section class="panel">
      <header class="panel-head"><h2>Configured network arrangement</h2><p id="topology-id">waiting for shared topology</p></header>
      <div id="map" class="map-wrap"></div>
      <p class="map-caption"><span><strong>Dashed:</strong> configured link only.</span><span><strong>Ochre box:</strong> accepted reciprocal support.</span><span><strong>Red / graphite halves:</strong> run-finish endpoint classification.</span><span>Neither route configuration nor application success assigns historical traffic to a link.</span></p>
    </section>
    <aside class="panel">
      <header class="panel-head"><h2>Interpretation conventions</h2><p>keep evidence planes separate</p></header>
      <div id="authorities" class="authority-body"></div>
    </aside>
  </section>

  <section class="panel journey-panel">
    <header class="panel-head"><h2>Scenario procedure: typed application journey</h2><p id="journey-id">twelve configured crossings · ten typed observations</p></header>
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
      <header class="panel-head"><h2>NCC report survey</h2><p>direct stream = verdict counts</p></header>
      <div class="body-pad"><table class="report-matrix"><thead><tr><th>Source IMP</th><th>Type 303</th><th>Type 302</th></tr></thead><tbody id="report-counts"></tbody></table><div id="application-facts"></div></div>
    </section>
    <section class="panel">
      <header class="panel-head"><h2>Mapped-line change record</h2><p>accepted support before later receiver tail</p></header>
      <div class="tape-wrap"><table><thead><tr><th>Seq</th><th>Phase</th><th>Observed</th><th>Direct fact</th><th>Authority</th></tr></thead><tbody id="evidence-tape"></tbody></table></div>
    </section>
    <aside class="panel">
      <header class="panel-head"><h2>Lifecycle & reference files</h2><p>fail-closed inputs</p></header>
      <div class="body-pad"><div id="lifecycle"></div><ul id="artifacts" class="artifact-list"></ul></div>
    </aside>
  </section>
  <footer class="footer">
    <span id="footer">Passive loopback desk.</span>
    <span class="folio-number">1</span>
    <span class="source-note">Presentation grammar after SRI / NIC 11863 (1972); no source scan assets embedded.</span>
  </footer>
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
