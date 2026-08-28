# Phase-one feasibility report

- **Observed:** 2026-08-28
- **Scope:** Background research and isolated native smoke testing on Apple Silicon

This is a dated evidence report. The README owns current status, [`pins/`](../../pins/) owns active revisions and hashes, and the [test plan](../test-plan.md) owns acceptance requirements.

## Finding

A genuine host–IMP–IMP–host pipeline is feasible on the tested Mac. Native arm64 H316 and KA10 simulators ran recovered 1973 IMP software, two IMPs routed normal and failure traffic, and a KA10/ITS guest exchanged three NCP echo transactions with a diagnostic endpoint through exactly those two IMPs.

The shortest production-shaped next step was two KA10/ITS guests: host `106` on IMP 6 and host `176` on IMP 62. This same-family pair avoided a modern NCP bridge and deferred new simulator-device development until the network and payload contracts were stable.

## Resource survey

[ARPANET in a Box](https://github.com/obsolescence/arpanet) supplied the most useful prepared laboratory: recovered IMP firmware, H316 configurations, KA10/ITS disk sets, nested simulator and NCP sources, and a network map. Its project page describes the simulated leased lines and self-organizing IMP routing. It remains a work in progress and is an external input, not vendored project source.

The recovered router software has a documented provenance trail through the [SIMH software-kit catalog](https://simh.trailing-edge.com/software.html) and the contemporary [ARPANET IMP resurrection report](https://www.bitsavers.org/pdf/bbn/imp/The_ARPANET_IMP_Program_-_Retrospective_and_Resurrection_201312.pdf). The older [H316 IMP documentation](https://opensimh.org/simdocs/h316_imp_doc.html) describes the device and UDP modem model, although its warning that the host interface is only a skeleton predates the working fork tested here.

The pinned [KA10 simulator fork](https://github.com/larsbrinkhoff/ka10-simh) adds NCP mode and an IMP-emulator attachment. Rebuilding it natively avoided the prepared bundle's Linux executable.

The current [PDP-10/ITS project](https://github.com/PDP-10/its) provides automated KA builds and configurable networking. Its pinned [`NITS.md`](https://github.com/PDP-10/its/blob/0f7d67997f9f5d30208e117e73272031e74f16b9/doc/NITS.md) identifies `IMPP`, `IMPUS`, and `NCPP` as the relevant interface, address, and NCP settings. At the observed revision, the generic KA configuration supplied the required host-`176` identity.

The [Stanford WAITS SIMH quick start](https://github.com/timereshared/stanford-waits-simh-quickstart) offered a visibly different prepared guest, but its available integration terminated NCP in a modern Linux bridge. It was therefore less faithful at the boundary under test.

[SRI/NOSC Network UNIX V6](https://github.com/pdp11/network-unix-v6) contained a genuine PDP-11 NCP and became the preferred heterogeneous follow-up. It was not turnkey because stock PDP-11 SIMH lacked the guest's IMP11-A or ACC host interface. The dedicated [PDP-11 research note](pdp11-network-unix.md) tracks that path.

## Candidate comparison

| Pair | Native historical interfaces | Preparation | Assessment on 2026-08-28 |
|---|---:|---:|---|
| KA10/ITS + KA10/ITS | Both endpoints | One known-good image; a second could be built | Selected baseline |
| KA10/ITS + Linux NCP | One endpoint | Ready and observable | Diagnostic oracle only |
| KA10/ITS + WAITS bridge | ITS endpoint only | Prepared | Deferred because the bridge bypasses guest NCP |
| KA10/ITS + SRI/NOSC Network UNIX V6 | Potentially both | Missing PDP-11 controller integration | Best heterogeneous follow-up |
| Existing VAX/BSD + PDP-11/BSD | Neither with current devices | Existing guest images | Not rewiring-compatible |

## Native builds

The bundled executables were Linux x86-64 and could not run on the arm64 host. H316 SIMH, the diagnostic NCP daemon and applications, and the KA10 simulator all built natively from the sources recorded in [`pins/sources.lock.toml`](../../pins/sources.lock.toml). No Docker daemon, system-Python modification, or system-directory installation was used.

The H316 and KA10 binaries identified the intended source revisions. The source-only project later added executable and build-receipt verification so a stale binary could not silently satisfy a smoke.

## Router oracle

Two diagnostic NCP endpoints attached to two H316 IMPs exchanged three echo requests and replies. A request for an adjacent IMP with no host returned the expected failure:

```text
NCP PING host 003
Reply from host 003: seq=1 time=123ms
Reply from host 003: seq=2 time=115ms
Reply from host 003: seq=3 time=71ms

Host is not up.
NCP PING host 004
```

The traces contained regular packets, RFNMs, return packets, and a type-7 DEAD response. This isolated recovered routing and failure reporting before a vintage guest was introduced.

## Mixed ITS and diagnostic-host smoke

Prepared ITS host `106` booted to `KA ITS 1652 IN OPERATION`, announced `SYSTEM JOB USING THIS CONSOLE`, reset its IMP interface, and exchanged host-interface traffic with IMP 6. The H316 trace converted the KA10's 96-bit long leaders into the short leaders used inside the recovered IMP network and converted replies back.

With diagnostic host `076` attached to IMP 62, ITS completed three NCP echo transactions through IMP 6 and IMP 62:

```text
NCP PING host 106
Reply from host 106: seq=1 time=148ms
Reply from host 106: seq=2 time=96ms
Reply from host 106: seq=3 time=109ms
```

For every transaction, the diagnostic NCP logged an ECO request, an RFNM from host `106`, and the matching ERP reply. Both H316s recorded host-interface traffic, and IMP 6 recorded the required leader conversions.

## Publication-snapshot revalidation

After the simulator command files were reduced to minimal project-specific compositions for public release, both passing gates were rerun from the candidate snapshot. The router run `router-oracle-config-minimal-20260828` received replies from host `003` at 57, 98, and 51 ms and received the expected host-`004` failure. The mixed run `its-linux-config-minimal-20260828` received replies from ITS host `106` at 97, 126, and 121 ms and satisfied the ordered leader-conversion check. Both external manifests ended with `outcome=passed` and `exit_status=0`.

The external result directories retain complete logs and machine-local paths. This report preserves only the nonrestricted application transcript and outcome summary; it does not turn raw evidence or historical media into repository content.

## Second ITS identity

A second prepared host at another address booted from an isolated disk copy, confirming that two KA10 simulators and media workspaces could coexist. The supplied host-`176` selector was not turnkey: one path entered `SALVAGER.317` and reported missing user-directory files, while another produced a file-not-found result.

On a copy of the known-good host-`106` disks, ITS assembled a monitor for the generic KA machine in roughly 30 seconds. A boot-time deposit also demonstrated `IMPUS=176`, but a persistent dump reproduced the prepared disk's salvager failure. Those experiments proved the address and simulator behavior, not a promotable image. The decision was therefore to use a clean current-source build.

## Host-platform findings

The upstream test wrapper depended on GNU Screen and sent literal control-sequence text that macOS Screen 4.00.03 did not interpret as expected. Exact-PID process orchestration was both portable and easier to clean up.

Each UDP interface needed a unique local port. An upstream example reused one local port for two modem interfaces, which macOS rejected. Explicit IPv4 loopback peers also avoided an IPv4/IPv6 mismatch because the diagnostic NCP daemon bound IPv4.

The reliable launch order was diagnostic listeners, H316 IMPs, then vintage hosts. Fixed boot sleeps were replaced by console and protocol evidence because ITS startup varied from seconds to minutes under load.

## Resulting decision

The experiment supported [ADR-001](../adr/0001-two-imp-baseline.md): establish the two-ITS network first, retain the diagnostic endpoint as an oracle, and substitute a heterogeneous native-NCP guest only after the application and anti-bypass contracts pass.

Redistribution conclusions are centralized in [`NOTICE.md`](../../NOTICE.md). This report's external links and checksums establish identity and research provenance, not permission to redistribute historical material.
