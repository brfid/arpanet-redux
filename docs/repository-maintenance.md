# Repository maintenance plan

- **Status:** Active
- **Updated:** 2026-09-02
- **Baseline:** `6baf5d041f5ddf62045b4c16bf905b526ac715e2`
- **Active phase:** Phase 3 — harness boundary
- **Worktree:** `/Users/brf/src/arpanet-redux-worktrees/maintenance`
- **Branch:** `codex/repository-maintenance`

## Purpose

This living plan owns the selected sequence, acceptance evidence, and resumable checkpoint for repository-organization maintenance. The [workstreams page](workstreams.md) owns active checkouts and handoffs, the [architecture](architecture.md) owns stable system boundaries, the [test plan](test-plan.md) owns formal acceptance claims, and ADRs own lasting design decisions.

The objective is to make the implementation reflect the repository's already-strong conceptual boundaries without changing accepted historical, application, network, or evidence semantics.

## Invariants

- Keep `main` as the integration checkout and perform development in the worktree recorded above.
- Preserve every existing Make target and executable script path unless a separately reviewed compatibility decision says otherwise.
- Do not change configured-fact, direct-evidence, harness-evidence, inference, missing-evidence, or verdict authority while reorganizing code.
- Treat accepted ADRs and dated findings as settled unless new exact-run evidence contradicts them.
- Keep topology documents complete and independently hashable; do not introduce topology inheritance merely to remove repeated configuration.
- Extract only mechanical behavior from scenario-specific validators. A shared helper may not make one scenario's evidence sufficient for another scenario.
- Keep source-only tests free of downloads, external media, simulator startup, and laboratory mutation.
- Keep third-party material, generated artifacts, raw logs, and retained run evidence in the external laboratory.
- Make each work item independently reviewable and reversible, with source-only verification and the narrowest relevant external smoke when runtime behavior changes.

## Baseline observations

- `make test` completed at the baseline commit. `unittest` discovered 282 tests and reported one sandbox-related skip; four historical-summary methods were discovered twice under different module names, leaving 278 unique class-and-method identities. The separate runtime test also skipped its sandbox-prohibited socket probe.
- `tests/test_ncc_board.py` imports and instantiates `HistoricalLineSummaryTests` as fixture support, causing the duplicate discovery.
- Importing `ncc.events` initializes 37 `ncc` modules because `ncc/__init__.py` eagerly re-exports the package. The repository uses direct submodule imports, and the initializer's board exports have already drifted from `__all__`.
- The four passive HTTP server modules share approximately 63–71 percent of their ordered lines, and the alternate-path fault and loopback smoke scripts share approximately 89 percent.
- The two-ITS, PDP-11, failover, and interactive controllers dynamically load hyphenated sibling scripts. Their principal `run` functions are 261, 326, 357, and 569 lines respectively.
- CI currently runs on pushes using Ubuntu and Python 3.11, while the documented source contract is Python 3.11 or newer on macOS and Linux.
- The tracked workstream registry and the untracked editor workspace do not exactly match the current local worktree layout. All currently attached non-main branches are contained in `main`, but no worktree should be removed without a fresh clean-state and ancestry check.

## Work inventory

Priority is `(impact + risk) × (6 - effort)`, with each input rated from 1 to 5. The score favors safe, high-return work; it does not make a large strategic refactor less important.

| ID | Category | Work item | Impact | Risk | Effort | Priority | Estimate | Status |
|---|---|---|---:|---:|---:|---:|---|---|
| RM-01 | Test debt | Move reusable historical-line result construction out of a `unittest.TestCase` and eliminate duplicate discovery | 3 | 3 | 1 | 30 | Less than half a day | Completed |
| RM-02 | Architecture debt | Minimize `ncc/__init__.py` and make direct submodules the explicit package boundary | 4 | 3 | 2 | 28 | Half to one day | Completed |
| RM-03 | Infrastructure debt | Make CI exercise pull requests and the documented Python and operating-system support edges | 3 | 4 | 2 | 28 | Half to one day | Completed |
| RM-05 | Code debt | Extract neutral passive-HTTP transport mechanics while retaining separate display applications | 4 | 4 | 3 | 24 | Two to four days | Completed |
| RM-04 | Documentation debt | Reconcile active-worktree documentation and local editor-workspace policy | 2 | 2 | 1 | 20 | Less than half a day | Completed |
| RM-07 | Architecture debt | Move reusable process, PTY, manifest, readiness, and cleanup behavior into an importable harness package | 5 | 4 | 4 | 18 | Four to eight days | In progress |
| RM-06 | Code debt | Share the fault and loopback smoke lifecycle without sharing their evaluators or verdict rules | 4 | 4 | 4 | 16 | Two to four days | Completed |
| RM-08 | Documentation debt | Add concise ADR and experiment indexes organized by claim and successor | 2 | 2 | 2 | 16 | Half to one day | Not started |
| RM-09 | Architecture debt | Introduce a scenario registry only when another composition needs the duplicated wiring | 3 | 3 | 4 | 12 | Two to four days | Deferred until triggered |

