# Architecture

## Purpose

ARPANET Redux separates historically authentic guest and IMP behavior from a modern orchestration, observation, and validation plane. The project advances by promoting bounded compositions with explicit claims and evidence, not by treating one host pair or IMP route as a permanent network definition.

For an application-bearing composition, success requires a historical guest application to send data through the configured IMP route and another historical guest application to consume it. For an NCC or network-behavior composition, success requires genuine attributed IMP observations and a verdict derived under the composition's explicit evidence rules. Configured topology is intent in both cases; it is never proof that a component ran, a link worked, or a route was historically real.

## System shape

```text
              modern orchestration and lifecycle control
                               │
                               ▼
      historical, diagnostic, or NCC host attachments
                               ↕ simulated 1822 interfaces
                  configured H316 IMP topology
                               ↕ simulated modem links
                  additional IMPs and endpoints
                               │
                               ▼
       transcripts + IMP traces/reports + per-run manifest
```

The modern plane allocates resources, drives simulator consoles, observes bounded results, and performs exact cleanup. It surrounds the simulated network but does not become an application bridge or substitute configured facts for observations.

## Baseline application composition

ADR-001 selected the following as the first complete vintage-to-vintage acceptance baseline:

```text
control: simulator consoles and per-run lifecycle management
             │                                      │
             ▼                                      ▼
       KA10 / ITS 106                         KA10 / ITS 176
       native NCP                             native NCP
             │ 1822 long leader                    │ 1822 long leader
             ▼                                      ▼
         H316 IMP 6 ───── simulated modem ───── H316 IMP 62
             │                                      │
             └──────────── guest data path ─────────┘

validation: console transcripts + both IMP traces + per-run manifest
```

This remains the normative Gate 4 and Gate 5 baseline, not a maximum network size or the project's final topology. Gate 4H reuses the proven IMP route while replacing ITS host 176 with SRI/NOSC Network UNIX on a PDP-11. The later NCC fault compositions add a third IMP and a passive receiver under separate network-behavior claims rather than extending the application gate by implication.

Loopback UDP models the point-to-point electrical links between simulator devices. It is transport for simulated interfaces, not an application bridge.

## Integrated application and NCC composition

The first accepted growing-network composition combines the Gate 4H route with the passive NCC triangle under one shared topology and lifecycle:

```text
Network UNIX 176 ↔ HI2 IMP 62 MI1 ══ MI3 IMP 6 HI2 ↔ ITS 106
                                      │ MI1
                                      │
NCC receiver ↔ HI1 IMP 5 MI1 ═════════╝
                  ╲ MI2            MI2 ╱
                   ╲────── IMP 7 ─────╱
```

IMP 6's MI1/MI2 links preserve the earlier NCC composition, and MI3 carries only the application cable to IMP 62. The shared topology maps report lines only on the previously evidenced IMP 5 MI1 / IMP 6 MI1 binding. The alternate links and application link remain configured-only for historical-line reconciliation.

The outer lifecycle owns the passive receiver plus IMPs 5 and 7. The existing heterogeneous application controller owns hosts 176 and 106 plus IMPs 62 and 6, emits the typed journey, and performs its existing cleanup. One composition evaluator reads the already separate application, journey, historical-event, receiver, manifest, and cleanup artifacts. It does not let one artifact fill another plane's missing evidence.

The exact accepted composition proves coexistence, not application rerouting through the NCC triangle. Its receiver deliberately outlives the application controller, so the later historical tape contains teardown observations after the accepted fresh direct-line `up` pair. A combined diagnostic view must present that phase distinction rather than reducing the last tape record to an application verdict.

The completed coexistence projection is that read-only handoff. It does not merge or replace the existing persistence contracts:

```text
shared topology + manifest + application evidence + composition verdict
                         + typed journey + historical events + cleanup
                                             │
                                             ▼
                         fail-closed in-memory Python projection
                                             │
                                             ▼
                           loopback GET/HEAD presentation only
```

The adapter verifies the application result, journey reducer, direct report counts, and composition support independently. Its detailed run report marks the exact verdict support and the later receiver tail, but it does not invent the unpersisted controller-exit sequence or align independent simulator clocks. The fixed map leaves every unmapped link configured-only; the browser receives resolved authority and state and performs no evidence reduction.

The default network board is a smaller passive presentation boundary over the already validated projections:

```text
growing historical-event sidecar ── existing historical projection ──┐
                                                                    ├── passive board ── fixed topology + state + attention
terminal structured artifacts ─── existing coexistence projection ─┘                         │
                                                                                              └── detailed run report
```

Before a run starts, only the configured topology is present. During a run, the board can show direct report activity, IMP report freshness, and the mapped paired-line conclusion from the progressive historical projection. After a terminal manifest appears, the board fails closed unless the completed coexistence adapter validates every required artifact; only then may it add the application and typed-journey conclusions and expose the detailed report. This switching layer creates no new persisted evidence contract.

The convenience runner is separate from both browser routes. One operator terminal launches the unchanged formal smoke as an exactly owned child session and serves the passive board beside it. Control-C signals that exact harness, whose existing trap owns cleanup. The browser cannot invoke the runner, signal a process, write a guest console, switch a relay, or restart a component.

## Composition roles

| Role | Boundary |
|---|---|
| Historical application | Both application endpoints are historical guests, and post-probe IMP evidence corroborates the configured route |
| Heterogeneous application | Different historical host families share the same application and evidence requirements |
| Mixed diagnostic | `linux-ncp` replaces one historical endpoint to isolate a guest interface or route; it cannot satisfy a vintage-to-vintage application gate |
| Router oracle | Diagnostic endpoints and a hostless adjacent peer test ordinary routing and explicit host-dead behavior |
| NCC and network behavior | A passive receiver, genuine attributed IMP reports, and topology-aware reducers test specific observation and fault claims without asserting an application exchange |
| Integrated application and NCC | One shared topology and bounded lifecycle run an accepted historical application exchange while the passive NCC path independently records genuine IMP reports; application and network claims retain separate evidence and verdicts |

