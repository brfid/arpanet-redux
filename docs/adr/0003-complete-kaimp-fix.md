# ADR-003: Complete the upstream KAIMP interrupt-state fix

- **Status:** Accepted
- **Date:** 2026-08-30
- **Decider:** Brad

## Context

[ADR-002](0002-kaimp-not-ready-fix.md) selected only the not-ready status hunk from upstream `larsbrinkhoff/ka10-simh` commit [`ee55f7de`](https://github.com/larsbrinkhoff/ka10-simh/commit/ee55f7de16c27c233d76fd1b58a21d239afe4625). That hunk corrects `STATUS &= IMPR` to `STATUS &= ~IMPR` and eliminates intermittent KA10 halts caused by corruption of the complete IMP status word.

The same upstream commit also makes CONO clear `IMPIC` whenever the instruction does not request ready interrupts:

```c
if (*data & IMPIR) {
    uptr->STATUS |= IMPIC;
    uptr->STATUS &= ~IMPERR;
} else {
    uptr->STATUS &= ~IMPIC;
}
```

ADR-002 omitted this hunk because a preliminary run attributed a later hang to it. A 2026-08-30 instruction trace reversed that conclusion. With the single-hunk pin, ITS receives an RRP but a stale `IMPIC` causes a continuing priority-interrupt storm that starves the scheduler. Applying the exact upstream CONO hunk lets ITS process the RRP and wake the opener. The retained evidence is `two-its-ncp-original-ufls-probe-clean-20260830T075549Z` under the external laboratory result root.

The simulator working tree used for the exploratory TELNET experiments contained this hunk as an uncommitted patch. That was sufficient to isolate the behavior but could not satisfy exact-source verification.

## Decision

Add the exact CONO/IMPIC hunk to the project-controlled `brfid/ka10-simh` fork on top of `8176903b0cdb8ba5c4ca1dd09d4743c1b339233d`, push commit `5f57231e96ea823fa3f109d68e970546dcb08a31`, and pin this project to that immutable revision. The clean rebuild identifies that exact commit and passes SIMH's register sanity check.

Do not pull the unrelated history surrounding upstream `ee55f7de`; the controlled fork contains only the two file-scoped hunks relative to the previously reviewed base.

## Consequences

- Exact-source verification now requires the promoted clean fork commit rather than the experimental dirty tree.
- The complete correction fixes KAIMP host-interface state handling. [ADR-004](0004-h316-hi-conversion-buffer.md) separately owns the H316 conversion-buffer crash discovered after this ADR was written.
- The focused trace and boot sanity check become regression evidence for future KAIMP repins.
