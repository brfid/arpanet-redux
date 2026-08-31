# NCC observability

## Purpose and current status

The NCC work adds a historically grounded observability layer to ARPANET Redux without weakening the project's evidence boundary or turning the first version into a remote-control console.

The implemented slice remains deliberately bounded: `ncc/` decodes and validates the recovered 1973 IMP firmware's original Type 301 and patched Type 303 trouble-report forms plus its distinct Type 302 throughput form into topology-neutral events, reconciles paired historical line endpoints against explicit report-line identities in the shared topology, validates a derived completed-run summary, adapts formal two-ITS result artifacts, renders deterministic local replay and a static viewer, and publishes the formal controller's existing lifecycle observations as a bounded JSON Lines stream. A passive snapshot reader marks expired observations stale without moving or discarding nominal topology. The attachment seam includes a passive host-interface receiver, an old-style leader adapter, shared two- and three-IMP topology inputs, a separately validated historical-event sidecar, and a supported alternate-path fault smoke. Exact run `ncc-imp6-original-20260831T215714Z` independently attributes checksum-valid Type 303 and Type 302 reports to IMP 6 and supplies the reciprocal line-1 endpoint required by [ADR-009](adr/0009-ncc-paired-line-topology-boundary.md). Exact clean run `ncc-alternate-path-fault-canonical-20260831T230203Z` then kept both endpoints observable, forced IMP 6 reports through IMP 7 after the cut, and changed their direct line from reciprocal `up` to reciprocal `down`; [ADR-010](adr/0010-ncc-down-report-neighbor-absence.md) records the narrowly accepted neighborless-down behavior exposed by the first fault run. A source-only message-journey diagnostic derives request/reply attachment boundaries from one shared-topology route, correlates direct source-local observations without assuming a common simulator clock, and identifies the first missing, contradictory, ambiguous, or wholly unknown boundary. It still has no normalized live-report publisher or browser-based live display.

The detailed historical evidence, format derivation, and visual references are in the dated [NCC telemetry research note](research/2026-08-30-ncc-telemetry.md). This page owns current product scope and next steps; the dated note should not be edited merely to reflect implementation progress.

## Product shape

The useful product is a read-only evidence console with two observation modes over one normalized contract:

1. **Completed-run mode:** reconstruct the configured route, lifecycle transitions, normalized IMP and host observations, application proof, and acceptance verdict from a safe derived summary. This is the first end-to-end deliverable because it can be tested deterministically and does not require a new live simulator attachment.
2. **Live mode:** consume the same normalized events while a bounded harness run is active, retain the last known topology when observations become stale, and finish with the same replayable summary used by completed-run mode. The current source-only seam is controller publication plus a passive snapshot reader; a browser is not yet a live consumer.
3. **Historical NCC telemetry:** attach a project-authored receiver at host 0 of BBN IMP 5 and feed genuine IMP status and throughput reports into the event stream. The ingress adapter validates and decodes the original Type 301 and patched Type 303 trouble-report wire forms plus Type 302 throughput, attributes each from the old-style leader, and preserves the on-wire code. Throughput counters remain cumulative values, not rates.
4. **Original NCC compatibility:** investigate booting the preserved 1971 NCC System 52 only after the required host interface, report generation, checksum, console, and lightbox behavior are understood. This is not required for the first useful console.

The first interface is observability-only. Historical remote loading, core transfer, DDT, and recovery functions are important evidence about the NCC's role, but they are neither implied by the word “console” nor authorized as first-version product features.

## Operator model

The steady display combines two historically distinct artifacts:

- A stable mid-1970s logical map supplies the spatial index. Positions do not move when state changes; IMPs and TIPs form the main graph and hosts attach as leaves.
- NCC behavior supplies time, diagnosis, and attention: current versus stale observations, directional line states, an ordered event log, alarm priority, acknowledgement, and explicit uncertainty.

Traffic animation and simulator-process health are optional explanatory layers. Neither substitutes for evidence that a guest application used the intended IMP path.

## Evidence model

Every displayed conclusion must be traceable to normalized observations. The model keeps these categories distinct:

| Category | Examples | Display rule |
|---|---|---|
| Configured fact | IMP identity, host attachment, expected link, intended route | Show as topology, not as evidence that the component ran |
| Historical-network observation | Trouble report, host-interface state, modem endpoint state | Attribute to the reporting IMP and retain observation time |
| Harness observation | Process start/exit, console readiness marker, watchdog state | Identify as modern simulator or controller evidence |
| Application evidence | Guest command, remote response, correlated payload digest | Tie directly to the acceptance gate it supports |
| Inference | IMP isolated by partition, complete line down, likely failure location | Label as a conclusion and retain the observations and nominal topology used to derive it |
| Missing evidence | Timeout, absent report, incomplete marker sequence | Show unknown or stale; do not silently convert absence into down |

The completed-run summary should contain only project-authored or safely derived data. Raw simulator logs, historical messages, disk images, and third-party material remain in the external laboratory. A summary may contain safe pointers to external evidence, but the viewer must still work when those local files are unavailable.

## Normalized contract