## Execution sequence

### Phase 1 — quick correctness and hygiene

1. Complete RM-01 so the test count reflects distinct tests and reusable fixture code has a non-test owner.
2. Complete RM-02 without moving production modules: reduce package import side effects first, then consider physical subpackages only if later extractions reveal a stable boundary.
3. Complete RM-03 by adding pull-request coverage, the minimum and newest supported Python versions, and one macOS source-only job while retaining the existing Linux job.
4. Complete RM-04 by distinguishing active worktrees from retained merged checkouts and deciding whether the local editor workspace should be repaired and ignored or replaced by a portable tracked file.

### Phase 2 — mechanical deduplication

1. Complete RM-05 by extracting response serialization, loopback binding, method rejection, security headers, and handler dispatch into a neutral transport module. Keep route selection, pending behavior, display errors, and snapshot production in the individual applications.
2. Complete RM-06 by extracting the common alternate-path lifecycle into `scripts/lib/` with an explicit fault or loopback mode. Preserve separate launchers, result names, evaluator programs, evidence artifacts, and verdict contracts.

### Phase 3 — harness boundary

Complete RM-07 incrementally. First move process and PTY ownership without changing a controller flow; then move manifest and readiness primitives; finally migrate the two-ITS, direct PDP-11, failover, and interactive controllers one at a time. Existing scripts remain thin command-line entry points throughout the migration.

### Phase 4 — navigation

Complete RM-08 after the code movement settles so indexes point at stable owners. Index entries should summarize subject, status, affected composition, and successor without copying the underlying decision or evidence.

### Phase 5 — conditional scenario registry

Start RM-09 only when a new composition would otherwise add another copy of the topology, configuration, evaluator, result-prefix, duration, and Make-target association. The registry may connect complete artifacts but must not fragment or inherit topology evidence.

## Acceptance by work item

### RM-01 — test fixture boundary

- Reusable result construction lives under `tests/support/` and contains no `unittest.TestCase` subclass.
- `tests/test_ncc_board.py` imports fixture support rather than another test case.
- Historical-summary behavior and board coverage remain unchanged.
- Test discovery contains no duplicate class-and-method identity.
- `make test` passes.

### RM-02 — package facade

- Importing a focused `ncc` submodule does not eagerly import unrelated displays, servers, controllers, or viewers.
- All in-repository imports continue to use their owning submodules.
- Any retained top-level exports are intentional, documented, and covered by a compatibility test.
- `make test` passes.

### RM-03 — CI support contract

- Pull requests run source-only checks before merge.
- CI covers Python 3.11 and the newest supported stable Python release.
- At least one source-only job runs on macOS, while full-history source guarding remains on a full clone.
- Local `make test` remains the single developer entry point.

### RM-04 — worktree and editor state

- `docs/workstreams.md` accurately distinguishes active work from retained or inactive checkouts.
- Every removal candidate is clean and its branch ancestry is checked immediately before removal.
- The integration checkout can remain clean during normal editor use.

### RM-05 — passive HTTP transport

- GET, HEAD, method rejection, fixed-route behavior, security headers, content length, loopback binding, and quiet logging remain byte-for-byte or assertion-equivalent where currently contractual.
- Board, historical, journey, and coexistence applications retain their own route and error semantics.
- Transport tests exercise the shared implementation and every application adapter.
- `make test` passes.

### RM-06 — line-scenario lifecycle

- Fault and loopback launchers retain distinct public commands, result directories, instruments, evaluators, verdicts, and cleanup evidence.
- Shell syntax and dry-run command tests pass.
- Both external alternate-path smokes pass at the current pins before integration.

### RM-07 — importable harness

- No controller uses `importlib.util.spec_from_file_location` to load a sibling production script.
- Reusable lifecycle code has ordinary underscore-named module imports and focused unit tests.
- Existing script paths, Make targets, arguments, artifacts, timeouts, and cleanup semantics remain stable.
- Each migrated controller passes `make test` and its narrowest accepted external smoke before the next controller moves.

