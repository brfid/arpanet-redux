# Simulator configuration boundary

These command files contain only the project-owned composition for each test topology: node identities, live point-to-point links, host attachments, and the minimum KA10 settings needed to boot ITS. They are deliberately not copies of a complete upstream simulator runner.

## Choose a topology

| Configuration | Responsibility |
|---|---|
| `imp/router-oracle/imp2.simh` | Attach Linux NCP host 002 to IMP 2, link IMP 2 to IMP 3, and leave the second modem pointed at the intentionally absent peer. |
| `imp/router-oracle/imp3.simh` | Attach Linux NCP host 003 to IMP 3 and join IMP 3 to IMPs 2 and 4. |
| `imp/router-oracle/imp4.simh` | Model the hostless IMP 4 used to prove host-dead signaling. |
| `imp/mixed/imp6.simh` | Join ITS host 106 to IMP 6 and IMP 6 to IMP 62. |
| `imp/mixed/imp62.simh` | Join IMP 62 to the Linux NCP diagnostic host 076. |
| `hosts/its70-mixed.simh` | Boot the prepared ITS host-106 media and attach its NCP device to IMP 6. |
| `imp/its-pair/imp6.simh` | Join ITS host 106 to IMP 6 and IMP 6 to IMP 62 for the two-ITS guest-to-guest topology. |
| `imp/its-pair/imp62.simh` | Join ITS host 176 to IMP 62 and IMP 62 to IMP 6 for the two-ITS guest-to-guest topology. |
| `imp/pdp11-its/imp62.simh` | Join the short-leader Network UNIX PDP-11 host 176 to IMP 62 without ITS leader conversion. |
| `topologies/pdp11-its-telnet.json` | Share the formal Network UNIX host 176 to ITS host 106 route, host attachments, modem link, positions, and port identities with typed message-journey emission. |
| `hosts/its106-pair.simh` | Boot the independently prepared ITS host-106 media. |
| `hosts/its176-pair.simh` | Boot the independently prepared ITS host-176 media. |
| `hosts/pdp11-176.simh` | Attach the receipt-bound Network UNIX root and swap media and its IMP11-A interface without booting before controller readiness. |
| `topologies/imp5-ncc-host-interface.json` | Share the configured NCC/IMP 5 host interface, IMP 5/IMP 6 modem link, positions, port names, and passive-proof scope. |
| `imp/ncc-proof/imp5.simh` | Attach the NCC receiver to IMP 5 host 0 and IMP 5 MI1 to the proof peer. |
| `imp/ncc-proof/imp6.simh` | Supply the proof peer at the other end of IMP 5 MI1. |
| `topologies/ncc-alternate-path-fault.json` | Share a nonhistorical IMP 5/6/7 triangle, the NCC receiver on IMP 5, direct and alternate IMP 6-to-NCC routes, and the evidenced direct-line report identities. |
| `imp/ncc-alternate-path/imp5.simh` | Attach the NCC receiver, the relay-mediated direct IMP 5/6 line, and IMP 5's alternate link to IMP 7. |
| `imp/ncc-alternate-path/imp6.simh` | Attach IMP 6 to the other end of the direct-line relay and to IMP 7. |
| `imp/ncc-alternate-path/imp7.simh` | Join the two alternate-path links between IMPs 5 and 6. |

The `router-oracle` files are consumed by `make smoke-router`, the `mixed` files by `make smoke-mixed`, and the `its-pair` files by the two-vintage-host design in the [test plan](../docs/test-plan.md). `make smoke-pdp11-its` reuses `imp/its-pair/imp6.simh` and `hosts/its106-pair.simh`, then pairs them with the committed PDP-11-specific IMP 62 and host configurations above. It validates `topologies/pdp11-its-telnet.json` before launch and uses the named route only to derive typed expected journey boundaries; configured crossings do not become observations. The older [`scripts/research/two-imp-its-with-pdp11.py`](../scripts/research/two-imp-its-with-pdp11.py) remains exploratory reproduction support rather than a formal lifecycle owner. Formal smoke outcomes are summarized in the project [README](../README.md).

## Runtime contract

The orchestration scripts start each simulator with an external asset directory as its working directory. Every IMP configuration therefore expects `impconfig.simh` and `impcode.simh` there; the former supplies the generic H316 device setup and the latter deposits the recovered IMP program. Every ITS host configuration expects `dskdmp.rim` and `rp03.0` through `rp03.3` in its working directory. None of those external files belongs in this repository.

