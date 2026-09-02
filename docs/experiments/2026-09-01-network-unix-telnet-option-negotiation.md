# Network UNIX TELNET option-negotiation repair

- **Observed:** 2026-09-01
- **Repository base:** `49277c7ad56303e786aa1199ee9b8c601d5b73bf` with the bounded repair under test
- **Pinned Network UNIX source:** `464893a99da8e3ac7f90577bc54749fa64bb0966`
- **Fresh external build:** `/Users/brf/src/arpanet-redux-lab/results/pdp11-telnet-option-fix-build-20260902T002513Z`
- **Fresh external result:** `/Users/brf/src/arpanet-redux-lab/results/pdp11-its-interactive-option-fix-20260902T003000Z`
- **Status:** Accepted for removal of the false client diagnostic; the existing interactive scope and authority are unchanged

## Question

Why does the preserved Network UNIX TELNET client print `Possible protocol error! command = 376, option = 3.` while opening an otherwise usable ITS session, and can the message be removed without modifying the pinned checkout, relaxing the evidence gate, changing a data contract, or expanding simulator authority?

## Primary evidence and diagnosis

The pinned [`usrtelnetin.c`](https://github.com/pdp11/network-unix-v6/blob/464893a99da8e3ac7f90577bc54749fa64bb0966/nosc-files/ncpp/tel-u/usrtelnetin.c) handles the four new-TELNET negotiation commands in one switch. Its `DONT` branch selects `WONT`, which is the intended refusal response, but uniquely lacks a `break` and therefore falls into the generic protocol-error printer. The pinned [`telnet.h`](https://github.com/pdp11/network-unix-v6/blob/464893a99da8e3ac7f90577bc54749fa64bb0966/nosc-files/h/net/telnet.h) identifies decimal command 254, octal `376`, as `DONT` and option 3 as Suppress Go Ahead.

This interpretation agrees with primary protocol documentation rather than being inferred from the successful session alone. [RFC 495](https://www.rfc-editor.org/rfc/rfc495.html) records Suppress Go Ahead among the official new-TELNET negotiations in May 1973, and the contemporary [RFC 694](https://www.rfc-editor.org/rfc/rfc694.html) registry assigns option 3 to it. The later consolidated [RFC 854](https://www.rfc-editor.org/rfc/rfc854.html) defines command 254 as `DONT`, while [RFC 858](https://www.rfc-editor.org/rfc/rfc858.html), which obsoletes the cited 1973 option specification, explicitly defines `DONT SUPPRESS-GO-AHEAD` and the `WONT`/`DONT` default. ITS therefore sent a valid negotiation command; only the client's diagnostic fallthrough was defective.

## Narrow repair

`scripts/research/build-guest-telnet.py` now adds the missing `break` only to its external staged copy. The helper requires exactly one occurrence of the pinned branch-to-default shape and fails closed if the source is already repaired, duplicated, or changed. It does not edit or vendor the historical checkout. Source-only tests cover the exact insertion and all three refusal cases, and moving the optional `pexpect` import into the live build function keeps those adaptation tests on the standard-library test path.

The real V6 compiler produced `/usr/bin/usrtelnetin` at 2,390 bytes, replacing the old 2,454-byte artifact. The build-log validator requires that observed size. The new receipt SHA-256 is `3923f3f58ac445f57f47793d3ce2697735957bedd247542c5fd9fd81b05296b9`; it binds staged `usrtelnetin.c` SHA-256 `2b298722eacf0a2f5352dad86683eda309a614e8de1cb8f3516d820d962b266e`, final root SHA-256 `cdb60aa311d387a3e6fafe6e5a0ad485470fe5099e0709aa5c928e05882684a0`, final swap SHA-256 `481e10a7c0bc085bef15d5bd4af21ca07c6cd07264ef4ac1d8cc7214d6317a79`, both clean pinned source identities, the simulator identity, build logs, builder hashes, and the complete media provenance chain.

## Exact run and result

The first runtime attempt, `pdp11-its-interactive-option-fix-20260902T002800Z`, stopped before simulator launch because the restricted execution environment denied the private UDP reservation helper; it is not application evidence. The accepted rerun used real loopback sockets and the new receipt-bound media:

```sh
make LAB_ROOT=/Users/brf/src/arpanet-redux-lab RUN_ID=option-fix-20260902T003000Z PDP11_INTERACTIVE_BUILD_ROOT=/Users/brf/src/arpanet-redux-lab/results/pdp11-telnet-option-fix-build-20260902T002513Z telnet
```

The session started at `2026-09-02T00:27:09Z` and finished at `00:29:11Z`. Network UNIX printed `Connection open`, ITS assigned service job `53TLNT`, and the greeting completed as `It's a lovely day to be a turist!` with no interleaved diagnostic. A recursive read-only scan of the completed result found no `Possible protocol error`, `command = 376`, or `option = 3` text.

The operator entered `:TIME`. ITS returned `(Please Log In)`, a full time and date, uptime, `:KILL`, and the documented CRLF-plus-asterisk DDT prompt. The strict transcript records one complete 203-byte result, zero failed commands, reason `operator-quit`, and SHA-256 `9541a61896e6551962844f8226672da998e6ef1a341f7e84cee9d19f4afffa66`. Both IMPs recorded post-start traffic correlated in both directions; `outcome=passed`, `exit_status=0`, `cleanup.outer-runtime=passed`, and `surviving_owned_processes=0`.

## Boundary

This result removes one false client-side message and improves local `/help`; it does not alter TELNET semantics, an NCC or transcript schema, the simulator, the IMPs, ITS, the accepted journey, or any extraction grammar. Older receipt-bound builds and their nonfatal diagnostic remain immutable historical evidence. The interactive controller remains limited to printable prompt-returning lines; character-at-a-time input, paging, full-screen programs, browser input, and both unproved guest-ingress boundaries remain outside this change.
