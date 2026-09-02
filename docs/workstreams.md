# Workstreams

- **Updated:** 2026-09-01
- **Canonical repository:** [`brfid/arpanet-redux`](https://github.com/brfid/arpanet-redux)
- **Integration policy:** Keep `main` test-passing; develop in dedicated branches and worktrees.

This page owns active local checkouts, selected work, and decision points. The [README](../README.md) owns public status, subsystem pages own current contracts, [ADRs](adr/) own decisions, and dated notes own evidence.

## Local checkouts

| Directory | Branch | Use |
|---|---|---|
| `/Users/brf/src/arpanet-redux` | `main` | Integration only |
| `/Users/brf/src/arpanet-redux-worktrees/docs` | `codex/docs-concision` | Documentation maintenance |
| `/Users/brf/src/arpanet-redux-worktrees/ncc` | `codex/ncc-failover-board` | Passive failover projection and terminal runner |
| `/Users/brf/src/arpanet-redux-worktrees/telnet` | `codex/pdp11-telnet` | Accepted Gate 4H, typed journey, and interactive TELNET |
| `/Users/brf/src/arpanet-redux-worktrees/network` | `codex/ncc-line-loopback-proof` | Accepted line-state proof and coordinated expansion |

The external laboratory is `/Users/brf/src/arpanet-redux-lab`; it holds third-party inputs and raw results, not Git worktree state. GitHub `origin` is canonical. Treat `gitlab` as historical unless explicitly directed otherwise.

## Branch safety

`codex/ncc-telemetry` and `codex/ncc-run-summary` preserve integrated history and are not development branches. These refs are recovery anchors, not development branches:

- `backup/pre-ncc-integration-20260830` at `d16b5d9`
- `backup/ncc-pre-rebase-20260830` at `bee5c91`

Do not delete, rebase, merge into, or develop on a recovery ref. Prefer reverting the relevant commit on `main` for an ordinary rollback. Never switch, remove, or repurpose a worktree with uncommitted changes.

## Current handoffs

| Workstream | State | Decision | Read first |
|---|---|---|---|
| Documentation | Current pages use one owner per concern; experiments and research remain dated records; source, link, and soft-wrap checks pass | No follow-up is selected; start later work from current `main` in a clean worktree | [README](../README.md), [architecture](architecture.md), [test plan](test-plan.md) |
| NCC | Genuine reports, paired `up`/`down`/`looped` states, typed journeys, coexistence, same-session application failover, its fail-closed board projection, terminal-owned runners, and the separate interactive TELNET stream are integrated | No required follow-up. Optional passive session-status presentation must remain read-only; browser input and simulator controls require a separate authority decision. Keep discovered application-link report identities candidate-only | [NCC observability](ncc.md), [interactive TELNET](experiments/2026-09-01-interactive-pdp11-its-telnet.md) |
| PDP-11 TELNET | Gate 4H, receipt-bound media, remote `:TIME`, correlated IMP evidence, ten-observation typed journey, bounded repeated operator commands in one session, a staged terminal boot display, and cleanup pass | No required follow-up. Optional work includes character-oriented terminal behavior or bounded legacy-client and NCP anomalies; neither may fill the unproved guest-ingress boundaries by inference | [IMP11-A record](research/imp11a-device.md), [Network UNIX research](research/pdp11-network-unix.md) |
| Network expansion | The three-IMP fault, loopback, coexistence, board, and failover compositions are integrated | No expansion is selected. A new host, IMP, mapping, or claim requires a separate bounded decision and evidence | [Configuration boundary](../config/README.md), [ADR-009](adr/0009-ncc-paired-line-topology-boundary.md) |

Do not reopen accepted byte order, leader handling, RFNM accounting, topology, report-line identity, state-specific neighbor rules, or application proof without new contradictory exact-run evidence. IMPs 5, 6, and 7 remain configured test components, not historical-site claims. Displays remain passive; the failover cut remains controller-owned.

## Integrate a workstream

1. Work and commit only in the selected clean worktree. Preserve unrelated changes and keep third-party inputs and raw results in the laboratory.
2. Run `make test` and the narrowest relevant external smoke.
3. Fetch `origin`, rebase the feature branch onto current `origin/main`, and rerun relevant checks.
4. Fast-forward the integration checkout to the tested feature branch, run `make test`, and push `main`. Never force-push `main`.
5. Advance another clean active branch only when it needs the new `main`; do not merge feature branches into one another.

## Start a task

1. Choose a workstream and a bounded objective. If no task is selected, decide one before implementation.
2. Open its recorded worktree and read [`AGENTS.md`](../AGENTS.md), this page, and the workstream's **Read first** documents.
3. Confirm the expected branch and an understood `git status --short --branch`.
4. State the claim, required evidence, and explicit exclusions.
5. Treat ADRs and dated findings as settled unless new exact-run or primary-source evidence contradicts them.

Update this page only when a checkout, active task, decision point, or integration policy changes.
