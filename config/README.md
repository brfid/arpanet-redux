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
| `hosts/its106-pair.simh` | Boot the independently prepared ITS host-106 media. |
| `hosts/its176-pair.simh` | Boot the independently prepared ITS host-176 media. |
| `hosts/pdp11-176.simh` | Attach the receipt-bound Network UNIX root and swap media and its IMP11-A interface without booting before controller readiness. |
| `topologies/imp5-ncc-host-interface.json` | Share the configured NCC/IMP 5 host interface, IMP 5/IMP 6 modem link, positions, port names, and passive-proof scope. |
| `imp/ncc-proof/imp5.simh` | Attach the NCC receiver to IMP 5 host 0 and IMP 5 MI1 to the proof peer. |
| `imp/ncc-proof/imp6.simh` | Supply the proof peer at the other end of IMP 5 MI1. |

The `router-oracle` files are consumed by `make smoke-router`, the `mixed` files by `make smoke-mixed`, and the `its-pair` files by the two-vintage-host design in the [test plan](../docs/test-plan.md). `make smoke-pdp11-its` reuses `imp/its-pair/imp6.simh` and `hosts/its106-pair.simh`, then pairs them with the committed PDP-11-specific IMP 62 and host configurations above. The older [`scripts/research/two-imp-its-with-pdp11.py`](../scripts/research/two-imp-its-with-pdp11.py) remains exploratory reproduction support rather than a formal lifecycle owner. Formal smoke outcomes are summarized in the project [README](../README.md).

## Runtime contract

The orchestration scripts start each simulator with an external asset directory as its working directory. Every IMP configuration therefore expects `impconfig.simh` and `impcode.simh` there; the former supplies the generic H316 device setup and the latter deposits the recovered IMP program. Every ITS host configuration expects `dskdmp.rim` and `rp03.0` through `rp03.3` in its working directory. None of those external files belongs in this repository.

The launch scripts reserve loopback UDP ports and export the `BRFID_*_PORT` variables referenced by these files. The port pairs are simulated cables only. Host application traffic must still enter and leave through a guest or Linux NCP implementation; a direct host-side application bridge would invalidate the test.

The KA10 and PDP-11 host files retain the octal `034` console WRU character because the interactive controllers use it to enter the simulator prompt during orderly shutdown. The KA10 files' four disk-pack attachments preserve the DSKDMP-to-RP03 ordering used by the prepared images. The IMP files retain interface debugging because acceptance evidence is extracted from the resulting packet logs.

Exact external source revisions and binary identities are maintained in [`../pins/`](../pins/). The reproduction sequence and result interpretation live in [`../docs/runbook.md`](../docs/runbook.md) and [`../docs/test-plan.md`](../docs/test-plan.md), respectively.

## Shared topology input

[`topologies/imp5-ncc-host-interface.json`](topologies/imp5-ncc-host-interface.json) is the first project-authored topology input shared between a simulator configuration and an NCC receiver. It gives the configured NCC receiver, IMP 5, and proof-peer IMP 6 identities; fixed display positions; the host-interface and modem endpoints; the `host 0` to `hi1` mapping; all four port-environment names; and the explicit report-line-1 identity at each end of this modem binding. The receiver resolves its two ports from the host-interface binding; the two simulator command files consume the corresponding host and modem names. The NCC reconciliation adapter consumes only a reciprocal pair of explicit report-line fields and never derives a report identity from `mi1`.

The two command files also require `BRFID_H316_MINI_ROOT` to name the external pinned `mini/` directory containing the generic H316 setup and recovered firmware. SIMH resolves nested command files beside the project command file, not the process working directory, so this explicit external-root variable keeps those third-party inputs out of the repository and makes the composition reproducible.

The route is a fidelity-minimal local proof path from IMP 6 through IMP 5 to the NCC receiver. Exact run `ncc-imp6-original-20260831T215714Z` independently observed checksum-valid reports and reciprocal line-1 endpoint identities from both IMPs before the report-line fields were added; the [dated experiment](../docs/experiments/2026-08-31-ncc-imp6-report-proof.md) owns that evidence. The fields are still configured facts, not a claim that every `MI1` corresponds to report line 1. The composition does not identify a historical site, recreate a historical route, or establish an NCP application exchange. The passive transport proof succeeds only after the receiver has sent its ready signal, received IMP readiness, and reassembled at least one complete IMP-to-host message.
