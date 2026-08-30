# Two-ITS readiness findings

- **Observed:** 2026-08-28 through 2026-08-30
- **Outcome:** The two-ITS NCP TELNET application and anti-bypass payload criteria passed on the exact clean-media pins. Host `176` used the restored `UT` client to interact with host `106` and recover a unique host-`106` sentinel through both IMPs, and the modem-link (MI1) packet content was independently correlated across both IMPs in both directions. The gate is promoted and reproducible.

This dated note explains why the normative two-ITS gate has its current readiness conditions. The gate itself lives in the [test plan](../test-plan.md).

## Promotion checkpoint on 2026-08-30

The source-only promotion baseline is commit `1120826` (`test: promote reproducible two-ITS TELNET gate`). It pins KA10 fork commit `5f57231e96ea823fa3f109d68e970546dcb08a31`, upstream H316 SIMH commit `feb155fbc49333e879ab082d481e6dcce27d2d91`, and PDP-10/ITS commit `0f7d67997f9f5d30208e117e73272031e74f16b9`. The KA10 fork commit is already pushed; the `arpanet-redux` commit is intentionally still one commit ahead of `origin/main`. The untracked root `AGENTS.md` belongs to the operator and is outside this work.

At the checkpoint, the clean ITS build in `/Users/brf/src/brfid-vintage-network-lab/work/its-readdress-src` had completed guest software construction and was still running the final `DUMP LINKS FULL LIST` filesystem inventory for `out/pdp10-ka/output.tape`. It had not yet returned to the host, completed the required no-op rebuild, or received `.brfid-build-receipt.json`. Do not claim a promoted-image pass from that intermediate state and do not start a competing build while the existing `make EMULATOR=pdp10-ka its` process is live.

Resume by allowing that build to exit successfully, then run the target once more and require it to be a no-op. Write and verify the receipt before starting the supported smoke:

```sh
cd /Users/brf/src/brfid-vintage-network-lab/work/its-readdress-src
make EMULATOR=pdp10-ka its

cd /Users/brf/src/arpanet-redux
./scripts/its-build-receipt.py write /Users/brf/src/brfid-vintage-network-lab/work/its-readdress-src /Users/brf/src/brfid-vintage-network-lab/work/its-readdress-src/.brfid-build-receipt.json
./scripts/its-build-receipt.py verify /Users/brf/src/brfid-vintage-network-lab/work/its-readdress-src /Users/brf/src/brfid-vintage-network-lab/work/its-readdress-src/.brfid-build-receipt.json
make LAB_ROOT=/Users/brf/src/brfid-vintage-network-lab smoke-two-its
```

The exact supported smoke is the only remaining technical gate. If it passes, update this note and the README with the immutable result leaf and sentinel digest, rerun `make test` plus the source-history and Markdown checks, commit the evidence update, and push `main`. If it fails, diagnose only from that result directory; do not reopen STELNT, NCPTN, ECHO, FTP, RJE, or alternate-host work unless the new evidence invalidates the already-settled findings below.

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

## Early harness consequences

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

