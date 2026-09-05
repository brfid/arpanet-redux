# ARPANET Redux

ARPANET Redux runs native TELNET from PDP-11/Network UNIX through simulated H316 systems running recovered 1973 Interface Message Processor (IMP) software to PDP-10/ITS. The accepted failover composition preserves one TELNET session when its direct application link is cut and the IMPs reroute traffic through a third IMP.

The project is a vintage-computing laboratory. Current development prioritizes independent setup, understandable observations and failures, reliable operation, and useful guest sessions. Website-pipeline integration is no longer a project goal.

This repository contains source-only orchestration, project-authored simulator configurations, observability code, pins, documentation, and tests. Third-party source trees, firmware, disk images, simulator binaries, generated media, and raw results remain in an external laboratory because several inputs have unresolved redistribution terms.

The project promotes bounded, reproducible compositions. It does not claim to reconstruct the complete ARPANET or identify configured IMPs as historical sites.

## Quick start

Install Git, Make, Python 3.11 or newer, a C compiler, and standard POSIX shell tools. Then run:

```sh
git clone https://github.com/brfid/arpanet-redux.git
cd arpanet-redux
make test
```

This command downloads no historical software and starts no simulator. To use an existing external laboratory, follow the [runbook](docs/runbook.md).

For either supported foreground experience, prepare the external sources and simulators, reconstruct the base disks, and build the guest applications:

```sh
make lab-setup
make build-pdp11-base
make build-pdp11-telnet
make doctor
```

The base reconstruction acquires pinned historical inputs directly into the external lab and produces identical unbooted disks on every build; it needs no private prepared image. Existing accepted disk pairs remain usable. Guest compilation writes a receipt and remembers the selected build. Once `make doctor` reports ready, start either surface with `make telnet` or `make ncc`; use `make telnet-failover` to operate one guest session across the link cut, or `make ncc-failover` for the longer passive-report proof. See the [fresh-clone guide](docs/getting-started.md) for the complete path and `make help` for the command summary.

To understand an existing successful, failed, or unfinished run, use `make diagnose-run RESULT=/absolute/path/to/result`. It reports retained outcomes, the last recorded checkpoint, cleanup evidence, and bounded diagnostic excerpts without starting a simulator or changing the result. See [run diagnostics](docs/runbook.md#diagnose-a-retained-run) for its evidence limits and JSON output.

To keep saved guest files between sessions, create a named [persistent workspace](docs/workspaces.md), then reopen that name whenever you return:

```sh
make workspace-create WORKSPACE=personal
make workspace WORKSPACE=personal
```

Save your editor buffers inside the guests and press Control-] to save their disks and stop. Each restart boots fresh processes from the last verified save; previous saves remain available for rollback. Reopen your applications and TELNET connections after restarting.

## Verified compositions

The following results pass at the revisions in [`pins/`](pins/). The linked test gates define their exact claims.

