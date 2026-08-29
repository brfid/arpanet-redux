# Two-ITS readiness findings

- **Observed:** 2026-08-28 through 2026-08-29
- **Outcome:** Boot-time and transport-timing failure modes root-caused and fixed; a guest-to-guest NCP TELNET connection now reaches a live protocol exchange but does not complete, with a specific and still-open hypothesis for why

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

## Trial 4: KAIMP status corruption

On 2026-08-29, host `106` began halting at unrelated program counters at unpredictable points during otherwise-normal two-host runs, with no consistent PC or trigger across runs. Tracing found the cause in the pinned `ka10-simh` revision's `imp_receive_udp()`: on a not-ready datagram it cleared the IMPR status bit with `STATUS &= IMPR`, which ANDs against the single IMPR bit and clobbers every other STATUS bit instead. Under real network timing this corrupts KA10 IMP device state at effectively random moments.

Upstream `larsbrinkhoff/ka10-simh` carries a fix for this on an unreleased, diverged branch, but that commit's other hunk (CONO handling of the IMPIC interrupt-enable bit) caused the two-host boot to hang rather than crash when tested. The project now carries an isolated single-hunk fix on a controlled fork; see [ADR-002](../adr/0002-kaimp-not-ready-fix.md) for the full rationale. Validated across five consecutive two-host boot runs with zero recurrence of the original crash.

## Trial 5: clean-image boot filename

The natively-built host-`176` image (produced by the `pdp10-its` / its-readdress-src pin) failed to boot with `FNF` (file not found) errors. Its boot script, copied from the debugger-modified-disk override script, loaded a file named `NITS`. The its-readdress-src build assembles the system under that working name but renames it to `ITS` as its final step (`:rename .;@ nits, .;@ its`). Corrected `its176-pair.simh` to load `ITS`, and confirmed the image now boots and self-identifies as host `176` natively, without the runtime `IMPUS` symbol override the prior debugger-modified disk required.

## Trial 6: throttle-driven host-link-up variance

With both fixes above in place, the watchdog transition to `075400` (attached host link up, [Gate 4](../test-plan.md) precondition 2) was still failing unpredictably, sometimes on IMP 6's side and sometimes on IMP 62's, taking anywhere from single-digit seconds to over 700 seconds with no consistent pattern. Comparing simulated-time counters between a historical passing run's two watchdog transitions showed a roughly 480-530 real-second gap at the pinned `set throttle 400K` rate.

Four throttled simulators (two H316 IMPs, two KA10 hosts) compete for real CPU on one test host, so wall-clock time to cross a simulated-time threshold varies with scheduling luck. This is consistent with both the long delay and its run-to-run variance. Relaxing the IMP throttle from `400K` to `50000K` for testing collapsed the wait to consistently fast across every subsequent run, with no change to protocol correctness or instruction sequence. This is a testing-throughput finding, not (yet) a committed configuration change; the pinned `config/imp/its-pair/*.simh` throttle is unchanged pending a decision on whether the accepted run should relax it too or keep historical pacing and simply budget for the variance.

## Trial 7: NCP TELNET connection stall

With trials 4 through 6 applied, host `176` reliably reaches `:ncptn 106` and gets `User TELNET.nnn`, `Open connection to 106`, `Trying...`. The connection then never resolves to either an open session or an explicit dead-host report, even after a 300-second wait. Both IMPs show one real `REGULAR` (data) packet and one `RFNM` acknowledgment exchanged in each direction, then silence — no retries, no reset, no further traffic — while host `106`'s console shows zero activity after its own local `:TIME` proof.

This is not a transport or routing failure: the same two-IMP path already carries real application data correctly in [Gate 2/3](../test-plan.md)'s passing `linux-ncp` echo traffic. The pattern (one control message delivered, then silence, with the target console otherwise idle) is consistent with the connection request arriving at a host with nothing listening to accept it.

Upstream PDP-10/its's own GitHub issues describe NCP-based TELNET as effectively unmaintained: "we don't enable NCP in the monitor configuration, because we don't have anyone talking NCP to us," and the legacy NCP TELNET server program (`SYSENG;STELNT`, dated 1975) is discussed as a thing nobody currently needs now that TCP and Chaosnet exist. The project's build does enable NCP in the monitor configuration (`NCPP==1`), and `SYS;@ STELNT` is assembled as part of the standard build, but nothing in the current harness starts it as a job.

Starting `STELNT` on host `106` via DDT's `<prgm>^K` (per the project's own `docs/DDT.md` cheat sheet, confirmed against the authoritative DDT reference: creates a job, loads the named program, starts it, and gives it the TTY) produced no visible console output, consistent with a silent, successful start rather than a failure. The subsequent connection attempt stalled identically. This neither confirms nor refutes the hypothesis: `STELNT`'s source contains a 1975-era access-control list (`WINNRS`/`LOSERS`, enumerated ARPANET host numbers) that does not include host `176`, and a legacy program running for the first time in a modern build could plausibly have failed silently in a way indistinguishable, from the console, from a healthy start.

## Consequences

- Observe both H316 modem-up and host-link watchdog transitions, then apply the route-settle interval.
- Require complete ITS system-console banners plus successful local commands on both guests.
- Track explicit simulator states and never send WRU to a child already at the simulator prompt.
- Drain both consoles concurrently and retain sent-character evidence.
- Capture IMP log offsets immediately before the application probe so startup traffic cannot satisfy it.
- Require remote application identity and time output, not merely an open connection.
- Pin `config/hosts/its176-pair.simh` to load `ITS`, not `NITS`, when booting the natively-built host-`176` image.
- Treat KA10 halts at inconsistent, unrelated program counters during two-host runs as a KAIMP-class transport-status bug, not guest-application misbehavior, until proven otherwise.
- Do not treat a long or variable wait for host-link-up watchdog lights as a protocol failure on its own; check for CPU contention among concurrently throttled simulators before assuming a firmware or guest defect.
- An `Open connection to 106` / `Trying...` state that never resolves, with real packet traffic still flowing between the IMPs, points at the destination guest's application layer (is anything listening?), not at the network path.
