# NCC-observed Network UNIX-to-ITS coexistence

- **Observed:** 2026-09-01
- **Repository checkpoint:** `982462e12de6fdc70bc1a73a1b3871377fb7ac9c`
- **Fresh external result:** `/Users/brf/src/arpanet-redux-lab/results/ncc-pdp11-its-coexistence-canonical-20260901T153758Z`
- **Scope:** One bounded composition combining the accepted Network UNIX-to-ITS application route with passive NCC report reception; no telemetry or journey schema change, report-line inference, simulator modification, or additional simulator authority

## Decision

The coexistence composition passes. Network UNIX host `176` completed the accepted TELNET and structured remote `:TIME` proof against ITS host `106` through IMP 62 MI1 and IMP 6 MI3 while the same lifecycle kept IMPs 5 and 7 plus the passive NCC receiver active. The receiver independently attributed checksum-valid patched Type 303 trouble reports and Type 302 throughput reports to IMPs 5, 6, 7, and 62. It also retained a fresh reciprocal `up` reduction for the already mapped IMP 5 line 1 / IMP 6 line 1 pair.

This result proves that an application-bearing heterogeneous route and genuine NCC report ingress can coexist in one growing simulation without copying either evidence plane into the other. It does not close `boundary:request:6`, map the application or alternate links to historical report lines, prove application rerouting through IMPs 5 or 7, or turn the receiver or a browser into a simulator controller.

## Composition and source basis

The shared topology preserves the accepted application route `host:176` → `imp:62` → `imp:6` → `host:106`. IMP 62 remains on MI1 and HI2. IMP 6 keeps the proven NCC triangle on MI1 and MI2, moves only the IMP 62 application cable to MI3, and keeps ITS on HI2. IMP 5 retains the passive receiver on HI1 and the exact reciprocal IMP 5 MI1 / IMP 6 MI1 report-line-1 mapping. The IMP 5 / IMP 7 and IMP 7 / IMP 6 bindings remain deliberately unmapped.

The pinned H316 simulator exposes independent MI1 through MI5 devices in its project source. The recovered firmware's unchanged `HOST34=0` build defines five modem and two host interfaces, so this composition needs no firmware deposit or simulator extension. BBN Technical Information Report 89 describes the firmware's distributed, per-destination routing and the five-modem IMP configuration; Dave Walden's [IMP-code preservation collection](https://walden-family.com/impcode/) and the primary [TIR 89 scan](https://walden-family.com/impcode/Technical_Information_Report_89.pdf) are the historical references. The current upstream H316 source still contains the pinned commit and has no later modem-interface change that this composition depends on.

## Exact-run readiness correction

The first live attempt, external result `/Users/brf/src/arpanet-redux-lab/results/ncc-pdp11-its-coexistence-canonical-20260901T153209Z` at repository commit `8cb23fe2b4021c6655dcd41b6eb0af21bdd5033d`, failed cleanly before either guest booted. IMP 6 reached watchdog word `017400`, but the reused application controller waited for the whole one-link sentinel `077400` and timed out after 60 seconds.

That failure was exact new evidence rather than an MI3 failure. The recovered 1973 firmware listing's `LITT` table assigns active-high dead indicators to modem channels 1 through 4 and host channels 1 through 4. `017400` therefore has the MI1, MI2, and MI3 dead bits clear; the extra live NCC channels make the whole word different from the one-link topology. The controller was narrowed to test only the topology-selected modem bit and HI2 host bit, and post-probe regression detection now tests only the selected modem bit. The unchanged one-link MI1/HI2 state `075400` still satisfies the same predicate. MI5 is rejected by this predicate because the recovered status-light table exposes no fifth modem bit.

The correction added synthetic bit-selection and regression tests. The complete source-only suite passed 173 tests with the expected local-socket skip in the restricted test environment. No existing two-ITS controller call site, schema, firmware, simulator, or accepted application condition changed.

## Exact accepted run

The accepted entry point was:

```sh
make LAB_ROOT=/Users/brf/src/arpanet-redux-lab RUN_ID=canonical-20260901T153758Z PDP11_BUILD_ROOT=/Users/brf/src/arpanet-redux-lab/results/pdp11-telnet-formal-build-20260831T200328Z smoke-ncc-pdp11-its
```

The run started at `2026-09-01T15:38:17Z` and finished passed at `15:40:54Z`. Its manifest records clean repository revision `982462e12de6fdc70bc1a73a1b3871377fb7ac9c`; clean ARPANET-in-a-Box, Network UNIX, H316 SIMH, KA10 SIMH, and IMP11-A sources at `78123c77b20dadd9b5967b184dbcb4195185eea6`, `464893a99da8e3ac7f90577bc54749fa64bb0966`, `feb155fbc49333e879ab082d481e6dcce27d2d91`, `5f57231e96ea823fa3f109d68e970546dcb08a31`, and `2722eef44f68642eaab9f5d4e989ccd26e55e7de`; and H316, KA10, and PDP-11 executable SHA-256 values `bdbcdffc63ada17c9ec6c7151aba42fd96388ff33d41ec6d42c5b27f47cfb994`, `ce491428206a64eecb691a1c5a54a33323e65c355e8507fdc4982cf9b2f9d350`, and `d1d6046647025cc822d90d3ebb2d633d24f9513e03bf2c7eca6dcef75bfe5ae3`.

