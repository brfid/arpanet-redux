# Two-ITS readiness findings

- **Observed:** 2026-08-28
- **Outcome:** Topology and failure modes characterized; guest-to-guest application proof not yet achieved

This dated note explains why the normative two-ITS gate has its current readiness conditions. The gate itself lives in the [test plan](../test-plan.md).

## Topology under test

KA10/ITS host `106` attached to H316 IMP 6, one simulated modem link to H316 IMP 62, and KA10/ITS host `176` attached to IMP 62. Both guest links used HI2 with long/short leader conversion and independent guest-media copies.

## Trial 1: paused destination

The first ITS-originated TELNET trial was invalid because host `106` remained at a SIMH command prompt. Host `176` sent its reset through IMP 62 and IMP 6, and IMP 6 delivered it to host `106`, but the paused KA10 could not answer.

This ruled out a live PID or bound UDP socket as guest-liveness evidence. Controller state and a current guest command response are required.

## Trial 2: route hold-down

The next controlled trial proved both guests locally with ITS `:TIME` but opened TELNET after only five seconds. IMP 62 returned a type-7 control message with subtype 0. The recovered H316 listing identifies subtype 0 as destination IMP dead, distinct from subtype 1 destination host dead; the console client's generic failure text obscured that distinction.

The response was historically correct. A newly discovered route remains in the firmware's `RUTCMU` coming-up hold-down. It begins at octal `0340`, loses octal `0040` every tenth slow tick, and needs roughly 44.7 seconds to become eligible. The test plan therefore requires a 60-second margin after both modem links report up.

## Trial 3: unreliable console telemetry

A later trial showed that `IMP: Interface-reset msg` cannot be a gate. Both H316s sent resets and completed their host-side NOP exchanges, but only one ITS console printed the informational line. The monitor prints and discards this message, so its absence does not prove interface failure.

The trial ran concurrently with a full historical ITS source build. CPU contention stretched a normally short cold boot into several minutes and caused a readiness deadline without exposing a network defect. Image building and network acceptance must therefore be serialized on the tested host.

## Consequences

- Observe both H316 modem-up and host-link watchdog transitions, then apply the route-settle interval.
- Require complete ITS system-console banners plus successful local commands on both guests.
- Track explicit simulator states and never send WRU to a child already at the simulator prompt.
- Drain both consoles concurrently and retain sent-character evidence.
- Capture IMP log offsets immediately before the application probe so startup traffic cannot satisfy it.
- Require remote application identity and time output, not merely an open connection.

## Subsequent image-build observation

Later on 2026-08-28, the clean generic KA/ITS source target completed and shut down normally after its final filesystem integrity check. That completion is not yet an image-promotion result: clean-tree and recursive-submodule state, a no-op rebuild, output hashes, a provenance receipt, and an independent host-`176` boot remain required before the media enters an acceptance run.
