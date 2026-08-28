# brfid-vintage-network

This repository is the source-only laboratory for replacing the `brfid.gitlab.io` vintage host-spool pipeline with a real host–IMP–IMP–host path. It keeps orchestration, SIMH machine configurations, source pins, checksums, research, and acceptance tests under version control while keeping third-party firmware, disk images, binaries, build trees, and raw logs outside Git.

The first production-shaped target is two KA10/PDP-10 hosts running ITS, with host `106` octal attached to H316 IMP 6 and host `176` octal attached to H316 IMP 62. The first two proven gates are retained as diagnostic tests: Linux NCP through two recovered 1973 IMPs, and a KA10/ITS guest exchanging NCP echo traffic with Linux NCP through exactly two IMPs.

No file in the `brfid.gitlab.io` sister checkout is read or modified by the smoke-test scripts.

## Current status

| Gate | Result | Meaning |
|---|---|---|
| Linux NCP → IMP 2 → IMP 3 → Linux NCP | Pass | Recovered routing firmware, modem path, host interfaces, echo reply, and host-dead reply work |
| KA10/ITS host `106` → IMP 6 → IMP 62 → Linux NCP host `076` | Pass | Native ITS NCP and the KA10 long-leader 1822 interface interoperate with the two-IMP path |
| KA10/ITS host `106` → IMP 6 → IMP 62 → KA10/ITS host `176` | In progress | Requires a clean second monitor/image and application-level guest-to-guest transcript |
| Bio payload through both vintage guests | Not started | Begins only after the two-host application test passes |

## Repository and lab layout

The default paths assume these sister directories:

```text
~/src/brfid-vintage-network/       # this Git repository
~/src/brfid-vintage-network-lab/   # ignored third-party sources, disks, builds, and results
~/src/brfid.gitlab.io/              # existing site; untouched during this phase
```

The lab currently uses native arm64 builds on macOS. Nothing is installed into system Python or system directories. The smoke scripts accept every external root or binary path explicitly so another checkout can use a different lab location.

## Reproduce the passing gates

The commands below assume the external lab has already been populated and built at the pinned revisions in [`pins/sources.lock.toml`](pins/sources.lock.toml).

```sh
make verify-assets
make smoke-router
make smoke-mixed
```

Each target creates a new timestamped directory under the external lab's `results/` tree and fails instead of overwriting an earlier run. The simulator processes are tracked by exact PID and cleaned up after success, failure, interruption, or timeout.

## Design boundary

The host operating system must originate and consume the application payload through its own NCP and simulated 1822 interface. Loopback UDP is permitted only as the cable between simulator devices. A host-side copy between guest disk directories is not a network test and is intentionally outside the acceptance contract.

The eventual integration seam begins after `generate_vintage_yaml()` and ends before the existing output validation and publication tail. The replacement must preserve `brad.bio.txt`, `build.log.html`, `pipeline-status.json`, semantic validation, exact source identity, provenance, reuse fingerprints, and fail-closed publication behavior.

## Documentation

- [`docs/adr/0001-two-imp-baseline.md`](docs/adr/0001-two-imp-baseline.md) records the background research, alternatives, evidence, and decision.
- [`docs/test-plan.md`](docs/test-plan.md) defines the layered smoke and acceptance gates.
- [`NOTICE.md`](NOTICE.md) explains why upstream assets are not committed.
