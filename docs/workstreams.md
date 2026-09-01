# Parallel workstreams and fresh-context handoff

- **Updated:** 2026-09-01
- **Canonical repository:** [`brfid/arpanet-redux`](https://github.com/brfid/arpanet-redux)
- **Integration policy:** `main` remains test-passing; feature work uses dedicated branches and worktrees

## Purpose and ownership

This is the project's operational planning and handoff document: active local checkouts, current workstream state, and either the next selected task or an explicit decision point. The [README](../README.md) owns present public status, subsystem living pages own implementation detail, dated notes own evidence, and ADRs own accepted decisions. Do not duplicate those records here or create a competing roadmap.

## Local checkouts

These directories share Git object storage but have independent branches and working trees.

| Directory | Branch | Use |
|---|---|---|
| `/Users/brf/src/arpanet-redux` | `main` | Integration only; do not develop here |
| `/Users/brf/src/arpanet-redux-worktrees/ncc` | `codex/ncc-imp6-report-proof` | Passive NCC displays and observation integration |
| `/Users/brf/src/arpanet-redux-worktrees/telnet` | `codex/pdp11-telnet` | Gate 4H and typed message-journey emission |
| `/Users/brf/src/arpanet-redux-worktrees/network` | `codex/ncc-line-loopback-proof` | Completed line-state proof; coordinated network expansion only |

The external laboratory is `/Users/brf/src/arpanet-redux-lab`; it holds third-party assets and raw results, not Git worktree state. GitHub `origin` is canonical; treat the `gitlab` remote as historical unless explicitly directed otherwise.

## Branch safety

Use the active branches above. `codex/ncc-telemetry` and `codex/ncc-run-summary` preserve already-integrated NCC history and are not development branches.

The following refs are recovery anchors, not development branches:

- `backup/pre-ncc-integration-20260830` at `d16b5d9`
- `backup/ncc-pre-rebase-20260830` at `bee5c91`

Do not delete, rebase, merge into, or develop on a recovery branch. Prefer reverting the relevant commit on `main` for an ordinary rollback. Never switch, rebase, remove, or repurpose a worktree with uncommitted changes.

## Workstream handoffs

### NCC

- **Read first:** [NCC observability](ncc.md) and the dated [telemetry research note](research/2026-08-30-ncc-telemetry.md).
- **State:** `main` contains accepted version-1 application and version-2 network-behavior completed-summary profiles, the unchanged bounded version-1 controller stream, deterministic replay and static viewing, genuine Type 301/303/302 report ingestion and event replay, topology-aware paired-line reconciliation with canonical `up`, `down`, and `looped` gates, a read-only final-snapshot adapter for supported fault and loopback results, and a passive progressive historical-line browser display with exact version-2 handoff. The source-only message-journey model, narrow H316 trace adapter, formal Gate 4H sidecar emission/readback, and passive Python-resolved journey browser display are also complete.
- **Decision:** No further NCC slice is selected. A next historical-evidence batch now requires an explicit choice: prove a complete KA10 or IMP11-A host-ingress extraction grammar, investigate original NCC System 52 feasibility, or select another documented historical host/application.
- **Evidence:** The [IMP 6 report](experiments/2026-08-31-ncc-imp6-report-proof.md), [alternate-path fault](experiments/2026-08-31-ncc-alternate-path-fault.md), [line-loopback](experiments/2026-08-31-ncc-line-loopback.md), and [typed Gate 4H journey](experiments/2026-09-01-pdp11-its-message-journey.md) records own the canonical runs. [ADR-006](adr/0006-ncc-line-reconciliation.md), [ADR-009](adr/0009-ncc-paired-line-topology-boundary.md), [ADR-010](adr/0010-ncc-down-report-neighbor-absence.md), [ADR-011](adr/0011-ncc-looped-report-self-neighbor.md), [ADR-012](adr/0012-ncc-network-behavior-summary-v2.md), and [ADR-013](adr/0013-ncc-message-journey-stream.md) own the accepted reconciliation, topology, completed-summary, and typed-sidecar rules.
- **Guardrails:** Displays have no simulator or controller authority, never animate unobserved traffic, and never convert configured topology, application success, or absence into observed state. The historical-line evidence slice is complete. The formal journey producer owns its manifest, ports, cleanup, transaction window, and application verdict; it does not depend on or modify the exploratory PDP-11 driver. Add KA10 or IMP11-A parsers only after their full extraction formats are proven.

### PDP-11 TELNET

- **Read first:** [IMP11-A device record](research/imp11a-device.md) and [Network UNIX research](research/pdp11-network-unix.md).
- **State:** The heterogeneous application proof and formal Gate 4H harness are complete. `make smoke-pdp11-its` verifies receipt-bound media, a usable Network UNIX-to-ITS TELNET session with remote `:TIME`, correlated traffic through both IMPs, a reducer-verified typed message-journey sidecar over fixed post-probe H316 trace windows, and complete cleanup. The sidecar records ten proven route-boundary observations and retains unproved destination-host ingress as missing evidence. Active revisions live in [`pins/`](../pins/).
- **Decision:** No required follow-up remains. Optional bounded investigations are `TIMOUT` or error-summary handling, output buffer chaining, the `IMP: Phantom Out Int` anomaly, and the non-fatal legacy TELNET option diagnostic.
- **Guardrails:** Do not reopen the accepted byte order, ITS leader handling, balanced RFNM accounting, receive continuation, topology, firmware, or application proof without contradictory exact-run evidence. The exploratory driver remains reproduction support, not a formal lifecycle or evidence owner.

### Network expansion

- **Read first:** [simulator configuration boundary](../config/README.md), the [fault](experiments/2026-08-31-ncc-alternate-path-fault.md) and [loopback](experiments/2026-08-31-ncc-line-loopback.md) records, and [ADR-009](adr/0009-ncc-paired-line-topology-boundary.md), [ADR-010](adr/0010-ncc-down-report-neighbor-absence.md), and [ADR-011](adr/0011-ncc-looped-report-self-neighbor.md).
- **State:** The two-IMP NCC attachment and coordinated three-IMP fault and loopback compositions are complete. [`imp5-ncc-host-interface.json`](../config/topologies/imp5-ncc-host-interface.json) owns the evidenced IMP 5/IMP 6 report-line mapping; [`ncc-alternate-path-fault.json`](../config/topologies/ncc-alternate-path-fault.json) adds IMP 7 and two deliberately unmapped alternate bindings. The formal two-ITS and PDP-11 harnesses are unchanged.
- **Decision:** No further route expansion is selected. Any new route is a coordinated NCC/network-expansion change with its own bounded claim and evidence.
- **Guardrails:** IMPs 5, 6, and 7 are configured test components, not asserted historical sites. Configuration alone does not establish a historical route, application exchange, live component, or line state. Never infer report-line identity from a SIMH device name or copy the direct binding's mapping onto alternate links.

## Integration procedure

1. Work and commit only in the selected clean feature worktree; preserve unrelated changes and keep third-party assets and raw logs in the external laboratory.
2. Run `make test` and the narrowest relevant external smoke before integration.
3. Fetch `origin`, rebase the feature branch onto current `origin/main`, and rerun the relevant checks. Never force-push `main`.
4. Fast-forward the integration checkout to the tested feature branch, rerun `make test`, and push `main`.
5. Advance other clean active branches to the new `main` only when needed; do not merge feature branches directly into one another.

## Starting a fresh task

1. Choose a workstream. If its handoff says no task is selected, discuss and select the bounded objective before implementation.
2. Open its recorded directory and read the root [`AGENTS.md`](../AGENTS.md), this page, and its **Read first** documents.
3. Confirm the expected branch and a clean or understood `git status --short --branch`; do not disturb another worktree's changes.
4. State the objective, evidence required, and explicit out-of-scope components.
5. Treat ADRs and dated findings as settled unless new exact-run or primary-source evidence contradicts them.

Update this page only when an active directory or branch, selected task, decision point, or integration policy changes. Link to the owning document for implementation detail, evidence, and acceptance criteria.
