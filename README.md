# ARPANET Redux

ARPANET Redux is a source-only laboratory for running real host applications through two simulated ARPANET IMPs. Its production-shaped targets join either two KA10/PDP-10 ITS hosts or ITS and SRI/NOSC Network UNIX on a PDP-11 through recovered 1973 H316 IMP software.

```text
KA10 / ITS 106 ↔ H316 IMP 6 ↔ H316 IMP 62 ↔ KA10 / ITS 176
PDP-11 / Network UNIX 176 ↔ H316 IMP 62 ↔ H316 IMP 6 ↔ KA10 / ITS 106
```

The repository contains orchestration, project-authored SIMH configurations, source pins, checksums, documentation, and acceptance tests. Third-party source trees, firmware, disk images, simulator binaries, generated media, and run logs remain in a separate local laboratory.

## Current status

| Gate | Result |
|---|---|
| Linux NCP ↔ IMP 2 ↔ IMP 3 ↔ Linux NCP | Passing, including explicit host-dead behavior |
| KA10/ITS 106 ↔ IMP 6 ↔ IMP 62 ↔ Linux NCP 076 | Passing with three guest NCP echo replies |
| KA10/ITS 106 ↔ IMP 6 ↔ IMP 62 ↔ KA10/ITS 176 | Passing on the exact clean-media pins: restored `UT` reached automatic `TELSER`, remote DDT, and `:TIME`, with two-way modem-link correlation. See [two-ITS readiness](docs/experiments/2026-08-28-two-its-readiness.md). |
| Application payload through both vintage guests | Passing anti-bypass proof: host `106` injected a unique `:OSEND` sentinel and host `176` recovered it only through NCP TELNET. The evidence trail records the exact run and matching digest. |
| PDP-11/Network UNIX 176 ↔ IMP 62 ↔ IMP 6 ↔ KA10/ITS 106 | Passing formal Gate 4H with receipt-bound guest media: the preserved TELNET client reached ITS `TELSER`, received the greeting, and executed remote `:TIME`, with post-probe traffic correlated through both IMPs and complete cleanup. See [the IMP11-A evidence record](docs/research/imp11a-device.md#formal-gate-4h-promotion-2026-08-31). |
| NCC receiver ↔ IMP 5 ↔ IMP 6 with alternate path through IMP 7 | Passing direct-line fault gate: both endpoints were observed `up`, the owned relay then dropped their direct cable in both directions, and both remained observable—with IMP 6 delivered through IMP 7—until fresh reciprocal reports established `down`. See [the alternate-path experiment](docs/experiments/2026-08-31-ncc-alternate-path-fault.md). |
| NCC receiver ↔ IMP 5 ↔ IMP 6 with two-ended direct-line loopback | Passing line-loopback gate: both endpoints were observed `up`, the owned reflector then returned each direction to its source, and both remained observable through the alternate route until repeated checksum-valid self-neighbor reports established `looped`. See [the loopback experiment](docs/experiments/2026-08-31-ncc-line-loopback.md). |

`linux-ncp` is a diagnostic oracle, not a production endpoint. A valid vintage-to-vintage pass must originate and consume its application data inside the two guests.

## Five-minute local check

The source-only checks need Python 3.11 or newer, POSIX shell tools, Git, and Make. They do not download or boot historical software.

```sh
git clone https://github.com/brfid/arpanet-redux.git
cd arpanet-redux
make test
```

The integration smokes require separately obtained and locally built historical assets. The [existing-laboratory runbook](docs/runbook.md) explains the expected layout and commands without pretending to grant or automate access to those materials.

## Project boundaries

- Loopback UDP represents point-to-point simulator cabling; it must not carry the application payload around a guest NCP.
- Each run owns its ports, processes, media copies, logs, and result directory.
- Generated and third-party artifacts stay outside Git and are checked against the source-only policy.
- The existing publishing pipeline is an eventual integration consumer, not a runtime dependency of this laboratory.

## Documentation

Start with the shortest document that answers the question:

- **Run source checks or an existing laboratory:** [existing-laboratory runbook](docs/runbook.md)
- **Understand the system boundary:** [architecture](docs/architecture.md)
- **Evaluate a result:** [test plan](docs/test-plan.md)
- **Understand orchestration internals:** [harness design](docs/harness.md)
- **Choose or resume a parallel workstream:** [workstreams and fresh-context handoff](docs/workstreams.md)
- **Understand NCC observability scope and current implementation:** [NCC observability](docs/ncc.md)
- **Understand why this topology was chosen:** [ADR-001](docs/adr/0001-two-imp-baseline.md)
- **Understand the complete KAIMP pin correction:** [ADR-003](docs/adr/0003-complete-kaimp-fix.md)
- **Understand the H316 buffer-fix pin:** [ADR-004](docs/adr/0004-h316-hi-conversion-buffer.md)
- **Review the original feasibility evidence:** [phase-one feasibility report](docs/research/2026-08-28-phase-one-feasibility.md)
- **Review the current two-ITS result and evidence trail:** [two-ITS readiness experiment](docs/experiments/2026-08-28-two-its-readiness.md)
- **Understand the formal heterogeneous endpoint:** [SRI/NOSC Network UNIX V6 research](docs/research/pdp11-network-unix.md)
- **Contribute safely:** [contributor guide](CONTRIBUTING.md)
- **Working here as an agent:** [agent instructions](AGENTS.md)
- **Understand redistribution limits:** [asset and licensing notice](NOTICE.md)
- **See what this project draws on:** [credits](CREDITS.md)

Active source revisions and asset hashes live only in [`pins/`](pins/); dated reports describe what was observed at those pins without acting as a second lock file.

## License status

Original work in this repository — orchestration code, project-authored SIMH configurations, documentation, ADRs, tests, and the scripts/research tooling — is MIT-licensed; see [`LICENSE`](LICENSE). Third-party material this project reads from or points at (`arpanet-in-a-box`, `linux-ncp`, PDP-10/ITS, the KA10 and H316 simulator forks, SRI/NOSC Network UNIX V6, and everything else pinned or cited) is not vendored here and retains its own, separately tracked terms; see [`NOTICE.md`](NOTICE.md) and [`CREDITS.md`](CREDITS.md).
