# Agent instructions

## Do not reopen settled findings without new exact-run evidence

ADRs and dated notes under `docs/adr/`, `docs/experiments/`, and `docs/research/` record decisions made after real, cited evidence, not guesses. Read the relevant one before touching an area it covers. If the current task looks like it repeats a question one of those documents already answered, treat that answer as settled and do not re-run the ruled-out alternative, unless a new exact run under the current pins produces evidence the document did not have.

## Prefer real replacement evidence over relaxing a broken check

If an acceptance or evidence check turns out to be structurally unable to pass against the correctly-built artifact (for example, it checks for output that only ever existed in earlier exploratory code), do not default to weakening or deleting the check. Check whether the real system already exposes, or can cheaply be made to expose, genuine evidence for what the check was actually trying to prove, and build that instead.

## Research stalled investigations

When an investigation reaches a wall — repeated experiments reproduce the same blocker, available evidence no longer distinguishes the remaining hypotheses, or the next action would otherwise be guesswork — check both of these source classes before changing scope or asking the operator for direction:

1. Search the relevant upstream GitHub repositories for current issues, pull requests, commits, and discussions about the exact component, protocol, and failure mode. Prefer primary project repositories, check dates and current status, and retain links to the useful results.
2. Consult primary historical documentation for the systems and versions involved, including manuals, memos, RFCs, INFO files, preserved source comments, and contemporary operator documentation when available.

Reconcile those sources with the experiment's local evidence. Distinguish documented behavior from inference, do not treat modern issue commentary as a substitute for a historical specification, and do not re-derive findings that the project has already validated.

## Third-party and historical material

Do not add firmware, disk or tape images, simulator executables, generated media, source checkouts, or raw logs to this repository; keep them in the external laboratory per [`docs/runbook.md`](docs/runbook.md). Before publishing anything derived from an externally obtained source (quoting it, deriving a register map or protocol from it, adapting its code), check [`NOTICE.md`](NOTICE.md) for that source's redistribution status. Several sources in [`pins/sources.lock.toml`](pins/sources.lock.toml) have no resolved license; treat that as a hard boundary, not a formality.

## NCC observability work

Before changing `ncc/`, an NCC data contract, or a visualization, read [`docs/ncc.md`](docs/ncc.md) for current scope and [`docs/research/2026-08-30-ncc-telemetry.md`](docs/research/2026-08-30-ncc-telemetry.md) for the historical and format evidence. The living page owns current direction; do not turn the dated research note into a second status tracker.
