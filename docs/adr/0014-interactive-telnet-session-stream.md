# ADR-014: Retain terminal-owned interactive TELNET exchanges in a separate stream

- **Status:** Accepted
- **Date:** 2026-09-01
- **Decider:** Brad

## Context

The accepted Network UNIX-to-ITS gate already proves that the PDP-11 guest's real TELNET client reaches TELSER on ITS host 106 through IMPs 62 and 6. Its formal controller owns every simulator PTY and currently sends one fixed `:TIME` line. The next operator step is to replace that fixed application action with bounded terminal input without giving the browser, a second process, or an untyped byte relay control of the run.

Line-oriented interaction needs a response boundary. At the pinned PDP-10/ITS revision, preserved DDT documentation identifies `..PROMPT` as the instruction that types `*`; the same source describes an asterisk when DDT regains control in the relevant case. The accepted direct and failover console artifacts independently end each completed `:TIME` exchange with CRLF followed by `*`. These sources support a narrow DDT-prompt grammar, not a general grammar for programs launched beneath DDT.

The completed-summary, live-observation, historical-event, and message-journey contracts do not represent operator commands or console responses. Extending any of them would mix application interaction with network observation or route diagnosis. Raw simulator and console logs remain external laboratory artifacts and are not suitable as a browser-facing command contract.

## Decision

Add one version-1 JSON Lines sidecar named `interactive-telnet.jsonl`. A single foreground controller owns the PDP-11 and KA10 simulator PTYs, standard input, command dispatch, prompt detection, transcript writer, evidence checks, and cleanup. There is no intermediary command server and no browser endpoint.

The immutable session-start record binds the run revision, Network UNIX host 176, ITS host 106, the accepted direct route, TELSER service job, operator standard input, PDP-11 console response source, carriage-return line ending, CRLF-plus-asterisk DDT prompt, Latin-1 capture encoding, per-command timeout, and byte and command limits. Command records accept only nonblank printable ASCII, preserve exact text, identify `operator-stdin`, and use a contiguous controller sequence. Result records must immediately follow their command and preserve a bounded exact console capture, byte count, SHA-256, elapsed time, response source, status, truncation state, and prompt identity when complete. A terminal record closes the stream with a typed reason and counts that the reader recomputes.

The reader rejects unknown fields, unsupported versions, wrong route or ownership, invalid source attribution, gaps or reordering, mismatched command IDs, records after terminal completion, command or response limit violations, digest disagreement, invalid prompt/status combinations, and incorrect terminal counts. It may ignore only a final record that lacks its newline terminator.

The local `/help` and `/quit` commands are controller instructions and never enter the transcript or guest. All other accepted lines are sent to the already-running guest TELNET client followed by carriage return. A complete response is the exact PDP-11 console slice through the next documented DDT prompt. Timeout, session-close, interrupt, or response-limit results stop further input and fail the run after retaining the bounded partial capture.

The terminal harness requires at least one complete command/result pair, correlated post-start application traffic in both directions across IMPs 62 and 6, a matching ITS TELSER job, stable selected host and modem readiness, read-back validation and hashing of the transcript, and complete process cleanup. It does not emit a message-journey sidecar for arbitrary commands because no new host-ingress extraction grammar is being claimed.

## Options considered

### Connect the operator directly to a simulator PTY

This would expose simulator escape handling and mix guest input with simulator control. It would also leave command attribution, framing, timeout, evidence, and cleanup outside a single owner.

### Add input to the NCC browser

This would turn a passive evidence display into a command surface before the terminal protocol and ownership model were proven. Browser input remains a separate authority decision.

### Stream arbitrary characters without prompts

This would be closer to a terminal emulator but would not provide deterministic command/result framing. Programs with their own input modes, paging, control characters, and asynchronous output need a later explicit contract.

### Reuse an existing NCC persistence schema

Operator commands and application responses are neither historical IMP observations nor journey-boundary evidence. A separate additive stream preserves those existing meanings.

## Consequences

- `make telnet` reuses and verifies the retained receipt-bound guest build when present, boots the accepted two-IMP composition, and provides a line-oriented ITS session in the invoking terminal. A new laboratory must run `make build-pdp11-telnet` first.
- The first slice supports prompt-returning printable DDT and colon commands, not full-screen programs, character-at-a-time editing, arbitrary control characters, or paged subsystems.
- Every forwarded line and captured response is attributable, bounded, retained, read-back validated, and separate from raw simulator logs.
- The browser and NCC board remain passive and receive no command, simulator, process, link, or result-mutation authority.
- The accepted message-journey and unresolved KA10/IMP11-A host-ingress boundaries remain unchanged.
- A later character-oriented terminal or browser surface must make a new framing, authority, and cleanup decision rather than silently broadening this contract.

## Sources

- PDP-10/ITS, [`doc/_info_/ddtord.1462` at pinned revision `0f7d679`](https://github.com/PDP-10/its/blob/0f7d67997f9f5d30208e117e73272031e74f16b9/doc/_info_/ddtord.1462), especially the `..PROMPT` and “Returning to DDT” sections.
- Retained accepted direct run `pdp11-its-telnet-20260831T200436Z` and failover run `ncc-pdp11-its-application-failover-canonical-20260901T204637Z`, read in place in the external laboratory.
