# Startup, shutdown, and recovery stabilization

- **Observed:** 2026-09-05
- **Baseline:** v0.4.0, `e8e5277feb728fb4a568061488808a542cbf4fd4`; clean `main` matched freshly fetched `origin/main` before work began
- **Implementation:** `e29e508a3495c0f9febf0d62d3b4307868385632`; cleanup-record completion refinement at `139b524119344188aee8935e5de2c18d24f37175`
- **Scope:** Existing direct Network UNIX-to-ITS lifecycle, shared ownership and diagnostic primitives, and an unchanged NCC coexistence composition; disposable guest media, simulator pins, topology, protocol behavior, and acceptance conditions retained

## Demonstrated defects

At the release baseline, synthetic lifecycle tests reproduced three failures: a failed PTY launch left its master descriptor open, one child shutdown exception prevented the remaining owners from being visited or cleanup evidence from being written, and another catchable signal during the shell's exit cleanup killed the launcher before it could release its lease or preserve its first exit status. A cleanup retry also needed to relinquish successful process, control-directory, and build-lease releases rather than retaining authority over names that another run could subsequently use. The regression test reacquires those released names and proves that a retry leaves them intact.

The real baseline run `lifecycle-baseline-peer-20260905T163104Z` killed only its own IMP 62 while the controller awaited the ITS boot banner. The driver checked the live launcher/controller parent relationships and exact IMP executable/configuration before signaling that child. Five seconds after the IMP exited, the controller was still waiting without a failure or cleanup record. The driver then sent TERM to its owned launcher to bound the observation; the run retained exit 143, both cleanup layers, no surviving owned processes, released ports and leases, and unchanged inputs. This is evidence of a missed peer-exit check during the wait, not a claim that the existing 900-second ITS deadline expired.

The initial restricted-environment attempt, `lifecycle-baseline-peer-20260905T162908Z`, ended earlier because the local execution sandbox denied UDP binds. Its original failed result and terminal output remain retained. The simulator experiments below ran with loopback UDP access.

## Repairs and record boundary

The direct launcher now creates its new result and manifest before input-path, build-lease, receipt, and simulator checks. It prints stages and retains increasing `progress.launcher.N` records. The direct controller retains `progress.controller.N` records naming the stage, actual awaited marker or watchdog devices, and existing timeout. Its failure record names the stage, awaited condition, exception, and component exit status where known. No readiness marker or timeout budget changed.

`ProcessWatch` checks all four launched simulator handles throughout direct console, IMP, and settling waits, including when the direct controller is reused in NCC coexistence. It permits not-yet-launched guests and is disabled before deliberate shutdown. Partial launches close their acquired descriptors and stop any created child; aggregate shutdown attempts every owner, even after an individual error. The shell exit handler and controller cleanup protect the first termination from subsequent catchable signals without reducing the accepted controller allowance.

Cleanup errors remain failures even when the process survivor count is zero. The completion refinement places the survivor-count marker last, so an interrupted new cleanup record cannot resemble an older clean record before its error is written. The diagnostic rejects an error paired with a missing or passed status, reports the error separately, and keeps a missing count unknown. Existing cleanup formats and old outcomes remain readable.

## Exact-run evidence

Every result name below is relative to `/Users/brf/src/arpanet-redux-lab/results/`. The listed simulator runs record a clean implementation checkout. Elapsed values are driver-observed wall time, including startup and final cleanup.

| Result | Revision | Exercise and observed result |
|---|---|---|
| `lifecycle-peer-20260905T164539Z` | `e29e508` | Owned IMP 62 killed during ITS boot; failure named IMP 62 and exit status -9 while waiting for the banner. Launcher exited 1 after 36.79 seconds total, 10.34 seconds after the injected exit, including cleanup |
| `lifecycle-timeout-20260905T164655Z` | `e29e508` | Owned IMP 62 paused before its listening marker; unchanged 30-second readiness deadline expired with the exact missing marker. Launcher exited 1 after 42.80 seconds total, with both never-launched guests recorded as such |
| `lifecycle-interrupt-20260905T164754Z` | `e29e508` | TERM after both guest simulators launched, then HUP, INT, and TERM at 0.4-second intervals. Launcher preserved handled TERM and exit 143, finished in 28.07 seconds total, and completed cleanup 19.27 seconds after the first signal |
| `lifecycle-pass-20260905T164917Z` | `e29e508` | Subsequent normal direct Gate 4H passed in 101.24 seconds with a complete twelve-observation journey |
| `lifecycle-pass-20260905T165418Z` | `139b524` | Repeated normal direct Gate 4H passed in 101.97 seconds with the complete twelve-observation journey and the revised cleanup completion order |