Version 1 is accepted for completed formal runs. Its stable concerns are:

- schema version, run identity, observation clock, and source provenance;
- nominal topology with stable component and endpoint identities plus fixed display positions;
- ordered observations and lifecycle transitions;
- derived component and path states, each with supporting observation identifiers;
- acceptance-gate verdicts and the application evidence supporting each verdict;
- explicit unknown, stale, incomplete, and contradictory states;
- optional external evidence references that are never required repository fixtures.

The accepted version-1 contract and its alternatives are in [ADR-005](adr/0005-ncc-run-summary-contract.md). `ncc.run_summary` validates project-authored synthetic fixtures: a passing run, explicit missing evidence, a partition-like failure, and a rejected assertion/evidence mismatch. `ncc.two_its_summary` then adapts only the formal two-ITS manifest, outcome, and sentinel evidence; its project-authored nominal topology input is `ncc.topology`, not a second controller configuration. It does not parse raw logs, control processes, or give an unavailable external-evidence locator semantic effect.

`ncc.live` writes one controller-owned header followed by flushed JSON Lines observations. The header carries the same version-1 nominal topology, run identity, provenance, and a staleness interval; each later line uses the version-1 direct-observation envelope and is validated against that topology. It has no derived states or gate verdicts, because those require the completed formal result and remain the adapter's responsibility. A reader ignores an incomplete final line, retains the nominal topology and last direct state, and marks only expired direct states as stale. It never attaches to or controls the simulator.

The existing `NccEvent` is one input form, not yet the complete run-summary schema. `ncc.reconciliation` pairs direct Type 301/patched Type 303 endpoint observations against a typed nominal topology and makes plus/minus direction, staleness, neighbor/configuration contradiction, and a narrow partition inference explicit. `nominal_topology_from_shared` constructs that input only from reciprocal `first_report_line` and `second_report_line` identities on an existing shared modem binding; it never infers a report line from `MI1`. The two-IMP project topology maps the exact observed IMP 5 line 1 and IMP 6 line 1 pair, and its retained exact sidecar reduces the final fresh observations to `up` with support sequences 103 and 114. The alternate-path topology reuses only that mapping; its canonical exact sidecar reduces the last pre-cut pair to `up` at sequences 80 and 91 and the final pair to `down` at sequences 377 and 387. A mapped down endpoint may omit the neighbor cleared by the recovered firmware, but a supplied wrong neighbor and an up endpoint without its configured neighbor remain contradictory. This remains a pure source-only boundary, not a new completed-run schema or controller configuration. [ADR-006](adr/0006-ncc-line-reconciliation.md) and [ADR-010](adr/0010-ncc-down-report-neighbor-absence.md) own the exact rules; the reducer must not be embedded in the decoder or browser.

`ncc.message_journey` is a separate source-only, in-memory diagnostic boundary. It derives every host and modem crossing from a named normalized route whose endpoint pairs must also have existing shared host-interface or modem bindings. Direct observations retain component and interface identity, ingress or egress direction, source-local sequence, optional source-local simulator tick and transport sequence, safely decoded 1822/NCP fields, a content SHA-256 correlation fingerprint, provenance, and optional opaque external evidence references. Its pure reducer compares request and reply observations without ordering independent sources against one another, rejects unknown topology identities and malformed correlations, and retains direct-observation identifiers for every conclusion. Absence remains missing evidence or wholly unknown, never a component-down claim.

The only log parser in this slice is `ncc.h316_journey`, a narrow H316 `HI`/`MI` transfer adapter for the established `MSG`, `UDP`, and receive-completion trace grammar. It reassembles literal consecutive host-interface chunks with the same firmware message number and refuses compressed or incomplete word content. KA10 `DATAIO` and PDP-11 IMP11-A DMA/packet evidence have named typed construction seams but no speculative universal log parser. A [read-only adapter exercise](experiments/2026-08-31-ncc-message-journey-trace.md) against the existing external `imp11a-telnet-ka10-trace-20260831T131616Z` record recovered exact IMP 62 `HI2` request ingress and repeated exact reply egress transfers; the external run remains outside the repository and is not required by tests.

## Implementation sequence

