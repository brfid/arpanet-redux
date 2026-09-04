# Decision index

This page routes to the decisions recorded under `docs/adr/`. Each ADR owns its own context, alternatives, decision, and consequences; this index repeats none of them. An entry names the subject a decision settles, the composition it affects, its status, and the decision that replaces, narrows, or extends it. Read the linked ADR before acting on anything here.

Composition names match the [configuration boundary](../../config/README.md). Gates and acceptance rules live in the [test plan](../test-plan.md); dated evidence lives in the [experiment index](../experiments/README.md).

Per [`AGENTS.md`](../../AGENTS.md), a decision recorded here is settled. Reopening one requires new exact-run evidence under the current pins, not a fresh argument.

## Baseline composition

| Decision | Subject | Composition | Status | Successor |
|---|---|---|---|---|
| [ADR-001](0001-two-imp-baseline.md) | Endpoint hosts and IMP count of the baseline path | Two ITS hosts | Accepted 2026-08-28 | — |

## Simulator fidelity

| Decision | Subject | Composition | Status | Successor |
|---|---|---|---|---|
| [ADR-002](0002-kaimp-not-ready-fix.md) | Whether to carry a local KAIMP status fix | All KA10 compositions | Accepted 2026-08-29; invalidated by later evidence 2026-08-30 | Replaced by [ADR-003](0003-complete-kaimp-fix.md) |
| [ADR-003](0003-complete-kaimp-fix.md) | The KAIMP interrupt-state fix and the pin carrying it | All KA10 compositions | Accepted 2026-08-30 | Replaces [ADR-002](0002-kaimp-not-ready-fix.md) |
| [ADR-004](0004-h316-hi-conversion-buffer.md) | The H316 pin covering leader conversion | All H316 compositions | Accepted 2026-08-30 | — |

## Passive report interpretation

| Decision | Subject | Composition | Status | Successor |
|---|---|---|---|---|
| [ADR-006](0006-ncc-line-reconciliation.md) | Where observed line endpoints are paired relative to the decoder | NCC host-interface proof | Accepted 2026-08-30 | Narrowed by [ADR-010](0010-ncc-down-report-neighbor-absence.md) and [ADR-011](0011-ncc-looped-report-self-neighbor.md) |
| [ADR-009](0009-ncc-paired-line-topology-boundary.md) | When a report-line identity may enter shared topology | NCC host-interface proof | Accepted 2026-08-31; deferral prerequisite met | Prerequisite satisfied by the [IMP 6 attribution record](../experiments/2026-08-31-ncc-imp6-report-proof.md) |
| [ADR-010](0010-ncc-down-report-neighbor-absence.md) | Neighbor identity required on a mapped down endpoint | NCC alternate-path fault | Accepted 2026-08-31 | Narrows [ADR-006](0006-ncc-line-reconciliation.md) |
| [ADR-011](0011-ncc-looped-report-self-neighbor.md) | Endpoint identity required on a mapped looped endpoint | NCC alternate-path loopback | Accepted 2026-08-31 | Narrows [ADR-006](0006-ncc-line-reconciliation.md) |

## Persisted NCC contracts

| Decision | Subject | Composition | Status | Successor |
|---|---|---|---|---|
| [ADR-005](0005-ncc-run-summary-contract.md) | Interchange shape of a completed run summary | All formal runs | Accepted 2026-08-30 | Extended by [ADR-012](0012-ncc-network-behavior-summary-v2.md) |
| [ADR-007](0007-ncc-historical-event-stream.md) | Whether direct passive reports get their own persisted stream | NCC host-interface proof | Accepted 2026-08-31 | Extended by [ADR-008](0008-ncc-throughput-event-stream-v2.md) |
| [ADR-008](0008-ncc-throughput-event-stream-v2.md) | Admission of Type 302 bodies and the stream version required to carry them | NCC host-interface proof | Accepted 2026-08-31 | Extends [ADR-007](0007-ncc-historical-event-stream.md) |
| [ADR-012](0012-ncc-network-behavior-summary-v2.md) | Derived-state vocabulary and gate kinds carried by completed summaries | All formal runs | Accepted 2026-08-31 | Extends [ADR-005](0005-ncc-run-summary-contract.md) |
| [ADR-013](0013-ncc-message-journey-stream.md) | Where formal message journeys are persisted | Network UNIX to ITS | Accepted 2026-09-01; superseded in part | Superseded in part by [ADR-016](0016-ka10-request-ingress-evidence.md) and [ADR-017](0017-imp11a-reply-ingress-evidence.md) for the two direct Gate 4H host-ingress boundaries |

## Guest session scope

| Decision | Subject | Composition | Status | Successor |
|---|---|---|---|---|
| [ADR-014](0014-interactive-telnet-session-stream.md) | Where interactive TELNET exchanges are retained | Network UNIX to ITS | Accepted 2026-09-01 | — |
| [ADR-015](0015-character-oriented-historical-terminal.md) | Which guest carries character-oriented TELNET fidelity | Network UNIX to ITS | Accepted 2026-09-01 | — |

## Host-ingress evidence

| Decision | Subject | Composition | Status | Successor |
|---|---|---|---|---|
| [ADR-016](0016-ka10-request-ingress-evidence.md) | Evidence standard admitting a direct request-ingress observation | Network UNIX to ITS | Accepted 2026-09-02 | Supersedes part of [ADR-013](0013-ncc-message-journey-stream.md) |
| [ADR-017](0017-imp11a-reply-ingress-evidence.md) | Evidence standard admitting a direct reply-ingress observation | Network UNIX to ITS | Accepted 2026-09-04 | Supersedes the remaining direct Gate 4H ingress gap in [ADR-013](0013-ncc-message-journey-stream.md) |
