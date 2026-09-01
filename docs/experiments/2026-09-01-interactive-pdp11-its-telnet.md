# Interactive Network UNIX-to-ITS TELNET session

- **Observed:** 2026-09-01
- **Repository checkpoint:** `04edaef137ccbe3ff44263edbe1ef526e5e62a67`
- **Fresh external result:** `/Users/brf/src/arpanet-redux-lab/results/pdp11-its-interactive-canonical-20260901T234119Z`
- **Status:** Accepted for the bounded line-oriented scope in [ADR-014](../adr/0014-interactive-telnet-session-stream.md) and [Gate 4I](../test-plan.md#gate-4i-interactive-network-unix-to-its-telnet)

## Question

Can one foreground controller let an operator enter more than one command through the real Network UNIX TELNET client to ITS host 106, deterministically frame each returned response, retain a strict command/result transcript, corroborate traffic through both recovered IMPs, and clean up the complete composition without adding browser control or claiming an unproved host-ingress grammar?

## Framing evidence

At the pinned PDP-10/ITS revision, the preserved DDT documentation defines `..PROMPT` as the instruction that types `*` and describes an asterisk when control returns to DDT in the relevant case. The accepted direct and failover console artifacts independently end each completed remote `:TIME` exchange with CRLF followed by `*`. Together they support a bounded response delimiter for commands that return to DDT; they do not define a general grammar for arbitrary ITS programs.

The primary historical source is PDP-10/ITS [`doc/_info_/ddtord.1462` at revision `0f7d67997f9f5d30208e117e73272031e74f16b9`](https://github.com/PDP-10/its/blob/0f7d67997f9f5d30208e117e73272031e74f16b9/doc/_info_/ddtord.1462). The local pinned checkout and retained accepted application artifacts were consulted read-only; no externally sourced text or media was copied into the repository.

## Method

The new source-only contract tests exercised strict session identity and ownership, command/result adjacency, ordering, byte and command limits, exact Latin-1 capture digests, prompt/status combinations, terminal recounting, interrupted tails, tampering, and rejection of records after terminal completion. Controller tests exercised local-command separation, printable-input validation, prompt slicing, timeout and response limits, fatal-session handling, evidence emission, and terminal-safe simulator identity probes.

The exact external run reused the accepted receipt-bound PDP-11 build rather than rebuilding guest media or rerunning a settled formal experiment:

```sh
make LAB_ROOT=/Users/brf/src/arpanet-redux-lab RUN_ID=canonical-20260901T234119Z telnet
```

One controller booted Network UNIX host 176, ITS host 106, and recovered IMPs 62 and 6; launched the guest's `/usr/bin/telnet - -h 106`; owned operator standard input and every simulator PTY; wrote and read back `interactive-telnet.jsonl`; checked the ITS service job and post-start traffic; and used the bounded existing cleanup model. The browser, passive NCC server, and message-journey extractor did not participate.

## Exact identity

The run started at `2026-09-01T23:47:06Z` and finished at `23:50:10Z`. Its retained environment records clean repository checkpoint `04edaef137ccbe3ff44263edbe1ef526e5e62a67`; clean ARPANET-in-a-Box, Network UNIX, H316 SIMH, KA10 SIMH, and IMP11-A source revisions `78123c77b20dadd9b5967b184dbcb4195185eea6`, `464893a99da8e3ac7f90577bc54749fa64bb0966`, `feb155fbc49333e879ab082d481e6dcce27d2d91`, `5f57231e96ea823fa3f109d68e970546dcb08a31`, and `2722eef44f68642eaab9f5d4e989ccd26e55e7de`; and H316, KA10, and PDP-11 executable SHA-256 values `bdbcdffc63ada17c9ec6c7151aba42fd96388ff33d41ec6d42c5b27f47cfb994`, `ce491428206a64eecb691a1c5a54a33323e65c355e8507fdc4982cf9b2f9d350`, and `d1d6046647025cc822d90d3ebb2d633d24f9513e03bf2c7eca6dcef75bfe5ae3`.

The reused PDP-11 build receipt SHA-256 was `1cc22c10da31c09f6066b421a0458478c70ac0dc48f065dc23295a5015a1532c`. The shared topology SHA-256 was `aca72d0e14fa70eb7e0af9f86c30612e0de692a766dc7e3500ca768fd2331ad0`. All six UDP ports were privately leased. The final interactive transcript SHA-256 was `3d9d51d7a589971c1dc0997eb40b76f53e25945ff41d7ddc6a137a6193d5a48c`.

## Result

Network UNIX printed `Connection open`, ITS recorded service user `53TLNT`, and one guest TELNET session remained open while the operator separately entered uppercase `:TIME` and lowercase `:time`. Both results completed through an `its-ddt-star` prompt. Each returned a time, full date, uptime, `:KILL`, and the CRLF-plus-asterisk prompt; their exact captured byte lengths were 203, with separately verified SHA-256 values. The terminal record reported two commands, two complete results, no failures, and `operator-quit`.

Both IMP 62 and IMP 6 recorded post-start interactive traffic, and exact significant inter-IMP content correlated in both directions. The application evidence retained `network-unix-telnet`, `TELSER`, service user `53TLNT`, `interactive-line-oriented`, two completed commands, and `its-ddt-star`. The transcript passed strict readback and digest validation.

The result records `repository.tracked_dirty=0`, `outcome=passed`, `exit_status=0`, `cleanup.outer-runtime=passed`, and `surviving_owned_processes=0`. ITS exited zero; the foreground controller boundedly stopped the PDP-11 and both IMPs after the operator quit.

## Limits

This result proves repeated line-oriented operator commands over one real Network UNIX-to-ITS TELNET session, deterministic DDT-prompt response framing, typed retained evidence, bidirectional recovered-IMP corroboration, and complete ownership and cleanup. It does not prove character-at-a-time editing, arbitrary controls, full-screen or paged programs, a browser command path, an interactive failover cut, or general ITS program framing.

It does not speculate from partial DATAIO records, emit a message-journey sidecar, fill `boundary:request:6` or the reply-side guest ingress, implement a KA10 or IMP11-A host-ingress parser, change an existing NCC schema, or expand simulator authority. Those remain separate evidence and design decisions.