1. Define and test a minimal derived run-summary schema using only synthetic fixtures. **Implemented as accepted version 1** with a small passing run, a missing-observation run, a partition-like run, and an assertion/evidence mismatch.
2. Add a read-only adapter from the current controller's manifest and existing evidence parsers into that schema. **Implemented for formal two-ITS results** without changing acceptance semantics.
3. Add deterministic replay and a local viewer for completed summaries. **Implemented** with Python's standard library plus project-authored HTML, CSS, JavaScript, and SVG; the viewer reads one summary and has no process-control authority.
4. Add live publication of the same normalized events from the controller without granting the viewer process-control authority. **Implemented as a bounded JSON Lines publisher and passive snapshot reader.**
5. Add nominal-topology reconciliation, paired line state, report timeouts, recording, and replay for genuine IMP reports. **The source-only paired-line and report-timeout reducer, explicit shared report-line adapter, exact IMP 5/IMP 6 up-state exercise, and supported alternate-path down-state gate are implemented.** [`ncc.historical_events`](../ncc/historical_events.py) provides a separately versioned, validated direct-event record and replay input for actual reports; version 2 adds Type 302 throughput while retaining version-1 reads. It does not persist reducer output or adapt it to the accepted run summary/live stream. [ADR-006](adr/0006-ncc-line-reconciliation.md), [ADR-007](adr/0007-ncc-historical-event-stream.md), [ADR-008](adr/0008-ncc-throughput-event-stream-v2.md), [ADR-009](adr/0009-ncc-paired-line-topology-boundary.md), [ADR-010](adr/0010-ncc-down-report-neighbor-absence.md), the [IMP 6 report experiment](experiments/2026-08-31-ncc-imp6-report-proof.md), and the [alternate-path fault experiment](experiments/2026-08-31-ncc-alternate-path-fault.md) own the rules and evidence boundary.
6. Attach the receiver at BBN IMP 5 after the current topology work is integrated and the required host-interface behavior is proven in isolation. **The passive transport proof, shared topology compositions, old-style leader adapter, attributed report decoders, checksum validation, reciprocal IMP 6 evidence, and bounded three-IMP fault lifecycle are implemented:** the receiver has sent host readiness, received IMP readiness, reassembled complete IMP output, and emitted direct events from genuine patched Type 303 and Type 302 reports independently attributed to IMPs 5, 6, and 7. The supported fault gate proves continued IMP 6 delivery through the configured alternate path while the direct IMP 5/IMP 6 line is fully down. The [transport experiment](experiments/2026-08-30-ncc-host-interface-proof.md), [report-ingress experiment](experiments/2026-08-31-ncc-report-ingress.md), [checksum experiment](experiments/2026-08-31-ncc-report-checksum-validation.md), [line-endpoint experiment](experiments/2026-08-31-ncc-line-endpoint-topology.md), [IMP 6 report experiment](experiments/2026-08-31-ncc-imp6-report-proof.md), and [alternate-path fault experiment](experiments/2026-08-31-ncc-alternate-path-fault.md) record the direct derived results and their limits.
7. Correlate one transaction across heterogeneous host attachments and inter-IMP links without adding another topology contract or global clock. **Implemented as a source-only typed model, shared-route boundary builder, conservative pure reducer, narrow H316 trace adapter, and explicit KA10/IMP11-A seams.** Synthetic fixtures cover a complete request/reply, a missing inter-IMP boundary, contradictory decoded destination evidence, ambiguity and total absence, and the observed PDP-11 reply-boundary byte-order shape. This output is not persisted or adapted to the accepted completed-run or controller-live contracts.

## Documentation ownership

Use each repository document for one kind of memory:

- This page is the living entry point: current scope, implemented state, boundaries, live-stream seam, and next step.
- [`docs/research/`](research/) records dated historical or experimental evidence and unresolved questions.
- [`docs/adr/`](adr/) records decisions after alternatives are explicit. [ADR-005](adr/0005-ncc-run-summary-contract.md) accepts the run-summary contract and read-only first-release boundary; [ADR-006](adr/0006-ncc-line-reconciliation.md) owns paired historical-line inference.
- [`docs/architecture.md`](architecture.md) should gain the NCC component only when its boundary is stable enough to describe as project architecture.
- [`docs/test-plan.md`](test-plan.md) should gain NCC gates when there is a runnable artifact and an exact pass/fail contract.
- [`docs/runbook.md`](runbook.md) should gain commands only when those commands exist and have been exercised.

Do not commit generated prompts, raw archive images, or a second free-standing roadmap. Extract new evidence into the dated research note, update this page when current direction changes, and link rather than repeat.

## Next decision

The next message-journey action is for a future heterogeneous or network-expansion harness to emit the typed direct observations at its exact shared-topology route boundaries, beginning with established H316 transfers and adding KA10 or IMP11-A parsers only when their complete extraction formats are proven. The harness must select an exact transaction window or preserve transport identity so repeated byte-identical transfers remain explicit evidence rather than being silently deduplicated. Any durable journey result or bridge to the accepted completed-run/controller-live contracts still requires an explicit versioning and compatibility decision.

The historical-line pair now has genuine complete `up` and `down` evidence. Exact run `ncc-imp6-original-20260831T215714Z` supplies the independently attributed reciprocal line-1 `up` pair; exact run `ncc-alternate-path-fault-canonical-20260831T230203Z` keeps both reporting IMPs observable through IMP 7, proves bidirectional direct-cable drops, and supplies the reciprocal `down` pair. The next evidence-producing historical-line task, if this track continues, is a bounded loopback composition that preserves the alternate report path and elicits genuine firmware `looped` observations from both mapped endpoints. It must first identify a supported simulator or firmware loopback mechanism from primary evidence, must not synthesize a looped report or infer an alternate report-line identity, and must retain the existing source/body/checksum and cleanup gates. This remains distinct from the separate product decision about persisting reducer output or bridging it into the accepted completed-run/controller-live contracts; that bridge still requires explicit versioning and compatibility work. IMPs 5, 6, and 7 remain configured test components, not asserted historical sites.
