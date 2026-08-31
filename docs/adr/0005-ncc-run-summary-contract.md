# ADR-005: Use a validated JSON contract for completed NCC run summaries

- **Status:** Accepted
- **Date:** 2026-08-30
- **Decider:** Brad

## Context

The NCC's first useful mode is a read-only view of a completed harness run. The existing formal two-ITS run leaves a line-oriented manifest, acceptance outcome, and evidence files in the external laboratory. Those formats are correct for their individual producers, but they are not a safe display contract: the manifest mixes configured inputs and modern harness facts, raw logs must remain outside the repository, and a browser should not infer that an absent line means a historical network failure.

The completed-run contract must preserve configured topology separately from observations, preserve observation order and provenance, make inferences traceable, and prevent a claimed gate pass from being backed only by unrelated or failed evidence. It must remain usable without an external laboratory or a running simulator and must not bake the current two-IMP layout into its model.

## Decision

Use a versioned, project-authored JSON summary validated by `ncc.run_summary`. Version 1 has one run clock and provenance record, a nominal topology with stable component and endpoint identities plus display positions, ordered direct observations, derived states with supporting observation identifiers, and named gate verdicts with their supporting observations. External evidence is optional opaque metadata; validation never opens it.

The validator accepts only a coherent summary. It rejects unknown schema fields, ambiguous topology identifiers, broken topology routes, observations outside the run clock or out of sequence, references to missing evidence, a passed run with a non-passing gate, and a passed gate without a passed application observation. Its canonical JSON serialization is deterministic.

The initial committed fixtures are synthetic only: a passing two-ITS-shaped run, an incomplete run with explicitly missing evidence, a partition-like failure inferred from endpoint observations, and an assertion/evidence mismatch that must be rejected. The read-only two-ITS adapter reads only the formal manifest, controller outcome, and sentinel evidence and emits JSON to standard output; it neither parses raw logs nor controls the laboratory.

## Options considered

### Reuse raw manifests and logs directly

| Dimension | Assessment |
|---|---|
| Complexity | Low initially, high in every consumer |
| Evidence boundary | Weak; callers must understand external files and formats |
| Determinism | Dependent on laboratory availability and ad hoc parsing |
| Topology reuse | Poor; each consumer would recreate configured topology |

This would make the first viewer a second harness parser and risks treating modern process telemetry or absent files as historical network state.

### Make the first viewer model controller-specific state

| Dimension | Assessment |
|---|---|
| Complexity | Medium initially, high for future topologies |
| Evidence boundary | Better than raw logs, but entangled with one controller |
| Determinism | Good for the current two-ITS controller only |
| Topology reuse | Poor; state names and route assumptions leak into the UI |

This would be fast to demonstrate but would prevent the later heterogeneous and third-IMP harnesses from producing the same summary without display-driven changes to their controllers.

### Validate a topology-neutral derived summary

| Dimension | Assessment |
|---|---|
| Complexity | Medium; one schema and validator before the adapter |
| Evidence boundary | Strong; summary contains project-authored or safely derived data only |
| Determinism | High; fixtures and summaries are self-contained |
| Topology reuse | High; stable identities and routes are data, not controller code |

This accepted option creates an explicit adapter boundary before a viewer or live publisher exists and makes uncertainty and inference displayable rather than implicit.

## Consequences

- The next NCC implementation task is a read-only adapter from the formal two-ITS manifest and retained evidence parsers into version 1; it must not change existing acceptance semantics.
- Consumers receive normalized, replayable data without access to raw logs or simulator process control.
- A later schema change requires an explicit version, fixtures, migration or compatibility decision, and an ADR update or successor.
- The version-1 contract is accepted for completed formal runs. A public replay or viewer interface must preserve the same read-only and evidence-traceability boundaries.
