# Interactive same-session Network UNIX TELNET failover

- **Observed:** 2026-09-04
- **Repository checkpoint:** `5dc6ba6d5e2ae53fefc96b21bce4503faa6be3fb`
- **Fresh external result:** `/Users/brf/src/arpanet-redux-lab/results/pdp11-its-interactive-failover-accepted-20260904T174500Z`
- **Status:** Accepted for the bounded human-operated failover scope in [ADR-018](../adr/0018-interactive-telnet-failover.md) and [Gate 4K](../test-plan.md#gate-4k-interactive-same-session-telnet-failover)

## Question

Can one foreground controller let a human open the preserved Network UNIX TELNET client, prove a structured ITS transaction on the direct IMP 62 / IMP 6 cable, intercept one local cut key, wait for the acknowledged transition to the IMP 62 / IMP 7 / IMP 6 route, and receive another structured response in the same guest connection while retaining exact terminal, relay, route, identity, and cleanup evidence?

## Method

The implementation adds no topology, simulator configuration, guest program, TELNET stack, browser input, report decoder, or report-line identity. It composes the accepted character terminal with the accepted four-IMP application-failover launcher, gives that launcher an explicit terminal profile, and extends the directional terminal stream additively to version 2. Version 1 and the formal failover profile remain the defaults for their existing entry points.

Before the exact run, 338 source tests passed. They cover the shared direct/failover character adapter, direct-mode Control-^ forwarding, failover-mode interception, strict version-1 and version-2 terminal records, refused and repeated cut semantics, one-connection enforcement, application evidence, formal and interactive evaluator profiles, shell parsing, Make wiring, lifecycle ownership, source-only boundaries, and existing reducers and displays. The environment-prohibited UDP-bind test was the only source-test skip; the exact external run exercised the real sockets.

The exact entry point was:

```sh
make RUN_ID=accepted-20260904T174500Z telnet-failover
```

After the controller reached the real Network UNIX root shell, the operator entered `/usr/bin/telnet`, `connect - -h 106`, and `:TIME`. After the full time, date, uptime, and DDT prompt returned, the operator pressed Control-^. The controller validated the direct transaction, requested its run-owned relay cut, required the atomic acknowledgement and direct-dead/alternate-ready state, applied the accepted settle interval, and announced that the IMP 7 route was ready. The operator entered a second `:TIME`, waited for its complete response, and pressed Control-] for validation and cleanup. No reconnect command was entered.

## Exact identity

The run started at `2026-09-04T16:25:04Z`, finished at `16:28:54Z`, and records clean repository checkpoint `5dc6ba6d5e2ae53fefc96b21bce4503faa6be3fb`. The clean ARPANET-in-a-Box, Network UNIX, H316 SIMH, KA10 SIMH, and IMP11-A source revisions are `78123c77b20dadd9b5967b184dbcb4195185eea6`, `464893a99da8e3ac7f90577bc54749fa64bb0966`, `feb155fbc49333e879ab082d481e6dcce27d2d91`, `4b59f21d00355a7a917fa7cd54ef8a1123b515b2`, and `c74e7040e186a6ea11d9cd816b94edc235959e27`.

The verified H316, KA10, and PDP-11 executable SHA-256 values are `bdbcdffc63ada17c9ec6c7151aba42fd96388ff33d41ec6d42c5b27f47cfb994`, `fbbaa7517ff84333bc6be7b148a1a3e4c43adcd08909b7270c68b157a8e97c98`, and `56e2e790a1bfc4cecc20ea2ffc2285fbccb772343d7d6cc551c2f259dbb92127`. The receipt-bound PDP-11 build SHA-256 is `b4fa7dd1519b4b658ddf2132a883a3ba57ec4e090f91462c13bc547d310f24dd`, and the shared failover topology SHA-256 is `902d660678b9ba8f56ebecf4fa8e03a61314d5634a1989b09d6296aaaa7be689`. All 18 UDP ports were privately leased, and all six tracked source identities report `tracked_dirty=0`.

## Terminal and application result