The launch scripts reserve loopback UDP ports and export the `BRFID_*_PORT` variables referenced by these files. The port pairs are simulated cables only. Host application traffic must still enter and leave through a guest or Linux NCP implementation; a direct host-side application bridge would invalidate the test.

The KA10 and PDP-11 host files retain the octal `034` console WRU character because the interactive controllers use it to enter the simulator prompt during orderly shutdown. The KA10 files' four disk-pack attachments preserve the DSKDMP-to-RP03 ordering used by the prepared images. The IMP files retain interface debugging because acceptance evidence is extracted from the resulting packet logs.

Exact external source revisions and binary identities are maintained in [`../pins/`](../pins/). The reproduction sequence and result interpretation live in [`../docs/runbook.md`](../docs/runbook.md) and [`../docs/test-plan.md`](../docs/test-plan.md), respectively.

## Shared topology input

[`topologies/pdp11-its-telnet.json`](topologies/pdp11-its-telnet.json) represents the already accepted heterogeneous Gate 4H composition without adding a route or changing simulator commands. It names Network UNIX host 176, IMP 62, IMP 6, and ITS host 106; the two host-interface bindings; the one modem binding; their existing six port-environment names; stable positions; and the single host-176-to-host-106 route. The formal controller and read-only retained-result adapter derive the same twelve request/reply boundary identities from this file. Direct trace observations and harness-derived connected-peer observations remain separately typed, and the topology alone never proves activity or host delivery.

[`topologies/imp5-ncc-host-interface.json`](topologies/imp5-ncc-host-interface.json) is the first project-authored topology input shared between a simulator configuration and an NCC receiver. It gives the configured NCC receiver, IMP 5, and proof-peer IMP 6 identities; fixed display positions; the host-interface and modem endpoints; the `host 0` to `hi1` mapping; all four port-environment names; and the explicit report-line-1 identity at each end of this modem binding. The receiver resolves its two ports from the host-interface binding; the two simulator command files consume the corresponding host and modem names. The NCC reconciliation adapter consumes only a reciprocal pair of explicit report-line fields and never derives a report identity from `mi1`.

The two command files also require `BRFID_H316_MINI_ROOT` to name the external pinned `mini/` directory containing the generic H316 setup and recovered firmware. SIMH resolves nested command files beside the project command file, not the process working directory, so this explicit external-root variable keeps those third-party inputs out of the repository and makes the composition reproducible.

The route is a fidelity-minimal local proof path from IMP 6 through IMP 5 to the NCC receiver. Exact run `ncc-imp6-original-20260831T215714Z` independently observed checksum-valid reports and reciprocal line-1 endpoint identities from both IMPs before the report-line fields were added; the [dated experiment](../docs/experiments/2026-08-31-ncc-imp6-report-proof.md) owns that evidence. The fields are still configured facts, not a claim that every `MI1` corresponds to report line 1. The composition does not identify a historical site, recreate a historical route, or establish an NCP application exchange. The passive transport proof succeeds only after the receiver has sent its ready signal, received IMP readiness, and reassembled at least one complete IMP-to-host message.

[`topologies/ncc-alternate-path-fault.json`](topologies/ncc-alternate-path-fault.json) reuses that exact NCC host attachment and direct IMP 5/6 report-line identity, then adds IMP 7 as an alternate route. Only the direct binding carries report-line fields: no line number is inferred for either alternate binding. Its ten environment variables represent the NCC host cable, two alternate modem cables, both simulator ends of the direct cable, and the two ports held by a project-owned direct-line instrument. The fault relay initially forwards the direct cable in both directions, then remains bound while dropping both directions. The loopback reflector uses the same initial forwarding phase, then returns each endpoint's unmodified datagrams to that same endpoint through the same bound socket. In either case, a later report from IMP 6 can reach the receiver only through IMP 7 and IMP 5. This is a deliberately nonhistorical line-state evidence composition, not a claim about a historical ARPANET route.

`make smoke-ncc-alternate-path` owns the cut lifecycle, and `make smoke-ncc-line-loopback` owns the reflection lifecycle. The [test plan](../docs/test-plan.md) defines their separate acceptance checks, the [runbook](../docs/runbook.md) gives both invocations, and the dated [fault](../docs/experiments/2026-08-31-ncc-alternate-path-fault.md) and [loopback](../docs/experiments/2026-08-31-ncc-line-loopback.md) experiments record why the composition and state-specific neighbor rules exist.
