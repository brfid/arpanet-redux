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
| `imp/its-pair/imp6.simh` | Join ITS host 106 to IMP 6 and IMP 6 to IMP 62 for the pending guest-to-guest topology. |
| `imp/its-pair/imp62.simh` | Join ITS host 176 to IMP 62 and IMP 62 to IMP 6 for the pending guest-to-guest topology. |
| `hosts/its106-pair.simh` | Boot the independently prepared ITS host-106 media. |
| `hosts/its176-pair.simh` | Boot the independently prepared ITS host-176 media. |

The `router-oracle` files are consumed by `make smoke-router`, the `mixed` files by `make smoke-mixed`, and the `its-pair` files by the two-vintage-host design in the [test plan](../docs/test-plan.md). Current outcomes are reported only in the project [README](../README.md).

## Runtime contract

The orchestration scripts start each simulator with an external asset directory as its working directory. Every IMP configuration therefore expects `impconfig.simh` and `impcode.simh` there; the former supplies the generic H316 device setup and the latter deposits the recovered IMP program. Every ITS host configuration expects `dskdmp.rim` and `rp03.0` through `rp03.3` in its working directory. None of those external files belongs in this repository.

The launch scripts reserve loopback UDP ports and export the `BRFID_*_PORT` variables referenced by these files. The port pairs are simulated cables only. Host application traffic must still enter and leave through a guest or Linux NCP implementation; a direct host-side application bridge would invalidate the test.

The KA10 files retain the octal `034` console WRU character because the interactive two-ITS controller uses it to enter the simulator prompt during orderly shutdown. Their four disk-pack attachments preserve the DSKDMP-to-RP03 ordering used by the prepared images. The IMP files retain interface debugging because acceptance evidence is extracted from the resulting packet logs.

Exact external source revisions and binary identities are maintained in [`../pins/`](../pins/). The reproduction sequence and result interpretation live in [`../docs/runbook.md`](../docs/runbook.md) and [`../docs/test-plan.md`](../docs/test-plan.md), respectively.
