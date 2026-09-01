# ARPANET Redux

ARPANET Redux runs native TELNET from PDP-11/Network UNIX through simulated H316 systems running recovered 1973 Interface Message Processor (IMP) software to PDP-10/ITS. The accepted failover composition preserves one TELNET session when its direct application link is cut and the IMPs reroute traffic through a third IMP.

This repository contains source-only orchestration, project-authored simulator configurations, observability code, pins, documentation, and tests. Third-party source trees, firmware, disk images, simulator binaries, generated media, and raw results remain in an external laboratory because several inputs have unresolved redistribution terms.

The project promotes bounded, reproducible compositions. It does not claim to reconstruct the complete ARPANET or identify configured IMPs as historical sites.

## Run source checks

Install Git, Make, Python 3.11 or newer, and standard POSIX shell tools. Then run:

```sh
git clone https://github.com/brfid/arpanet-redux.git
cd arpanet-redux
make test
```

This command downloads no historical software and starts no simulator. To use an existing external laboratory, follow the [runbook](docs/runbook.md).

## Verified compositions

The following results pass at the revisions in [`pins/`](pins/). The linked test gates define their exact claims.

| Composition | Verified result |
|---|---|
| Linux NCP 002 ↔ IMP 2 ↔ IMP 3 ↔ Linux NCP 003, with adjacent hostless IMP 4 | Diagnostic echo, ordinary routing, and explicit host-dead behavior ([Gate 2](docs/test-plan.md#gate-2-router-oracle)) |
| ITS 106 ↔ IMP 6 ↔ IMP 62 ↔ Linux NCP 076 | Native ITS NCP interoperates with the diagnostic endpoint ([Gate 3](docs/test-plan.md#gate-3-mixed-vintage-and-diagnostic-hosts)) |
| ITS 106 ↔ IMP 6 ↔ IMP 62 ↔ ITS 176 | Guest-to-guest TELNET, remote DDT and `:TIME`, correlated IMP traffic, and anti-bypass sentinel transfer ([Gates 4 and 5](docs/test-plan.md#gate-4-two-vintage-its-hosts)) |
| Network UNIX 176 ↔ IMP 62 ↔ IMP 6 ↔ ITS 106 | Receipt-bound heterogeneous TELNET, structured remote `:TIME`, correlated IMP traffic, and a typed journey that stops at unproved guest ingress ([Gate 4H](docs/test-plan.md#gate-4h-network-unix-pdp-11-to-its)) |
| NCC receiver on IMP 5 with IMPs 5, 6, and 7 | Genuine trouble and throughput reports plus reciprocal direct-line transitions from `up` to evidenced [`down`](docs/experiments/2026-08-31-ncc-alternate-path-fault.md) or [`looped`](docs/experiments/2026-08-31-ncc-line-loopback.md) |
| Network UNIX/ITS route plus the IMP 5/6/7 NCC triangle | One lifecycle preserves the accepted application transaction and typed journey while receiving both report forms from IMPs 5, 6, 7, and 62 ([coexistence gate](docs/test-plan.md#ncc-observed-heterogeneous-coexistence-gate)) |
| The same composition with the IMP 62/IMP 6 application cable cut and an alternate route through IMP 7 | The same TELNET session returns structured `:TIME` output before and after the cut, the post-cut H316 journey covers IMPs 62, 7, and 6, and all four IMPs remain observable ([failover gate](docs/test-plan.md#ncc-observed-application-link-failover-gate)) |

`linux-ncp` is a diagnostic oracle, not a historical application endpoint. A vintage-to-vintage application pass must originate and consume application data inside the historical guests.

## Evidence boundaries

- Configured topology records intent. It does not prove that a component ran, a link worked, or a route was historically real.
- Loopback UDP models point-to-point simulator cabling. It cannot bypass a guest NCP for application traffic.
- Direct observations, derived state, and acceptance verdicts retain separate authority and supporting evidence.
- NCC browser views are passive and have no simulator, relay, guest, or result-mutation authority.
- Each run owns its ports, processes, media copies, logs, locks, and result directory.
- Generated and third-party artifacts stay outside Git.

## Find documentation

| Need | Owner |
|---|---|
| Run checks, smokes, or passive viewers | [Runbook](docs/runbook.md) |
| Understand stable system boundaries | [Architecture](docs/architecture.md) |
| Evaluate a result | [Test plan](docs/test-plan.md) |
| Understand NCC contracts and authority | [NCC observability](docs/ncc.md) |
| Understand orchestration internals | [Harness design](docs/harness.md) |
| Select simulator and topology inputs | [Configuration boundary](config/README.md) |
| Check active branches and decisions | [Workstreams](docs/workstreams.md) |
| Review decisions or dated evidence | [ADRs](docs/adr/), [experiments](docs/experiments/), and [research](docs/research/) |
| Check source identities or redistribution boundaries | [`pins/`](pins/), [NOTICE](NOTICE.md), and [credits](CREDITS.md) |

Active source revisions and asset hashes live only in [`pins/`](pins/). Dated reports record observations at those pins; they are not lock files or current status pages.

## License

Original work in this repository is MIT-licensed; see [`LICENSE`](LICENSE). External material retains its own terms and is not vendored or relicensed here. See [`NOTICE.md`](NOTICE.md) before publishing any derived artifact.
