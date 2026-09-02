# Architecture

## Purpose

ARPANET Redux separates historical guest and IMP behavior from modern orchestration, observation, and validation. The project advances by promoting bounded compositions with explicit claims, not by treating one host pair or route as a permanent network definition.

An application composition passes only when one historical guest application sends data through the configured IMP route and another historical guest application consumes it. A network-behavior composition passes only when genuine, attributed IMP observations support its verdict. Configured topology is intent, never proof of activity or historical identity.

## System boundary

```text
              modern orchestration and lifecycle control
                               │
                               ▼
      historical, diagnostic, or NCC host attachments
                               ↕ simulated 1822 interfaces
                  configured H316 IMP topology
                               ↕ simulated modem links
                  additional IMPs and endpoints
                               │
                               ▼
       transcripts + IMP observations + per-run manifest
```

The modern plane allocates resources, drives simulator consoles, records evidence, evaluates a bounded claim, and cleans up exact child processes. It does not bridge application traffic around a guest NCP. Loopback UDP represents point-to-point simulator cables, not an application shortcut.

## Composition model

Each composition owns:

- a project-authored topology and simulator configuration;
- an exact set of external inputs and executable identities;
- one bounded lifecycle and private resource namespace;
- a claim with normative acceptance criteria;
- direct evidence and derived verdicts that retain their authority;
- cleanup that releases every owned process, socket, port lock, and media copy.

A composition may reuse a proven component, but it does not inherit a broader claim. Adding a host, IMP, link, route, fault, or evidence source requires a new bounded composition or an explicit extension of an existing gate.

## Composition roles

| Role | Boundary |
|---|---|
| Historical application | Both endpoints are historical guests; guest-visible output and post-probe IMP evidence prove the exchange |
| Heterogeneous application | Different historical host families meet the same application and route-evidence requirements |
| Mixed diagnostic | `linux-ncp` replaces one historical endpoint to isolate an interface or route; it cannot satisfy a vintage-to-vintage application gate |
| Router oracle | Diagnostic endpoints and a hostless peer prove ordinary routing and explicit host-dead behavior |
| NCC network behavior | A passive receiver, genuine IMP reports, explicit topology, and reducers support a specific line or reachability claim |
| Integrated application and NCC | One lifecycle runs an accepted application exchange and passive NCC observation while keeping their evidence and verdicts separate |
| Application failover | A controller cuts one run-owned cable after a pre-cut transaction; the same guest session, alternate-route observations, post-cut reports, and cleanup must pass independently |
| Historical terminal | One foreground controller safely bridges operator characters to a historical host console while the guest application retains protocol authority and directional bytes remain separate from network diagnosis |

IMPs 5, 6, and 7 in NCC compositions are configured test components, not asserted historical sites. An IMP number or simulator device name does not establish historical identity or report-line mapping.

## Separation of concerns

| Concern | Owner | Rule |
|---|---|---|
| Guest data plane | Historical guest NCP and applications | Payload enters and exits through guest networking |
| Simulated network | Host-interface models and recovered H316 firmware | Interfaces convert leaders where required, route packets, and emit network reports |
| Control plane | Launchers and controllers | Code allocates resources, drives consoles, applies owned faults, and performs exact cleanup |
| Evidence plane | Structured artifacts, assertions, and manifests | Every claim binds to post-start observations and exact inputs |
| NCC observation plane | Decoders, validated streams, reducers, and read-only projections | Configured facts, direct evidence, harness evidence, inference, and verdicts remain distinct |
| Artifact plane | External laboratory | Third-party inputs, generated media, executables, and raw results stay outside Git |

The controller cannot satisfy an application test by copying a payload between guest workspaces. A process exit, configured route, absent report, or successful application transaction cannot substitute for evidence owned by another plane. The historical terminal does not expose a simulator PTY: its controller blocks the SIMH WRU character, safely projects controls, and leaves TELNET state and negotiation in the Network UNIX guest.

## NCC data flow

```text
configured topology ─────────────────────────────────────────┐
genuine IMP reports ── validated historical-event stream ── reducer
H316 trace windows ─── validated message-journey stream ──── reducer
application + lifecycle artifacts ───────────────────────────┤
                                                             ▼
                                               validated in-memory projection
                                                             │
                                                             ▼
                                             loopback GET/HEAD presentation
```

The historical-event stream records direct reports. The message-journey stream records route-boundary observations with source-local order and provenance. Completed summaries and composition verdicts derive conclusions from those inputs. No stream becomes a second topology, independent simulator clocks never become a global clock, and missing evidence remains unknown rather than down.

Python consumers import NCC contracts from their owning `ncc.<module>` directly. The `ncc` package root deliberately has no aggregate facade, so importing one contract does not initialize unrelated displays, servers, controllers, or viewers.

Browser code receives resolved presentation data. It does not parse raw traces, pair report endpoints, reduce evidence, control a simulator, send guest input, switch a link, or mutate a result. The terminal runner may own one complete supported scenario through its existing lifecycle; that authority is not exposed through HTTP.

The neutral passive-HTTP transport owns IPv4-loopback binding, threaded request handling, GET/HEAD dispatch, method rejection, deterministic JSON encoding, security headers, UTF-8 content length, and each adapter's selected logging policy. Board, historical, journey, and coexistence adapters retain their own response types, server identities, fixed routes, rendered pages, snapshot production, pending states, and display errors. The transport has no evidence, reduction, or lifecycle authority.

See [NCC observability](ncc.md) for the supported contracts and [the test plan](test-plan.md) for their pass/fail rules.

## Resource model

Every run receives a new result directory, leased UDP ports, private control sockets, distinct guest-media workspaces, and an exact child-process set. The harness verifies source and executable identities before launch and records the inputs, configuration hashes, resource allocation, outcome, and cleanup in the result.

The sibling external laboratory contains replaceable build inputs and immutable run evidence, not repository state. See the [runbook](runbook.md) for its layout and [harness design](harness.md) for lifecycle mechanics.

## Publication seam

The eventual site pipeline may replace its two historical-machine stages with a network stage only if it preserves these external contracts:

- final bundle names `brad.bio.txt`, `build.log.html`, and `pipeline-status.json`;
- exact name and headline plus summary equality after whitespace normalization;
- pipeline identity, success result, zero exit status, build ID, and source revision;
- build-log identity, provenance, reuse fingerprints, semantic validation, and fail-closed publication.

The laboratory smokes do not read or modify the site checkout. [Gate 6](test-plan.md#gate-6-site-integration) owns acceptance of any integration.

## Decisions and evidence

[ADRs](adr/) own accepted design decisions. [Experiments](experiments/) and [research notes](research/) own dated observations and unresolved evidence. The [README](../README.md) owns public status, and the [test plan](test-plan.md) owns normative gates.
