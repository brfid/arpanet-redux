# Workstreams

- **Updated:** 2026-09-03
- **Canonical repository:** [`brfid/arpanet-redux`](https://github.com/brfid/arpanet-redux)
- **Integration policy:** Keep `main` test-passing; develop in dedicated branches and worktrees.

This page owns active local checkouts, selected work, and decision points. The [README](../README.md) owns public status, subsystem pages own current contracts, [ADRs](adr/) own decisions, and dated notes own evidence.

## Local checkouts

| Directory | Branch | Use |
|---|---|---|
| `/Users/brf/src/arpanet-redux` | `main` | Integration only |
| `/Users/brf/src/arpanet-redux-worktrees/maintenance` | `codex/repository-maintenance` | Repository-organization maintenance plan and bounded remediation |

This table lists attached checkouts, not every retained branch. Settled workstream branches remain available as refs after their clean, main-merged worktrees are retired; start future work from current `main` in a fresh dedicated worktree rather than reusing those branches.

One unmerged development branch is currently awaiting review and has no attached worktree: `research/historical-addressing-model`, on `origin`, five commits ahead of `main`. See the historical addressing handoff below before starting work that touches shared topology, address identifiers, or `config/`.

The external laboratory is `/Users/brf/src/arpanet-redux-lab`; it holds third-party inputs and raw results, not Git worktree state. GitHub `origin` is canonical. Treat `gitlab` as historical unless explicitly directed otherwise.

## Branch safety

`codex/ncc-telemetry` and `codex/ncc-run-summary` preserve integrated history and are not development branches. These refs are recovery anchors, not development branches:

- `backup/pre-ncc-integration-20260830` at `d16b5d9`
- `backup/ncc-pre-rebase-20260830` at `bee5c91`
- `backup/main-pre-squash-20260903` at `0db5d00`, local only; it preserves `main` before two documentation commits were squashed into `4961d70`. Delete it once that rewrite is settled.

Do not delete, rebase, merge into, or develop on a recovery ref. Prefer reverting the relevant commit on `main` for an ordinary rollback. Never switch, remove, or repurpose a worktree with uncommitted changes.

## Current handoffs

| Workstream | State | Decision | Read first |
|---|---|---|---|
| Repository maintenance | Phases 1 and 2 are complete; RM-07 gives both two-ITS and direct PDP-11 controllers ordinary focused harness owners, each with a passing real smoke | Immediate: replace the failover controller's dynamic direct-controller load with ordinary imports. Following, as a separate smoke-verified migration: migrate the interactive controller and remove temporary compatibility exports | [Repository maintenance plan](repository-maintenance.md), [harness design](harness.md), [test plan](test-plan.md) |
| Documentation | Current pages use one owner per concern; experiments and research remain dated records; source, link, and soft-wrap checks pass | No follow-up is selected; start later work from current `main` in a clean worktree | [README](../README.md), [architecture](architecture.md), [test plan](test-plan.md) |
| NCC | Genuine reports, paired `up`/`down`/`looped` states, typed journeys, coexistence, same-session application failover, and terminal-owned runners feed one fail-closed mid-1970s-style operator console with a banked annunciator, log, and quick summary | No required follow-up. Keep the console read-only and discovered application-link report identities candidate-only; browser input and simulator controls require a separate authority decision | [NCC observability](ncc.md), [telemetry research](research/2026-08-30-ncc-telemetry.md) |
| PDP-11 TELNET | Gate 4H, receipt-bound media, remote `:TIME`, correlated IMP evidence, an eleven-observation direct journey through ITS request ingress, deterministic repeated commands, clean option negotiation, and a safe character-oriented Network UNIX terminal using the preserved client's command, mode, and protocol controls are integrated | No required follow-up. A cursor-addressed terminal profile, host-176 reply ingress, or remaining bounded NCP anomaly requires separate evidence and may not be filled by inference | [IMP11-A record](research/imp11a-device.md), [KA10 request-ingress result](experiments/2026-09-02-ka10-request-ingress.md), [historical terminal result](experiments/2026-09-01-historical-network-unix-telnet-terminal.md) |
| KA10 host ingress | Versioned observation-only assembly and matching `DATAI` records independently reconstruct the exact direct Gate 4H request, so `boundary:request:6` is accepted with direct provenance at simulator revision `4b59f21d`; the exact run and read-only replay both stop at `boundary:reply:6` | No required follow-up. Do not extend this result to KA10 reply egress, host-176 ingress, coexistence, failover, a complete guest grammar, or a protocol/application claim without a separately fixed evidence window and decision | [ADR-016](adr/0016-ka10-request-ingress-evidence.md), [accepted experiment](experiments/2026-09-02-ka10-request-ingress.md), [earlier feasibility result](experiments/2026-09-01-ka10-host-ingress-grammar.md) |
| Network expansion | The three-IMP fault, loopback, coexistence, board, and failover compositions are integrated | No expansion is selected. A new host, IMP, mapping, or claim requires a separate bounded decision and evidence | [Configuration boundary](../config/README.md), [ADR-009](adr/0009-ncc-paired-line-topology-boundary.md) |
| Historical addressing | A dated note on `main` establishes the July 1975 *ARPANET Directory* (NIC 32992) as an address authority: ITS `106` is confirmed as MIT-DMS and needs no change, `176` decodes to an IMP the 1975 network had not reached, and RAND-ISO at `107` is the only supported PDP-11 UNIX target. No address, configuration, or run has changed on `main`. Phases 3 and 4 — an authority extract with site-claim validation, and role renames for the identifiers no retained result depends on — are implemented on the unmerged branch `research/historical-addressing-model` | Blocking: decide whether the project asserts dated historical host identity at all, since the branch's `site` claim contradicts the standing statement below that IMPs 5, 6, and 7 are not historical-site claims. Then the note's three remaining open decisions. Phase 5 re-addresses the PDP-11 and requires fresh accepted runs of Gates 3, 4, 4H, 4I, 4J, 5 and both NCC gates; do not land it on inference | [Addressing evidence](research/2026-09-02-1975-host-addressing.md), [configuration boundary](../config/README.md) |

Do not reopen accepted byte order, leader handling, RFNM accounting, topology, report-line identity, state-specific neighbor rules, or application proof without new contradictory exact-run evidence. IMPs 5, 6, and 7 remain configured test components, not historical-site claims. That statement still holds for `main`; the unmerged historical addressing branch proposes replacing it with dated, cited host identity, and merging it is the decision that would retire it. Displays remain passive; the failover cut remains controller-owned.

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
