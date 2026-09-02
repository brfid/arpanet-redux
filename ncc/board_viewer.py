"""Render the single passive NCC operator console."""

from __future__ import annotations

from html import escape
import json

from .shared_topology import SharedTopology


def render_ncc_board_html(shared: SharedTopology) -> str:
    """Return one historically grounded, presentation-only operator console."""

    config = _operator_config(shared)
    encoded_config = json.dumps(config, separators=(",", ":"), sort_keys=True)
    encoded_config = encoded_config.replace("<", "\\u003c").replace(">", "\\u003e")
    return (
        _PAGE_TEMPLATE.replace("__TOPOLOGY_ID__", _text(shared.id))
        .replace("__OPERATOR_CONFIG__", encoded_config)
        .replace("__LAMP_BUTTONS__", _lamp_buttons())
    )


def _operator_config(shared: SharedTopology) -> dict[str, object]:
    imps = []
    for component in shared.topology["components"]:
        if component["kind"] != "imp":
            continue
        identifier = str(component["id"])
        slot = int(identifier.split(":", 1)[1])
        if not 1 <= slot <= 64:
            raise ValueError(
                f"NCC console cannot place {identifier!r} outside positions 1..64"
            )
        imps.append(
            {
                "slot": slot,
                "id": identifier,
                "label": str(component["label"]),
            }
        )
    return {"topology_id": shared.id, "imps": imps}


def _lamp_buttons() -> str:
    return "".join(
        f'<button class="lamp is-dark" type="button" data-slot="{slot}" '
        f'aria-label="Position {slot}, no observation"><i aria-hidden="true"></i>'
        f'<span>{slot:02d}</span></button>'
        for slot in range(1, 65)
    )


def _text(value: object) -> str:
    return escape(str(value))


_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ARPANET Redux · NCC operator console</title>
<style>
:root {
  --room: #c9c3ae;
  --cabinet: #535642;
  --cabinet-dark: #393c2f;
  --bezel: #20231d;
  --engraving: #ede5c9;
  --muted: #b8b194;
  --paper: #e9e3cb;
  --paper-ink: #28291f;
  --lamp-off: #171914;
  --lamp-good: #e3ad3c;
  --lamp-warn: #e0712e;
  --lamp-fault: #c93626;
  --lamp-special: #d6d0a6;
  --display: "DIN Condensed", "Avenir Next Condensed", "Arial Narrow", sans-serif;
  --mono: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--room); color: var(--engraving); font: 14px/1.4 var(--mono); }
