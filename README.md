# ARPANET Redux

ARPANET Redux is a source-only laboratory for running real host applications through two simulated ARPANET IMPs. The first production-shaped target joins two KA10/PDP-10 hosts running ITS through recovered 1973 H316 IMP software.

```text
KA10 / ITS 106 ↔ H316 IMP 6 ↔ H316 IMP 62 ↔ KA10 / ITS 176
```

The repository contains orchestration, project-authored SIMH configurations, source pins, checksums, documentation, and acceptance tests. Third-party source trees, firmware, disk images, simulator binaries, generated media, and run logs remain in a separate local laboratory.

## Current status

| Gate | Result |
|---|---|
| Linux NCP ↔ IMP 2 ↔ IMP 3 ↔ Linux NCP | Passing, including explicit host-dead behavior |
| KA10/ITS 106 ↔ IMP 6 ↔ IMP 62 ↔ Linux NCP 076 | Passing with three guest NCP echo replies |
| KA10/ITS 106 ↔ IMP 6 ↔ IMP 62 ↔ KA10/ITS 176 | In progress; both guests boot, prove local time, and reach a live NCP TELNET exchange with real packet traffic, but the connection does not complete. See [two-ITS readiness](docs/experiments/2026-08-28-two-its-readiness.md) |
| Application payload through both vintage guests | Not started |

`linux-ncp` is a diagnostic oracle, not a production endpoint. A valid vintage-to-vintage pass must originate and consume its application data inside the two guests.

## Five-minute local check

The source-only checks need Python 3.11 or newer, POSIX shell tools, Git, and Make. They do not download or boot historical software.

```sh
git clone https://gitlab.com/brfid/arpanet-redux.git
cd arpanet-redux
make test
```

The integration smokes require separately obtained and locally built historical assets. The [existing-laboratory runbook](docs/runbook.md) explains the expected layout and commands without pretending to grant or automate access to those materials.

## Project boundaries

- Loopback UDP represents point-to-point simulator cabling; it must not carry the application payload around a guest NCP.
- Each run owns its ports, processes, media copies, logs, and result directory.
- Generated and third-party artifacts stay outside Git and are checked against the source-only policy.
- The existing `brfid.gitlab.io` pipeline is an eventual integration consumer, not a runtime dependency of this laboratory.

## Documentation

Start with the shortest document that answers the question:

- **Run source checks or an existing laboratory:** [existing-laboratory runbook](docs/runbook.md)
- **Understand the system boundary:** [architecture](docs/architecture.md)
- **Evaluate a result:** [test plan](docs/test-plan.md)
- **Understand orchestration internals:** [harness design](docs/harness.md)
- **Understand why this topology was chosen:** [ADR-001](docs/adr/0001-two-imp-baseline.md)
- **Review the original feasibility evidence:** [phase-one feasibility report](docs/research/2026-08-28-phase-one-feasibility.md)
- **Review the current two-ITS failure analysis:** [two-ITS readiness experiment](docs/experiments/2026-08-28-two-its-readiness.md)
- **Explore the heterogeneous follow-up:** [SRI/NOSC Network UNIX V6 research](docs/research/pdp11-network-unix.md)
- **Contribute safely:** [contributor guide](CONTRIBUTING.md)
- **Understand redistribution limits:** [asset and licensing notice](NOTICE.md)

Active source revisions and asset hashes live only in [`pins/`](pins/); dated reports describe what was observed at those pins without acting as a second lock file.

## License status

No license has yet been granted for the original work in this repository. Public visibility permits reading and GitLab's normal fork behavior but does not grant broader reuse rights. Third-party assets are excluded and retain their own terms; see [`NOTICE.md`](NOTICE.md).
