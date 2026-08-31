# ADR-010: Accept absent neighbor identity on an explicitly mapped down endpoint

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

[ADR-006](0006-ncc-line-reconciliation.md) requires a direct line observation to agree with nominal topology before it can support a paired state. The initial implementation applied that rule by requiring every non-unknown observation's `neighbor_imp` to equal the configured peer. Synthetic down fixtures supplied that peer and could therefore reach the reducer's complete and directional down states.

Exact run `ncc-alternate-fault-20260831T224448Z` produced the first genuine reciprocal down pair while both reporting IMPs remained observable through a third-IMP alternate route. The checksum-valid Type 303 reports were independently attributed to IMPs 5 and 6 and repeatedly reported their explicitly mapped line 1 endpoints as down, but both omitted the remembered neighbor. The current matcher consequently labelled the pair contradictory even though the direct source, mapped endpoint, state, and reciprocal report were all present. The [dated experiment](../experiments/2026-08-31-ncc-alternate-path-fault.md) owns the exact evidence and failed initial verdict.

## Decision

Treat `neighbor_imp=null` as compatible only for a direct `down` observation whose `(source IMP, report line)` is already mapped to one endpoint of a project-authored nominal line. The report still supplies the down state; topology supplies only the previously evidenced endpoint-to-line identity. A neighbor value that is present must equal the configured peer or the observation is contradictory.

Keep the existing rules for every other state. An `up` observation must supply the configured neighbor. This decision does not change looped-state handling because the exact run did not exercise loopback. One missing reciprocal endpoint remains unknown, an expired endpoint remains stale, and neither becomes down.

## Options considered

### Continue requiring a neighbor on down reports

This would preserve the original synthetic assumption but make the reducer's down states unreachable for the genuine recovered-firmware behavior now observed in an exact run.

### Accept every down observation regardless of a present neighbor

This would hide a real configuration/report mismatch. A report that names the wrong peer remains direct contradictory evidence and must fail closed.

### Accept absence only on an explicitly mapped down endpoint

This accepted option uses genuine direct source, line, and state evidence while retaining the configured-neighbor check whenever the report supplies a peer. It neither invents a line identity nor substitutes configuration for observed state.

## Consequences

- Two fresh reciprocal down observations with absent neighbors can establish complete line down and retain both supporting event sequences.
- Directional down and partition inference may use the same direct endpoint evidence, but all existing reciprocal, freshness, and independent-peer requirements still apply.
- A present wrong neighbor remains contradictory, and an up report with no configured neighbor remains contradictory.
- The decoder, historical-event stream, nominal-topology schema, completed-run contract, controller-live contract, and browser remain unchanged.
- The retained failed run is not rewritten; a read-only re-evaluation with this accepted rule must produce a new derived verdict.
