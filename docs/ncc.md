# NCC observability

## Purpose and current status

The NCC work adds a historically grounded observability layer to ARPANET Redux without weakening the project's evidence boundary or turning the first version into a remote-control console.

The implemented source-only slice is intentionally small: `ncc/` decodes the recovered 1973 IMP firmware's Type 301 trouble report into topology-neutral events, validates a derived completed-run summary, and adapts formal two-ITS result artifacts. Synthetic unit tests establish each boundary. No live IMP attachment, topology reducer, event recorder, replay, or user interface exists yet.

The detailed historical evidence, format derivation, and visual references are in the dated [NCC telemetry research note](research/2026-08-30-ncc-telemetry.md). This page owns current product scope and next steps; the dated note should not be edited merely to reflect implementation progress.

## Product shape

The useful product is a read-only evidence console with two observation modes over one normalized contract:

1. **Completed-run mode:** reconstruct the configured route, lifecycle transitions, normalized IMP and host observations, application proof, and acceptance verdict from a safe derived summary. This is the first end-to-end deliverable because it can be tested deterministically and does not require a new live simulator attachment.
2. **Live mode:** consume the same normalized events while a bounded harness run is active, retain the last known topology when observations become stale, and finish with the same replayable summary used by completed-run mode.
3. **Historical NCC telemetry:** attach a project-authored receiver at host 0 of BBN IMP 5 and feed genuine IMP status and throughput reports into the event stream. The Type 301 decoder is preparatory work for this mode.
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

The existing `NccEvent` is one input form, not yet the complete run-summary schema. A topology reducer should pair endpoint observations and derive historical plus/minus line state; it should not be embedded in the decoder or the browser.

## Implementation sequence

1. Define and test a minimal derived run-summary schema using only synthetic fixtures. **Implemented as accepted version 1** with a small passing run, a missing-observation run, a partition-like run, and an assertion/evidence mismatch.
2. Add a read-only adapter from the current controller's manifest and existing evidence parsers into that schema. **Implemented for formal two-ITS results** without changing acceptance semantics.
3. Add deterministic replay and a local viewer for completed summaries. The initial implementation can use Python's standard library plus project-authored HTML, CSS, JavaScript, and SVG.
4. Add live publication of the same normalized events from the controller without granting the viewer process-control authority.
5. Add nominal-topology reconciliation, paired line state, report timeouts, recording, and replay for genuine IMP reports.
6. Attach the receiver at BBN IMP 5 after the current topology work is integrated and the required host-interface behavior is proven in isolation.

## Documentation ownership

Use each repository document for one kind of memory:

- This page is the living entry point: current scope, implemented state, boundaries, and next step.
- [`docs/research/`](research/) records dated historical or experimental evidence and unresolved questions.
- [`docs/adr/`](adr/) records decisions after alternatives are explicit. [ADR-005](adr/0005-ncc-run-summary-contract.md) accepts the run-summary contract and read-only first-release boundary.
- [`docs/architecture.md`](architecture.md) should gain the NCC component only when its boundary is stable enough to describe as project architecture.
- [`docs/test-plan.md`](test-plan.md) should gain NCC gates when there is a runnable artifact and an exact pass/fail contract.
- [`docs/runbook.md`](runbook.md) should gain commands only when those commands exist and have been exercised.

Do not commit generated prompts, raw archive images, or a second free-standing roadmap. Extract new evidence into the dated research note, update this page when current direction changes, and link rather than repeat.

## Next decision

The next engineering task is deterministic replay and a local viewer for completed summaries. It must consume the accepted version-1 contract, preserve the configured-fact/observation/inference distinction, and remain read-only; it can proceed entirely in the NCC worktree while the parallel third-IMP/host work continues.
