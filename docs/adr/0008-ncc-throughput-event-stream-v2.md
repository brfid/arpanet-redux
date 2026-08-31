# ADR-008: Add Type 302 throughput events in historical-event stream version 2

- **Status:** Accepted
- **Date:** 2026-08-31
- **Decider:** Brad

## Context

ADR-007 introduced a version-1 historical-event sidecar for direct Type 301 / patched Type 303 trouble-report observations. Its explicit vocabulary intentionally excluded unrecognized report bodies. Primary 1973 evidence and an exact passive run now establish a distinct Type 302 throughput body: five local line packet/word pairs, ten cumulative counter families for each of four real host interfaces, checksum, and optional pad. The live 55-word messages matched that layout after the two-word old-style leader.

Type 302 is not a trouble report and has a different source kind, event type, and details shape. Accepting it as version 1 would make a prior version-1 reader reject a newly written record without any version signal. It must not be placed in the accepted completed-run schema or controller-owned live stream merely to reuse their containers.

## Decision

Write new historical-event sidecars as schema version 2. Version 2 adds exactly one direct event form: `imp.throughput-report`, attributed to `imp-throughput-report`, subject `imp:<reporting-imp>`, and state `received`. Its details retain Type 302, the five line counter pairs, four host counter groups, checksum word, and any padding; they do not claim an interval, rate, reset rule, topology edge, or application effect.

Readers continue to accept valid version-1 trouble-report records. A version-1 record containing a Type 302 event is rejected. The existing Type 301 / patched Type 303 report, host-interface, and line-endpoint forms retain their version-1 meaning in version 2.

## Options considered

### Add Type 302 as a version-1 event

This would break the version signal: a reader built for the earlier contract would see a structurally valid header but an unsupported direct-event vocabulary.

### Convert Type 302 to a trouble-report event

The fields and meaning differ. Reusing the trouble-report source or event type would erase the on-wire distinction and invite incorrect rate or topology inference.

### Publish through the completed-run or controller live contract

Those contracts have separate ownership and identity limits. The throughput report is direct historical telemetry, not an application verdict or controller observation.

### Add a version-2 sidecar event form

This accepted option makes compatibility explicit, preserves the Type 302 body independently, and keeps version-1 records readable.

## Consequences

- A passive report run can record Type 301, patched Type 303, and Type 302 observations in one version-2 event stream.
- Direct consumers can show or compare cumulative counters but must not call them rates without independently established timing and reset semantics.
- Checksum validation, Type 304/305 formats, a bridge to the completed-run/live contracts, and topology-aware line inference remain separate work.