The reused PDP-11 build receipt SHA-256 was `1cc22c10da31c09f6066b421a0458478c70ac0dc48f065dc23295a5015a1532c`. The shared topology SHA-256 was `cbbbe8f191c93786085c234fe513efb6ece65ad0d408eaba3bb94da0dcd2e43f`; the IMP 5 and IMP 6 configuration SHA-256 values were `8d0658f6474d07cee94d26381e058cb0535ad77a640057dbbf0924a2bc8c066b` and `5ab915d2985f66804a2f9c512409fc7a255ddaa99cf38f25e8db59b60ac89c3d`. The run leased fourteen distinct dual-stack UDP ports.

## Application and typed journey

The application controller recorded `Connection open`, ITS service job `53TLNT` from `HST176`, the complete greeting, structured remote time/date/uptime, HI2 traffic on both application IMPs, and exact significant MI content correlated in both directions across IMP 62 MI1 / IMP 6 MI3. The non-fatal legacy TELNET option diagnostic remained observed.

The same controller emitted and read back the existing version-1 journey sidecar from fixed H316 trace windows. The IMP 6 slice was bytes `3486230` through `3966688`, SHA-256 `e4abe3b6f5476ef872bce9aa4499bc45477a1d82cdbbd61e7aa6cb848f5e3746`; the IMP 62 slice was bytes `1825661` through `2089028`, SHA-256 `b635862b7ee79baacd7a49d5b995df8c3ee0d846b3046352b186510af24fd3fd`. The sidecar SHA-256 was `004106f0b11b5f6c7fdb75abf29cb873e72da17eacbbd6d9ff453c084f59da52`.

The journey retained ten observations and the same `missing-boundary` diagnosis at `boundary:request:6`. Moving the application cable to IMP 6 MI3 changed only which exact H316 device the topology-selected extractor reads; it supplied no KA10 receive-assembly evidence and created no host-ingress observation.

## NCC report result

During its 150-second attachment, the receiver sent 149 host-ready packets, received 93 IMP-ready packets, reassembled 90 complete IMP output messages, and wrote 481 direct events after its stream header. It accepted 44 checksum-valid trouble reports: 15 from IMP 5, 8 from IMP 6, 13 from IMP 7, and 8 from IMP 62. It accepted 41 checksum-valid throughput reports: 14 from IMP 5, 7 from IMP 6, 13 from IMP 7, and 7 from IMP 62.

The evaluator's latest fresh reciprocal direct-line `up` pair was IMP 6 sequence 322 at `15:39:46.630719Z` and IMP 5 sequence 355 at `15:39:57.108588Z`. Those exact sequences are retained in `verdict.json`; its SHA-256 is `3e8896c3025e2e23ba1ac3462d54d77c4a804cb7ae3a0baa743d90b530cec9ec`.

The receiver intentionally remained alive after the application controller stopped IMPs 6 and 62. Its later tape therefore records teardown effects: IMP 5 eventually reported the direct line down at sequence 475 while IMP 6's last endpoint report aged stale. The formal coexistence verdict requires an earlier fresh reciprocal `up` pair and does not relabel the final teardown snapshot as an application failure. A future combined desk must keep the accepted support pair, later direct observations, and lifecycle phase visibly distinct.

## Lifecycle and visualization audit

All nine evaluator checks passed. The application controller and receiver exited zero, every source checkout was clean, `surviving_owned_processes=0`, `cleanup.outer-runtime=passed`, `outcome=passed`, and `exit_status=0`. No simulator log contains a transport failure. The build/use lease and cooperative port lease were released.

Read-only projection of the retained journey sidecar reaches its existing terminal view with ten observations and the unchanged missing boundary. Read-only projection of the historical sidecar accepts the seven-component shared topology, preserves six configured-only links, and shows only the mapped IMP 5 / IMP 6 direct line as historically reconciled. Its completed-summary handoff remains pending because that adapter intentionally supports only the fault and loopback result forms.

## Limits and next decision

This pass establishes the architectural seam needed for a growing simulation: one shared topology and lifecycle can carry a historical application route, additional routing peers, and passive NCC report ingress while retaining separate application, journey, report, reducer, and harness authority. It does not prove that application packets traverse IMPs 5 or 7, that any configured IMP number represents a historical site, that unmapped MI devices correspond to report lines, or that the original NCC System 52 can boot.

The next bounded NCC slice should be a unified passive coexistence desk over the already retained `historical-events.jsonl`, `message-journey.jsonl`, `application-evidence.txt`, and `verdict.json`. It should create only an in-memory Python projection and GET-only loopback presentation, show the accepted direct-line support pair separately from later teardown observations, and preserve the journey's missing host-ingress boundary. It should not add a persisted schema, parse raw logs, infer traffic on configured-only links, or gain simulator/controller authority. An application-relevant alternate-route fault remains a separate later gate.
