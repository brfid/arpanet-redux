# Parallel workstreams and fresh-context handoff

- **Updated:** 2026-08-31
- **Canonical repository:** [`brfid/arpanet-redux`](https://github.com/brfid/arpanet-redux)
- **Integration policy:** `main` remains test-passing and receives completed feature slices; feature work happens in dedicated branches and worktrees

## Local worktree convention

This machine uses one Git repository with an integration checkout and a grouped worktree container. They share Git object storage and remote history but have independent checked-out branches and uncommitted files.

| Local directory | Active branch | Role |
|---|---|---|
| `/Users/brf/src/arpanet-redux` | `main` | Integration only; do not begin feature work here |
| `/Users/brf/src/arpanet-redux-worktrees/ncc` | `codex/ncc-run-summary` | NCC event model, derived run summary, replay, and visualization |
| `/Users/brf/src/arpanet-redux-worktrees/telnet` | `codex/pdp11-telnet` | Completed SRI/NOSC PDP-11 TELNET application proof and formal Gate 4H harness |
| `/Users/brf/src/arpanet-redux-worktrees/network` | `codex/network-expansion` | Additional IMPs, hosts, topology, and the notes that establish those changes |

The separate external laboratory is `/Users/brf/src/arpanet-redux-lab`; it is not a Git worktree, and the [runbook](runbook.md) owns its layout and handling. The GitHub `origin` remote is canonical. The `gitlab` remote is retained as historical/secondary state but is not the upstream for `main` or the active workstream branches.

## Branch roles

`codex/ncc-telemetry` records the already-merged NCC foundation and is not the active NCC branch. New NCC work belongs on `codex/ncc-run-summary`.

Branches below `backup/` are recovery anchors, not development branches:

- `backup/pre-ncc-integration-20260830` points to `d16b5d9`, the exact integrated repository state before the NCC foundation was added.
- `backup/ncc-pre-rebase-20260830` points to `bee5c91`, the exact two-commit NCC history before it was rebased onto the completed TELNET-client commit.

Do not delete, rebase, merge into, or begin work on the backup branches. A public rollback should normally revert the relevant commits on `main`; the backup branches exist for comparison and recovery if that is insufficient.

## Current workstream handoffs

### NCC

Read [`docs/ncc.md`](ncc.md) and the dated [NCC telemetry research note](research/2026-08-30-ncc-telemetry.md) before changing `ncc/`, its schema, or a visualization.

Define and test the smallest safe derived run-summary contract over the formal two-ITS artifacts, using synthetic fixtures before reading real external results. [`docs/ncc.md`](ncc.md) owns the implemented-state summary, contract sequence, and product rationale.

NCC work must not depend on or modify the exploratory PDP-11 TELNET driver. Its first adapter should read the formal two-ITS manifest and derived evidence; a promoted heterogeneous harness can adopt the same contract later.

### PDP-11 TELNET

Read [`docs/research/imp11a-device.md`](research/imp11a-device.md) and [`docs/research/pdp11-network-unix.md`](research/pdp11-network-unix.md) before changing or promoting this proof. The earlier byte-order, ITS header-acceptance, and balanced control-link RFNM findings remain settled.

The application proof is complete. Trace-only control run `imp11a-telnet-sktrace-control-20260831T173527Z` showed that ITS's returned STR/RTS/STR control stream was present on the wire but never reached daemon decoding: the old `imp11a-device` model completed the guest's four-word leader DMA with `ENDMSG` and discarded the retained control text. Published simulator revision `2722eef44f68642eaab9f5d4e989ccd26e55e7de` now preserves surplus input across guest buffers, updates residual `IWC`, completes only on a full buffer or real end marker, and supplies robust fixed input/output interrupt vectors through DIB callbacks. [`../pins/sources.lock.toml`](../pins/sources.lock.toml) pins that canonical `origin/imp11a-device` revision.

Fresh daemon build `imp11a-ncpd-sktrace-final-build-20260831T192000Z` and exact final run `imp11a-telnet-usable-final-20260831T193000Z`, built and run by the current hardened scripts, record the returned contact socket transition to open, both data sockets, kernel ready code zero, `Connection open`, the ITS `TTY 53` welcome banner, and a remote `:TIME` response with time, date, and uptime on the PDP-11 console. This closes the heterogeneous-host application criterion without changing adapter byte order, H316 topology, firmware, ITS configuration, NCC, or network expansion. See [the dated device record](research/imp11a-device.md#receive-continuation-root-cause-and-usable-telnet-proof-2026-08-31) for the complete evidence chain.

Formal build `pdp11-telnet-formal-build-20260831T200328Z` rebuilds the guest TELNET client and staged trace daemon under published simulator `2722eef4` and retains a receipt binding both build stages, their exact sources and logs, every input and output image, the pinned Network UNIX and IMP11-A revisions, and builder and simulator hashes. Exact formal run `pdp11-its-telnet-20260831T200436Z` used six leased ports and the production standard-library PTY controller, passed Gate 4H with the ITS `53TLNT` service job and structured remote `:TIME`, recorded correlated post-probe traffic through both IMPs in both directions, and left no owned process, socket namespace, port lock, or build lease. The exploratory driver remains available only for historical reproduction; `make smoke-pdp11-its` owns the production-shaped run.

The formal promotion is complete. Remaining work is optional and must not reopen the accepted adapter, daemon, topology, firmware, or ITS findings without contradictory exact-run evidence: `TIMOUT`/error-summary handling, output buffer chaining, the `IMP: Phantom Out Int` anomaly, and the non-fatal legacy TELNET option diagnostic remain possible bounded investigations.

### Network expansion

This branch begins with no unmerged network-expansion change. Before editing shared simulator configurations or controllers, define the intended IMP/host identities, endpoint ports, logical-map positions, expected route, and exact evidence that will prove the new path. Read [`docs/architecture.md`](architecture.md), [`docs/test-plan.md`](test-plan.md), and [`docs/harness.md`](harness.md) first.

Nominal topology should become a shared project-authored input rather than being independently hard-coded by the harness, NCC reducer, and display. Until that contract is designed, keep experimental topology work isolated from the formal two-ITS controller.

## Integration procedure

For each workstream:

1. Work and commit only in its dedicated worktree and branch.
2. Preserve unrelated changes and keep third-party artifacts and raw logs in the external laboratory.
3. Run `make test` before proposing integration.
4. Fetch `origin`, rebase the feature branch onto current `origin/main`, and rerun the relevant tests. Never force-push `main`.
5. In the integration checkout, fast-forward `main` to the tested feature branch when possible, rerun `make test`, and push `main`.
6. Fast-forward other clean active branches to the new `main` when they need the integrated change; do not merge feature branches directly into one another.

If a worktree contains uncommitted changes, do not switch its branch, rebase it, remove it, or use it as an integration checkout. Commit a coherent checkpoint or make an explicit external backup first.

## Starting a fresh task

1. Choose the workstream and open its local directory, not the integration checkout.
2. Read the root [`AGENTS.md`](../AGENTS.md), this page, and the workstream-specific documents linked above.
3. Confirm `git status --short --branch` names the intended branch and does not contain unexpected work.
4. State the current bounded objective and the files or components that are out of scope.
5. Treat dated research and ADR findings as settled unless new exact-run or primary-source evidence changes them.

Update this page whenever a workstream's active branch, next evidence-producing task, canonical remote, or local worktree convention changes. Do not duplicate detailed research or acceptance criteria here; link to their owning documents.
