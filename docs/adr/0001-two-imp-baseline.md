# ADR-001: Use a two-IMP ARPANET path with ITS endpoints

- **Status:** Accepted
- **Date:** 2026-08-28
- **Decider:** Brad

## Context

The existing vintage publishing stage transfers an intermediate file between two simulated computers through the host filesystem. The desired replacement must make the application payload traverse authentic guest networking and two simulated IMPs while preserving the existing validation and publication boundary.

Phase-one testing established that native arm64 H316 and KA10 simulators can run the recovered IMP software, route traffic through two IMPs, and connect a KA10/ITS guest's NCP to a diagnostic NCP endpoint. The remaining uncertainty is the second authentic guest endpoint and its application-level proof.

## Decision

Use the following baseline:

```text
KA10 / ITS host 106
  ↕ native NCP and simulated 1822 interface
H316 IMP 6
  ↕ simulated point-to-point modem
H316 IMP 62
  ↕ simulated 1822 interface and native NCP
KA10 / ITS host 176
```

Retain `linux-ncp` only as a deterministic diagnostic oracle. It may prove an interface or route but may not occupy either endpoint in the final vintage-to-vintage acceptance test.

The modern control plane may drive simulator consoles and loopback transport. The application payload must originate in one guest, cross the NCP/1822/IMP/IMP/NCP path, and be recovered from the other guest. A host-side copy between guest workspaces is forbidden.

## Decision drivers

- KA10 SIMH has a purpose-built NCP-mode IMP device that already interoperates with the recovered H316 host interface.
- ITS has a native NCP and configurable ARPANET identity.
- Current ITS source supports the generic KA identity `176`, allowing a clean second image instead of a debugger-modified recovered disk.
- A same-family pair minimizes unknowns while the network, lifecycle, and payload contracts are established.
- The two-IMP boundary remains useful when a heterogeneous guest later replaces one ITS endpoint.

## Alternatives

| Alternative | Reason not selected first |
|---|---|
| KA10/ITS plus Linux NCP | Already useful as an oracle, but only one endpoint is vintage |
| KA10/ITS plus WAITS | Available integration terminates NCP in a modern bridge rather than the guest |
| KA10/ITS plus SRI/NOSC Network UNIX V6 | Historically strong candidate, but the PDP-11 simulator lacks the required IMP11-A/ACC interface |
| Existing VAX/BSD plus PDP-11/BSD | Their current simulated machine models expose no compatible 1822 controllers |
| Archived VAX–H316–H316–KS10 experiment | The chosen KS10 device emitted an Ethernet-oriented format rather than the required 1822 framing |

## Consequences

- The first complete topology sacrifices host-family diversity for a shorter and better-observed path.
- Four simulators must be managed as one lifecycle with exact process ownership, dynamic ports, readiness predicates, and bounded cleanup.
- A passing result needs an application transcript and corroborating post-start IMP evidence; boot banners are insufficient.
- Guest images and historical assets require independent provenance review and remain outside Git.
- The eventual site integration can replace the two machine stages without weakening existing semantic, provenance, reuse, or publication checks.

## Follow-up

Complete the two-ITS application and payload-integrity gates defined in the [test plan](../test-plan.md). After that baseline is repeatable, investigate [SRI/NOSC Network UNIX V6](../research/pdp11-network-unix.md) as the first heterogeneous endpoint.

The [architecture](../architecture.md) owns the system boundary. The dated [phase-one feasibility report](../research/2026-08-28-phase-one-feasibility.md) owns the supporting resource survey and smoke evidence.
