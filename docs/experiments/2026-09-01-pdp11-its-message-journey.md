# Formal Gate 4H typed message-journey emission

- **Observed:** 2026-09-01
- **Repository checkpoint:** `c52a5796de73d2e32ff0cba5eb6307d5db18e5e2`
- **Fresh external result:** `/Users/brf/src/arpanet-redux-lab/results/pdp11-its-telnet-message-journey-20260901T123307Z`
- **Retained replay input:** `/Users/brf/src/arpanet-redux-lab/results/pdp11-its-telnet-20260831T200436Z`
- **Scope:** Formal emission, manifest binding, readback, retained replay, and cleanup for the additive version-1 typed journey sidecar accepted by [ADR-013](../adr/0013-ncc-message-journey-stream.md)

## Question

Can the accepted PDP-11-to-ITS Gate 4H harness emit the existing source-only message-journey model from exact post-probe H316 trace windows, retain direct and harness-derived authority separately, verify the reducer result and sidecar digest, and still complete its formal lifecycle without changing a guest, simulator, accepted application verdict, or existing NCC schema?

## Method

Source-only extraction and stream tests first exercised exact and changed MI packet content, repeated observations, progressive prefixes, an incomplete final JSONL record that later becomes complete, a record after terminal diagnosis, a tampered terminal diagnosis, exact trace-window offsets and digests, and the read-only retained-result command. The complete source-only suite passed 155 tests with one expected local-UDP skip; the runtime shell suite passed with its expected Unix-domain-socket skip in the restricted test environment.

The retained accepted Gate 4H result was then read through `scripts/ncc-extract-pdp11-its-journey.py`, with output directed to a new temporary directory. SHA-256 checks of its manifest, application evidence, cleanup evidence, outcome, and both H316 logs were identical before and after the replay.

Only controller integration remained live-only. One fresh formal smoke reused the accepted receipt-bound build rather than rebuilding media or reconsidering settled TELNET and simulator findings:

```sh
make LAB_ROOT=/Users/brf/src/arpanet-redux-lab RUN_ID=message-journey-20260901T123307Z PDP11_BUILD_ROOT=/Users/brf/src/arpanet-redux-lab/results/pdp11-telnet-formal-build-20260831T200328Z smoke-pdp11-its
```

The controller validated the dedicated shared topology before launch, captured fixed H316 end offsets only after the existing application reducer passed, wrote and read back `message-journey.jsonl`, recorded its digest and diagnosis in the manifest, and then used the unchanged bounded cleanup path. No retained result was modified and no raw artifact was added to the repository.

## Exact identity

The fresh run started at `2026-09-01T12:33:30Z` and finished passed at `12:35:15Z`. Its manifest records clean repository revision `c52a5796de73d2e32ff0cba5eb6307d5db18e5e2`; clean ARPANET-in-a-Box, Network UNIX, H316 SIMH, KA10 SIMH, and IMP11-A sources at `78123c77b20dadd9b5967b184dbcb4195185eea6`, `464893a99da8e3ac7f90577bc54749fa64bb0966`, `feb155fbc49333e879ab082d481e6dcce27d2d91`, `5f57231e96ea823fa3f109d68e970546dcb08a31`, and `2722eef44f68642eaab9f5d4e989ccd26e55e7de`; and H316, KA10, and PDP-11 executable SHA-256 values `bdbcdffc63ada17c9ec6c7151aba42fd96388ff33d41ec6d42c5b27f47cfb994`, `ce491428206a64eecb691a1c5a54a33323e65c355e8507fdc4982cf9b2f9d350`, and `d1d6046647025cc822d90d3ebb2d633d24f9513e03bf2c7eca6dcef75bfe5ae3`.

The reused PDP-11 build receipt SHA-256 was `1cc22c10da31c09f6066b421a0458478c70ac0dc48f065dc23295a5015a1532c`. The committed message-journey topology SHA-256 was `aca72d0e14fa70eb7e0af9f86c30612e0de692a766dc7e3500ca768fd2331ad0`. All six UDP ports were privately leased for the run.

## Typed journey result

The existing Gate 4H application evidence passed unchanged: Network UNIX printed `Connection open`, ITS recorded service job `53TLNT`, the client received the greeting and structured remote `:TIME`, and both IMPs had exactly correlated post-probe traffic. The typed sidecar then recorded ten observations across the twelve topology-derived request/reply boundaries.

Eight observations have direct `h316-hi-mi-trace` provenance. The request host-176 egress and reply host-106 egress observations have separate `h316-connected-peer-delivery` provenance because an H316 host-interface receive directly proves receipt by the connected IMP and supports only the peer egress conclusion. The request transport identities were `783`, `783`, `1131`, `1131`, and `9`; the reply identities were `6`, `6`, `1140`, `1140`, and `269`. Literal MI packet equality joined the two IMP sources, while no independent simulator ticks were compared.

The reducer marked request boundaries 1 through 5 and reply boundaries 1 through 5 observed. It retained request boundary 6 at host-106 ingress and reply boundary 6 at host-176 ingress as missing. The terminal state was therefore `missing-boundary`, with first unresolved `boundary:request:6` and supporting observation IDs `observation:request:1` through `observation:request:5` plus `observation:reply:1` through `observation:reply:5`. This diagnostic result coexists with the independently passed application verdict; it does not reinterpret application success as a packet-level host-ingress observation.

The fresh IMP 6 transaction window was bytes `1166992` through `1424766`, SHA-256 `6ca9f908439f6198a4af27d825b72b44baf3fc9e29928716f8a86cce3e6295b3`. The IMP 62 window was bytes `1805052` through `2065933`, SHA-256 `2ec76da86f556b5991ec88bcaf480625cd9030465db22d6bce2c3691ccecce3e`. The terminal sidecar SHA-256 was `c1be793d7120d8f98bd22681dd7b420513f1ec8c20190a7c2fe4c888d3080d8e`. A separate read-only derivation using the manifest's recorded end offsets was byte-identical to the controller-emitted sidecar.

The retained accepted run independently replayed to the same ten observation identities, direct/harness authority split, transport identities, terminal state, and first missing boundary. Its IMP 6 and IMP 62 trace slices began at offsets `1161897` and `1799890`; their retained file ends were `1582689` and `2251125`. No retained artifact hash changed.

## Lifecycle result

The formal smoke recorded `repository.tracked_dirty=0`, `cleanup.outer-runtime=passed`, `surviving_owned_processes=0`, `outcome=passed`, and `exit_status=0`. The owned PDP-11 and both IMP processes were terminated through the existing bounded path, ITS exited zero, and the runtime directory retained only its manifest and lease logs after socket-namespace cleanup.

## Limits and next decision

This result proves typed emission, exact-window provenance, reducer/readback agreement, deterministic retained replay, and formal lifecycle integration for one accepted Network UNIX-to-ITS TELNET transaction. It does not prove either destination guest's exact packet ingress, add a KA10 or IMP11-A parser, change the Gate 4H application standard, extend an accepted completed-summary or live schema, add browser control, or authorize animated traffic from configured topology.

No next slice is selected by this experiment. The closest continuation is a passive journey view over Python-resolved stream snapshots. Closing either missing host-ingress boundary instead requires a separately proven full extraction grammar, and original NCC System 52 or another historical host/application remains a later explicit decision.