| Composition | Verified result |
|---|---|
| Linux NCP 002 ↔ IMP 2 ↔ IMP 3 ↔ Linux NCP 003, with adjacent hostless IMP 4 | Diagnostic echo, ordinary routing, and explicit host-dead behavior ([Gate 2](docs/test-plan.md#gate-2-router-oracle)) |
| ITS 106 ↔ IMP 6 ↔ IMP 62 ↔ Linux NCP 076 | Native ITS NCP interoperates with the diagnostic endpoint ([Gate 3](docs/test-plan.md#gate-3-mixed-vintage-and-diagnostic-hosts)) |
| ITS 106 ↔ IMP 6 ↔ IMP 62 ↔ ITS 176 | Guest-to-guest TELNET, remote DDT and `:TIME`, correlated IMP traffic, and anti-bypass sentinel transfer ([Gates 4 and 5](docs/test-plan.md#gate-4-two-vintage-its-hosts)) |
| Network UNIX 176 ↔ IMP 62 ↔ IMP 6 ↔ ITS 106 | Receipt-bound heterogeneous TELNET, structured remote `:TIME`, correlated IMP traffic, and a complete twelve-observation typed journey with direct ITS request-ingress and Network UNIX reply-ingress evidence ([Gate 4H](docs/test-plan.md#gate-4h-network-unix-pdp-11-to-its)) |
| The same direct Network UNIX-to-ITS route under one foreground terminal controller | Repeated operator-entered commands and exact prompt-framed results in one real guest TELNET session, with a strict retained transcript and complete cleanup ([Gate 4I](docs/test-plan.md#gate-4i-interactive-network-unix-to-its-telnet)) |
| The same route from the real Network UNIX shell and preserved TELNET command interface | Character-oriented seven-bit terminal input, guest-owned connection and option handling, remote `:TIME`, TELNET `AYT`, message/character modes, exact directional bytes, correlated IMP traffic, and safe cleanup ([Gate 4J](docs/test-plan.md#gate-4j-historical-network-unix-telnet-terminal)) |
| One human-operated Network UNIX TELNET connection with the direct application cable cut after a pre-cut `:TIME` | Local Control-^ cut ownership, atomic acknowledgement, direct-dead/alternate-ready transition, a second structured `:TIME` in the same guest session, typed IMP 7 journey, exact directional bytes, and safe cleanup ([Gate 4K](docs/test-plan.md#gate-4k-interactive-same-session-telnet-failover)) |
| A named workspace on the direct Network UNIX-to-ITS route | Guest-created and edited files survive repeated complete stop/restart cycles on both hosts; verified disk generations, exclusive ownership, interrupted-publication recovery, and rollback preserve complete saves ([Gate 4L](docs/test-plan.md#gate-4l-persistent-direct-guest-disks)) |
| NCC receiver on IMP 5 with IMPs 5, 6, and 7 | Genuine trouble and throughput reports plus reciprocal direct-line transitions from `up` to evidenced [`down`](docs/experiments/2026-08-31-ncc-alternate-path-fault.md) or [`looped`](docs/experiments/2026-08-31-ncc-line-loopback.md) |
| Network UNIX/ITS route plus the IMP 5/6/7 NCC triangle | One lifecycle preserves the accepted application transaction and typed journey while receiving both report forms from IMPs 5, 6, 7, and 62 ([coexistence gate](docs/test-plan.md#ncc-observed-heterogeneous-coexistence-gate)) |
| The same composition with the IMP 62/IMP 6 application cable cut and an alternate route through IMP 7 | The same TELNET session returns structured `:TIME` output before and after the cut, the post-cut H316 journey covers IMPs 62, 7, and 6, and all four IMPs remain observable ([failover gate](docs/test-plan.md#ncc-observed-application-link-failover-gate)) |

The passive NCC surface is one mid-1970s-style operator console: a banked 64-position annunciator, automatic attention selection, local alarm acknowledgement, Teletype-style network log, and quick summary. Direct report and explicitly mapped line state use source IMP positions; a clearly modern RUN PROOF bank shows validated application, journey, failover, and cleanup facts without promoting candidate report-line numbers. `make ncc` or `make ncc-failover` runs an existing formal scenario beside the console and selects its completed result; `make view-ncc` or `make view-ncc-failover` replays the selected, or newest passing, retained result through the same interface without launching a simulator. `make telnet` boots to the real Network UNIX shell for character-oriented use of its preserved TELNET client; `make telnet-failover` gives that foreground controller one run-local cut key and an alternate route; `make telnet-check` retains the separate deterministic prompt-framed proof. The browser remains read-only.

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
| Prepare a fresh clone for TELNET or NCC | [Getting started](docs/getting-started.md) |
| Run checks, smokes, or passive viewers | [Runbook](docs/runbook.md) |
| Understand stable system boundaries | [Architecture](docs/architecture.md) |
| Evaluate a result | [Test plan](docs/test-plan.md) |
| Understand NCC contracts and authority | [NCC observability](docs/ncc.md) |
| Understand orchestration internals | [Harness design](docs/harness.md) |
| Select simulator and topology inputs | [Configuration boundary](config/README.md) |
| Check active branches and decisions | [Workstreams](docs/workstreams.md) |
| Review decisions or dated evidence | [ADRs](docs/adr/), [experiments](docs/experiments/), and [research](docs/research/) |
| Check source identities or redistribution boundaries | [`pins/`](pins/), [NOTICE](NOTICE.md), and [credits](CREDITS.md) |

Active source revisions and external asset hashes live only in [`pins/`](pins/). Dated reports record observations at those pins; they are not lock files or current status pages.

## License

Original work in this repository is MIT-licensed; see [`LICENSE`](LICENSE). External material retains its own terms and is not vendored or relicensed here. See [`NOTICE.md`](NOTICE.md) before publishing any derived artifact.
