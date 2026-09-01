# Contributing to ARPANET Redux

Contributions should preserve the distinction between project source and externally obtained historical material.

## Before changing code

Read the [architecture](docs/architecture.md) for system boundaries and the [test plan](docs/test-plan.md) for normative evidence requirements. Dated experiment and research notes explain prior observations but do not override those documents.

Do not add firmware, disk or tape images, simulator executables, generated media, source checkouts, or raw logs. Do not copy an upstream simulator command file into `config/`; express only the minimal project-specific configuration and document its dependency in `config/README.md`.

## Checks

Run the source-only suite before proposing a change:

```sh
make test
make check-source-history
```

If the required external laboratory is available, follow [the runbook](docs/runbook.md) and run the narrowest affected verification or smoke target. Report the result directory and manifest, not generated artifacts.

The optional local guard can be enabled with:

```sh
git config core.hooksPath hooks
```

Local hooks are not authoritative. `make test` checks indexed files in the current tree; unrelated untracked files are outside Git policy until staged. `make check-source-history` also rejects prohibited material that was committed and later deleted. The GitHub Actions workflow runs the complete-history form on every push, against a full, non-shallow checkout (`fetch-depth: 0`).

## Documentation style

Write Markdown with one source line per paragraph or list item. Do not wrap prose to a fixed column. Preserve intentional hard breaks, which use two trailing spaces. Link to the document that owns a fact rather than duplicating it:

- README owns the high-level current status and verified-composition summary.
- `docs/architecture.md` owns the reusable system boundaries and composition roles.
- `docs/workstreams.md` owns active branches, worktrees, handoffs, and next-task decisions.
- `docs/test-plan.md` owns pass/fail requirements.
- `docs/harness.md` owns orchestration implementation details.
- ADRs own decisions and consequences.
- Dated experiment and research notes own historical observations.
- `pins/` owns active revisions and checksums.
- `NOTICE.md` owns repository-wide provenance and redistribution boundaries.

Run the repository's Markdown soft-wrap check when available, and review its diff before changing pre-existing prose.