### RM-08 — documentation indexes

- ADR and experiment directories each have one concise index.
- Every entry links to its source and identifies status or evidentiary scope without restating conclusions.
- Local-link and Markdown soft-wrap checks pass.

### RM-09 — scenario registry

- The triggering new composition demonstrates that a registry removes real cross-file association drift.
- The registry names complete topology and configuration artifacts rather than composing topology fragments.
- Make, doctor, runner, and documentation consumers agree on one validated scenario identity.

## Resume in a fresh context

Start in the recorded maintenance worktree and read [`AGENTS.md`](../AGENTS.md), the repository-maintenance row in [`docs/workstreams.md`](workstreams.md), [`docs/harness.md`](harness.md), and the applicable gates in [`docs/test-plan.md`](test-plan.md). Fetch `origin` and compare the clean maintenance branch with `origin/main` before editing. Fast-forward when the maintenance branch is an ancestor; if both sides have commits, rebase it onto `origin/main` and rerun the relevant checks. Treat **Selected** and **Next action** below as the complete immediate scope; do not begin **Following action** in the same change.

## Current checkpoint

- **Last completed:** `Extract importable harness process owners` moves the characterized PTY and IMP child ownership into `ncc.harness_process` and its validated append dependency into `ncc.harness_manifest`. The two-ITS controller now imports those owners normally while preserving compatibility aliases for unmigrated dependent controllers, its public command, arguments, flow, logs, PID fields, state transitions, timeouts, and cleanup behavior.
- **Selected:** RM-07, manifest and readiness primitives.
- **Next action:** Characterize the remaining manifest hashing and generic log-readiness contracts in `scripts/two-its-controller.py`, then move them into focused ordinary harness modules without changing controller behavior.
- **Following action:** After that slice is committed, integrated, and smoke-verified, remove `scripts/pdp11-its-controller.py`'s dynamic sibling load in its own separately verified migration.
- **Blockers:** None.
- **Last verification:** The focused process and dependent-controller suites passed 42 tests; formal run `two-its-telnet-maintenance-rm07-process-20260902` passed Gates 4 and 5 at the pinned external sources and simulator binaries with clean repository identity and complete cleanup; [GitHub Actions run 33696737623](https://github.com/brfid/arpanet-redux/actions/runs/33696737623) passed Linux on Python 3.11 and 3.14 plus macOS on Python 3.14. Handoff hardening then passed 294 discovered tests with the expected sandbox socket skips and completed the real external `lab-setup` path with exact clean pins and all three native simulator builds.

## Update protocol

- At the start of work, fetch `origin`; confirm the recorded branch, worktree, baseline, selected item, and `git status --short --branch`; then compare the maintenance branch with `origin/main` as described above.
- At the end of each bounded change, update the work-item status and this checkpoint with the commit subject, verification commands and results, next action, and genuine blockers.
- Store only concise conclusions and artifact identities here. Raw command output and external run evidence stay outside the repository.
- Record a lasting design decision in an ADR and link it here; do not let this plan become a substitute decision record.
- When all unconditional items are complete, mark the plan complete and remove the active maintenance handoff from `docs/workstreams.md`. Git history remains the archive.

## Decision log

- **2026-09-02:** Use this detailed plan as the execution ledger and keep `docs/workstreams.md` as its concise router.
- **2026-09-02:** Prefer incremental extractions with stable entry points over a wholesale directory move.
- **2026-09-02:** Preserve complete topology documents and scenario-specific evidence validators even where their shapes overlap.
- **2026-09-02:** Treat owning `ncc` submodules as the Python package boundary; repository use and history provide no evidence for retaining an aggregate root facade.
- **2026-09-02:** Exercise both the documented Python 3.11 lower bound and current stable 3.14 series on Linux, add a 3.14 macOS edge, and keep complete-history guarding in one non-shallow job.
- **2026-09-02:** Use the Node 24-based version 6 majors of the official checkout and Python setup actions after the first expanded matrix run exposed Node 20 deprecation warnings from the older majors.
- **2026-09-02:** Keep editor workspace configuration local and ignored, list only attached checkouts in `docs/workstreams.md`, and retain settled branch refs when removing their clean, main-merged worktrees.
- **2026-09-02:** Pass the system zlib link explicitly to the pinned KA10 build on Darwin because its legacy Makefile recognizes physical `.dylib` files but not Apple's SDK stub; keep other platforms and simulator targets unchanged.
