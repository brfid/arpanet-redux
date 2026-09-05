# Experiment index

This page routes to the dated evidence records under `docs/experiments/`. Each record owns its own question, exact run identities, observations, and limits; this index repeats none of them. An entry names the subject a record observes, the composition it ran on, its evidentiary standing, and the record or decision that extends or supersedes it. Read the linked record before citing anything here.

Entries are grouped by claim and ordered by dependency within each group, not by filename. Composition names match the [configuration boundary](../../config/README.md). Gates and acceptance rules live in the [test plan](../test-plan.md); decisions live in the [decision index](../adr/README.md).

Per [`AGENTS.md`](../../AGENTS.md), an evidence record is settled. A retained failing manifest keeps its recorded outcome and must not be relabelled after the fact; extending a record's reach requires a new exact run under the current pins.

## Laboratory lifecycle

| Record | Subject | Composition | Standing | Successor |
|---|---|---|---|---|
| [Launcher cleanup](2026-09-04-launcher-cleanup.md) | Retained failures, handled interruptions, and controller shutdown ownership | Network UNIX to ITS; NCC line loopback | Exact interruption exposed and verified a controller-deadline repair; normal application and manual-finalization runs passed | Extended by [lifecycle recovery](2026-09-05-lifecycle-recovery.md) |
| [Lifecycle recovery](2026-09-05-lifecycle-recovery.md) | Startup stages, readiness failures, repeated interruption, and resource recovery | Network UNIX to ITS; NCC coexistence | Bounded failures and repeated normal starts verified with preserved inputs and complete cleanup | — |
| [Persistent guest workspaces](2026-09-05-persistent-guest-workspaces.md) | Saved guest files across complete stop and restart | Direct Network UNIX to ITS | Both guests preserved created and edited files through repeated restarts; interrupted publication and rollback retained verified complete generations | [ADR-019](../adr/0019-persistent-direct-guest-disks.md) and [Gate 4L](../test-plan.md#gate-4l-persistent-direct-guest-disks) |
| [Base reconstruction](2026-09-04-pdp11-base-reconstruction.md) | Deterministic base media and fresh public-input setup | Network UNIX to ITS | Two identical assemblies, independent guest filesystem checks, fresh guest compilation and passing direct Gate 4H; nested-checkout setup bug repaired | — |

## Baseline guest path

| Record | Subject | Composition | Standing | Successor |
|---|---|---|---|---|
| [Two-ITS readiness](2026-08-28-two-its-readiness.md) | NCP TELNET application and anti-bypass criteria across two IMPs | Two ITS hosts | Promoted gate, observed 2026-08-28 through 2026-08-30 | — |

## Passive NCC ingress at IMP 5

| Record | Subject | Composition | Standing | Successor |
|---|---|---|---|---|
| [Host-interface proof](2026-08-30-ncc-host-interface-proof.md) | Passive attachment at IMP 5 host 0 and complete message reassembly | NCC host-interface proof | Transport boundary only; no leader decode, report attribution, or event production | Extended by [report ingress](2026-08-31-ncc-report-ingress.md) |
| [Report ingress](2026-08-31-ncc-report-ingress.md) | Old-style leader separation, source-IMP attribution, and patched Type 303 decode | NCC host-interface proof | Decode and attribution only; no checksum rule, Type 302 decoder, or persisted record | Extended by [throughput ingress](2026-08-31-ncc-throughput-report-ingress.md); acceptance narrowed by [checksum validation](2026-08-31-ncc-report-checksum-validation.md) |
| [Throughput ingress](2026-08-31-ncc-throughput-report-ingress.md) | Type 302 body decode against the primary-derived layout | NCC host-interface proof | Counters retained as cumulative; no interval, reset rule, or rate claim | Acceptance narrowed by [checksum validation](2026-08-31-ncc-report-checksum-validation.md) |
| [Checksum validation](2026-08-31-ncc-report-checksum-validation.md) | The 1973 checksum and padding domain for Type 303 and Type 302 bodies | NCC host-interface proof | Ingress acceptance rule only; introduces no event form | — |
| [Historical-event record](2026-08-31-ncc-historical-event-record.md) | Whether a passive run can write a replayable validated direct-event record | NCC host-interface proof | Version-1 sidecar; no verdict, raw traffic, checksum rule, or paired-line inference | Record shape carried to version 2 by [throughput ingress](2026-08-31-ncc-throughput-report-ingress.md) |
| [Line-endpoint evidence](2026-08-31-ncc-line-endpoint-topology.md) | Directly observed IMP 5 line-endpoint identity on the configured proof path | NCC host-interface proof | One-sided observation; no reciprocal endpoint or complete line state | Reciprocal endpoint supplied by [IMP 6 attribution](2026-08-31-ncc-imp6-report-proof.md) |
| [IMP 6 attribution](2026-08-31-ncc-imp6-report-proof.md) | Whether the unchanged IMP 6 peer originates independently attributed reports | NCC host-interface proof | Satisfies the [ADR-009](../adr/0009-ncc-paired-line-topology-boundary.md) prerequisite; read-only reducer exercise with no durable output | Fault and loop states exercised by [alternate-path fault](2026-08-31-ncc-alternate-path-fault.md) and [line loopback](2026-08-31-ncc-line-loopback.md) |

## Three-IMP line-state gates

| Record | Subject | Composition | Standing | Successor |
|---|---|---|---|---|
| [Alternate-path fault](2026-08-31-ncc-alternate-path-fault.md) | Attributed reporting while a directly mapped line changes from up to down | NCC alternate-path fault | Promoted canonical gate; the exploratory fault manifest retains `outcome=failed` | Reducer rule settled by [ADR-010](../adr/0010-ncc-down-report-neighbor-absence.md) |
| [Line loopback](2026-08-31-ncc-line-loopback.md) | Reciprocal firmware loop indications under two-ended reflection | NCC alternate-path loopback | Promoted canonical gate; the exploratory loop manifest retains `outcome=failed` | Reducer rule settled by [ADR-011](../adr/0011-ncc-looped-report-self-neighbor.md) |

## Message journey and host ingress

| Record | Subject | Composition | Standing | Successor |
|---|---|---|---|---|
| [Journey adapter exercise](2026-08-31-ncc-message-journey-trace.md) | Narrow H316 trace adapter run against an existing exact run | Network UNIX to ITS | Read-only; no simulator rerun and no persisted contract | Its retained KA10 trace reused by [host-ingress grammar](2026-09-01-ka10-host-ingress-grammar.md) |
| [Formal journey emission](2026-09-01-pdp11-its-message-journey.md) | Typed journey emission, manifest binding, readback, replay, and cleanup | Network UNIX to ITS | Accepted under [ADR-013](../adr/0013-ncc-message-journey-stream.md) as an additive version-1 sidecar | Its `boundary:request:6` evidence superseded by [KA10 request ingress](2026-09-02-ka10-request-ingress.md); its recorded observations remain immutable |
| [Host-ingress grammar](2026-09-01-ka10-host-ingress-grammar.md) | Feasibility of a KA10/ITS observation at `boundary:request:6` | Network UNIX to ITS | Read-only feasibility; no rerun, parser, schema change, or instrumentation | Carried to an accepted observation by [KA10 request ingress](2026-09-02-ka10-request-ingress.md) |
| [KA10 request ingress](2026-09-02-ka10-request-ingress.md) | One observation-only simulator boundary over one exact direct transaction | Network UNIX to ITS | Accepted under [ADR-016](../adr/0016-ka10-request-ingress-evidence.md); its retained result stops at `boundary:reply:6` | Direct journey completed separately by [IMP11-A reply ingress](2026-09-04-imp11a-reply-ingress.md) |
| [IMP11-A reply ingress](2026-09-04-imp11a-reply-ingress.md) | Post-store PDP-11 DMA evidence over one exact direct transaction | Network UNIX to ITS | Accepted under [ADR-017](../adr/0017-imp11a-reply-ingress-evidence.md); direct journey is twelve observations and `complete` | — |

## Interactive and terminal sessions

| Record | Subject | Composition | Standing | Successor |
|---|---|---|---|---|
| [Interactive TELNET session](2026-09-01-interactive-pdp11-its-telnet.md) | One-controller line-oriented operator session to ITS | Network UNIX to ITS | Accepted for the bounded line-oriented scope in [ADR-014](../adr/0014-interactive-telnet-session-stream.md) and [Gate 4I](../test-plan.md#gate-4i-interactive-network-unix-to-its-telnet) | Client diagnostic repaired by [option negotiation](2026-09-01-network-unix-telnet-option-negotiation.md) |
| [Option negotiation](2026-09-01-network-unix-telnet-option-negotiation.md) | Bounded repair of a false client diagnostic | Network UNIX to ITS | Accepted for the repair; interactive scope and authority unchanged | — |
| [Historical terminal](2026-09-01-historical-network-unix-telnet-terminal.md) | Character-oriented interaction with the preserved guest client | Network UNIX to ITS | Accepted for the bounded character-oriented scope in [ADR-015](../adr/0015-character-oriented-historical-terminal.md) and [Gate 4J](../test-plan.md#gate-4j-historical-network-unix-telnet-terminal) | — |
| [Interactive failover](2026-09-04-interactive-pdp11-its-failover.md) | One human-operated guest TELNET connection before and after a controller-owned direct-link cut | Network UNIX to ITS over direct and alternate routes | Accepted for the bounded same-session scope in [ADR-018](../adr/0018-interactive-telnet-failover.md) and [Gate 4K](../test-plan.md#gate-4k-interactive-same-session-telnet-failover) | — |

## NCC-observed compositions

| Record | Subject | Composition | Standing | Successor |
|---|---|---|---|---|
| [Coexistence](2026-09-01-ncc-pdp11-its-coexistence.md) | Accepted application route combined with passive NCC report reception | Application and NCC coexistence | One bounded composition; no telemetry or journey schema change | Projected by [coexistence desk](2026-09-01-ncc-coexistence-desk.md) |
| [Coexistence desk](2026-09-01-ncc-coexistence-desk.md) | Unified display projection of the retained coexistence result | Application and NCC coexistence | Completed-artifact projection and loopback presentation only | — |
| [Application failover](2026-09-01-ncc-pdp11-its-application-failover.md) | Observed cut of the application cable and continued service over a configured route | Application failover | One bounded acceptance pass; no schema change, report-line inference, or browser control | Projected by [failover board](2026-09-01-ncc-application-failover-board.md) |
| [Failover board](2026-09-01-ncc-application-failover-board.md) | Passive board projection of the retained failover result | Application failover | Accepted implementation and read-only retained replay | — |
