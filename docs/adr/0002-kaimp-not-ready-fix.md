# ADR-002: Fork ka10-simh to apply an isolated KAIMP status fix

- **Status:** Accepted 2026-08-29; invalidated by subsequent evidence 2026-08-30
- **Date:** 2026-08-29
- **Decider:** Brad
- **Replacement:** [ADR-003](0003-complete-kaimp-fix.md) (accepted)

## Context

Two-ITS boot attempts (the [Gate 4](../test-plan.md) topology) failed intermittently: a KA10 guest would halt at an unrelated program counter, with no consistent pattern across runs. Tracing the crash to `PDP10/kx10_imp.c` in the pinned `ka10-simh` revision found the cause in `imp_receive_udp()`:

```c
if (data[0] & PFLG_READY)
    imp_unit[0].STATUS |= IMPR;
else
    imp_unit[0].STATUS &= IMPR;   /* bug: ANDs against the single IMPR bit */
```

On a not-ready datagram, `STATUS &= IMPR` clobbers every STATUS bit except IMPR instead of clearing only IMPR. Under real network timing this corrupts KA10 IMP device state at effectively random moments, producing the observed halts at unrelated PCs.

Upstream `larsbrinkhoff/ka10-simh` already carried a fix, commit `ee55f7de` ("PDP10: Fix for KAIMP.") on the `lars/ncp` branch. That commit has two hunks: the `STATUS &= IMPR` correction above and a second change to CONO handling of the interrupt-enable bit (IMPIC). The preliminary test was interpreted as showing that the IMPIC hunk caused the two-host NCP boot sequence to hang, so this decision selected only the first hunk.

`lars/ncp` had also diverged from the pinned revision by roughly a year of unrelated upstream work (IBM360, SEL32, I7000, build-system changes), so pinning directly to `ee55f7de` was rejected at the time: it would pull in a much larger, unrelated review surface than this project's file-scoped redistribution review expects.

The project's source verification (`scripts/verify-sources.py`) requires an exact pinned revision with a clean working tree, so a local, uncommitted patch on top of the pinned commit was also rejected as it would not reproduce from a fresh checkout and would fail verification.

## Subsequent evidence

An instruction-level KAIMP trace on 2026-08-30 showed that the second hunk prevents the hang. Without the `else { STATUS &= ~IMPIC; }` branch, an ITS CONO that clears the ready-interrupt enable leaves `IMPIC` set. Repeated priority interrupts after the monitor receives an RRP then starve normal scheduling. Applying the exact omitted hunk lets the monitor process the RRP and wake the connection opener.

The original five-run validation proved only that the first hunk stopped random status-corruption crashes. It did not prove that the resulting pin could complete an NCP exchange. Do not use this ADR as authority to retain the single-hunk pin.

## Historical decision

Fork `ka10-simh` to `https://github.com/brfid/ka10-simh.git`. On top of the pinned base revision (`b45fedc048c4a064aae6f771156349e78b3c21e8`), add one commit containing only the `STATUS &= IMPR` → `STATUS &= ~IMPR` correction, omitting the IMPIC hunk. Pin `ka10-simh` in [`pins/sources.lock.toml`](../../pins/sources.lock.toml) to that fork and commit.

This keeps the change minimal, auditable as a single-line diff against the previously-reviewed base, fully reproducible from a fresh clone, and compliant with the project's exact-revision-plus-clean-tree verification model.

## Historical consequences

- `ka10-simh`'s source of truth is now a project-controlled fork rather than upstream directly. Re-pin to upstream `master` once this fix (or an equivalent one without the IMPIC regression) lands there.
- The IMPIC/CONO interrupt-enable behavior remained unchanged from the original pinned revision. Subsequent evidence established that this was incorrect.
- Validated across five consecutive two-host boot runs with zero recurrence of the original crash, using both the override-identity and natively-built-176 host images.