Additional hosts, IMPs, links, or routes enter the project as new bounded compositions. A composition may reuse proven components, but it must own its topology, lifecycle, acceptance boundary, and evidence. The repository does not infer historical site identity from an IMP number or turn a configured route into a historical reconstruction claim.

## Separation of concerns

| Concern | Owner | Boundary |
|---|---|---|
| Guest data plane | Historical guest NCP and applications | Payload enters one historical guest, crosses the configured IMP route, and exits another historical guest |
| Simulated network | Host-interface device models and H316 firmware | Converts 1822 leaders where required, routes packets, and reports network conditions |
| Control plane | Source-only launch and controller code | Allocates resources, drives consoles, observes readiness, and cleans up exact children; the combined terminal runner may own one complete formal smoke but exposes no browser command route |
| Evidence plane | Test assertions and run manifests | Correlates claimed behavior with post-start observations and pinned inputs |
| NCC observation plane | Versioned v1/v2 completed summaries, bounded v1 controller stream, validated historical-event and message-journey sidecars, topology-aware reducers, deterministic replay, and passive viewers | Separates configured topology, direct observations, harness-derived peer evidence, in-memory reconciliation, and completed gate evidence; progressive consumers receive already-resolved snapshots, independent simulator order never becomes a global clock, and only an exactly matching completed-result adapter may grant a final reducer state gate authority |
| Artifact plane | External laboratory | Holds third-party sources, media, executables, copied guest workspaces, and raw results |

The repository never uses a guest-media directory as a transfer channel between endpoints. Guest workspaces are distinct, and a payload test is invalid if the controller can satisfy it by copying a host file.

A version-2 completed network-behavior summary is a derived evidence artifact, not a second topology or a live controller channel. Its passed gate must close over a supported completed harness outcome and every direct historical observation supporting the cited final reducer state. The adapter maps report identities only through the supplied shared topology's explicit reciprocal bindings; unmatched configured links remain unobserved.

The passive historical display reuses that same mapping and reducer in Python. It reads only complete validated JSONL records, retains an interrupted final record as input status rather than evidence, and gives the browser a presentation-ready snapshot over loopback GET requests. The browser never pairs endpoints or infers freshness. The topology-first board may consume that projection while the integrated result grows, but it does not use the historical display's completed-summary handoff for the heterogeneous result; after a terminal manifest it instead requires the separately validated coexistence projection before exposing completed application, journey, and report detail.

The formal heterogeneous harness writes a separate version-1 message-journey sidecar over fixed post-probe H316 trace windows. Its header contains the one shared topology and expected route boundaries; its typed observation records retain direct versus harness-derived provenance and source-local order; and its terminal record must exactly match the existing pure reducer. This diagnostic stream neither changes the Gate 4H application verdict nor extends a completed-summary, live-observation, or historical-report schema. The H316 adapter stops at unproved guest ingress instead of inferring it from topology or application success.

The passive message-journey display reuses that validated reader and reducer in Python and projects their resolved route, boundary assessments, observations, provenance, and retained byte-window metadata into a deterministic in-memory snapshot. Its loopback server accepts GET and HEAD only, and its browser is a presentation client: it neither parses the sidecar nor assigns evidence to boundaries. The observer reports interrupted final records and resets its stream generation on truncation, replacement, restart, or identity change without treating independent simulator ticks as a common clock. A terminal view means only that the persisted diagnosis matched the reducer; it does not create a completed-run verdict or fill either unproved guest-ingress boundary.

## Resource model

Every run receives a unique result directory, UDP port set, Unix-domain control sockets, and exact child-process set. Simulator configurations obtain port numbers from the run environment. External source and executable identities are verified before launch; result manifests record the exact inputs used.

The external laboratory is a sibling of the source checkout by default. Its contents are replaceable build inputs and evidence, not repository state. See the [runbook](runbook.md) for its layout and the [harness design](harness.md) for lifecycle mechanics.

## Future site integration

The original consumer generates a vintage YAML input, runs two historical-machine stages, validates a final text artifact, records provenance, and publishes through Hugo. The intended replacement seam begins after YAML generation and ends before artifact validation.

The network stage may replace the two current machine stages, but it must preserve these external contracts:

- Final bundle identities remain `brad.bio.txt`, `build.log.html`, and `pipeline-status.json`.
- Name and headline remain exact; summary text remains equal after whitespace normalization.
- Status retains the expected pipeline identity, success result, zero exit status, build ID, and source revision.
- Build-log identity, provenance, reuse fingerprints, semantic validation, and fail-closed publication remain intact.

The site checkout is not read or modified by the laboratory smokes. The two-vintage-host and payload-integrity prerequisites in the [test plan](test-plan.md) now pass; connecting the network stage to the publishing pipeline remains future work.

## Decisions and evidence

- [ADR-001](adr/0001-two-imp-baseline.md) records why the two-IMP, two-ITS composition was selected as the first acceptance baseline.
- [Phase-one feasibility](research/2026-08-28-phase-one-feasibility.md) records the resource survey and passing diagnostic experiments.
- [Two-ITS readiness findings](experiments/2026-08-28-two-its-readiness.md) records the evidence and failed trials that established the application baseline's current readiness rule.
- [The test plan](test-plan.md) owns the normative gates for the diagnostic, application, heterogeneous, NCC, and eventual site-integration compositions.
- [NCC observability](ncc.md) owns the current observation product shape, implemented scope, and next decision.
