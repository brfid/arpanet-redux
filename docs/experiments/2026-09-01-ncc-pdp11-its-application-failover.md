# NCC-observed Network UNIX-to-ITS application failover

- **Observed:** 2026-09-01
- **Source-only implementation checkpoint:** `c73ef6d016214c2ee261653f7d8e42ab6413fdd8`
- **Readiness-gate checkpoint:** `6fd617f54d31ee5453d58656d892952b2b3003e6`
- **First retained exact attempt:** `/Users/brf/src/arpanet-redux-lab/results/ncc-pdp11-its-application-failover-canonical-20260901T201803Z`
- **Second retained exact attempt:** `/Users/brf/src/arpanet-redux-lab/results/ncc-pdp11-its-application-failover-canonical-20260901T202912Z`
- **Accepted exact run:** `/Users/brf/src/arpanet-redux-lab/results/ncc-pdp11-its-application-failover-canonical-20260901T204637Z`
- **Accepted comparison result:** `/Users/brf/src/arpanet-redux-lab/results/ncc-pdp11-its-coexistence-canonical-20260901T153758Z`
- **Scope:** One bounded acceptance pass for an NCC-observed cut of the existing IMP 62 / IMP 6 application cable and continued service over a configured IMP 62 / IMP 7 / IMP 6 route; no schema change, report-line inference, browser control, simulator modification, new component, or host-ingress parser

## Decision

Application failover passes at the bounded configured-composition claim. Exact run `ncc-pdp11-its-application-failover-canonical-20260901T204637Z` proves that one Network UNIX TELNET session reached ITS before and after a two-ended cut of the direct IMP 62 / IMP 6 application cable. Complete post-cut H316 records yield fourteen typed observations over IMP 62 / IMP 7 / IMP 6 and stop at the explicitly unproved host-ingress boundary `boundary:request:8`. The passive receiver retained post-cut trouble reports from IMPs 5, 6, 7, and 62, and every identity, application, relay, journey, observation, and cleanup check passed.

The first two exact attempts remain useful failed evidence. The first opened TELNET before Network UNIX had consumed the Reset Reply that marks host 106 alive. The second added that exact readiness gate and isolated a deterministic pre-cut configuration defect: the new IMP 62 configuration selected `set hi2 convert`, while the accepted Network UNIX attachment selects `set hi2 noconvert`. Complete IMP11-A packet records show the failed composition delivering the first complete IMP messages as six guest words in 24-byte transport records, rather than the accepted two guest words in 16-byte records. Network UNIX printed four `IMP:Pad error` diagnostics and never consumed the Reset Reply. Restoring `noconvert` removed that failure in the accepted run.

The run discovers reciprocal report-line candidates but does not promote them into the shared topology. It identifies the direct application binding as IMP 62 line 1 / IMP 6 line 3, changing from pre-cut `up` to post-cut `down`, and the alternate application binding as IMP 62 line 2 / IMP 7 line 3, post-cut `up`. Their retained status is `candidate-only-one-exact-run`. A future topology mapping requires independent reciprocal evidence rather than copying these values from one discovery run.

## Implemented gate

The source-only slice adds a shared topology with the existing IMP 62 / IMP 6 application binding behind a two-ended UDP relay and one configured IMP 62 MI2 / IMP 7 MI3 alternate binding. Both application-relevant bindings remain report-line-unmapped. The controller alone can request a cut through a run-owned request file; neither browser route gains command authority. The application gate requires two structured `:TIME` replies in the same TELNET session, one before and one after the cut.

The narrow journey adapter extends only the already-proven H316 message grammar. Its expected request route is host 176, IMP 62, IMP 7, IMP 6, and host 106, with fourteen direct or connected-peer observations and the first missing boundary at `boundary:request:8`. Synthetic fixtures prove construction, reduction, interrupted-record handling, and rejection paths. The accepted exact run, not those fixtures, supplies the route observation claim.

The default board gained only a completed-result adapter for the already accepted alternate-path fault and line-loopback result families. It did not acquire a new persisted contract, raw-log parser, simulator connection, link switch, or TELNET input path.

## First exact attempt and readiness correction

