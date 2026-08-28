# Test plan

## Purpose

The tests must distinguish a genuinely networked vintage pipeline from four simulators that merely boot. A pass requires evidence at the highest layer under test and evidence from the lower layers that the intended route carried it.

## Test layers

| Layer | Test type | Required evidence | Current state |
|---|---|---|---|
| Source and asset identity | Fast static check | Exact Git revisions and SHA-256 checksums | Implemented for five source heads and both tested asset sets |
| IMP routing oracle | Integration smoke | Three echo replies through two IMPs and a type-7 host-dead outcome | Passing |
| Vintage host interoperability | Integration smoke | ITS operational banner, both IMP host-link traces, three NCP echo replies | Passing against Linux NCP |
| Two vintage hosts | End-to-end smoke | Both ITS operational banners and an application transcript crossing IMP 6 and IMP 62 | In progress |
| Payload integrity | End-to-end contract | Unique sentinel originates in guest A, is recovered only from guest B, and matches a host-side digest | Pending |
| Pipeline compatibility | Contract/regression | Existing semantic output, status, provenance, reuse, fingerprint, and publication tests remain green | Pending and deliberately outside this repository for now |
| Lifecycle failure | Fault-injection integration | Forced endpoint or IMP failure produces a bounded nonzero result and leaves no owned process, socket, or port | Pending |

## Acceptance cases

### Router oracle

Start two Linux NCP endpoints, IMP 2, IMP 3, and an adjacent IMP 4 with no host. Host `002` must receive the third echo reply from host `003`; a request for host `004` must fail with `Host is not up.` This covers both normal routing and explicit network failure reporting.

### Mixed vintage/diagnostic path

Start Linux NCP host `076`, IMP 62, IMP 6, and KA10/ITS host `106` in that order. Wait for the ITS operational banner, then require three echo replies. The IMP logs must show host-interface packets on both sides, and IMP 6 must show long/short leader conversion.

### Two-vintage-host path

Start both IMPs before both KA10 guests. Host A must identify as `106` octal and host B as `176` octal. A guest application on one endpoint must receive a response from the other; boot traffic, interface reset packets, or debugger-only symbol inspection do not satisfy this gate.

The initial application may be TELNET, FINGER, or another standard ITS NCP service. The eventual regression should use the narrowest deterministic command that produces a stable transcript and a nonzero payload.

### Payload anti-bypass contract

Generate a per-run printable-ASCII sentinel, inject it only through host A's console/control channel, transfer it with the guest NCP application, and extract it only through host B's console/control channel. Keep guest disk workspaces separate and make the orchestrator unable to copy a payload between them. Compare a digest only after extraction. A test that writes the sentinel directly into both guest workspaces must fail review even if all reported checks pass.

### Lifecycle and cleanup

Every process must be started as a child whose exact PID is recorded. Cleanup must be idempotent and run after success, command failure, timeout, and interruption. Before a test starts, it must refuse to replace a results directory. Each run must allocate its own UDP ports, retain cooperative per-user locks until cleanup, and use private Unix-domain NCP sockets.

## Coverage gaps before site integration

- The two-ITS application test has not yet passed.
- The source-built generic KA image has not yet completed a clean reproducible build in this repository's workflow.
- The test harness has not yet demonstrated the payload anti-bypass contract.
- Forced-failure cleanup and occupied-port behavior need automated tests.
- The existing site pipeline's publication and reuse contracts have been analyzed but not exercised against a network-stage implementation.
- The eventual CI runtime, image packaging, and asset-licensing policy remain undecided.