button { font: inherit; }
button:focus-visible { outline: 3px solid var(--paper); outline-offset: 3px; }
.console { background: var(--cabinet); border: 10px solid var(--cabinet-dark); box-shadow: 0 10px 34px rgba(31, 31, 23, .28); margin: 22px auto; max-width: 1460px; min-height: calc(100vh - 44px); padding: 18px; }
.nameplate { align-items: end; border-bottom: 2px solid var(--muted); display: flex; gap: 26px; justify-content: space-between; padding: 0 2px 14px; }
.nameplate h1 { font: 800 30px/1 var(--display); letter-spacing: .08em; margin: 0; text-transform: uppercase; }
.nameplate p { color: var(--muted); font: 700 10px/1.5 var(--mono); letter-spacing: .08em; margin: 5px 0 0; text-transform: uppercase; }
.profile { max-width: 520px; text-align: right; }
.profile strong { display: block; font: 800 13px/1.3 var(--display); letter-spacing: .08em; text-transform: uppercase; }
.profile span { color: var(--muted); display: block; font-size: 9px; margin-top: 3px; }
.alarm-rack { align-items: center; border-bottom: 2px solid var(--muted); display: grid; gap: 14px; grid-template-columns: auto minmax(0, 1fr) auto; padding: 12px 2px; }
.alarm-lamp { background: var(--lamp-off); border: 3px solid var(--bezel); border-radius: 50%; box-shadow: inset 0 0 7px #000; height: 25px; width: 25px; }
.alarm-lamp.active { animation: alarm-flash 1s steps(1, end) infinite; background: var(--lamp-fault); box-shadow: 0 0 14px rgba(201, 54, 38, .9), inset 0 0 4px #fff; }
.alarm-lamp.active.warning { background: var(--lamp-warn); box-shadow: 0 0 14px rgba(224, 113, 46, .9), inset 0 0 4px #fff; }
.alarm-copy { min-width: 0; }
.alarm-copy strong { display: block; font: 800 14px/1.2 var(--display); letter-spacing: .12em; text-transform: uppercase; }
.alarm-copy span { color: var(--muted); display: block; font-size: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ack { background: var(--paper); border: 3px solid var(--bezel); color: var(--paper-ink); cursor: pointer; font: 800 11px/1 var(--display); letter-spacing: .09em; padding: 9px 13px; text-transform: uppercase; }
.ack:disabled { cursor: default; opacity: .45; }
.hardware { display: grid; gap: 18px; grid-template-columns: 180px minmax(520px, 1fr) 310px; padding: 18px 0; }
.bank-panel, .inspector { border: 2px solid var(--muted); padding: 13px; }
.panel-label { color: var(--muted); font: 800 10px/1 var(--display); letter-spacing: .13em; margin: 0 0 11px; text-transform: uppercase; }
.bank-controls { display: grid; gap: 7px; }
.bank { background: var(--cabinet-dark); border: 2px solid var(--bezel); color: var(--engraving); cursor: pointer; font: 800 11px/1.15 var(--display); letter-spacing: .08em; min-height: 43px; padding: 7px 9px; text-align: left; text-transform: uppercase; }
.bank[aria-pressed="true"] { background: var(--paper); color: var(--paper-ink); }
.bank small { display: block; font: 8px/1.2 var(--mono); letter-spacing: .03em; margin-top: 3px; opacity: .7; }
.bank-note { color: var(--muted); font-size: 9px; margin: 12px 0 0; }
.annunciator { background: var(--bezel); border: 8px solid var(--cabinet-dark); padding: 14px; }
.annunciator-head { align-items: baseline; display: flex; gap: 12px; justify-content: space-between; margin: 0 0 12px; }
.annunciator-head strong { font: 800 16px/1 var(--display); letter-spacing: .1em; text-transform: uppercase; }
.annunciator-head span { color: var(--muted); font-size: 9px; text-align: right; }
.lamp-grid { display: grid; gap: 10px 12px; grid-template-columns: repeat(8, minmax(42px, 1fr)); }
.lamp { background: transparent; border: 0; color: var(--muted); cursor: pointer; min-width: 0; padding: 0; }
.lamp i { background: var(--lamp-off); border: 3px solid #080906; border-radius: 50%; box-shadow: inset 0 0 9px #000; display: block; height: 26px; margin: 0 auto 4px; width: 26px; }
.lamp span { font: 9px/1 var(--mono); }
.lamp.is-good i { background: var(--lamp-good); box-shadow: 0 0 10px rgba(227, 173, 60, .72), inset 0 0 4px #fff4c7; }
.lamp.is-warn i { background: var(--lamp-warn); box-shadow: 0 0 11px rgba(224, 113, 46, .8), inset 0 0 4px #ffe0be; }
.lamp.is-fault i { background: var(--lamp-fault); box-shadow: 0 0 13px rgba(201, 54, 38, .9), inset 0 0 4px #ffd0c8; }
.lamp.is-special i { background: var(--lamp-special); box-shadow: 0 0 10px rgba(214, 208, 166, .7), inset 0 0 4px #fff; }
.lamp.is-dark { cursor: default; opacity: .48; }
.lamp.is-selected span { color: var(--paper); text-decoration: underline; text-underline-offset: 3px; }
.lamp.is-pulse i { animation: report-pulse .7s ease-out; }
.inspector dl { margin: 0; }
.inspector div { border-top: 1px solid rgba(233, 227, 203, .25); padding: 8px 0; }
.inspector div:first-child { border-top: 0; padding-top: 0; }
.inspector dt { color: var(--muted); font: 800 9px/1.2 var(--display); letter-spacing: .1em; text-transform: uppercase; }
.inspector dd { margin: 3px 0 0; overflow-wrap: anywhere; }
.inspector .state { font: 800 20px/1 var(--display); letter-spacing: .05em; text-transform: uppercase; }
.evidence { color: var(--muted); font-size: 10px; }
.run-strip { background: var(--cabinet-dark); border: 2px solid var(--bezel); display: grid; grid-template-columns: 1.4fr repeat(3, 1fr); }
.run-cell { border-right: 1px solid var(--muted); min-width: 0; padding: 9px 11px; }
.run-cell:last-child { border-right: 0; }
.run-cell span { color: var(--muted); display: block; font: 800 8px/1.2 var(--display); letter-spacing: .1em; text-transform: uppercase; }
.run-cell strong { display: block; font-size: 10px; margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.paperwork { background: var(--paper); border: 6px solid var(--cabinet-dark); color: var(--paper-ink); display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(280px, .7fr); margin-top: 18px; }
.log, .quick { min-width: 0; padding: 16px; }
.quick { border-left: 2px solid var(--paper-ink); }
.paperwork h2 { font: 800 18px/1 var(--display); letter-spacing: .09em; margin: 0 0 12px; text-transform: uppercase; }
.log table { border-collapse: collapse; table-layout: fixed; width: 100%; }
.log th { border-bottom: 2px solid var(--paper-ink); font: 800 9px/1.2 var(--display); letter-spacing: .08em; padding: 5px 7px; text-align: left; text-transform: uppercase; }
.log td { border-bottom: 1px solid rgba(40, 41, 31, .24); font-size: 10px; overflow-wrap: anywhere; padding: 7px; vertical-align: top; }
.log th:first-child, .log td:first-child { width: 52px; }
.log th:nth-child(2), .log td:nth-child(2) { width: 150px; }
.empty { color: #706f5e; }
.quick dl { margin: 0; }
.quick div { border-top: 1px solid rgba(40, 41, 31, .35); padding: 8px 0; }
.quick div:first-child { border-top: 2px solid var(--paper-ink); }
.quick dt { font: 800 9px/1.2 var(--display); letter-spacing: .08em; text-transform: uppercase; }
.quick dd { font-size: 11px; margin: 3px 0 0; overflow-wrap: anywhere; }
.boundary { color: var(--muted); font-size: 9px; margin: 13px 0 0; }
.error { background: #f0c9bd; border: 3px solid var(--lamp-fault); color: #641c13; margin: 14px 0 0; padding: 9px 12px; }
.error[hidden] { display: none; }
@keyframes alarm-flash { 50% { background: var(--lamp-off); box-shadow: inset 0 0 7px #000; } }
@keyframes report-pulse { 45% { transform: scale(1.22); } }
@media (max-width: 1080px) {
  .hardware { grid-template-columns: 155px minmax(470px, 1fr); }
  .inspector { grid-column: 1 / -1; }
  .inspector dl { display: grid; gap: 0 18px; grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 760px) {
  .console { border-width: 5px; margin: 0; min-height: 100vh; padding: 12px; }
  .nameplate { align-items: start; flex-direction: column; gap: 10px; }
  .profile { text-align: left; }
  .alarm-rack { grid-template-columns: auto minmax(0, 1fr); }
  .ack { grid-column: 1 / -1; }
  .hardware { grid-template-columns: 1fr; }
  .bank-controls { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .annunciator { padding: 10px; }
  .annunciator-head { align-items: flex-start; flex-direction: column; gap: 5px; }
  .annunciator-head span { text-align: left; }
  .lamp-grid { gap: 10px 4px; grid-template-columns: repeat(8, minmax(28px, 1fr)); }
  .inspector { grid-column: auto; }
  .inspector dl { display: block; }
  .run-strip, .paperwork { grid-template-columns: 1fr; }
  .run-cell { border-bottom: 1px solid var(--muted); border-right: 0; }
  .quick { border-left: 0; border-top: 2px solid var(--paper-ink); }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; scroll-behavior: auto !important; transition: none !important; }
}
</style>
</head>
<body>
<main class="console">
  <header class="nameplate">
    <div><h1>Network Control Center</h1><p>ARPANET Redux · operational observation console</p></div>
    <div class="profile"><strong>Operational model: mid-1970s NCC</strong><span>Telemetry profile: 1973 Type 301/303 + 302 · banked controls follow the documented 1976 interaction model; this is not a facsimile.</span><span>Configured projection: __TOPOLOGY_ID__</span></div>
  </header>
  <section class="alarm-rack" aria-label="Alarm status">
    <i id="alarm-lamp" class="alarm-lamp" aria-hidden="true"></i>
    <div class="alarm-copy" aria-live="polite"><strong id="alarm-state">No alarm</strong><span id="alarm-detail">Waiting for a validated observation.</span></div>
    <button id="ack" class="ack" type="button" disabled>Acknowledge</button>
  </section>
  <p id="error" class="error" role="alert" hidden></p>
  <section class="hardware">
    <nav class="bank-panel" aria-label="Annunciator banks">
      <p class="panel-label">Display select</p>
      <div class="bank-controls">
        <button class="bank" type="button" data-bank="auto" aria-pressed="true">Auto select<small>highest attention</small></button>
        <button class="bank" type="button" data-bank="reports" aria-pressed="false">IMP reports<small>arrival / freshness</small></button>
        <button class="bank" type="button" data-bank="minus" aria-pressed="false">Minus lines<small>direct endpoint state</small></button>
        <button class="bank" type="button" data-bank="plus" aria-pressed="false">Plus lines<small>direct endpoint state</small></button>
        <button class="bank" type="button" data-bank="proof" aria-pressed="false">Run proof<small>modern validated facts</small></button>
      </div>
      <p class="bank-note">AUTO selects the bank containing the highest-priority observed condition. Selection and acknowledgement are local display actions only.</p>
    </nav>
    <section class="annunciator" aria-label="64-position NCC annunciator">
      <div class="annunciator-head"><strong id="bank-title">Auto select</strong><span>positions identify source IMPs except the explicitly modern RUN PROOF bank</span></div>
      <div id="lamp-grid" class="lamp-grid">__LAMP_BUTTONS__</div>
    </section>
    <aside class="inspector" aria-label="Selected indication">
      <p class="panel-label">Selected indication</p>
      <dl>
        <div><dt>Position</dt><dd id="selected-position">—</dd></div>
        <div><dt>State</dt><dd id="selected-state" class="state">dark</dd></div>
        <div><dt>Meaning</dt><dd id="selected-meaning">No indication selected.</dd></div>
        <div><dt>Observed</dt><dd id="selected-observed">—</dd></div>
        <div><dt>Authority</dt><dd id="selected-authority" class="evidence">No observation.</dd></div>
      </dl>
    </aside>
  </section>
  <section class="run-strip" aria-label="Current run">
    <div class="run-cell"><span>Run</span><strong id="run-id">waiting</strong></div>
    <div class="run-cell"><span>Mode</span><strong id="run-mode">waiting</strong></div>
    <div class="run-cell"><span>Complete events</span><strong id="event-count">0</strong></div>
    <div class="run-cell"><span>Last observation</span><strong id="last-observed">—</strong></div>
  </section>
  <section class="paperwork">
    <section class="log">
      <h2>ARPA Network Log</h2>
      <table><thead><tr><th>Seq.</th><th>Time</th><th>Validated observation</th></tr></thead><tbody id="log-body"><tr><td colspan="3" class="empty">Waiting for a complete validated record.</td></tr></tbody></table>
    </section>
    <aside class="quick">
      <h2>Quick Summary</h2>
      <dl>
        <div><dt>Network reports</dt><dd id="summary-network">No attributed reports yet.</dd></div>
        <div><dt>Mapped line</dt><dd id="summary-line">No reciprocal report support yet.</dd></div>
        <div><dt>Application</dt><dd id="summary-application">No completed application claim.</dd></div>
        <div><dt>Typed journey</dt><dd id="summary-journey">No completed journey claim.</dd></div>
      </dl>
      <p class="boundary">Passive GET/HEAD presentation over existing typed projections. No simulator, controller, guest, result-mutation, report-line promotion, arbitrary-file, or external-network authority.</p>
    </aside>
  </section>
</main>
<script id="operator-config" type="application/json">__OPERATOR_CONFIG__</script>
<script>
const config = JSON.parse(document.getElementById("operator-config").textContent);
const bankLabels = { reports: "IMP reports", minus: "Minus lines", plus: "Plus lines", proof: "Run proof" };
const faultStates = new Set(["cut", "down", "contradictory", "looped"]);
const warnStates = new Set(["stale", "unknown", "missing", "missing-boundary", "completion-mismatch", "completion-invalid"]);
let selectedBank = "auto";
let visibleBank = "reports";
let selectedSlot = null;
let acknowledgedKey = null;
let latestSequence = null;
let model = emptyModel();

function emptyRecord(slot) {
  return { slot, configured: false, state: "dark", meaning: "No configured observation at this position.", observed: null, authority: "none" };
}

function emptyBank(label) {
  return { label, records: Array.from({ length: 64 }, (_, index) => emptyRecord(index + 1)) };
}

function emptyModel() {
  return {
    mode: "waiting", runId: "waiting", eventCount: 0, lastObserved: null, events: [],
    banks: { reports: emptyBank(bankLabels.reports), minus: emptyBank(bankLabels.minus), plus: emptyBank(bankLabels.plus), proof: emptyBank(bankLabels.proof) },
    summary: { network: "No attributed reports yet.", line: "No reciprocal report support yet.", application: "No completed application claim.", journey: "No completed journey claim." }
  };
}

function record(bank, slot, update) {
  if (!Number.isInteger(slot) || slot < 1 || slot > 64) return;
  bank.records[slot - 1] = { ...emptyRecord(slot), configured: true, ...update };
}

function impNumber(value) {
  const match = String(value || "").match(/^imp:(\\d+)/);
  return match ? Number(match[1]) : null;
}

function severity(state) {
  if (faultStates.has(state)) return 3;
  if (warnStates.has(state)) return 2;
  if (["up", "received", "recorded", "passed", "observed"].includes(state)) return 1;
  return 0;
}

function combine(records) {
  if (!records.length) return null;
  return [...records].sort((left, right) => severity(right.state) - severity(left.state))[0];
}

function eventLabel(event) {
  if (event.label) return event.label;
  if (event.type === "imp.report") return `IMP ${event.source?.imp} trouble report arrived`;
  if (event.type === "imp.throughput-report") return `IMP ${event.source?.imp} cumulative throughput report arrived`;
  return `${event.subject || "observation"} · ${event.state || "recorded"}`;
}

function modelFromHistorical(snapshot) {
  const next = emptyModel();
  next.mode = snapshot.mode;
  next.runId = snapshot.run.id;
  next.eventCount = snapshot.stream.complete_event_count;
  next.lastObserved = snapshot.event_tape.at(-1)?.observed_at || null;
  next.events = snapshot.event_tape;
  config.imps.forEach((imp) => record(next.banks.reports, imp.slot, { meaning: `${imp.label}: no attributed trouble report observed`, authority: "in-memory absence classification" }));
  snapshot.direct.imps.forEach((imp) => record(next.banks.reports, impNumber(imp.subject_id), { state: imp.state, meaning: imp.meaning, observed: imp.observed_at, authority: imp.state_authority }));
  for (const direction of ["minus", "plus"]) {
    const grouped = new Map();
    snapshot.direct.endpoints.filter((endpoint) => endpoint.direction === direction).forEach((endpoint) => {
      const slot = endpoint.source?.imp ?? impNumber(endpoint.subject);
      const current = grouped.get(slot) || [];
      current.push(endpoint);
      grouped.set(slot, current);
    });
    grouped.forEach((endpoints, slot) => {
      const endpoint = combine(endpoints);
      record(next.banks[direction], Number(slot), { state: endpoint.state, meaning: `${endpoint.subject}; peer IMP ${endpoint.configured_peer_imp}; ${endpoint.state}`, observed: endpoint.observed_at, authority: endpoint.state_authority });
    });
  }
  const line = snapshot.mode === "completed" ? snapshot.completion.summary_lines?.[0] : snapshot.reconciled.lines[0];
  const fresh = snapshot.direct.imps.filter((imp) => imp.state === "up").length;
  next.summary.network = `${snapshot.stream.complete_event_count} complete events; ${fresh} fresh attributed IMP reports.`;
  next.summary.line = line ? `${line.id || line.subject_id}: ${line.state}.` : "No reciprocal report support yet.";
  next.summary.application = snapshot.mode === "completed" ? "This completed line-state run makes no application claim." : "Progressive report observation makes no application claim.";
  next.summary.journey = "Typed application journey is validated separately.";
  return next;
}

function countReports(counts) {
  return Object.values(counts || {}).reduce((total, value) => total + (typeof value === "number" ? value : Object.values(value).reduce((inner, count) => inner + count, 0)), 0);
}

function addCompletedReports(next, snapshot) {
  const counts = snapshot.historical.report_counts_by_source_imp;
  const totals = {};
  if (counts.trouble) {
    Object.entries(counts.trouble).forEach(([imp, count]) => { totals[imp] = count + (counts.throughput?.[imp] || 0); });
  } else {
    Object.assign(totals, counts);
  }
  config.imps.forEach((imp) => {
    const count = totals[String(imp.slot)] || 0;
    record(next.banks.reports, imp.slot, { state: count ? "recorded" : "unknown", meaning: `${imp.label}: ${count} attributed report${count === 1 ? "" : "s"} in completed result`, authority: snapshot.historical.authority });
  });
}

function proof(next, slot, state, meaning, authority, observed = null) {
  record(next.banks.proof, slot, { state, meaning, authority, observed });
}

function modelFromCoexistence(snapshot) {
  const next = emptyModel();
  next.mode = "completed";
  next.runId = snapshot.run.id;
  next.eventCount = snapshot.historical.complete_event_count;
  next.lastObserved = snapshot.phases.markers.at(-1)?.observed_at || snapshot.run.finished_at;
  next.events = snapshot.historical.evidence_tape;
  addCompletedReports(next, snapshot);
  const endpoints = snapshot.historical.final_at_run_finish.endpoints;
  for (const direction of ["minus", "plus"]) {
    endpoints.filter((endpoint) => endpoint.direction === direction).forEach((endpoint) => record(next.banks[direction], Number(endpoint.source_imp), { state: endpoint.state, meaning: `${endpoint.subject}; ${endpoint.state}`, observed: endpoint.observed_at, authority: endpoint.state_authority }));
  }
  const journey = snapshot.journey.assessment;
  const line = snapshot.historical.accepted_line;
  proof(next, 1, snapshot.application.state, `Application: ${snapshot.application.facts[0].label} ${snapshot.application.facts[0].value}`, snapshot.application.authority, snapshot.run.finished_at);
  proof(next, 2, journey.state, journey.first_boundary_id ? `Typed journey first unresolved boundary: ${journey.first_boundary_id}` : "Typed journey complete", journey.authority || "typed message-journey projection", snapshot.run.finished_at);
  proof(next, 3, line.state, `Accepted mapped line ${line.id}: ${line.state}`, line.authority, snapshot.run.finished_at);
  proof(next, 4, snapshot.lifecycle.outer_runtime_cleanup === "passed" ? "passed" : "missing", `Outer runtime cleanup: ${snapshot.lifecycle.outer_runtime_cleanup}`, snapshot.lifecycle.authority, snapshot.run.finished_at);
  next.summary.network = `${next.eventCount} complete events; ${countReports(snapshot.historical.report_counts_by_source_imp)} attributed reports.`;
  next.summary.line = `${line.id}: ${line.state}; support ${line.supporting_sequences.join(" / ")}.`;
  next.summary.application = `${snapshot.application.facts[0].label}: ${snapshot.application.facts[0].value}; ${snapshot.application.facts[3].label}: ${snapshot.application.facts[3].value}.`;
  next.summary.journey = journey.first_boundary_id ? `${journey.state}; first unresolved ${journey.first_boundary_id}.` : journey.state;
  return next;
}

function modelFromFailover(snapshot) {
  const next = emptyModel();
  next.mode = "completed";
  next.runId = snapshot.run.id;
  next.eventCount = snapshot.historical.complete_event_count;
  next.lastObserved = snapshot.historical.last_observed_at;
  next.events = snapshot.historical.evidence_tape;
  addCompletedReports(next, snapshot);
  const journey = snapshot.journey.assessment;
  proof(next, 1, snapshot.application.state, "Same TELNET session returned structured ITS time before and after the cut", snapshot.application.authority, snapshot.run.finished_at);
  proof(next, 2, journey.state, `Typed journey first unresolved boundary: ${journey.first_boundary_id}`, journey.authority || "typed message-journey projection", snapshot.run.finished_at);
  proof(next, 3, snapshot.failover.direct_link.state, `Direct application link: ${snapshot.failover.direct_link.state}`, snapshot.failover.direct_link.authority, snapshot.failover.fault_started_at);
  proof(next, 4, snapshot.failover.alternate_route.state, "Alternate route via IMP 7 observed", snapshot.failover.alternate_route.authority, snapshot.run.finished_at);
  proof(next, 5, snapshot.lifecycle.outer_runtime_cleanup === "passed" ? "passed" : "missing", `Outer runtime cleanup: ${snapshot.lifecycle.outer_runtime_cleanup}`, snapshot.lifecycle.authority, snapshot.run.finished_at);
  next.summary.network = `${next.eventCount} complete events; post-cut reports from IMPs ${snapshot.historical.post_cut_report_sources.join(", ")}.`;
  next.summary.line = "Direct application link cut; alternate route observed. Report-line candidates remain unpromoted.";
  next.summary.application = `TELNET ${snapshot.application.state}; service ${snapshot.application.service_user}; same session survived cut.`;
  next.summary.journey = `${journey.state}; first unresolved ${journey.first_boundary_id}.`;
  return next;
}

function alarmCandidate() {
  const candidates = [];
  Object.entries(model.banks).forEach(([bank, value]) => value.records.forEach((item) => {
    if (severity(item.state) >= 2) candidates.push({ bank, item, severity: severity(item.state) });
  }));
  return candidates.sort((left, right) => right.severity - left.severity || left.item.slot - right.item.slot)[0] || null;
}

function effectiveBank(candidate) {
  return selectedBank === "auto" ? candidate?.bank || "reports" : selectedBank;
}

function lampClass(state) {
  if (faultStates.has(state)) return "is-fault";
  if (warnStates.has(state)) return "is-warn";
  if (["up", "received", "recorded", "passed", "observed"].includes(state)) return "is-good";
  if (state === "configured") return "is-special";
  return "is-dark";
}

function renderLamps(candidate) {
  visibleBank = effectiveBank(candidate);
  const bank = model.banks[visibleBank];
  document.getElementById("bank-title").textContent = `${selectedBank === "auto" ? "AUTO · " : ""}${bank.label}`;
  document.querySelectorAll(".bank").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.bank === selectedBank)));
  if (selectedBank === "auto" && candidate?.bank === visibleBank) selectedSlot = candidate.item.slot;
  if (selectedSlot === null || !bank.records[selectedSlot - 1].configured) selectedSlot = bank.records.find((item) => item.configured)?.slot || null;
  document.querySelectorAll(".lamp").forEach((button) => {
    const item = bank.records[Number(button.dataset.slot) - 1];
    button.className = `lamp ${lampClass(item.state)}${item.slot === selectedSlot ? " is-selected" : ""}`;
    button.disabled = !item.configured;
    button.setAttribute("aria-label", `Position ${item.slot}, ${item.state}: ${item.meaning}`);
  });
  renderInspector();
}

function renderInspector() {
  const item = selectedSlot === null ? null : model.banks[visibleBank].records[selectedSlot - 1];
  setText("selected-position", item ? `${visibleBank.toUpperCase()} / ${String(item.slot).padStart(2, "0")}` : "—");
  setText("selected-state", item?.state || "dark");
  setText("selected-meaning", item?.meaning || "No indication selected.");
  setText("selected-observed", item?.observed || "—");
  setText("selected-authority", item?.authority || "No observation.");
}

function renderAlarm(candidate) {
  const key = candidate ? `${candidate.bank}:${candidate.item.slot}:${candidate.item.state}:${candidate.item.observed}` : null;
  if (key !== acknowledgedKey) acknowledgedKey = null;
  const active = Boolean(candidate && key !== acknowledgedKey);
  const lamp = document.getElementById("alarm-lamp");
  lamp.className = "alarm-lamp";
  if (active) lamp.classList.add("active", candidate.severity === 2 ? "warning" : "fault");
  document.getElementById("ack").disabled = !active;
  setText("alarm-state", active ? `${candidate.item.state} · position ${candidate.item.slot}` : candidate ? "Alarm acknowledged" : "No alarm");
  setText("alarm-detail", candidate ? candidate.item.meaning : "No warning or fault indication in the current validated projection.");
  document.getElementById("ack").onclick = () => { acknowledgedKey = key; render(); };
}

function renderLog() {
  const body = document.getElementById("log-body");
  body.replaceChildren();
  const visible = model.events.slice(-9).reverse();
  if (!visible.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.className = "empty";
    cell.textContent = "Waiting for a complete validated record.";
    row.append(cell);
    body.append(row);
    return;
  }
  visible.forEach((event) => {
    const row = document.createElement("tr");
    [event.sequence ?? "—", event.observed_at ?? "—", eventLabel(event)].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = String(value);
      row.append(cell);
    });
    body.append(row);
  });
  const newest = model.events.at(-1);
  if (newest && newest.sequence !== latestSequence) {
    latestSequence = newest.sequence;
    const slot = newest.source?.imp;
    const lamp = slot ? document.querySelector(`.lamp[data-slot="${slot}"]`) : null;
    if (lamp) {
      lamp.classList.remove("is-pulse");
      void lamp.getBoundingClientRect();
      lamp.classList.add("is-pulse");
    }
  }
}

function setText(id, value) { document.getElementById(id).textContent = String(value ?? "—"); }

function render() {
  const candidate = alarmCandidate();
  renderAlarm(candidate);
  renderLamps(candidate);
  renderLog();
  setText("run-id", model.runId);
  setText("run-mode", model.mode);
  setText("event-count", model.eventCount);
  setText("last-observed", model.lastObserved || "—");
  setText("summary-network", model.summary.network);
  setText("summary-line", model.summary.line);
  setText("summary-application", model.summary.application);
  setText("summary-journey", model.summary.journey);
}

document.querySelectorAll(".bank").forEach((button) => button.addEventListener("click", () => { selectedBank = button.dataset.bank; selectedSlot = null; render(); }));
document.querySelectorAll(".lamp").forEach((button) => button.addEventListener("click", () => { if (!button.disabled) { selectedSlot = Number(button.dataset.slot); renderLamps(alarmCandidate()); } }));

async function poll() {
  const error = document.getElementById("error");
  try {
    const response = await fetch("/api/snapshot", { cache: "no-store", credentials: "same-origin" });
    const payload = await response.json();
    if (response.status === 202) {
      model = emptyModel();
      model.runId = payload.run_id;
    } else if (!response.ok) {
      throw new Error(payload.error || `snapshot request failed (${response.status})`);
    } else if (payload.failover && payload.historical && payload.journey) {
      model = modelFromFailover(payload);
    } else if (payload.composition && payload.historical && payload.journey) {
      model = modelFromCoexistence(payload);
    } else {
      model = modelFromHistorical(payload);
    }
    error.hidden = true;
    error.textContent = "";
    render();
  } catch (problem) {
    error.hidden = false;
    error.textContent = `Validated NCC snapshot unavailable: ${problem.message}`;
  }
  window.setTimeout(poll, 1000);
}

render();
poll();
</script>
</body>
</html>
"""
