# Architecture

## Purpose

ARPANET Redux separates a historically authentic guest data path from a modern orchestration and validation plane. The project succeeds only when a guest application sends data through both simulated IMPs and another guest application consumes it.

## Target topology

```text
control: simulator consoles and per-run lifecycle management
             │                                      │
             ▼                                      ▼
       KA10 / ITS 106                         KA10 / ITS 176
       native NCP                             native NCP
             │ 1822 long leader                    │ 1822 long leader
             ▼                                      ▼
         H316 IMP 6 ───── simulated modem ───── H316 IMP 62
             │                                      │
             └──────────── guest data path ─────────┘

validation: console transcripts + both IMP traces + per-run manifest
```

Loopback UDP models the point-to-point electrical links between simulator devices. It is transport for simulated interfaces, not an application bridge.

## Separation of concerns

| Concern | Owner | Boundary |
|---|---|---|
| Guest data plane | ITS NCP and guest applications | Payload enters guest A, crosses both IMPs, and exits guest B |
| Simulated network | KA10 IMP devices and H316 firmware | Converts 1822 leaders, routes packets, and reports network failures |
| Control plane | Source-only launch and controller code | Allocates resources, drives consoles, observes readiness, and cleans up exact children |
| Evidence plane | Test assertions and run manifests | Correlates application output with post-start IMP traffic and pinned inputs |
| NCC observation plane | Versioned completed summary, bounded controller stream, deterministic replay, and passive viewers | Separates configured topology, direct observations, inferences, and gate evidence; live consumers retain stale state without simulator authority |
| Artifact plane | External laboratory | Holds third-party sources, media, executables, copied guest workspaces, and raw results |

The repository never uses a guest-media directory as a transfer channel between endpoints. Guest workspaces are distinct, and a payload test is invalid if the controller can satisfy it by copying a host file.

## Diagnostic topology

The retained mixed topology replaces one vintage endpoint with `linux-ncp`. It is an observability oracle for the KA10 interface and two-IMP route, not an acceptable final data path. The router oracle replaces both vintage endpoints and adds an unreachable adjacent IMP so normal echo and explicit host-dead behavior can be tested independently.

## Resource model

Every run receives a unique result directory, UDP port set, Unix-domain control sockets, and exact child-process set. Simulator configurations obtain port numbers from the run environment. External source and executable identities are verified before launch; result manifests record the exact inputs used.

The external laboratory is a sibling of the source checkout by default. Its contents are replaceable build inputs and evidence, not repository state. See the [runbook](runbook.md) for its layout and the [harness design](harness.md) for lifecycle mechanics.

## Future site integration

The original consumer generates a vintage YAML input, runs two historical-machine stages, validates a final text artifact, records provenance, and publishes through Hugo. The intended replacement seam begins after YAML generation and ends before artifact validation.

The network stage may replace the two current machine stages, but it must preserve these external contracts:

- Final bundle identities remain `brad.bio.txt`, `build.log.html`, and `pipeline-status.json`.
- Name and headline remain exact; summary text remains equal after whitespace normalization.
- Status retains the expected pipeline identity, success result, zero exit status, build ID, and source revision.
- Build-log identity, provenance, reuse fingerprints, semantic validation, and fail-closed publication remain intact.

The site checkout is not read or modified by the laboratory smokes. Integration begins only after the two-vintage-host and payload-integrity gates in the [test plan](test-plan.md) pass.

## Decisions and evidence

- [ADR-001](adr/0001-two-imp-baseline.md) records why the two-IMP, two-ITS baseline was selected.
- [Phase-one feasibility](research/2026-08-28-phase-one-feasibility.md) records the resource survey and passing diagnostic experiments.
- [Two-ITS readiness findings](experiments/2026-08-28-two-its-readiness.md) records the failed trials that established the current readiness rule.
