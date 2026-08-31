# Parallel workstreams and fresh-context handoff

- **Updated:** 2026-08-30
- **Canonical repository:** [`brfid/arpanet-redux`](https://github.com/brfid/arpanet-redux)
- **Integration policy:** `main` remains test-passing and receives completed feature slices; feature work happens in dedicated branches and worktrees

## Local worktree convention

This machine uses one Git repository with an integration checkout and a grouped worktree container. They share Git object storage and remote history but have independent checked-out branches and uncommitted files.

| Local directory | Active branch | Role |
|---|---|---|
| `/Users/brf/src/arpanet-redux` | `main` | Integration only; do not begin feature work here |
| `/Users/brf/src/arpanet-redux-worktrees/ncc` | `codex/ncc-run-summary` | NCC event model, derived run summary, replay, and visualization |
| `/Users/brf/src/arpanet-redux-worktrees/telnet` | `codex/pdp11-telnet` | SRI/NOSC PDP-11 TELNET diagnosis and eventual formal application proof |
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

Read [`docs/research/imp11a-device.md`](research/imp11a-device.md) and [`docs/research/pdp11-network-unix.md`](research/pdp11-network-unix.md) before resuming the application proof.

One real bug has been found, fixed, and confirmed fixed, and a second, separate one remains open. The guest's 1822-level leader and this project's IMP fabric are both confirmed working correctly, byte-for-byte. The first bug was inside the preserved NCP daemon (`ncpd/` in `network-unix-v6`): its own defensive `chk_host()` sends a reset (RST) before every connection attempt to a host not yet known to be up, and that RST's own send marked the host's RFNM-tracking bit, which then blocked the real RFC queued moments later from ever being sent — a bookkeeping deadlock, not a network problem. [`scripts/research/build-guest-ncpd.py`](../scripts/research/build-guest-ncpd.py) patches `ncpd/kr_dcode.c` (clearing the bit right after `chk_host()` returns) and rebuilds `Largedaemon` from source with V6's own `cc`, entirely in-guest; a rerun confirms the daemon now genuinely sends the real 10-word RFC where it previously only ever sent the 5-word RST. See [the dated root-cause and patch write-up](research/imp11a-device.md#the-real-root-cause-an-rfnm-bookkeeping-deadlock-not-a-leader-or-transport-problem-2026-08-30-continued) in the IMP11-A device record for the full source trace, the three real build issues the daemon rebuild surfaced (none in the patch itself), and the empirical confirmation. A workaround tried first (having ITS dial the guest before the guest dials ITS, so it would already look "up" — real historical fidelity, not a synthetic shortcut) got a genuine inbound RFC to the guest's device but did not unblock it; the script for that (`scripts/research/its-speaks-first-then-pdp11-telnet.py`) is kept as a working, reusable tool, not deleted, since the approach remains valid in principle.

The connection still does not complete: IMP 62 does not relay the guest's traffic toward IMP 6 via `MI1` even for the now-genuine, complete RFC — the same fate as the RST before it, ruling out anything RST-specific. This is the same relay gap the previous session flagged, now confirmed independent of the daemon bug and still not isolated. That is the next evidence-producing action.

The current driver under `scripts/research/` is exploratory, not a formal harness: it does not yet own the standard run manifest, port lease, exact acceptance verdict, or failure gates.

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