The first correction isolated only the `STATUS &= ~IMPR` hunk from upstream commit [`ee55f7de`](https://github.com/larsbrinkhoff/ka10-simh/commit/ee55f7de16c27c233d76fd1b58a21d239afe4625). It stopped the random halts across five consecutive two-host boots, but that was not a complete validation of the upstream change. A later instruction-level trace showed that omitting the commit's CONO hunk leaves the `IMPIC` interrupt-enable bit set when ITS clears the ready interrupt. Repeated priority interrupts after an RRP then starve the guest scheduler, producing the apparent hang. Restoring the exact `else { STATUS &= ~IMPIC; }` hunk lets the monitor process the RRP and wake the opener.

This invalidates [ADR-002](../adr/0002-kaimp-not-ready-fix.md)'s claim that the second hunk caused the hang. [ADR-003](../adr/0003-complete-kaimp-fix.md) records the accepted correction. Fork commit `5f57231e96ea823fa3f109d68e970546dcb08a31` now contains both focused hunks and is the reproducible project pin.

## Trial 5: clean-image boot filename

The natively-built host-`176` image (produced by the `pdp10-its` / its-readdress-src pin) failed to boot with `FNF` (file not found) errors. Its boot script, copied from the debugger-modified-disk override script, loaded a file named `NITS`. The its-readdress-src build assembles the system under that working name but renames it to `ITS` as its final step (`:rename .;@ nits, .;@ its`). Corrected `its176-pair.simh` to load `ITS`, and confirmed the image now boots and self-identifies as host `176` natively, without the runtime `IMPUS` symbol override the prior debugger-modified disk required.

## Trial 6: throttle-driven host-link-up variance

With both fixes above in place, the watchdog transition to `075400` (attached host link up, [Gate 4](../test-plan.md) precondition 2) was still failing unpredictably, sometimes on IMP 6's side and sometimes on IMP 62's, taking anywhere from single-digit seconds to over 700 seconds with no consistent pattern. Comparing simulated-time counters between a historical passing run's two watchdog transitions showed a roughly 480-530 real-second gap at the pinned `set throttle 400K` rate.

Four throttled simulators (two H316 IMPs and two KA10 hosts) compete for real CPU on one test host, so wall-clock time to cross a simulated-time threshold varies with scheduling luck. Relaxing the IMP throttle from `400K` to `50000K` for exploratory runs collapsed the initial link-up wait. That finding concerns startup throughput only: later runs at `400K`, `5M`, `10M`, and `50M` showed that changing the throttle did not prevent the later H316 process failure. The supported two-ITS configuration uses `10M`, the lowest exploratory rate that completed promptly and the rate of the retained functional pass.

## Trial 7: automatic NCP TELNET service

The initial stall looked like a missing listener, but direct guest evidence disproved that hypothesis. The current ITS build installs `SYSBIN; TELSER BIN` and automatically binds NCP sockets 1 and 23 to `TELSER`; it does not require the 1975 `STELNT` program. An incoming request from host `176` created `LBSIGN RFC137` under `SYSBIN TELSER` on host `106` and a remote `nnTLNT` job. In 10M-paced runs the client reached `Open`, and the IMP trace carried TELNET negotiation plus the server's `MIT Dynamic Modeling PDP-10` greeting. Host `176` accepted and acknowledged those bytes even though the console client did not render the greeting before the later failure.

The attempted compact DDT form `stelnt` followed by two ESC characters, `4`, and Control-K produced `?U?`. The historical DDT contract defines `<program>^K` as creating and starting a job and `$$4^K` as disowning the already-current job; they are separate operations, not one compact command. `:LISTJ` only reports jobs owned by the current DDT user, so it is not evidence against a system-owned server job. In this build `:PEEK A` prints summary IMP/TCP state because PEEK's detailed NCP display is compiled out. Neither command is an adequate NCP listener oracle here.

`STELNT` is therefore retired from this investigation. `TELSER` has already supplied stronger evidence than a manually started legacy listener could provide.

## Trial 8: ITS receive-condition experiment

An experimental reversal of the ITS monitor's `TDNE` receive condition in `src/system/ncp.9` did not cure the connection and was reverted in source after a clean rebuild. Subsequent packet and device traces showed that the original condition was correct. The experimental host-`176` disk still contains the reversed instruction, so every valid later run patches that word back to the original `TDNE 16,52234(14)` before starting ITS. That disk is not promotable media.

## Trial 9: device-level DEAD message

A KAIMP device trace captured the word ITS read while waiting for a type-5 RFNM: `036000000160`, whose leader type is 7, followed by a subtype-zero word. The recovered IMP firmware identifies this as destination IMP dead. This moved the active fault below NCP and TELNET: the application was waiting correctly, but the IMP path returned a network-control failure instead of the expected acknowledgment.

## Trial 10: H316 leader-conversion buffer overflow

The apparent modem-line death was a host-process crash, not a firmware liveness decision. The macOS crash record for the failing H316 process reports `SIGTRAP` in `libsystem_malloc` on an invalid free, with `mfm_free` called from `hi_start_tx`. The H316 source allocated a temporary transmit buffer of the original word count plus five words, but short-to-long 1822 leader conversion can expand the packet further. The captured case grew from 17 to 27 words in a 22-word allocation, overwrote five words, and later failed while freeing the corrupted allocation.

Upstream `larsbrinkhoff/simh` commit [`feb155fb`](https://github.com/larsbrinkhoff/simh/commit/feb155fbc49333e879ab082d481e6dcce27d2d91) replaces that allocation with a fixed 1500-word buffer and removes the free. Applying those exact two lines to the pinned working tree, rebuilding H316, and repeating the exchange eliminated the process crash. Both IMPs then retained `075400` throughout the application proof. IMP 6 changes to `175400` only during intentional cleanup after its peer is terminated, outside the proof interval.

[ADR-004](../adr/0004-h316-hi-conversion-buffer.md) records the accepted upstream repin. The project now pins directly to clean upstream commit `feb155fbc49333e879ab082d481e6dcce27d2d91`.

## Trial 11: live NCP state and the NCPTN client bug

With the H316 fix present, host `176`'s `NCPTN` client reached `Open`. While the connection was pending, host `106`'s `:PEEK A` reported `IMP is up`, showed the STY map entry `T53 ... TELSER`, and then printed `LOGIN 53TLNT 0 HST176` after client input triggered TELNET negotiation. `:LISTJ` remained empty because it reports only the current DDT user's jobs. This directly settles the original question: the incoming connection registers at the NCP layer, automatic `TELSER` owns it, and the remote pseudo-terminal exists.

The newer `NCPTN` client still did not display received server data. This exactly matches open upstream issue [`PDP-10/its#2351`](https://github.com/PDP-10/its/issues/2351): the NCP connection opens, but the client fails on the first received text, while the older `UT` client displays the banner. Pull request [`PDP-10/its#2350`](https://github.com/PDP-10/its/pull/2350) restored `UT` to current builds. The server and NCP route therefore need no further STELNT work; the remaining application choice is client-side.

## Trial 12: UT application and payload pass

The retained run `two-its-ut-ncp-telnet-e2e-upstream-h316-buffer-fix-paced10m-upstream-kaimp-runtime-original-tdne-20260830T114351Z` used `UT.76` on host `176`. `UT` printed `CONNECT` and host `106`'s `MIT Dynamic Modelling PDP-10` greeting. Its local `TRANSPARENT` command allowed Control-Z to traverse the connection, after which the host-`176` transcript displayed host `106`'s DDT banner, remote TTY 53, and a structured remote `:TIME` result dated 2025 rather than host `176`'s 2026 clock.

For the anti-bypass proof, host `106`'s console logged in as `DB`, the remote pseudo-terminal logged in as `NETTST`, and host `106` injected `ARPANET-REDUX-20260830T114351Z` with DDT `:OSEND`. Host `176` recovered the sentinel only through its `UT` transcript. The source and recovered SHA-256 values both equal `7a88f51441d840041f628a96fd467df4878828ff65a476525dc4bebbf1aef41a`, and both IMP logs contain bidirectional post-probe host traffic.

This passes the functional criteria of Gates 4 and 5. It is not yet the clean reproducible gate because the run used two locally patched simulator trees, a pre-start restoration of source-original `TDNE` in an experimental ITS disk, and a disposable driver. Promote the two simulator fixes, rebuild the clean host-`176` image from the reverted source, move stable orchestration into the repository, and repeat with exact clean pins before treating the gate as release evidence.

## Trial 13: no-op check and dead-evidence-marker bugs at promotion

Resuming the checkpoint's no-op rebuild surfaced two structural bugs in the acceptance harness itself, not in the guest software or simulator pins.

`its-build-receipt.py`'s no-op check ran `make -q ... its`, which depends on per-submodule `$(SMF)` sentinel files. The pinned `pdp6` fork (`aap/pdp6` at `lars/cscope-20-g5f4d511`) has no root-level `.gitignore`, so that sentinel can never exist and `make -q` always reported the target stale regardless of build freshness. The fix checks the real build-output stamp, `out/$(EMULATOR)/stamp/its`, directly; recursive submodule state is independently captured and verified through `git submodule status --recursive` in the same receipt, so nothing is lost.

`two-its-controller.py`'s `assert_imp_application_evidence()` and `regular_message_ids()`/`correlated_ids` required `Short leader:`, `Long leader:`, `Converted:`, `type=0`, and an `id=` field in the IMP debug logs. Those exact fprintf lines came only from a hand-instrumented `h316_hi.c` used during Trial 10's diagnosis and left behind in `its-readdress-src/tools/ncp/test/simh`; the clean pinned upstream `h316-simh` (`feb155fb`) never emits them. Both checks could never pass against correctly promoted media.

The fix replaces the dead checks with real evidence from the MI1 modem-interface link between the two IMPs, which the harness had never logged. `config/imp/its-pair/imp6.simh` and `imp62.simh` now enable `set mi1 debug`; the controller reconstructs each MI1 packet's exact word content and requires that content sent by one IMP appear verbatim as received by the other, in both directions, above a four-word floor that excludes generic single-word acks from coincidental matches. This is a strictly more literal proof of the two-hop path than the retired ID-correlation check: it matches genuine wire content crossing the real inter-IMP hop instead of a host-facing conversion side effect. `assert_imp_application_evidence()` keeps only the two markers the clean build actually emits, `HI2 MSG: message received` and `HI2 MSG: message sent`.

With both fixes applied, the clean image (source revision `0f7d67997f9f5d30208e117e73272031e74f16b9`, matching the pin, tree and submodules clean) passed its no-op rebuild, receipt write and verify, and `smoke-two-its`: result `two-its-telnet-20260830T155246Z-fe47a86c-eb93-4403-8549-8a3c431be43c`, sentinel `ARPANET-REDUX-20260830T155516Z-10FF4`, matching SHA-256 `ed7e64a9a9f7d228cb76e11342b2d0a8efb51a54f959e20be7327863b5752e37` on both ends, and over 1,400 exact-content MI1 packet matches in each direction post-probe. `make test`, `check-source-history`, and the full acceptance suite pass with the updated harness.

## Application and host alternatives

- FTP and RJE depend on the same NCP and IMP path now proven by the interactive `UT` session. They remain possible follow-up applications, but no longer offer diagnostic leverage over the accepted TELNET baseline.
- ITS's user-facing `ECHO` program is Chaosnet-only. The ITS NCP monitor can answer an incoming host-host ECO, but the current tree has no user-facing NCP ECO originator and treats ERP as unsupported. A new two-ITS ECO utility would add guest code without strengthening the application-visible proof already obtained.
- Current ITS remains the closest vintage endpoint: two instances boot, use native NCP, run the correct incoming TELNET server, and now complete a payload exchange. WAITS integrations still terminate NCP in a modern bridge, while SRI/NOSC Network UNIX V6 needs a missing PDP-11 IMP11-A/ACC simulator device.

## Current-source and historical-document review

The 2026-08-30 wall check covered both active GitHub work and primary system documentation:

- [`PDP-10/its` PR 2348](https://github.com/PDP-10/its/pull/2348) independently demonstrates incoming NCP TELNET, including RST/RRP behavior. Open issue [`#2351`](https://github.com/PDP-10/its/issues/2351) exactly matches the newer client's receive failure, and merged PR [`#2350`](https://github.com/PDP-10/its/pull/2350) restored the known-working `UT` client.
- [`larsbrinkhoff/ka10-simh` commit `ee55f7de`](https://github.com/larsbrinkhoff/ka10-simh/commit/ee55f7de16c27c233d76fd1b58a21d239afe4625) contains both KAIMP corrections now shown to be required.
- [`larsbrinkhoff/simh` commit `feb155fb`](https://github.com/larsbrinkhoff/simh/commit/feb155fbc49333e879ab082d481e6dcce27d2d91) contains the H316 transmit-buffer correction that eliminates the conversion overflow. The recovered [`obsolescence/arpanet`](https://github.com/obsolescence/arpanet) tree is current at the tested revision.
- The historical DDT reference settled the job/disown syntax and the distinction between `:SEND` and `:OSEND`; BBN Report 1822 settled the RFNM and host/IMP control-message meanings; and the recovered H316 firmware listing settled the type-7 subtype and watchdog-light decoding. The H316 simulator source and crash record exposed the actual conversion-buffer overflow.

## Investigation register

| Question | Decisive evidence | Decision | State |
|---|---|---|---|
| Are both ITS images live and distinct? | Complete banners, local `:TIME`, native host identities `106` and `176` | Keep the two-ITS topology | Settled |
| Did the clean image name the boot monitor incorrectly? | `NITS` is renamed to `ITS` at build completion | Boot `ITS`; do not restore `NITS` | Fixed |
| Did KAIMP corrupt status on a not-ready datagram? | Random-PC halts stopped after `STATUS &= ~IMPR` | Require the complete upstream fix | Settled |
| Is the isolated KAIMP hunk sufficient? | Instruction trace shows a persistent PI interrupt after RRP until `IMPIC` is cleared | Promote the complete upstream fix | Settled |
| Does host `106` lack an NCP TELNET listener? | Dynamic `RFC137`/`TELSER`, remote `nnTLNT`, negotiation, and greeting bytes | Use automatic `TELSER`; retire `STELNT` | Settled |
| Is ITS mishandling the received RFNM? | KAIMP delivered type 7 subtype 0 instead of type 5 | Do not modify the ITS receive condition | Settled |
| Does changing simulator throttle cure the connection? | The same failure occurs from `400K` through `50M` | Treat throttle only as test throughput | Settled |
| Why did the H316 modem appear to die? | Crash record and exact 17-to-27-word conversion show a five-word heap overwrite | Promote upstream H316 buffer fix | Settled |
| Why did `NCPTN` open but not display data? | Behavior matches upstream issue `#2351`; `UT` displays the same stream | Use restored `UT` for the baseline | Settled |
| Can two ITS guests complete the application proof on clean, exact-pin media? | Remote greeting, DDT, `:TIME`, matching `:OSEND` sentinel digests, and correlated MI1 packet content across both IMPs in the promoted run | Keep ITS and promote the working dependency set | Settled |
| Did the acceptance harness itself prove what it claimed to? | `assert_imp_application_evidence`/`regular_message_ids` required fprintf strings that exist only in a leftover hand-instrumented `h316_hi.c`, never in the clean pinned upstream build | Check the real build-output stamp for no-op; correlate genuine MI1 modem-link content instead | Settled |
| Would FTP, RJE, or another host improve the baseline? | Native ITS NCP TELNET now passes the functional criteria | Defer alternatives until after reproducible promotion | Settled |

## Evidence retention

Raw logs and historical assets remain outside Git under the laboratory result root. Retain these result-directory leaves as the minimal evidence set for the current conclusions:

- `two-its-ncp-original-ufls-probe-clean-20260830T075549Z`: instruction trace proving the complete KAIMP interrupt-clear behavior.
- `two-its-ncp-telnet-live-diagnostics-upstream-h316-buffer-fix-paced10m-upstream-kaimp-runtime-original-tdne-20260830T111157Z`: live `:PEEK A`, TELSER/STY ownership, and remote `nnTLNT` registration.
- `two-its-ncp-telnet-e2e-upstream-h316-buffer-fix-paced10m-upstream-kaimp-runtime-original-tdne-20260830T112140Z`: `NCPTN` opens while failing to display received data, matching upstream issue `#2351`.
- `two-its-ut-ncp-telnet-e2e-upstream-h316-buffer-fix-paced10m-upstream-kaimp-runtime-original-tdne-20260830T114351Z`: functional Gate 4/5 pass with remote DDT, `:TIME`, matching sentinel digests, and post-probe IMP traffic.
- `two-its-telnet-20260830T155246Z-fe47a86c-eb93-4403-8549-8a3c431be43c`: the promoted clean-media pass. Exact source and simulator pins, no-op rebuild, verified build receipt, matching sentinel digest `ed7e64a9a9f7d228cb76e11342b2d0a8efb51a54f959e20be7327863b5752e37`, and over 1,400 exact-content MI1 packet matches per direction across the real IMP 6 ↔ IMP 62 hop.

This note is the canonical chronological evidence record; the [test plan](../test-plan.md) is the normative acceptance contract, and ADRs own durable decisions. The stable behavior from the disposable driver now lives in `scripts/smoke-two-its.sh` and `scripts/two-its-controller.py`; exploratory drivers remain outside Git. Do not add one report per failed timing attempt or copy mutable status into parallel briefs.

## Consequences

- Observe both H316 modem-up and host-link watchdog transitions, then apply the route-settle interval.
- Require complete ITS system-console banners plus successful local commands on both guests.
- Track explicit simulator states and never send WRU to a child already at the simulator prompt.
- Drain both consoles concurrently and retain sent-character evidence.
- Capture IMP log offsets immediately before the application probe so startup traffic cannot satisfy it.
- Require remote application identity and time output, not merely an open connection.
- Pin `config/hosts/its176-pair.simh` to load `ITS`, not `NITS`, when booting the natively-built host-`176` image.
- Treat KA10 halts at inconsistent, unrelated program counters during two-host runs as a KAIMP-class transport-status bug, not guest-application misbehavior, until proven otherwise.
- Require the promoted complete two-hunk KAIMP correction.
- Require the promoted H316 leader-conversion buffer fix; do not diagnose the prior process crash as firmware modem timing.
- Use automatic `TELSER` with restored `UT` for the two-ITS baseline; do not pursue `STELNT` or the broken `NCPTN` receive path.
- Distinguish functional proof from reproducible acceptance: the simulator pins, clean ITS media, and supported harness must all agree before the gate becomes release evidence.
- Check ITS build no-op status against the real output stamp (`out/$(EMULATOR)/stamp/its`), not the `its` target itself; the pinned `pdp6` submodule has no root `.gitignore`, so its `$(SMF)` sentinel can never satisfy `make -q`.
- Enable `set mi1 debug` on both IMPs and require exact-content MI1 packet matches across both directions of the real inter-IMP hop as post-probe application evidence; never gate acceptance on debug strings that exist only in an exploratory, non-promoted simulator build.
