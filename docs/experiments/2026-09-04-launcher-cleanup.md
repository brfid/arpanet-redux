# Retained launcher failures and interrupted-run cleanup

- **Observed:** 2026-09-04
- **Initial implementation:** `3711669`, retained launcher termination and cleanup evidence
- **Cleanup repair:** `97e3561`, sufficient controller shutdown time and persistent failure when forced termination loses delegated cleanup
- **Scope:** Modern launcher evidence and process ownership on the existing pinned compositions; no guest, firmware, protocol, topology, or application-acceptance change

## Startup failure evidence

Run `run-failure-evidence-blocked-20260904T203200Z` used the direct Network UNIX-to-ITS launcher at clean revision `3711669`. Its private port-lock root was deliberately a regular file. Receipt, simulator, and media verification completed, then the port-reservation helper failed before controller launch. The result retained the helper's error, the launcher's explanation that reservation ended before readiness, exit status `1`, and a successful final cleanup attempt. No controller outcome was invented.

## Interruption exposed an ownership gap

Run `run-failure-evidence-interrupt-20260904T203218Z` used the same clean revision. The verification driver waited until both guest simulators had been launched, then sent `TERM` to its exact owned shell launcher. The manifest retained handled `TERM`, exit status `143`, and successful outer-runtime cleanup, but no controller outcome or controller cleanup file appeared.

A separate inspection matched four surviving simulator processes to this run's exact executables and configuration paths. The controller had been killed after the outer runtime's five-second allowance expired. Its own forced-shutdown path sequentially waits for guest and IMP termination, which can exceed five seconds. Killing that controller did not stop the separately sessioned simulators it owned. The diagnostic correctly kept controller cleanup unknown; its outer cleanup result described only the shell's direct resources.

The verification driver separately stopped those four identified simulators and retained `interruption-recovery.json` under the external review directory. The failed run's manifest and absent controller records were not replaced or relabelled.

## Repair and repeated interruption

The runtime now gives an owned background application controller 60 seconds to complete its existing bounded shutdown; leaf processes retain five seconds. The NCC operator allows 90 seconds for the whole launcher. These budgets cover the current sequential controller shutdown and the remaining outer resources. If a controller still requires `KILL`, outer cleanup records a persistent `controller-cleanup:PID` failure: retrying after its disappearance cannot recover knowledge of its delegated resources.

Run `run-failure-evidence-interrupt-20260904T203755Z` repeated the same interruption boundary at clean revision `97e3561`. It finished at `20:38:24Z` with handled `TERM`, exit status `143`, both cleanup layers recorded, and zero controller-owned survivors. The four simulator exit statuses were `-9`, reflecting their controller's bounded escalation; the controller itself completed and wrote its evidence. Independent checks immediately afterward found all five recorded controller/simulator PIDs absent, all six leased UDP ports bindable, the private control directory removed, and the port and build leases released.

## Normal application run

Run `run-failure-evidence-pass-20260904T203913Z` used clean revision `97e3561`, the existing receipt-bound PDP-11 build, and unchanged source and simulator pins. The direct TELNET smoke passed with its complete twelve-observation message journey, a passed controller outcome, zero controller-owned survivors, and successful outer cleanup. All five recorded PIDs were absent afterward and all six UDP ports could be rebound. The diagnostic reported the recorded success without acquiring application-gate authority.

## NCC manual finalization

Run `run-failure-evidence-line-20260904T204133Z` exercised the three-IMP loopback launcher at clean revision `97e3561`. Its existing evaluator passed, and its manually finalized manifest retained `cleanup.completed=1` alongside the new successful runtime cleanup record, one cleanup attempt, exit status `0`, and a finish time of `20:43:54Z`. All five recorded PIDs were absent afterward, all ten UDP ports could be rebound, and the cooperative port locks were released. The diagnostic reconciled both cleanup formats and reported the recorded pass. No line-state, mapping, or evaluator rule changed.

## Source and retained-result checks

All 379 source tests passed with one expected restricted-environment UDP skip; the runtime shell suite passed with its expected Unix-socket skip. New tests cover explicit failure descriptions, actual handled signals versus numeric signal-style exits, uncatchable termination, failed cleanup and retries, forced controller termination, manifest collisions and write failures, bounded error text, and cleanup that takes longer than a leaf-process allowance. The complete-history source guard passed.

Five older direct, interactive-failover, failed two-ITS, line-fault, and loopback results kept their recorded outcomes and cleanup uncertainty. Repeated diagnostics were identical, reported input digests matched their exact byte ranges, and retained files were unchanged. New-run verification uses the same digest and immutability checks.

Raw results remain under `/Users/brf/src/arpanet-redux-lab/results/`. Verification drivers, diagnostic reports, check logs, and the separate recovery record remain under `/Users/brf/src/arpanet-redux-lab/reviews/run-failure-evidence-20260904/`. The [harness](../harness.md#launcher-termination-records) owns the current record contract; the [runbook](../runbook.md#diagnose-a-retained-run) owns usage.

The repaired interruption proves cleanup for this exact direct composition. A host crash or uncatchable kill can still prevent terminal records, and no missing record proves current process liveness or release. Historical application and network evidence remains governed by the existing scenario gates.
