# Simulator configuration boundary

The files under `config/` define only project-owned composition: node identities, point-to-point links, host attachments, named routes, display positions, and the minimum host settings required by the harness. They do not copy complete upstream simulator runners or include external firmware and media.

## Directory layout

| Path | Contents |
|---|---|
| `hosts/` | KA10 and PDP-11 host attachments and boot settings |
| `imp/<composition>/` | H316 identity, host-interface, modem, debug, and external firmware-loading commands for one composition |
| `topologies/` | Shared typed component, binding, route, position, and port identities used by controllers and NCC reducers |

## Select a composition

| Composition | Configuration | Shared topology | Make target |
|---|---|---|---|
| Router oracle | `imp/router-oracle/` | None | `smoke-router` |
| ITS and diagnostic Linux NCP | `imp/mixed/`, `hosts/its70-mixed.simh` | None | `smoke-mixed` |
| Two ITS hosts | `imp/its-pair/`, `hosts/its106-pair.simh`, `hosts/its176-pair.simh` | None | `smoke-two-its` |
| Network UNIX to ITS | `imp/pdp11-its/imp62.simh`, reused ITS-pair IMP 6, `hosts/pdp11-176.simh`, `hosts/its106-pair.simh` | `topologies/pdp11-its-telnet.json` | `smoke-pdp11-its` |
| NCC host-interface proof | `imp/ncc-proof/` | `topologies/imp5-ncc-host-interface.json` | Bounded proof tools |
| NCC alternate-path fault or loopback | `imp/ncc-alternate-path/` | `topologies/ncc-alternate-path-fault.json` | `smoke-ncc-alternate-path`, `smoke-ncc-line-loopback` |
| Application and NCC coexistence | `imp/ncc-pdp11-its/` plus reused IMP 7, IMP 62, and host files | `topologies/ncc-pdp11-its-coexistence.json` | `smoke-ncc-pdp11-its` |
| Application failover | `imp/ncc-pdp11-its-failover/` plus reused IMP 5 and host files | `topologies/ncc-pdp11-its-application-failover.json` | `smoke-ncc-pdp11-its-failover` |

Use the [runbook](../docs/runbook.md) for commands and the [test plan](../docs/test-plan.md) for claims. Dated experiments own why a composition was introduced and what its canonical run observed.

## Runtime contract

Launchers start each simulator in a run-specific external workspace. IMP configurations expect the external generic `impconfig.simh` and recovered `impcode.simh`. ITS configurations expect `dskdmp.rim` and four `rp03.*` disk images. PDP-11 configurations receive receipt-bound root and swap copies. None of these files belongs in Git.

The harness leases loopback UDP ports and exports the `BRFID_*_PORT` variables used through SIMH `%NAME%` expansion. This keeps tracked configurations immutable. Each pair of ports models one simulator cable; application traffic must still enter and leave through guest or diagnostic NCP code.

H316 compositions that load nested external command files also receive `BRFID_H316_MINI_ROOT`, the absolute path to the pinned external `mini/` directory. SIMH resolves nested command files relative to the project command file, so an explicit root is required.

KA10 and PDP-11 host files retain octal `034` as the console WRU character for orderly controller shutdown. The historical terminal controller blocks that byte from operator input and never exposes `sim>`; only its cleanup path sends WRU. KA10 disk attachments preserve the prepared DSKDMP-to-RP03 order. IMP files retain interface debugging because formal evidence uses bounded post-probe trace windows.

## Shared topology rules

A topology file is configuration, not evidence. It may name:

- stable component and interface identities;
- host-interface and modem endpoint bindings;
- named application routes composed from existing bindings;
- fixed display positions;
- environment-variable names for run-owned ports;
- explicit reciprocal report-line numbers backed by independent evidence.

Controllers use topology to select configuration and derive expected boundaries. Reducers use it to interpret observations. Neither may turn a configured crossing into an observation.

Report-line fields are valid only as a reciprocal pair of line numbers on one modem binding. Never infer them from `MI1`, another simulator device name, an application route, or a successful transaction. The accepted IMP 5/IMP 6 direct binding is mapped because both endpoints were independently observed. Alternate, application, and failover bindings remain unmapped unless separately promoted.

The failover topology names direct and alternate application routes but leaves both application bindings report-line-unmapped. The accepted run's unique reciprocal candidates remain `candidate-only-one-exact-run`; one run does not change configuration authority.

Exact external revisions and assets live in [`../pins/`](../pins/). The [NCC page](../docs/ncc.md) defines observation authority, and [`NOTICE.md`](../NOTICE.md) defines the redistribution boundary.
