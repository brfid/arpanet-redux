# ADR-006: Reconcile historical line endpoints outside the decoder

- **Status:** Accepted
- **Date:** 2026-08-30
- **Decider:** Brad

## Context

The recovered firmware's Type 301 trouble report gives a direct status for one local modem-line endpoint. It names the reporting IMP, local interface, reported neighbor, local line state, and counters, but it does not identify a complete logical edge or establish the historical plus/minus condition by itself. The dated NCC research note records that TIR 90 assigns the lower-numbered IMP to a line's minus end and the higher-numbered IMP to its plus end; the NCC paired both endpoint reports and timed out missing reports before classifying a line.

The completed-run summary contract in ADR-005 deliberately has no historical interface-to-line mapping. Extending it now would change an accepted persisted schema before a genuine report receiver or shared network topology exists. The reducer needs an isolated source-only boundary that can be tested with project-authored topology and synthetic direct observations without changing the two-ITS controller, simulator configuration, or browser.

## Decision

Use `ncc.reconciliation` as a pure topology-aware reducer. Its nominal input lists each logical line by stable identifier and exactly two distinct `(IMP, interface)` endpoints. The lower-numbered IMP is the minus endpoint and the higher-numbered IMP is the plus endpoint. A direct Type 301 endpoint event must agree with its reporting IMP, local endpoint, and configured neighbor before it can support that line.

The reducer accepts ordered, timestamped `NccEvent` values plus an observation start time, current time, and explicit report interval. It exposes source-only line and IMP reachability conditions with the direct event sequences supporting them. It keeps these rules deliberately conservative:

- Two fresh matching endpoint observations yield `up`, complete `down` or `looped`, or one-direction `minus-*` / `plus-*` conditions.
- A missing endpoint is `unknown`; an expired endpoint is `stale`; neither becomes network-down merely because evidence disappeared.
- A direct report that conflicts with configured neighbor identity is `contradictory`, not a network failure claim.
- An IMP is `partitioned` only when its report is missing or stale and every incident line has a fresh down observation from at least two independent configured peers. This is an inference that the IMP is unreachable from observed peers, not a diagnosis of failed IMP hardware.

This is not a new completed-run JSON schema or a controller configuration. When a real receiver and shared topology are ready, any persisted/replayed reducer output requires an explicit contract and compatibility decision.

## Options considered

### Infer complete lines in the Type 301 decoder

The decoder has no nominal topology or reciprocal endpoint evidence. Doing this there would turn a direct historical observation into a controller-specific inference and make a single report appear to prove a line condition.

### Let the browser pair endpoints

This would duplicate topology and timeout logic in every consumer, make tests depend on JavaScript presentation code, and weaken the evidence trail for derived states.

### Add interface mappings to the accepted completed-run schema now

This would broaden ADR-005's persisted version-1 contract before a genuine receiver or shared network topology requires it. The existing two-ITS summary is not historical Type 301 telemetry and should not acquire a second controller configuration merely to exercise a reducer.

### Use a pure nominal-topology reducer

This accepted option preserves the decoder's direct-fact boundary, permits deterministic synthetic tests, and leaves receiver and persisted-schema decisions to the later topology integration slice.

## Consequences

- The reducer can classify paired historical endpoint observations without raw logs, a running simulator, or browser authority.
- Its output retains supporting sequence numbers, so a future recorder can map conclusions back to direct events.
- The first `partitioned` condition is intentionally a narrow connectivity class. Missing evidence or a single failed peer remains `unknown` or `stale`.
- A shared project topology and any durable reducer-result format remain future work; they must not be inferred from the current two-ITS harness.
