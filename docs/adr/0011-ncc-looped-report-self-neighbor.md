# ADR-011: Match an explicitly mapped looped endpoint to its reporting IMP

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

[ADR-006](0006-ncc-line-reconciliation.md) requires a direct line observation to agree with nominal topology before it can support a paired state. The initial implementation applied that rule by requiring every non-unknown observation's `neighbor_imp` to equal the configured peer. Its project-authored looped fixtures repeated that synthetic assumption, so the reducer could produce complete and directional looped states without having exercised recovered-firmware loopback.

Exact external-laboratory run `ncc-line-loopback-experiment-20260831T232858Z` produced the first genuine reciprocal looped pair while both reporting IMPs remained observable through the three-IMP alternate-path composition. A project-authored relay first forwarded the direct cable and then returned each endpoint's datagrams byte for byte to that same endpoint. The checksum-valid Type 303 reports were independently attributed to IMPs 5 and 6 and repeatedly reported their explicitly mapped line 1 endpoints as looped. Every such report named the reporting IMP itself as neighbor: IMP 5 reported `neighbor_imp=5`, and IMP 6 reported `neighbor_imp=6`.

That shape agrees with the preserved firmware's loop recognition path: an incoming routing message records its source as the line neighbor, and receiving the local IMP's own routing message marks the endpoint looped for a later trouble report. The existing matcher consequently labelled the genuine pair contradictory because neither self-neighbor was the configured peer. The [dated experiment](../experiments/2026-08-31-ncc-line-loopback.md) owns the exact primary-source boundary, run evidence, transition, and intentionally failed initial verdict.

## Decision

Treat a direct `looped` observation as topology-compatible only when its reported `neighbor_imp` equals its own source IMP. The observation's `(source IMP, report line)` must already map to one endpoint of a project-authored nominal line. The report supplies both the looped state and self-neighbor identity; topology supplies only the separately evidenced endpoint pairing and plus/minus direction.

Do not accept the configured remote peer, an absent neighbor, or a third IMP as the neighbor of a looped observation. Keep the existing rules for every other state: `up` requires the configured peer; `down` accepts either the configured peer or the absent-neighbor form accepted by [ADR-010](0010-ncc-down-report-neighbor-absence.md); `unknown` remains non-assertive. A self-neighbor value does not gain special meaning for up or down.

## Options considered

### Continue requiring the configured remote peer on looped reports

This would retain the earlier synthetic fixture shape but make the reducer's looped states unreachable for the genuine recovered-firmware behavior established by the exact run.

### Accept any neighbor on a looped report

This would hide direct source/configuration contradictions and let a missing or unrelated peer support a derived loop state. The firmware evidence establishes one exact signature, not a reason to disable identity checks.

### Accept self-neighbor only on an explicitly mapped looped endpoint

This accepted option follows the direct firmware report while retaining fail-closed behavior for every unproved shape. It neither invents an endpoint mapping nor substitutes configured topology for observed state.

### Infer loopback from the relay phase or simulator configuration

The relay and simulator are harness facts, not historical-network observations. Using either as the line state would bypass the checksum-valid firmware report and violate the decoder/reducer evidence boundary.

## Consequences

- Two fresh reciprocal looped-to-self observations can establish complete line loopback and retain both supporting event sequences.
- A fresh looped-to-self observation paired with a fresh up observation can establish the existing minus-looped or plus-looped directional state.
- A looped report that names the configured remote peer, omits the neighbor, or names a third IMP is contradictory. Self-neighbor up and down reports are also contradictory.
- Up, down, unknown, freshness, reciprocal-evidence, plus/minus direction, and partition-inference rules remain unchanged.
- The decoder, historical-event stream, nominal-topology schema, completed-run contract, controller-live contract, and browser remain unchanged.
- The retained failed run is not rewritten; a read-only re-evaluation with this accepted rule must produce a new derived verdict.
