# Historical Network UNIX TELNET terminal

- **Observed:** 2026-09-01
- **Repository checkpoint:** `101f27f6e42b13e2120ec944bffbe0bf42c0b72b`
- **Fresh external result:** `/Users/brf/src/arpanet-redux-lab/results/pdp11-its-terminal-historical-terminal-accepted-20260902T011936Z`
- **Status:** Accepted for the bounded character-oriented scope in [ADR-015](../adr/0015-character-oriented-historical-terminal.md) and [Gate 4J](../test-plan.md#gate-4j-historical-network-unix-telnet-terminal)

## Question

Can one foreground controller begin at the real Network UNIX host-176 shell, let an operator use the preserved guest TELNET command interface and protocol controls across recovered IMPs 62 and 6 to ITS host 106, retain exact bounded directional bytes, isolate simulator controls, present a clean teletype surface, and close the application and cleanup evidence without adding a second TELNET implementation or claiming an unproved host-ingress grammar?

## Primary evidence

The pinned Network UNIX [`telnet.c.org`](https://github.com/pdp11/network-unix-v6/blob/464893a99da8e3ac7f90577bc54749fa64bb0966/nosc-files/ncpp/tel-u/telnet.c.org) supplies the no-argument command processor, connection lifecycle, literal flag-command path, message and character modes, and TELNET controls. Its companion [`usrtelnetin.c`](https://github.com/pdp11/network-unix-v6/blob/464893a99da8e3ac7f90577bc54749fa64bb0966/nosc-files/ncpp/tel-u/usrtelnetin.c) owns network input and option negotiation, while [`mcharset.h`](https://github.com/pdp11/network-unix-v6/blob/464893a99da8e3ac7f90577bc54749fa64bb0966/nosc-files/h/net/mcharset.h) establishes the default literal `^` flag and character mappings. Open SIMH [`scp.c` at pinned revision `2722eef`](https://github.com/open-simh/simh/blob/2722eef44f68642eaab9f5d4e989ccd26e55e7de/scp.c) defines console WRU behavior; the tracked PDP-11 configuration assigns octal `034`, `Control-\`, so that byte must remain controller-owned. [RFC 854](https://www.rfc-editor.org/rfc/rfc854.html) supplies the protocol meaning of Are You There and the network virtual terminal model.

The local pinned source checkouts and earlier retained results were consulted read-only. No external source, firmware, media, executable, or raw log was copied into the repository; the conservative redistribution boundary in [`NOTICE.md`](../../NOTICE.md) remains unchanged.

## Method

Source-only tests exercised terminal attribute restoration, seven-bit input mapping, blocked WRU and local exit, control-safe output, diagnostic projection across delayed prompt boundaries, exact directional byte retention, local-control accounting, finite chunk and direction limits, cumulative hashes, interrupted tails, tampering, and rejection of records after completion. The original deterministic prompt-framed mode remained separately tested under `make telnet-check`.

The exact run reused the accepted receipt-bound PDP-11 build and existing direct Gate 4H topology:

```sh
make LAB_ROOT=/Users/brf/src/arpanet-redux-lab RUN_ID=historical-terminal-accepted-20260902T011936Z telnet
```

After the controller reached the Network UNIX root shell, the operator first entered `Control-\` to exercise the local safety boundary, then entered `/usr/bin/telnet`, `connect - -h 106`, remote `:TIME`, literal `^ayt`, `^msg`, `^character`, `^close`, and `bye`, followed by local Control-] exit. The Network UNIX client and its input companion—not the controller—generated and consumed TELNET protocol. The controller retained and read back `terminal-session.jsonl`, checked ITS and both IMPs only after a real connection opened, and used the existing bounded cleanup path.

An immediately preceding clean-revision trial exposed one presentation race: a delayed `PBTRACE` continuation arrived after the guest prompt had already been displayed. That result was not selected. The controller now preserves prompt-prefix recognition across idle flushes; a regression test and read-only replay of the exact trial prove the correction before this fresh run.

## Exact identity

The accepted run started at `2026-09-02T01:19:53Z` and finished at `01:23:08Z`. Its manifest records clean repository checkpoint `101f27f6e42b13e2120ec944bffbe0bf42c0b72b`; clean ARPANET-in-a-Box, Network UNIX, H316 SIMH, KA10 SIMH, and IMP11-A source revisions `78123c77b20dadd9b5967b184dbcb4195185eea6`, `464893a99da8e3ac7f90577bc54749fa64bb0966`, `feb155fbc49333e879ab082d481e6dcce27d2d91`, `5f57231e96ea823fa3f109d68e970546dcb08a31`, and `2722eef44f68642eaab9f5d4e989ccd26e55e7de`; and H316, KA10, and PDP-11 executable SHA-256 values `bdbcdffc63ada17c9ec6c7151aba42fd96388ff33d41ec6d42c5b27f47cfb994`, `ce491428206a64eecb691a1c5a54a33323e65c355e8507fdc4982cf9b2f9d350`, and `d1d6046647025cc822d90d3ebb2d633d24f9513e03bf2c7eca6dcef75bfe5ae3`.

The reused build-receipt SHA-256 was `3923f3f58ac445f57f47793d3ce2697735957bedd247542c5fd9fd81b05296b9`; the shared-topology SHA-256 was `aca72d0e14fa70eb7e0af9f86c30612e0de692a766dc7e3500ca768fd2331ad0`. All six UDP ports were privately leased. The final `terminal-session.jsonl` SHA-256 was `5b0bd8af0add0be846555813ce226022b88441396c0823f36765eb93f926df22`.

## Result

The strict stream terminated with `operator-exit`, no incomplete tail, 60 data records, one local-control record, 71 operator-to-PDP-11 bytes, and 6,868 PDP-11-to-operator bytes. The input and output cumulative SHA-256 values were `b3f195b15ef5e00a095ad3f6700a86b5ee7c5bbb5a877fb95b101ce1cdb292cf` and `42dc688c07331da5795d78fb1781ee4a4bf815518b9977ef7c937baadacdd39f`. The one blocked-WRU control record accounts for the injected `Control-\`; `terminal.simulator-wru-forwarded=0`, and no simulator prompt appeared in the human projection.

The guest displayed its preserved `UNIX User Telnet -- Ver I.5` interface, attempted the operator-entered connection, and reported `Connection open`. ITS created service job `53TLNT` for `HST176`, returned its ordered greeting, and answered remote `:TIME` with structured time, date, and uptime. The literal client command `^ayt` received `YES`; `^msg` reported `Msgmode`; and `^character` reported `Charmode`. Every bounded fidelity fact was `1`, both IMPs retained post-start traffic correlated in both directions, and the repaired client emitted no false protocol-error diagnostic.

The raw directional output retained 92 `SKTRACE` and 46 `PBTRACE` token occurrences. Replaying its 52 output records through the exact human projection produced zero such tokens and zero `sim>` tokens, demonstrating that only presentation changed while raw evidence remained intact.

The result records `repository.tracked_dirty=0`, `outcome=passed`, `exit_status=0`, `cleanup.outer-runtime=passed`, and `surviving_owned_processes=0`. ITS exited zero; the controller boundedly stopped the PDP-11 and both IMPs after local Control-] exit.

## Limits

This result proves a safe seven-bit teletype surface over the real Network UNIX shell and preserved TELNET client, guest-owned connection and option behavior, literal historical protocol controls, exact directional retention, correlated two-IMP transport evidence, and complete controller cleanup. It does not establish a cursor-addressed terminal type or safe operation of full-screen or paged ITS programs, interactive application-link failover, browser input, or a general command/result grammar.

It emits no message-journey sidecar, does not speculate from partial DATAIO records, and does not fill `boundary:request:6` or the reply-side guest-ingress seam. It changes no existing NCC schema, implements no KA10 or IMP11-A host-ingress parser, and grants no new simulator or browser authority.
