# Two-ITS readiness findings

**Status:** Topology and failure modes characterized; guest-to-guest application pass pending

The target topology is KA10/ITS host `106` on H316 IMP 6 connected by one simulated modem line to H316 IMP 62 and KA10/ITS host `176`. Both host interfaces use HI2 with long/short leader conversion. The committed configurations encode that wiring with per-run ports, but this note does not claim the end-to-end gate has passed.

## What the failed trials established

The first ITS-originated TELNET trial was invalid because host `106` had been left at a SIMH command prompt. Host `176` sent its reset through IMP 62 and IMP 6, and IMP 6 delivered it to host `106`, but a paused KA10 could not generate the reply. A live PID and bound UDP socket are therefore insufficient guest-liveness evidence.

The next controlled trial proved both guests locally with ITS `:TIME`, but it opened TELNET at only five seconds of guest uptime. IMP 62 returned a type-7 control message with subtype 0. The recovered H316 listing distinguishes subtype 0, destination IMP dead, from subtype 1, destination host dead. The console client's generic “Host dead due to random network lossage” text concealed that distinction.

The router response was historically correct. A newly discovered route remains in the firmware's `RUTCMU` coming-up hold-down: the route begins at octal `0340`, loses octal `0040` every tenth slow tick, and needs about 44.7 seconds to become eligible. A 60-second margin after both modem links come up is the initial portable readiness rule.

A later trial showed why `IMP: Interface-reset msg` must remain telemetry rather than a gate. Both H316s sent the reset and completed their host-side NOP exchanges, but only one ITS console printed the informational note. The ITS monitor prints and discards this message; absence of the line is not evidence that the host interface failed.

## Acceptance predicate for the next run

Before host `176` opens TELNET to host `106`, the controller must require all of the following:

- Both H316 logs have reported watchdog lights `077400`, indicating the modem path is up.
- Both H316 logs have later reported watchdog lights `075400`, indicating the attached HI2 host link is up.
- At least 60 seconds have elapsed since the later modem-up observation, covering the firmware's peer-route hold-down.
- Both ITS consoles have printed `SYSTEM JOB USING THIS CONSOLE`, not merely the earlier `IN OPERATION` substring.
- Each guest has entered DDT with Control-Z, completed local `:TIME`, printed `The time is`, `Today is`, and its uptime, and returned to the DDT prompt.
- Both controller state variables are `RUNNING`; neither simulator is at `sim>`.

The application pass then requires host `176` to run `:NCPTN 106`, report `Open`, send `:TIME` over that connection, and receive the remote time/date/uptime transcript. Both IMP traces must show the regular traffic and the required leader conversions, and all owned processes and ports must be released after the run.

The clean host-`176` source build must identify itself as `IMPUS=176` in its boot transcript. A debugger deposit into a copied host-`106` monitor remains useful diagnostic evidence but is not an image-promotion candidate.

## Harness consequences

The build and acceptance smoke should be serialized. Running a full historical ITS build alongside two throttled KA10 guests stretched a normally seconds-long cold boot into several minutes and caused a readiness deadline to expire without exposing a network defect.

The controller must drain both KA consoles concurrently, record sent characters as well as received output, and maintain explicit `BOOTING`, `RUNNING`, and `PROMPT` states. Cleanup may send the WRU character only to a `RUNNING` simulator; a child already at `PROMPT` must receive `quit` directly.

Until the application transcript passes, these configurations and findings are an in-progress experiment rather than a promoted smoke target.
