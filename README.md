# ARPANET Redux

ARPANET Redux is an active, source-only laboratory for rebuilding working pieces of the early ARPANET from preserved host software, recovered 1973 H316 Interface Message Processor (IMP) software, and modern simulators. It grows one reproducible, evidence-backed composition at a time rather than treating any current host count, IMP count, or route as the finished network.

```text
              modern orchestration and lifecycle control
                               │
                               ▼
historical / diagnostic hosts ↔ configured H316 IMP topology ↔ host / NCC attachments
                               │
                               ▼
             guest results + IMP observations + run manifests
```

The modern control and evidence planes drive consoles, allocate resources, and observe results; they do not carry an application payload around the historical guest networking. Exact host and IMP identities below name reproducible test compositions, not a fixed network size, a final topology, or automatic claims about historical sites.

The repository contains orchestration, project-authored SIMH configurations, normalized observability code, source pins, checksums, documentation, and acceptance tests. Third-party source trees, firmware, disk images, simulator binaries, generated media, and raw run logs remain in a separate local laboratory.

## Project status

ARPANET Redux is under active development. The repository contains reproducibly verified but deliberately bounded application, routing, fault, and observability compositions. It is neither a complete reconstruction of the ARPANET nor a one-command distribution of the historical assets it depends on.

## Five-minute local check

The source-only checks need Python 3.11 or newer, POSIX shell tools, Git, and Make. They do not download or boot historical software.

```sh
git clone https://github.com/brfid/arpanet-redux.git
cd arpanet-redux
make test
```

This verifies the repository's source-only policy and deterministic contracts. Integration smokes require separately obtained and locally built historical assets; the [existing-laboratory runbook](docs/runbook.md) explains the expected layout and commands without pretending to grant or automate access to those materials.

## Verified compositions

These are promoted milestones at the current pins. Their exact scope is defined by the linked gates and evidence records.

| Composition | Established result |
|---|---|
| Linux NCP 002 ↔ IMP 2 ↔ IMP 3 ↔ Linux NCP 003, with hostless IMP 4 as an adjacent peer | Diagnostic echo and explicit host-dead behavior through recovered routing firmware; see [Gate 2](docs/test-plan.md#gate-2-router-oracle) |
| KA10/ITS 106 ↔ IMP 6 ↔ IMP 62 ↔ Linux NCP 076 | Native ITS NCP and its simulated 1822 interface interoperate with the two-IMP diagnostic path; see [Gate 3](docs/test-plan.md#gate-3-mixed-vintage-and-diagnostic-hosts) |
| KA10/ITS 106 ↔ IMP 6 ↔ IMP 62 ↔ KA10/ITS 176 | Guest-to-guest TELNET, remote DDT and `:TIME`, correlated modem traffic, and recovery of a unique `:OSEND` sentinel only through guest NCP; see [the readiness and evidence record](docs/experiments/2026-08-28-two-its-readiness.md) |
| PDP-11/Network UNIX 176 ↔ IMP 62 ↔ IMP 6 ↔ KA10/ITS 106 | Formal heterogeneous TELNET from the preserved client to ITS, with a remote `:TIME`, receipt-bound media, correlated IMP traffic, and complete cleanup; see [the Gate 4H evidence](docs/research/imp11a-device.md#formal-gate-4h-promotion-2026-08-31) |
| NCC receiver on IMP 5, a direct IMP 5/IMP 6 line, and an alternate path through IMP 7 | Genuine reports from all three IMPs and reciprocal direct-line transitions from `up` to evidenced [`down`](docs/experiments/2026-08-31-ncc-alternate-path-fault.md) or [`looped`](docs/experiments/2026-08-31-ncc-line-loopback.md) while both endpoints remain observable |

The NCC results can be watched through a passive local browser display that preserves configured-only links, direct endpoint reports, in-memory reconciliation, and completed-summary authority as separate layers; see the [existing-laboratory runbook](docs/runbook.md#view-a-growing-ncc-historical-event-sidecar).

`linux-ncp` is a diagnostic oracle, not a historical application endpoint. An accepted vintage-to-vintage application pass must originate and consume its application data inside the historical guests. IMPs 5, 6, and 7 in the NCC fault compositions are configured test components, not asserted historical sites.

## Evidence and project boundaries

- Configured topology records the intended composition; it does not by itself prove that a component ran, a link was up, or a route was historically real.
- Loopback UDP represents point-to-point simulator cabling; it must not carry an application payload around a guest NCP.
- Direct observations, derived state, and acceptance verdicts remain distinct and retain their supporting evidence.
- NCC consumers are passive observers and receive no authority to control the simulators.
- Each run owns its ports, processes, media copies, logs, and result directory.
- Generated and third-party artifacts stay outside Git and are checked against the source-only policy.

## Documentation

### Start here

- **Run source checks or an existing laboratory:** [existing-laboratory runbook](docs/runbook.md)
- **Understand the system and evidence boundaries:** [architecture](docs/architecture.md)
- **Evaluate a result:** [test plan](docs/test-plan.md)

### Implementation and project records

- **Understand orchestration internals:** [harness design](docs/harness.md)
- **See current branches, workstream state, and handoffs:** [workstreams and fresh-context handoff](docs/workstreams.md)
- **Understand NCC observability scope and implementation:** [NCC observability](docs/ncc.md)

### Decisions, evidence, and policy

- **Review design decisions:** [architecture decision records](docs/adr/)
- **Review dated results:** [experiments](docs/experiments/) and [research](docs/research/)
- **Contribute safely:** [contributor guide](CONTRIBUTING.md) and [agent instructions](AGENTS.md)
- **Understand provenance and redistribution:** [asset and licensing notice](NOTICE.md) and [credits](CREDITS.md)

Active source revisions and asset hashes live only in [`pins/`](pins/); dated reports describe what was observed at those pins without acting as a second lock file.

## License status

Original work in this repository — orchestration code, project-authored SIMH configurations, documentation, ADRs, tests, and the scripts and research tooling — is MIT-licensed; see [`LICENSE`](LICENSE). Third-party material this project reads from or points at (`arpanet-in-a-box`, `linux-ncp`, PDP-10/ITS, the KA10 and H316 simulator forks, SRI/NOSC Network UNIX V6, and everything else pinned or cited) is not vendored here and retains its own, separately tracked terms; see [`NOTICE.md`](NOTICE.md) and [`CREDITS.md`](CREDITS.md).