The first exact entry point was:

```sh
make smoke-ncc-pdp11-its-failover LAB_ROOT=/Users/brf/src/arpanet-redux-lab PDP11_BUILD_ROOT=/Users/brf/src/arpanet-redux-lab/results/pdp11-telnet-formal-build-20260831T200328Z RUN_ID=canonical-20260901T201803Z
```

The manifest records clean repository checkpoint `c73ef6d016214c2ee261653f7d8e42ab6413fdd8`, the accepted PDP-11 build receipt, and clean pinned source checkouts. Network UNIX booted and the controller opened TELNET too early; the guest printed `Host is Unavailable`, and the controller stopped. The relay forwarded 1,952 records from IMP 62 toward IMP 6 and 1,909 in the reverse direction, dropped none, recorded no unexpected source, and retained `fault_started_at: null`. Cleanup left zero owned processes.

Complete H316 host-interface records show the host-host Reset and Reset Reply traversing the interface after the attempted open had begun, but the guest had not consumed the reply before deciding host 106 was unavailable. That ordering is meaningful in the primary Network UNIX sources. [`hhi.h`](https://github.com/pdp11/network-unix-v6/blob/464893a99da8e3ac7f90577bc54749fa64bb0966/nosc-files/ncpd/hhi.h) assigns opcodes 12 and 13 to Reset and Reset Reply; [`hr_proc.c`](https://github.com/pdp11/network-unix-v6/blob/464893a99da8e3ac7f90577bc54749fa64bb0966/nosc-files/ncpd/hr_proc.c#L603-L646) makes `hr_rrp()` call `hs_alive()`; and [`send_pro.c`](https://github.com/pdp11/network-unix-v6/blob/464893a99da8e3ac7f90577bc54749fa64bb0966/nosc-files/ncpd/send_pro.c#L290-L418) sends Reset to hosts not yet marked up. The accepted coexistence console records `ir_reset`, `rst_all`, and `SKTRACE hh h=106 bytes=1 op=15` before TELNET begins. The failed console has no equivalent pre-open host-ready record.

The controller and evaluator were therefore narrowed to require that exact guest-consumed Reset Reply trace before invoking TELNET. This is a readiness condition derived from the guest's own source and accepted run, not a delay or an inference from network traffic.

## Second exact attempt and configuration diagnosis

The second exact entry point was:

```sh
make smoke-ncc-pdp11-its-failover LAB_ROOT=/Users/brf/src/arpanet-redux-lab PDP11_BUILD_ROOT=/Users/brf/src/arpanet-redux-lab/results/pdp11-telnet-formal-build-20260831T200328Z RUN_ID=canonical-20260901T202912Z
```

The manifest records clean readiness-gate checkpoint `6fd617f54d31ee5453d58656d892952b2b3003e6`. The new gate timed out after 120 seconds waiting for `SKTRACE hh h=106 bytes=1 op=15`. IMPs 62 and 6 and their host interfaces remained active and exchanged complete records, but the Network UNIX console never recorded `ir_reset`, `rst_all`, or Reset Reply consumption. The relay forwarded 2,762 records toward IMP 6 and 2,716 toward IMP 62, dropped none, recorded no unexpected source, and again retained `fault_started_at: null`. Cleanup left zero owned processes.

Comparison with the immutable accepted coexistence result isolates the mismatch before any route or extraction question. Its IMP 62 configuration uses `set hi2 noconvert`; the new composition copied `set hi2 convert`. The pinned H316 upstream implementation describes this switch directly: [`h316_hi.c`](https://github.com/larsbrinkhoff/simh/blob/feb155fbc49333e879ab082d481e6dcce27d2d91/H316/h316_hi.c#L401-L490) expands a short IMP leader into a long host leader only when conversion is enabled. Accepted complete IMP11-A records receive the initial messages as two words in 16-byte transport records. Both failed runs receive the corresponding expanded messages as six words in 24-byte records. Network UNIX reports four pad errors before its daemon initialization and does not process the reset sequence.

This diagnosis uses complete H316 message records, complete IMP11-A packet records, the guest console, and an exact accepted comparison. It does not reconstruct a message from partial `DATAIO` output, predict guest scheduling, or infer a report-line identity from MI or HI device names.

The IMP11-A upstream branch remains at the pinned receive-state fix [`2722eef44f68642eaab9f5d4e989ccd26e55e7de`](https://github.com/brfid/imp11a-simh/commit/2722eef44f68642eaab9f5d4e989ccd26e55e7de); a bounded issue, pull-request, and file-history check found no later device change or tracked report for this configuration mismatch. The pinned Network UNIX repository likewise has no tracked issue about this failure mode. The evidence points to this composition's setting, not a reason to alter either simulator.

## Accepted exact run

The accepted entry point was:

```sh
make smoke-ncc-pdp11-its-failover LAB_ROOT=/Users/brf/src/arpanet-redux-lab PDP11_BUILD_ROOT=/Users/brf/src/arpanet-redux-lab/results/pdp11-telnet-formal-build-20260831T200328Z RUN_ID=canonical-20260901T204637Z
```

The run started at `2026-09-01T20:47:02Z` and finished passed at `20:52:11Z`. Its manifest records clean repository checkpoint `26a99a070fbb96d35244dd736aa4e44cf6673d38`, the same clean pinned source identities and accepted PDP-11 build receipt as the earlier attempts, eighteen distinct leased UDP ports, controller/receiver/relay exit status zero, `cleanup.outer-runtime=passed`, `outcome=passed`, and `exit_status=0`.

Network UNIX recorded `ir_reset`, `rst_all`, and guest consumption of the host-106 Reset Reply before TELNET. The application evidence retains one connection, ITS service user `53TLNT`, structured remote time before the cut, an acknowledged cut, survival of that same session, and structured remote time after the cut. The relay began dropping both directions at `2026-09-01T20:48:31.683758Z`; before then it forwarded 1,380 records toward IMP 6 and 1,383 toward IMP 62, and afterward it dropped 1,228 and 1,103 respectively. It recorded no unexpected source.

The post-cut message-journey sidecar has SHA-256 `66dcfd737f93c26e03581f0b25c4983928378f1d1e6ca1ab7c43b4662229e252`. It retains fourteen observations: request and reply crossings at each host-side connected-peer seam and every direct H316 ingress/egress boundary through IMP 62 MI2, IMP 7 MI3/MI2, and IMP 6 MI2. The reducer marks request boundaries 1 through 7 and reply boundaries 1 through 7 observed, then retains `missing-boundary` at `boundary:request:8`; neither application success nor connected-peer provenance fills the two host-ingress boundaries.

During its 300-second attachment the receiver sent 297 host-ready packets, received 176 IMP-ready packets, reassembled 173 complete messages, and wrote 933 direct events after its stream header. It accepted 85 checksum-valid trouble reports: 28 from IMP 5, 15 from IMP 6, 28 from IMP 7, and 14 from IMP 62. It accepted 83 checksum-valid throughput reports: 28 from IMP 5, 14 from IMP 6, 27 from IMP 7, and 14 from IMP 62. Trouble reports from all four IMPs occur after the cut.

All thirteen evaluator checks passed. `verdict.json` has SHA-256 `40b5feb263b82339e26525e0ef376131002708de5c4aad7f5165728cc6ac0ede`; `historical-events.jsonl` has SHA-256 `40de32073f7bf0838b20b90858a73c579ea3a1874b2aaf5363b0e92bdb9283a6`. Cleanup retained `surviving_owned_processes=0`, and the outer runtime released its ports, locks, and process ownership.

## Limits and next decision

This result proves application-relevant failover in this exact configured test composition. It does not claim that IMPs 5, 6, or 7 are historical sites, establish a historical ARPANET route, generalize routing behavior beyond the observed transaction, or promote candidate report lines. The cut remains controller-owned through a run-local request file; the browser retains no simulator, relay, guest-input, restart, or result-mutation authority.

The earlier KA10 host-ingress finding is unchanged. `boundary:request:6` in the accepted direct journey still lacks a complete receive-assembly grammar, and no parser is implemented for it. The accepted failover route's later `boundary:request:8` is likewise an explicit missing host-ingress boundary, not a claim derived from application success.