The strict `terminal-session.jsonl` header is schema version 2. It binds the exact run and repository revision, controller `pdp11-its-failover-controller`, initial route `route:host176-to-host106`, post-cut route `route:host176-to-host106-alternate`, the `seven-bit-safe-teletype` profile, local Control-] exit, blocked simulator WRU, and local Control-^ cut. Its SHA-256 is `7fb9f03f3bb37c6d37fdbd10c9aaebbd341edef73306e40965fc3b653d52224b`.

The stream ends with `operator-exit`, has no incomplete tail, and retains 48 data records, one local-control record, 45 operator-to-PDP-11 bytes, and 5,670 PDP-11-to-operator bytes. The input bytes are exactly the preserved-client launch, one connect command, and the two `:TIME` commands; neither Control-^ nor Control-] entered the guest stream. The sole local-control record is one `application-link-cut-requested`. The cumulative input and output SHA-256 values are `b18f6ecdbd1dc80123fcd39d8e038195774d63ecd0ff95dbf4ea372fddba968b` and `42f0cce6f5cca0903dd660cb76943d0641ce143270a64754f780ddd7960158ed`.

The preserved client printed `UNIX User Telnet -- Ver I.5` and exactly one `Connection open`. ITS created `53TLNT` for `HST176`, returned its ordered greeting, and answered both operator-entered `:TIME` commands with structured time, date, and uptime. The application evidence records `session_mode=interactive-failover`, `cut_acknowledged=1`, `session_survived_cut=1`, and no second connection.

## Cut and route result

The relay and atomic state file agree on fault time `2026-09-04T16:27:07.757532Z`. Before the request, the relay forwarded 1,946 IMP-62-to-IMP-6 datagrams and 1,954 in the reverse direction. After the cut, it dropped 1,442 and 1,394 datagrams respectively, accepted no unexpected source, and never resumed forwarding. Both direct endpoint devices became dead; the alternate endpoints and both IMP 7 route devices remained ready.

The pre-cut direct journey retains ten observations and stops at the existing missing `boundary:request:6`; its SHA-256 is `f02e67fe025e59e0829f1932617d5eeca9392588b75af534d2002a4c66e75c45`. The post-cut journey retains fourteen request and reply observations across IMPs 62, 7, and 6 on `route:host176-to-host106-alternate`, with its existing `missing-boundary` diagnosis at `boundary:request:8`; its SHA-256 is `9b7e6626b3a41d5f79f23d971bf4b3aec4d6edab5ce542e8c8d2a7b7c10c4dd7`. Neither application output nor configured topology fills either missing host-ingress boundary.

All 13 interactive verdict checks are true: identity chain, terminal-owned cut, forwarded and dropped relay traffic, no unexpected relay source, same-session post-cut time, Network UNIX host readiness, typed alternate journey, clean owned processes, clean pinned inputs, passed application outcome, outer cleanup, and declared interactive profile. The verdict SHA-256 is `cac54ffa1e903b86e50cf3ae589806cbe4f930b42740ccd3213eeb783da11c0c`; an independent read-only evaluation into `/private/tmp` reproduced it byte for byte.

The controller and relay exited zero, the run records `outcome=passed` and `exit_status=0`, `cleanup.outer-runtime=passed`, and `surviving_owned_processes=0`. The human profile did not start an NCC receiver and the verdict contains no report-source, report-line, or mapping check.

## Limits

This result proves one human-operated preserved Network UNIX TELNET connection before and after one controller-owned simulated cable cut, a controller-confirmed transition to the configured IMP 7 path, structured ITS service in the same guest session, exact bounded terminal retention, typed direct and alternate route evidence, and complete cleanup.

It does not prove passive NCC report reception, report-line identity, historical site identity for configured IMP numbers, a new topology, a new host-interface observation, full-screen or cursor-addressed terminal behavior, safe paged-program interaction, browser control, or a second TELNET implementation. The fourteen-observation failover journey remains incomplete at its explicitly named host-ingress boundary, and this application result does not alter that diagnosis.
