"""Render the passive browser shell for a progressive message journey."""

from __future__ import annotations


def render_journey_display_html() -> str:
    """Return one self-contained observer page with no evidence-reduction logic."""

    return _PAGE


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ARPANET Redux · passive message journey bench</title>
<style>
:root {
  --chassis: #d5d9d2;
  --paper: #f4f3e8;
  --ink: #17272d;
  --signal: #28656b;
  --harness: #b67619;
  --fault: #94405d;
  --display: "Avenir Next Condensed", "Arial Narrow", sans-serif;
  --body: "Avenir Next", system-ui, sans-serif;
  --mono: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
body { background: var(--chassis); color: var(--ink); font: 15px/1.45 var(--body); margin: 0; }
button { color: inherit; font: inherit; }
code, time, .mono { font-family: var(--mono); }
.bench { margin: 0 auto; max-width: 1640px; padding: 22px; }
.masthead { align-items: end; border-bottom: 2px solid var(--ink); display: grid; gap: 18px; grid-template-columns: minmax(0, 1fr) auto; padding: 4px 2px 14px; }
.eyebrow, .section-label, .socket-kicker, dt, th { font: 750 11px/1.2 var(--display); letter-spacing: .13em; text-transform: uppercase; }
.eyebrow { color: var(--signal); margin: 0 0 5px; }
h1 { font: 850 clamp(34px, 5vw, 66px)/.88 var(--display); letter-spacing: -.025em; margin: 0; text-transform: uppercase; }
.passive-seal { align-items: center; border: 2px solid var(--signal); display: flex; font: 800 12px var(--display); gap: 8px; letter-spacing: .11em; padding: 8px 10px; text-transform: uppercase; }
.passive-seal::before { background: var(--signal); border-radius: 50%; content: ""; height: 9px; width: 9px; }
.status-strip { background: var(--ink); color: var(--paper); display: grid; gap: 1px; grid-template-columns: 1.55fr 1fr 1fr 1.2fr; margin-top: 12px; }
.status-cell { border-right: 1px solid rgba(244, 243, 232, .25); min-width: 0; padding: 10px 12px; }
.status-cell:last-child { border-right: 0; }
.status-cell span { color: rgba(244, 243, 232, .68); display: block; font: 700 10px var(--display); letter-spacing: .11em; margin-bottom: 3px; text-transform: uppercase; }
.status-cell strong { display: block; font: 650 12px/1.35 var(--mono); overflow-wrap: anywhere; }
.alert { border: 2px solid var(--harness); background: var(--paper); color: var(--ink); margin-top: 12px; padding: 10px 12px; }
.alert.error { border-color: var(--fault); }
.alert.terminal { border-color: var(--signal); }
.alert[hidden] { display: none; }
.panel { background: var(--paper); border: 1px solid rgba(23, 39, 45, .42); box-shadow: 0 3px 12px rgba(23, 39, 45, .13); min-width: 0; }
.panel-head { align-items: baseline; border-bottom: 1px solid rgba(23, 39, 45, .34); display: flex; gap: 14px; justify-content: space-between; padding: 12px 14px; }
.panel-head h2 { font: 800 17px var(--display); letter-spacing: .07em; margin: 0; text-transform: uppercase; }
.panel-head p { color: rgba(23, 39, 45, .7); font: 11px var(--mono); margin: 0; text-align: right; }
.route-panel { margin-top: 16px; }
.route-chain { align-items: center; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(132px, 1fr) minmax(72px, .45fr); overflow-x: auto; padding: 16px 18px 10px; }
.route-node { align-items: center; align-self: stretch; background: var(--paper); border: 2px solid var(--ink); display: flex; flex-direction: column; justify-content: center; min-height: 78px; min-width: 132px; padding: 10px; text-align: center; }
.route-node.imp { border-radius: 50%; justify-self: center; min-height: 92px; min-width: 92px; width: 92px; }
.route-node strong { font: 800 14px/1.12 var(--display); letter-spacing: .035em; text-transform: uppercase; }
.route-node code { color: var(--signal); font-size: 10px; margin-top: 5px; }
.route-link { align-items: center; color: rgba(23, 39, 45, .66); display: flex; flex-direction: column; font: 9px/1.25 var(--mono); gap: 5px; min-width: 72px; text-align: center; }
.route-link::before { border-top: 3px dashed rgba(23, 39, 45, .45); content: ""; width: 100%; }
.route-caption { color: rgba(23, 39, 45, .72); font: 11px/1.45 var(--mono); margin: 0; padding: 0 18px 14px; }
.authority-key { border-top: 1px solid rgba(23, 39, 45, .24); display: flex; flex-wrap: wrap; gap: 8px 18px; margin: 0 18px; padding: 10px 0; }
.authority-key span { align-items: center; display: flex; font: 750 9px var(--display); gap: 6px; letter-spacing: .08em; text-transform: uppercase; }
.authority-key i { border: 2px dashed rgba(23, 39, 45, .45); display: inline-block; height: 12px; width: 12px; }
.authority-key .direct i { background: var(--signal); border-color: var(--signal); }
.authority-key .harness i { background: var(--harness); border-color: var(--harness); }
.authority-key .reducer i { border: 3px double var(--fault); }
.lanes { border-top: 3px double var(--ink); padding: 14px; }
.lane + .lane { margin-top: 13px; }
.lane-heading { align-items: baseline; display: flex; gap: 12px; justify-content: space-between; margin-bottom: 6px; }
.lane-heading strong { font: 800 16px var(--display); letter-spacing: .08em; text-transform: uppercase; }
.lane-heading span { color: rgba(23, 39, 45, .68); font: 10px var(--mono); }
.socket-scroll { overflow-x: auto; padding-bottom: 3px; }
.socket-grid { display: grid; gap: 7px; grid-template-columns: repeat(6, minmax(142px, 1fr)); min-width: 900px; }
.boundary-socket { background: transparent; border: 2px dashed rgba(23, 39, 45, .42); cursor: pointer; min-height: 104px; padding: 8px 9px; position: relative; text-align: left; }
.boundary-socket:hover { border-color: var(--ink); }
.boundary-socket:focus-visible { outline: 4px solid var(--harness); outline-offset: 2px; }
.boundary-socket[aria-pressed="true"] { box-shadow: inset 0 0 0 3px var(--ink); }
.boundary-socket.state-observed.authority-direct { background: var(--signal); border-color: var(--signal); color: var(--paper); }
.boundary-socket.state-observed.authority-harness-derived { background: var(--harness); border-color: var(--harness); color: var(--ink); }
.boundary-socket.state-contradictory { border: 4px double var(--fault); color: var(--fault); }
.boundary-socket.state-ambiguous { border: 4px dotted var(--harness); }
.boundary-socket.state-missing { border-style: dashed; }
.socket-kicker { display: flex; justify-content: space-between; }
.socket-state { display: block; font: 850 19px/1 var(--display); margin: 10px 0 8px; text-transform: uppercase; }
.socket-endpoint { display: block; font: 10px/1.3 var(--mono); overflow-wrap: anywhere; }
.socket-authority { display: block; font: 750 9px/1.25 var(--display); letter-spacing: .1em; margin-top: 7px; text-transform: uppercase; }
.work-grid { display: grid; gap: 16px; grid-template-columns: minmax(320px, .72fr) minmax(0, 1.55fr); margin-top: 16px; }
.inspector { padding: 14px; }
.inspector h3 { font: 850 26px/1 var(--display); margin: 0 0 5px; text-transform: uppercase; }
.inspector > p { color: rgba(23, 39, 45, .72); margin: 4px 0 12px; }
.fact-grid { display: grid; gap: 0 14px; grid-template-columns: minmax(90px, .5fr) minmax(0, 1.5fr); margin: 0; }
.fact-grid dt, .fact-grid dd { border-top: 1px solid rgba(23, 39, 45, .22); margin: 0; padding: 7px 0; }
.fact-grid dd { font: 11px/1.45 var(--mono); overflow-wrap: anywhere; }
.observation-block { border-left: 6px solid var(--signal); margin-top: 12px; padding: 8px 10px; }
.observation-block.harness-derived { border-color: var(--harness); }
.observation-block.typed-other { border-color: var(--ink); }
.observation-block h4 { font: 800 13px var(--display); margin: 0; text-transform: uppercase; }
.observation-block p { font: 10px/1.45 var(--mono); margin: 4px 0 0; overflow-wrap: anywhere; }
.tape-wrap { max-height: 540px; overflow: auto; }
table { border-collapse: collapse; font: 10px/1.38 var(--mono); width: 100%; }
th { background: var(--chassis); color: rgba(23, 39, 45, .76); position: sticky; text-align: left; top: 0; z-index: 1; }
th, td { border-bottom: 1px solid rgba(23, 39, 45, .2); padding: 8px 9px; vertical-align: top; }
td:first-child { color: var(--signal); font-weight: 750; }
.authority-chip { border: 1px solid currentColor; display: inline-block; font: 750 8px var(--display); letter-spacing: .08em; padding: 2px 4px; text-transform: uppercase; }
.authority-chip.harness-derived { color: var(--harness); }
.authority-chip.direct { color: var(--signal); }
.metadata-grid { display: grid; gap: 16px; grid-template-columns: repeat(3, minmax(0, 1fr)); margin-top: 16px; }
.metadata-body { padding: 5px 14px 13px; }
.metadata-list { list-style: none; margin: 0; padding: 0; }
.metadata-list li { border-bottom: 1px solid rgba(23, 39, 45, .2); padding: 8px 0; }
.metadata-list strong, .metadata-list code { display: block; overflow-wrap: anywhere; }
.metadata-list strong { font: 750 11px var(--display); letter-spacing: .04em; text-transform: uppercase; }
.metadata-list code { color: rgba(23, 39, 45, .72); font-size: 9px; margin-top: 3px; }
.empty { color: rgba(23, 39, 45, .65); margin: 0; padding: 16px; }
.footer { color: rgba(23, 39, 45, .7); font: 10px/1.5 var(--mono); margin: 14px 2px 0; }
@media (max-width: 980px) {
  .work-grid, .metadata-grid { grid-template-columns: 1fr; }
  .status-strip { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 580px) {
  .bench { padding: 10px; }
  .masthead { grid-template-columns: 1fr; }
  .passive-seal { justify-self: start; }
  .status-strip { grid-template-columns: 1fr; }
  .status-cell { border-bottom: 1px solid rgba(244, 243, 232, .25); border-right: 0; }
  .panel-head { align-items: start; flex-direction: column; }
  .panel-head p { text-align: left; }
}
@media (prefers-reduced-motion: reduce) {
  * { scroll-behavior: auto !important; transition: none !important; }
}
</style>
</head>
<body>
<main class="bench">
  <header class="masthead">
    <div><p class="eyebrow">ARPANET Redux · typed evidence observer</p><h1>Message journey bench</h1></div>
    <div class="passive-seal">Read only</div>
  </header>
  <section class="status-strip" aria-label="Journey status" aria-live="polite">
    <div class="status-cell"><span>Run</span><strong id="run-id">waiting for validated header</strong></div>
    <div class="status-cell"><span>Stream</span><strong id="stream-mode">progressive</strong></div>
    <div class="status-cell"><span>Observations</span><strong id="observation-count">0 / 12 crossings</strong></div>
    <div class="status-cell"><span>Reducer diagnosis</span><strong id="diagnosis">unknown</strong></div>
  </section>
  <div id="terminal-alert" class="alert terminal" role="status" hidden></div>
  <div id="tail-alert" class="alert" role="status" hidden></div>
  <div id="error-alert" class="alert error" role="alert" hidden></div>

  <section class="panel route-panel">
    <header class="panel-head"><h2>Configured route and resolved crossings</h2><p id="route-identity">waiting for topology</p></header>
    <div id="route-chain" class="route-chain" aria-label="Configured journey route"></div>
    <p class="route-caption"><strong>Dashed conductors are configuration only.</strong> A numbered socket changes only when the Python reducer assigns typed evidence to that exact interface crossing. Independent simulator ticks are never aligned into a common clock.</p>
    <div class="authority-key" aria-label="Authority key"><span><i></i>configured crossing</span><span class="direct"><i></i>direct H316 trace</span><span class="harness"><i></i>harness-derived delivery</span><span class="reducer"><i></i>in-memory reducer</span></div>
    <div class="lanes">
      <section class="lane">
        <div class="lane-heading"><strong>Request →</strong><span>Network UNIX host 176 toward ITS host 106</span></div>
        <div class="socket-scroll"><div id="request-lane" class="socket-grid"></div></div>
      </section>
      <section class="lane">
        <div class="lane-heading"><strong>← Reply</strong><span>ITS host 106 toward Network UNIX host 176</span></div>
        <div class="socket-scroll"><div id="reply-lane" class="socket-grid"></div></div>
      </section>
    </div>
  </section>

  <section class="work-grid">
    <aside class="panel">
      <header class="panel-head"><h2>Boundary inspector</h2><p>configured · reducer · source</p></header>
      <div id="inspector" class="inspector"><p class="empty">Select a boundary socket.</p></div>
    </aside>
    <section class="panel">
      <header class="panel-head"><h2>Observation tape</h2><p>emission order only · no global clock</p></header>
      <div id="tape" class="tape-wrap"><p class="empty">No complete observations yet.</p></div>
    </section>
  </section>

  <section class="metadata-grid">
    <section class="panel"><header class="panel-head"><h2>Transaction windows</h2><p>retained metadata</p></header><div id="windows" class="metadata-body"></div></section>
    <section class="panel"><header class="panel-head"><h2>Provenance ledger</h2><p>declared producers</p></header><div id="provenance" class="metadata-body"></div></section>
    <section class="panel"><header class="panel-head"><h2>Message contracts</h2><p>safe decoded fields</p></header><div id="expectations" class="metadata-body"></div></section>
  </section>
  <p class="footer">Passive loopback observer. No simulator, controller, guest, result mutation, arbitrary-file, or external-network route is present.</p>
</main>
<script>
const display = { snapshot: null, selectedBoundaryId: null };

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

function replace(id, ...children) {
  document.getElementById(id).replaceChildren(...children);
}

function setText(id, value) {
  document.getElementById(id).textContent = String(value);
}

function stateClass(value) {
  return ["observed", "missing", "contradictory", "ambiguous"].includes(value)
    ? `state-${value}` : "state-missing";
}

function authorityClass(boundary) {
  if (boundary.source_authority_classes.includes("direct")) return "authority-direct";
  if (boundary.source_authority_classes.includes("harness-derived")) return "authority-harness-derived";
  return "authority-configured";
}

function authorityLabel(boundary) {
  const classes = boundary.source_authority_classes;
  if (!classes.length) return "configured · no observation";
  if (classes.length > 1) return classes.join(" + ");
  return classes[0];
}

function renderRoute(snapshot) {
  const chain = document.getElementById("route-chain");
  const children = [];
  snapshot.route.components.forEach((component, index) => {
    const node = element("article", `route-node ${component.kind}`);
    node.append(element("strong", "", component.label));
    node.append(element("code", "", component.id));
    children.push(node);
    const link = snapshot.route.links[index];
    if (link) {
      const conductor = element("div", "route-link");
      conductor.append(element("span", "", link.id));
      conductor.title = `${link.authority}: ${link.from_interface_id} ↔ ${link.to_interface_id}`;
      children.push(conductor);
    }
  });
  chain.replaceChildren(...children);
  chain.style.gridTemplateColumns = children.map((_, index) => index % 2 ? "minmax(72px,.45fr)" : "minmax(132px,1fr)").join(" ");
}

function renderLane(id, boundaries, reverse) {
  const ordered = reverse ? [...boundaries].reverse() : boundaries;
  const buttons = ordered.map((boundary) => {
    const button = element("button", `boundary-socket ${stateClass(boundary.state)} ${authorityClass(boundary)}`);
    button.type = "button";
    button.dataset.boundaryId = boundary.id;
    button.dataset.state = boundary.state;
    button.dataset.authority = boundary.source_authority_classes.join(",") || "configured-only";
    button.setAttribute("aria-pressed", String(display.selectedBoundaryId === boundary.id));
    button.setAttribute("aria-label", `${boundary.id}, ${boundary.state}, ${boundary.component_label}, ${boundary.direction}`);
    const kicker = element("span", "socket-kicker");
    kicker.append(element("span", "", String(boundary.position).padStart(2, "0")));
    kicker.append(element("span", "", boundary.direction));
    button.append(kicker);
    button.append(element("span", "socket-state", boundary.state));
    button.append(element("span", "socket-endpoint", `${boundary.component_id} · ${boundary.interface_label}`));
    button.append(element("span", "socket-authority", authorityLabel(boundary)));
    button.addEventListener("click", () => {
      display.selectedBoundaryId = boundary.id;
      renderLanes(display.snapshot);
      renderInspector(display.snapshot);
    });
    return button;
  });
  replace(id, ...buttons);
}

function renderLanes(snapshot) {
  const request = snapshot.assessment.boundaries.filter((item) => item.leg === "request");
  const reply = snapshot.assessment.boundaries.filter((item) => item.leg === "reply");
  renderLane("request-lane", request, false);
  renderLane("reply-lane", reply, true);
}

function factList(items) {
  const list = element("dl", "fact-grid");
  items.forEach(([term, value]) => {
    list.append(element("dt", "", term));
    list.append(element("dd", "", value === null || value === undefined || value === "" ? "—" : value));
  });
  return list;
}

function observationBlock(observation) {
  const block = element("article", `observation-block ${observation.authority_class}`);
  block.append(element("h4", "", observation.id));
  block.append(element("p", "", observation.authority));
  block.append(element("p", "", `${observation.provenance.id} · ${observation.provenance.kind}`));
  const decoded = Object.entries(observation.decoded)
    .filter(([, value]) => value !== null)
    .map(([name, value]) => `${name}=${value}`)
    .join(" · ");
  block.append(element("p", "", decoded));
  block.append(element("p", "", `local sequence ${observation.source_local_sequence} · simulator tick ${observation.simulator_tick ?? "not recorded"} · transport ${observation.transport_sequence ?? "not recorded"}`));
  block.append(element("p", "", `fingerprint ${observation.correlation_fingerprint}`));
  observation.external_evidence.forEach((item) => {
    block.append(element("p", "", `external reference ${item.id} · ${item.kind} · ${item.locator}`));
  });
  return block;
}

function renderInspector(snapshot) {
  const boundaries = snapshot.assessment.boundaries;
  let boundary = boundaries.find((item) => item.id === display.selectedBoundaryId);
  if (!boundary) {
    boundary = boundaries.find((item) => item.id === snapshot.assessment.first_boundary_id)
      || boundaries.find((item) => item.state !== "observed")
      || boundaries[0];
    display.selectedBoundaryId = boundary ? boundary.id : null;
  }
  if (!boundary) {
    replace("inspector", element("p", "empty", "No configured boundary is available."));
    return;
  }
  const container = element("div", "inspector");
  container.append(element("p", "section-label", `${boundary.leg} crossing ${boundary.position}`));
  container.append(element("h3", "", boundary.state));
  container.append(element("p", "", `${boundary.component_label} · ${boundary.direction} through ${boundary.interface_label}`));
  container.append(factList([
    ["Boundary", boundary.id],
    ["Component", boundary.component_id],
    ["Interface", boundary.interface_id],
    ["Configuration", boundary.configured_authority],
    ["State authority", boundary.state_authority],
    ["Evidence IDs", boundary.evidence_observation_ids.join(", ") || "none at this boundary"],
    ["Reducer context", boundary.context_supporting_observation_ids.join(", ") || "no prior leg evidence"],
  ]));
  boundary.evidence_observation_ids
    .map((identifier) => snapshot.observations.find((item) => item.id === identifier))
    .filter(Boolean)
    .forEach((observation) => container.append(observationBlock(observation)));
  if (!boundary.evidence_observation_ids.length) {
    container.append(element("p", "empty", "This socket is configured, but no typed observation was assigned to it. Missing evidence is not a down state."));
  }
  replace("inspector", ...container.childNodes);
}

function renderTape(snapshot) {
  if (!snapshot.observations.length) {
    replace("tape", element("p", "empty", "No complete observations yet; the journey remains unknown."));
    return;
  }
  const table = element("table", "");
  const head = element("thead", "");
  const heading = element("tr", "");
  ["Record", "Observation", "Crossing", "Endpoint", "Source authority", "Local identity"].forEach((label) => heading.append(element("th", "", label)));
  head.append(heading);
  table.append(head);
  const body = element("tbody", "");
  snapshot.observations.forEach((observation) => {
    const row = element("tr", "");
    row.append(element("td", "", String(observation.record_position).padStart(2, "0")));
    row.append(element("td", "", observation.id));
    row.append(element("td", "", `${observation.leg} · ${observation.boundary_id}`));
    row.append(element("td", "", `${observation.component_id} · ${observation.interface_id} · ${observation.direction}`));
    const authority = element("td", "");
    authority.append(element("span", `authority-chip ${observation.authority_class}`, observation.authority_class));
    authority.append(element("div", "", observation.provenance.kind));
    row.append(authority);
    row.append(element("td", "", `seq ${observation.source_local_sequence} · tick ${observation.simulator_tick ?? "—"} · transport ${observation.transport_sequence ?? "—"}`));
    body.append(row);
  });
  table.append(body);
  replace("tape", table);
}

function metadataList(records, renderer) {
  const list = element("ul", "metadata-list");
  records.forEach((record) => list.append(renderer(record)));
  return list;
}

function renderMetadata(snapshot) {
  const windows = metadataList(snapshot.transaction_window.sources, (source) => {
    const item = element("li", "");
    item.append(element("strong", "", `${source.id} · ${source.artifact}`));
    item.append(element("code", "", `bytes ${source.start_offset}…${source.end_offset}`));
    item.append(element("code", "", `sha256 ${source.sha256}`));
    return item;
  });
  replace("windows", windows);

  const provenance = metadataList(snapshot.provenance, (source) => {
    const item = element("li", "");
    item.append(element("strong", "", `${source.id} · ${source.kind}`));
    item.append(element("code", "", source.revision ? `revision ${source.revision}` : "revision not declared"));
    return item;
  });
  replace("provenance", provenance);

  const records = ["request", "reply"].map((leg) => ({ leg, contract: snapshot.expected_messages[leg] }));
  const expectations = metadataList(records, ({ leg, contract }) => {
    const item = element("li", "");
    item.append(element("strong", "", `${leg} · ${contract.message_class}`));
    const fields = Object.entries(contract)
      .filter(([name, value]) => name !== "correlation_fingerprint" && value !== null)
      .map(([name, value]) => `${name}=${value}`)
      .join(" · ");
    item.append(element("code", "", fields));
    item.append(element("code", "", `fingerprint ${contract.correlation_fingerprint}`));
    return item;
  });
  replace("expectations", expectations);
}

function render(snapshot) {
  display.snapshot = snapshot;
  const total = snapshot.assessment.boundaries.length;
  setText("run-id", snapshot.run.id);
  setText("stream-mode", `${snapshot.mode} · generation ${snapshot.stream.generation} · ${snapshot.stream.change}`);
  setText("observation-count", `${snapshot.stream.complete_observation_count} observations / ${total} crossings`);
  setText("diagnosis", snapshot.assessment.first_boundary_id ? `${snapshot.assessment.state} · first ${snapshot.assessment.first_boundary_id}` : snapshot.assessment.state);
  setText("route-identity", `${snapshot.route.topology_id} · ${snapshot.route.route_id}`);
  const terminal = document.getElementById("terminal-alert");
  terminal.hidden = !snapshot.stream.is_terminal;
  if (!terminal.hidden) terminal.textContent = "Terminal diagnosis verified against the existing Python reducer. This diagnostic is not a completed-run or Gate 4H verdict.";
  const tail = document.getElementById("tail-alert");
  tail.hidden = !snapshot.stream.incomplete_final_record;
  if (!tail.hidden) tail.textContent = "Incomplete final JSONL record ignored. It will become visible only after its terminating newline arrives.";
  document.getElementById("error-alert").hidden = true;
  renderRoute(snapshot);
  renderInspector(snapshot);
  renderLanes(snapshot);
  renderTape(snapshot);
  renderMetadata(snapshot);
}

async function refresh() {
  try {
    const response = await fetch("/api/snapshot", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `snapshot request failed (${response.status})`);
    render(payload);
  } catch (error) {
    const alert = document.getElementById("error-alert");
    alert.textContent = `Observer error: ${error.message}`;
    alert.hidden = false;
  } finally {
    window.setTimeout(refresh, 1250);
  }
}

refresh();
</script>
</body>
</html>
"""
