# Workstreams

- **Updated:** 2026-09-04
- **Canonical repository:** [`brfid/arpanet-redux`](https://github.com/brfid/arpanet-redux)
- **Integration policy:** Keep `main` test-passing; develop in dedicated branches and worktrees.

This page owns active local checkouts, selected work, and decision points. The [README](../README.md) owns public status, subsystem pages own current contracts, [ADRs](adr/README.md) own decisions, and [dated notes](experiments/README.md) own evidence.

## Current direction

The project is a vintage-computing laboratory. Prioritize independent setup, understandable live and failed runs, reliable operation and recovery, and useful guest sessions. Website-pipeline integration is retired as a project goal; dated decisions retain the context in which they were made. New applications, hosts, and historically dated addressing follow improvements to operating the existing laboratory.

## Local checkouts

| Directory | Branch | Use |
|---|---|---|
| `/Users/brf/src/arpanet-redux` | `main` | Integration only |
| `/Users/brf/src/arpanet-redux-worktrees/base-media` | `codex/base-media` | Reconstruct Network UNIX base disks from pinned external inputs and verify fresh setup |

This table lists attached checkouts. An integrated branch is deleted rather than retained, per Branch safety below; start future work from current `main` in a fresh dedicated worktree.

Selected laboratory-usability work: replace the undocumented prepared-disk dependency with an original, deterministic reconstruction helper using pinned historical inputs held in the external laboratory. Retain existing accepted media and evidence. Required evidence is repeatable output hashes, safe failure on changed inputs or occupied destinations, and a fresh guest build followed by the existing direct TELNET gate. Historical protocol, simulator, and acceptance decisions remain settled.

One optional branch is parked with no attached worktree: `research/historical-addressing-model`, on `origin`, containing unintegrated historical-addressing work. It is not queued for review or integration; inspect its current divergence before reviving it. See the historical addressing handoff below before deliberately reviving work that touches shared topology, address identifiers, or `config/`.

The external laboratory is `/Users/brf/src/arpanet-redux-lab`; it holds third-party inputs and raw results, not Git worktree state. GitHub `origin` is canonical. Treat `gitlab` as historical unless explicitly directed otherwise.

## Branch safety

`origin/main` is the archive. Its history is linear, so an integrated branch ref preserves nothing that `origin/main` does not already hold; delete such a branch once its work is on `origin/main`. Dated experiment records and ADRs cite the commit identities that matter, and tags pin release points.

Keep a recovery anchor only while a specific rewrite is unsettled, meaning `main` has not yet been verified and built upon. Record it here with its ref, SHA, and the rewrite it protects, then delete it when that rewrite settles. There are no open anchors.

Prefer reverting the relevant commit on `main` for an ordinary rollback. Never switch, remove, or repurpose a worktree with uncommitted changes.

## Current handoffs

| Workstream | State | Decision | Read first |
|---|---|---|---|
| Laboratory usability | Retained-run diagnostics and cleanup evidence are complete. Base reconstruction now produces an exact pinned pair from public historical inputs, preserves the legacy pair, and checks complete-pair identity at build and receipt verification. A fresh lab exposed and verified a nested-checkout setup repair; two assemblies matched, guest filesystem checks and compilation passed, and direct Gate 4H retained twelve complete observations with cleanup. All 392 source tests passed with one expected UDP sandbox skip | Finish integration of the verified reconstruction batch. Remaining usability work includes failures before result creation, live startup stages, broader recovery exercises, and persistent guest workspaces; missing evidence remains unknown. Historical protocols and acceptance rules remain settled | [Base reconstruction](experiments/2026-09-04-pdp11-base-reconstruction.md), [base-media contract](pdp11-base.md), [cleanup evidence](experiments/2026-09-04-launcher-cleanup.md), [run diagnostics](runbook.md#diagnose-a-retained-run) |
| Documentation | Current pages use one owner per concern; experiments and research remain dated records; source, link, and soft-wrap checks pass. Retained-result media pruning now has a tracked, fail-closed helper and source-only coverage | No follow-up is selected; start later work from current `main` in a clean worktree | [README](../README.md), [architecture](architecture.md), [test plan](test-plan.md) |
| NCC | Genuine reports, paired `up`/`down`/`looped` states, typed journeys, coexistence, same-session application failover, and terminal-owned runners feed one fail-closed mid-1970s-style operator console with a banked annunciator, log, and quick summary | No required follow-up. Keep the console read-only and discovered application-link report identities candidate-only; browser input and simulator controls require a separate authority decision | [NCC observability](ncc.md), [telemetry research](research/2026-08-30-ncc-telemetry.md) |
| PDP-11 TELNET | Gate 4H, receipt-bound media, remote `:TIME`, correlated IMP evidence, and a complete twelve-observation direct journey include independent KA10 request-ingress and IMP11-A reply-ingress traces; deterministic repeated commands, clean option negotiation, and a safe character-oriented Network UNIX terminal continue to use the preserved client's command, mode, and protocol controls. Gate 4K now composes that terminal with the accepted four-IMP failover topology: one local Control-^ cuts the run-owned direct relay only after a proved transaction, and one structured post-cut `:TIME` returns through IMP 7 in the same guest session | No required follow-up. Keep the direct terminal profile unchanged, the interactive cut controller-owned, and the human evaluator independent of passive NCC reports. Browser authority, report-line promotion, a guest-protocol implementation, a new host-interface claim, full-screen terminal behavior, and historical addressing remain separate optional decisions | [interactive failover result](experiments/2026-09-04-interactive-pdp11-its-failover.md), [ADR-018](adr/0018-interactive-telnet-failover.md), [Gate 4K](test-plan.md#gate-4k-interactive-same-session-telnet-failover) |
| KA10 host ingress | Versioned observation-only assembly and matching `DATAI` records independently reconstruct the exact direct Gate 4H request, so `boundary:request:6` is accepted with direct provenance at simulator revision `4b59f21d`; that result and replay remain immutable at their recorded `boundary:reply:6` stop | No required follow-up. The separate IMP11-A decision closes the current direct journey but does not extend this KA10 evidence to reply egress, coexistence, failover, a complete guest grammar, or a protocol/application claim | [ADR-016](adr/0016-ka10-request-ingress-evidence.md), [accepted experiment](experiments/2026-09-02-ka10-request-ingress.md), [IMP11-A successor](adr/0017-imp11a-reply-ingress-evidence.md) |
| Network expansion | The three-IMP fault, loopback, coexistence, board, and failover compositions are integrated | No expansion is selected. A new host, IMP, mapping, or claim requires a separate bounded decision and evidence. A composition that would duplicate topology, configuration, evaluator, and Make-target wiring triggers deferred RM-09 | [Configuration boundary](../config/README.md), [ADR-009](adr/0009-ncc-paired-line-topology-boundary.md), [closed maintenance plan](repository-maintenance.md) |
| Historical addressing | A dated note on `main` evaluates the July 1975 *ARPANET Directory* (NIC 32992): ITS `106` is confirmed as MIT-DMS and needs no change, `176` decodes to an IMP the 1975 network had not reached, and RAND-ISO at `107` is the only supported PDP-11 UNIX target. No address, configuration, or run has changed on `main`. Phases 3 and 4 — an authority extract with site-claim validation, and role renames for the identifiers no retained result depends on — exist only on the parked branch `research/historical-addressing-model` | Optional and not selected. If revived, first review and rebase the branch, decide whether the project asserts dated historical host identity at all, and record the directory's formal source pin and redistribution status before treating it as active schema authority. Phase 5 re-addresses the PDP-11 and still requires fresh accepted runs of Gates 3, 4, 4H, 4I, 4J, 5 and both NCC gates; do not land it on inference | [Addressing evidence](research/2026-09-02-1975-host-addressing.md), [configuration boundary](../config/README.md) |

Do not reopen accepted byte order, leader handling, RFNM accounting, topology, report-line identity, state-specific neighbor rules, or application proof without new contradictory exact-run evidence. IMPs 5, 6, and 7 remain configured test components, not historical-site claims. That statement still holds for `main`; the parked historical-addressing branch proposes replacing it with dated, cited host identity, and would need a new selection decision before review or integration. Displays remain passive; the failover cut remains controller-owned.

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