All five runs above recorded successful controller and outer-runtime cleanup, zero controller-owned survivors, and no remaining recorded process immediately after completion. The driver rebound every leased UDP port in its recorded address families, found the private control namespace removed and the cooperative port and build leases released, and compared SHA-256 hashes of the selected-build state file, selected receipt and guest media, and all five original ITS media inputs before and after each run. No recovery cleanup of a launcher-owned process, port, socket, or lease was needed between the runs. Each start used new disposable guest copies.

Run `lifecycle-coexistence-20260905T165600Z` at clean `139b524` extended verification to the existing NCC composition. It passed all nine established evaluator checks in 162.22 seconds, with attributed trouble and throughput reports from IMPs 5, 6, 7, and 62 and the supported mapped-line observation. Its own accepted ten-observation journey retained `missing-boundary` at `boundary:request:6`; no direct-route host-ingress trace was added or inferred. All eight recorded processes were absent immediately afterward, all fourteen leased ports were bindable, both cleanup layers passed, the control directory and leases were released, and the same input-preservation and diagnostic immutability checks passed.

At clean `139b524`, `lifecycle-missing-build-20260905T170128Z` retained the missing build-directory reason with exit 66, and `lifecycle-busy-build-20260905T170128Z` retained the build-lease stage, busy-lease diagnostic, and exit 75. Neither allocated a controller or ports; neither invented controller cleanup. The busy test's independently owned lease directory kept its exact device/inode identity until its owning driver released it. The stable selected-build file remained unchanged. Earlier exploratory results `lifecycle-missing-build-20260905T165337Z` and `lifecycle-busy-build-20260905T165337Z` remain retained; the clean repetitions above are the cited preflight evidence.

## Verification and remaining gaps

The complete suite passes 404 source tests, with the expected local-UDP skip in the restricted environment; the shell suite passes with its expected restricted-environment Unix-socket skip. Tests cover partial launch and post-spawn manifest failure, peer exits during buffered console readiness and settling waits, missing watchdog logs, continued cleanup after individual errors, repeated signals, ownership relinquishment on cleanup retry, result collisions, early input failure, and incomplete or contradictory progress and cleanup records. The full-history source guard passes. Linux Python 3.11 and 3.14 and macOS Python 3.14 CI passed [implementation `139b524`](https://github.com/brfid/arpanet-redux/actions/runs/33979276140).

Five older retained results — direct TELNET, interactive failover, a failed two-ITS run, line fault, and loopback — kept their previous recorded outcomes and cleanup uncertainty. Repeated read-only diagnostics were identical, matched the input byte-range digests, and left retained file sizes and modification times unchanged. The same checks passed on the new simulator results. These diagnostic operations neither revalidated a historical gate nor probed or signaled an old recorded PID.

This batch does not make every preflight failure retain a result. Make verification prerequisites still run before the launcher, and invalid invocations, result collisions, unwritable result paths, host crashes, uncatchable termination, or failed evidence writes can prevent records. Missing terminal and cleanup records remain unknown. Live peer watching covers the direct controller's owned simulators; outer auxiliary processes and the other controller compositions retain their existing checks. Permanent I/O failure and forced controller termination can still prevent complete cleanup evidence. Persistent guest workspaces, automatic stale-lock reclamation, and broader failover tracing are deferred.

Raw results, verification drivers, terminal logs, diagnostics, CI records, and input-preservation checks remain in the external laboratory, with review artifacts under `/Users/brf/src/arpanet-redux-lab/reviews/lifecycle-recovery-20260905/`. The [harness](../harness.md) owns current record and ownership contracts; the [runbook](../runbook.md#diagnose-a-retained-run) owns operator usage.
