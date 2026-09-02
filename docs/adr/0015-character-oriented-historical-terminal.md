# ADR-015: Put character-oriented TELNET fidelity in the historical guest

- **Status:** Accepted
- **Date:** 2026-09-01
- **Decider:** Brad

## Context

The accepted line-oriented session in [ADR-014](0014-interactive-telnet-session-stream.md) automatically starts `/usr/bin/telnet - -h 106`, frames responses at the documented ITS DDT prompt, and retains deterministic command/result evidence. That framing is appropriate for repeatable acceptance but bypasses the preserved Network UNIX client's own command interface and cannot represent character mode, client escape commands, asynchronous output, or TELNET controls.

The pinned Network UNIX source contains a complete user TELNET program and its network-input companion. When invoked without arguments, the client presents its own command processor. Its preserved commands include connection lifecycle, message and character modes, local echo, a configurable literal flag character, and TELNET controls including Are You There, break, abort output, go ahead, interrupt process, and synch. Its input companion parses and answers option negotiation. Reimplementing those behaviors in the modern controller would reduce fidelity and create competing protocol authority.

A direct simulator-PTY handoff is not acceptable. The tracked PDP-11 configuration reserves octal `034`, `Control-\`, as the SIMH WRU character. If forwarded, that byte stops guest execution and exposes the simulator command prompt. Raw guest output can also contain controls that should not be interpreted by a modern terminal without an explicit terminal profile.

## Decision

Keep two foreground interfaces with different evidence purposes. `make telnet-check` retains ADR-014 unchanged: it starts the client with arguments, accepts printable prompt-returning lines, and emits `interactive-telnet.jsonl`. `make telnet` becomes the human historical-terminal surface: it boots to the Network UNIX root shell, lets the operator invoke `/usr/bin/telnet` without arguments, and lets the preserved client establish and operate the connection.

The same foreground controller continues to own standard input and every simulator PTY. During the human session it relays characters between the operator terminal and the PDP-11 console. It never parses or generates TELNET protocol: the Network UNIX client and its companion remain authoritative.

The controller applies a declared `seven-bit-safe-teletype` adapter. It maps local line feed to carriage return and modern Delete to the guest's backspace character, rejects high-bit input, blocks `Control-\` so SIMH WRU cannot reach the simulator, and reserves Control-] for clean controller exit. Control-C and other nonreserved seven-bit controls reach the historical guest. Guest carriage return and line feed render as a stable newline; bell, backspace, and tab remain active; other controls render as visible hexadecimal text so guest output cannot inject modern terminal escape sequences.

Known project-added `SKTRACE` and `PBTRACE` instrumentation lines are omitted only from the human display. Their exact bytes remain in the raw PDP-11 console log and the retained terminal stream. The projection does not suppress unknown lines or reinterpret application state.

Add one version-1 `terminal-session.jsonl` sidecar. Its immutable start record binds the exact run and repository revision, available host-176-to-host-106 route, sole controller ownership, terminal profile, reserved controls, input mappings, and finite input, output, and chunk limits. Directional byte records use contiguous controller order, UTC observation time, base64 data, byte count, and SHA-256. Local-control records account for blocked WRU and rejected high-bit bytes. The terminal record closes over directional byte counts, cumulative digests, record counts, and a typed reason. Its strict reader rejects unknown fields, bad order, unsupported identity or profile, invalid base64, chunk or directional limit violations, digest disagreement, and records after completion; it may ignore only one interrupted final record.

An operator may leave before starting TELNET; such a run proves only terminal lifecycle and makes no connection claim. If `Connection open` is observed, the controller closes the stronger application claim over the real no-argument client banner and command interface, connection attempt, ordered ITS greeting, ITS TELSER service job, correlated post-offset traffic through both IMPs, stable selected host and modem readiness, transcript readback, and complete cleanup. It does not infer application success from configured topology.

## Options considered

### Add only a manual-launch pause to the line controller

This would expose the Network UNIX shell but would still turn the connected session back into synthetic line commands and DDT-prompt parsing. It would not support the historical client's own modes or TELNET controls.

### Implement TELNET negotiation in the controller

The preserved guest already implements it. A modern second stack would be less historical, duplicate authority, and risk silently compensating for guest behavior the simulation should expose.

### Hand the simulator PTY directly to the operator

This would expose SIMH WRU and `sim>`, lose sole-controller attribution and limits, and make cleanup dependent on an untrusted terminal session.

### Provide a general terminal emulator or browser terminal

Full terminal-type negotiation, cursor addressing, screen programs, paging, and browser input require a separately evidenced terminal profile and authority decision. They are not necessary for faithful teletype TELNET interaction.

## Consequences

- The operator now begins on Network UNIX host 176, invokes the preserved client, and uses its actual command language to connect to ITS host 106.
- Historical character/message modes and TELNET controls can be exercised without adding a modern protocol implementation.
- The deterministic Gate 4I path and its schema remain available under `make telnet-check`; the character stream does not pretend to have command/result or general ITS-program grammar.
- Simulator command authority does not expand, the NCC browser remains passive, and no host-ingress observation is added to the message journey.
- Full-screen ITS programs and a browser terminal remain out of scope until a historically supported terminal type and a separate control boundary are selected.

## Sources

- Network UNIX, [`nosc-files/ncpp/tel-u/telnet.c.org` at pinned revision `464893a`](https://github.com/pdp11/network-unix-v6/blob/464893a99da8e3ac7f90577bc54749fa64bb0966/nosc-files/ncpp/tel-u/telnet.c.org), preserved user-client command and terminal behavior.
- Network UNIX, [`nosc-files/ncpp/tel-u/usrtelnetin.c` at pinned revision `464893a`](https://github.com/pdp11/network-unix-v6/blob/464893a99da8e3ac7f90577bc54749fa64bb0966/nosc-files/ncpp/tel-u/usrtelnetin.c), preserved network-input and option-negotiation behavior.
- Network UNIX, [`nosc-files/h/net/mcharset.h` at pinned revision `464893a`](https://github.com/pdp11/network-unix-v6/blob/464893a99da8e3ac7f90577bc54749fa64bb0966/nosc-files/h/net/mcharset.h), default seven-bit mappings, literal flag character, and character mode.
- Open SIMH, [`scp.c` at pinned revision `2722eef`](https://github.com/open-simh/simh/blob/2722eef44f68642eaab9f5d4e989ccd26e55e7de/scp.c), `SET CONSOLE WRU` and simulator-stop semantics.
- [RFC 854, TELNET Protocol Specification](https://www.rfc-editor.org/rfc/rfc854.html), command semantics and the network virtual terminal model.
