# NCC-observed Network UNIX-to-ITS application failover feasibility

- **Observed:** 2026-09-01
- **Source-only implementation checkpoint:** `c73ef6d016214c2ee261653f7d8e42ab6413fdd8`
- **Readiness-gate checkpoint:** `6fd617f54d31ee5453d58656d892952b2b3003e6`
- **First retained exact attempt:** `/Users/brf/src/arpanet-redux-lab/results/ncc-pdp11-its-application-failover-canonical-20260901T201803Z`
- **Second retained exact attempt:** `/Users/brf/src/arpanet-redux-lab/results/ncc-pdp11-its-application-failover-canonical-20260901T202912Z`
- **Accepted comparison result:** `/Users/brf/src/arpanet-redux-lab/results/ncc-pdp11-its-coexistence-canonical-20260901T153758Z`
- **Scope:** One bounded feasibility pass for an NCC-observed cut of the existing IMP 62 / IMP 6 application cable and continued service over a configured IMP 62 / IMP 7 / IMP 6 route; no schema change, report-line inference, browser control, simulator modification, new component, or host-ingress parser

## Decision

Application failover is not proven, and this branch is not ready for integration. Both exact attempts stopped before the direct application cable was cut. They therefore provide no evidence of route convergence through IMP 7, a post-cut application transaction, the proposed fourteen-observation typed journey, a new report-line identity, or extraction from real post-cut trace windows.

The second stop did isolate a deterministic pre-cut configuration defect. The new IMP 62 configuration selected `set hi2 convert`, while the accepted Network UNIX attachment selects `set hi2 noconvert`. Complete IMP11-A packet records show the failed composition delivering the first complete IMP messages as six guest words in 24-byte transport records, rather than the accepted two guest words in 16-byte records. Network UNIX printed four `IMP:Pad error` diagnostics and never consumed the Reset Reply needed to mark host 106 alive. The configuration now restores `noconvert`, with a source-only regression assertion, but this pass deliberately stops before a third exact run.

The exact missing property is therefore a clean post-correction run that first proves guest consumption of the host-106 Reset Reply and then proves the entire fault contract: one TELNET session returns structured ITS `:TIME` output before and after the cut; the relay records the requested two-ended cut of only the IMP 62 / IMP 6 cable; the network converges over IMP 62 / IMP 7 / IMP 6; complete H316 records yield the proposed fourteen typed observations and stop at the still-unproved `boundary:request:8`; NCC reports continue after the cut; any newly reciprocal report-line identities remain candidates rather than topology authority; and every owned process and lease is cleaned up. Until one run proves all of those properties, the failover result, typed route, and candidate mappings must not be promoted.

## Source-only feasibility gate

The source-only slice adds a shared topology with the existing IMP 62 / IMP 6 application binding behind a two-ended UDP relay and one configured IMP 62 MI2 / IMP 7 MI3 alternate binding. Both application-relevant bindings remain report-line-unmapped. The controller alone can request a cut through a run-owned request file; neither browser route gains command authority. The application gate requires two structured `:TIME` replies in the same TELNET session, one before and one after the cut.

The proposed narrow journey adapter extends only the already-proven H316 message grammar. Its expected request route is host 176, IMP 62, IMP 7, IMP 6, and host 106, with fourteen direct or connected-peer observations and the first missing boundary at `boundary:request:8`. Synthetic fixtures prove construction, reduction, interrupted-record handling, and rejection paths. They do not claim that an exact run traversed the alternate route.

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

## Bounded stop and next exact gate

`config/imp/ncc-pdp11-its-failover/imp62.simh` now matches the accepted Network UNIX interface mode with `set hi2 noconvert`, and the topology test rejects a return to `set hi2 convert`. Source-only verification is necessary but cannot replace the missing exact run.

No third run was made in this pass. The correction has therefore not yet proved even the first runtime gate, much less the cut and alternate path. The next action is exactly one clean post-correction run through the existing formal entry point. If it fails, the retained artifacts must identify the first unsatisfied acceptance property and the investigation must stop there. It must not be converted into a looser parser, expanded simulator authority, a browser-side control, inferred telemetry, or another component.

The earlier KA10 host-ingress finding is unchanged. `boundary:request:6` in the accepted direct journey still lacks a complete receive-assembly grammar, and no parser is implemented for it. The source-only failover route's later `boundary:request:8` is likewise an explicit missing host-ingress boundary, not a claim derived from application success.
