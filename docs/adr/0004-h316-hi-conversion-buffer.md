# ADR-004: Repin H316 SIMH to the leader-conversion buffer fix

- **Status:** Accepted
- **Date:** 2026-08-30
- **Decider:** Brad

## Context

The pinned H316 simulator revision `2ccfed85acad83b254a6ed5fdd1c342bcdf3a3dd` allocates a temporary host-interface transmit buffer from the pre-conversion packet length plus five words. Its short-to-long 1822 leader conversion can expand the packet farther. A captured TELNET packet grew from 17 to 27 words in a 22-word allocation, overwrote five words, and caused the H316 process to trap in `libsystem_malloc` when `hi_start_tx` freed the corrupted allocation.

Upstream `larsbrinkhoff/simh` commit [`feb155fb`](https://github.com/larsbrinkhoff/simh/commit/feb155fbc49333e879ab082d481e6dcce27d2d91) replaces the allocation with a 1500-word static buffer and removes the free. Applying those exact two lines to the pinned working tree, rebuilding, and running the two-ITS proof eliminated the crash and allowed interactive NCP TELNET plus the unique-sentinel exchange to complete.

The upstream range from the current pin to `feb155fb` contains six commits and changes 11 files. In `H316/h316_hi.c`, the remaining changes clarify octal constants and remove diagnostic prints; the buffer behavior is the only relevant semantic change. The other commits affect unrelated simulator targets and the GitHub workflow.

## Decision

Repin `h316-simh` directly to `feb155fbc49333e879ab082d481e6dcce27d2d91` after reviewing the complete upstream range. The clean checkout and rebuilt H316 identify that exact commit and pass SIMH's register sanity check.

Prefer the upstream pin over a project fork because the correction is already on upstream `master`, the intervening range is bounded and reviewable, and no local divergence is needed.

## Consequences

- Exact-source verification now requires the clean upstream fix rather than an experimental local patch.
- The fix removes a simulator memory-safety crash; it does not change the recovered IMP firmware or its timing policy.
- A final `175400` after intentional peer termination belongs to cleanup. The acceptance harness must record the last watchdog state before cleanup separately from the complete process log.
- Pin promotion does not by itself complete the gate: the KAIMP fix, clean ITS image, and supported orchestration must be promoted and rerun together.
