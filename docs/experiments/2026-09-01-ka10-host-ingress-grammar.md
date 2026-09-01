# KA10/ITS host-ingress extraction-grammar feasibility

- **Observed:** 2026-09-01
- **Repository baseline:** `bde94128cc36cbd3d3f953a6f93ed916c2c4d5ef`
- **Accepted journey target:** `/Users/brf/src/arpanet-redux-lab/results/pdp11-its-telnet-message-journey-20260901T123307Z`
- **Retained KA10 trace:** `/Users/brf/src/arpanet-redux-lab/results/imp11a-telnet-ka10-trace-20260831T131616Z`
- **Scope:** Read-only feasibility pass for a KA10/ITS observation at `boundary:request:6`; no simulator rerun, parser, schema change, or simulator instrumentation

## Decision

A complete extraction grammar is not proven. The exact missing property is a direct trace binding from each printed KA10 `DATAI` value to the receive-assembly event that produced it: at minimum the input message identity, assembled width of 32 or 36 bits, and valid-bit count for the final word. The retained trace records the CPU's later read of `ibuf`, not that assembly event. No parser or typed host-ingress observation is implemented, and `boundary:request:6` remains missing.

The accepted formal result has an additional evidence gap: it retains H316 `imp6.debug.log`, `imp62.debug.log`, and the KA10 console, but no KA10 IMP device-debug trace. A grammar proven elsewhere could therefore not retroactively create a direct host-106 observation for that immutable run.

## Bounded question

Can the complete `CONI`, `CONO`, and `DATAIO` record retained from the earlier PDP-11-to-ITS investigation be inverted into the exact 1822/NCP message presented to ITS, strongly enough to correlate the accepted request fingerprint `f1d4dba566165c587ee584588aa3ea5091db970185b87bb98f0b7e462bfd4ee4` and construct the already-typed KA10 observation seam without treating the known IMP 6 egress message as the answer?

The pass did not reconsider the accepted application proof, H316 message grammar, PDP-11 byte order, ITS long-leader handling, or message-journey schema. It did not compare clocks from separate simulators. Retained artifacts were read only, and raw third-party logs remain in the external laboratory under the boundary in [`NOTICE.md`](../../NOTICE.md).

## Inputs and identity

The accepted target is the exact run already recorded by the [formal journey experiment](2026-09-01-pdp11-its-message-journey.md). Its sidecar SHA-256 is `c1be793d7120d8f98bd22681dd7b420513f1ec8c20190a7c2fe4c888d3080d8e`; request observations 1 through 5 carry the request fingerprint above, and the terminal diagnosis stops at `boundary:request:6`. The accepted result's KA10 console SHA-256 is `d754bebbec51b46b63669a42be384c0e578801e0fa3b7397b7c13dffddab15b2`. Its file inventory has no `host106-imp-device-debug.log` or equivalent KA10 `DATAIO` record.

The only retained KA10 device trace relevant to this route is the earlier failed application run `imp11a-telnet-ka10-trace-20260831T131616Z`. Its `host106-imp-device-debug.log` SHA-256 is `fdb2e83511185155844b9cab648506e42c10a7342f616a949634f5311a61fc2f`; its configuration enabled the complete available `CONI`, `CONO`, and `DATAIO` debug categories. The paired H316 console SHA-256 is `f666692e9ae223a3e9446e6fa93f42ccbfa31003511758503e5289f102b7ec9a`. That run predates the accepted PDP-11 byte-order fix: its RFC-bearing short message has byte count 11 and fingerprint `09cbf41d4b5005dc5d5b878612d9b34f2906eea91bc010b9e88b06b86291683b`, not the accepted request's byte count 10 and fingerprint.

## Primary source findings

The pinned KA10 simulator at `5f57231e96ea823fa3f109d68e970546dcb08a31` makes the trace boundary explicit in `PDP10/kx10_imp.c`. `DATAI` copies `imp_data.ibuf`, clears `IMPID` and `IMPLW`, prints the 36-bit value and a shifted hexadecimal convenience value, and schedules the device service. It does not print an input width. The later service routine chooses 32 or 36 bits from `IMPI32` while assembling the next `ibuf`; the NCP UDP receive routine separately collects 16-bit transport words and turns `PFLG_FINAL` into an internal byte-count boundary. Neither the service event, transport sequence, internal input position, chosen width, nor final valid-bit count appears in the debug record. The current [upstream file history](https://github.com/larsbrinkhoff/ka10-simh/commits/master/PDP10/kx10_imp.c) retains the same `DATAI` format; the latest upstream commit touching that file is [`04bfdd884a522a3a85cc776bbf1166c7068ab93d`](https://github.com/larsbrinkhoff/ka10-simh/commit/04bfdd884a522a3a85cc776bbf1166c7068ab93d), and it adds no receive-assembly record.

The pinned [ITS KAIMP definitions](https://github.com/PDP-10/its/blob/0f7d67997f9f5d30208e117e73272031e74f16b9/src/system/kaimp.defs1) identify `IMPI32` as input mode, `IMPID` as a word available for `DATAI`, and `IMPLW` as last IMP word. More decisively, the pinned [ITS input implementation](https://github.com/PDP-10/its/blob/0f7d67997f9f5d30208e117e73272031e74f16b9/src/system/impold.ncp2) says that a regular NCP message reaches dispatch with its sixth leader word already waiting in 36-bit mode. ITS then sets 32-bit mode and performs the `DATAI` that consumes that already-waiting 36-bit word; the mode change governs further input. A parser therefore cannot assign the mode visible immediately before a `DATAI` to the value on that same line.

DEC's primary [*AN10/AN20 ARPANET Interface Technical Manual*](https://www.rcsri.org/library/dec-pdp10/PDP10-Arpanet-Interface.pdf), EK-AN1/2-TM-001, corroborates the hardware distinction. Printed pages 3-26 through 3-31 describe `IN DONE` as the state produced when a word has been assembled or the last IMP bit arrives, describe zero filling when the last bit arrives before a word is full, and describe the Input Data Register as a 36-bit shift register whose leftmost 32 bits are filled first and whose remaining four bits are filled only in 36-bit mode. These are receive-assembly properties, not properties recoverable merely from a later register read.

The pinned H316 [short-to-long conversion](https://github.com/larsbrinkhoff/simh/blob/feb155fbc49333e879ab082d481e6dcce27d2d91/H316/h316_hi.c#L401-L449) is also relevant but cannot supply direct KA10 authority. It moves a regular short-header payload behind a generated long leader and the negotiated host padding before sending 16-bit transport words. Using that conversion plus the paired H316 trace answers what IMP 6 sent; it does not by itself prove how the KA10 device assembled and presented every word to ITS.

## Retained cross-check and ambiguity witness

The earlier retained trace is internally consistent with the known RFC when the H316 conversion's five padding words and the KA10 simulator's unlogged service timing are supplied from outside the `DATAI` records. Under that interpretation, the RFC is consumed as six 36-bit input words followed by three 32-bit input words. This is a useful cross-check, not a complete grammar proof.

The transition itself demonstrates the ambiguity. The trace shows ITS set `IMI32S` immediately before reading value `001000005400`. The ITS source establishes that this particular value was the already-assembled sixth 36-bit leader word and that only the following word was assembled in 32-bit mode. The `DATAI` line contains no width field, and its low four bits are zero, so the printed value is also syntactically compatible with a 32-bit assembly. Recovering the intended width requires predicting the unlogged service event from simulator timing and exact guest control flow. That would turn a trace extractor into a partial simulator/guest execution model and exceed the observation authority allowed for this path.

The last-word record has the same problem in another dimension. `IMPLW` proves that the interface considered the current buffer final, but the trace does not state how many bits in that buffer came from the message before zero filling. The 1822 leader length, H316 transport length, negotiated padding, and expected request fingerprint can select one reconstruction, but selecting the reconstruction that matches the already-observed IMP 6 egress would not independently prove host-106 ingress.

These are not defects in the accepted H316 observation or in the typed construction seam. They are missing information at the proposed KA10 evidence source.

## Stop condition and revisit requirement

This pass stops before a parser. It adds no code, fixtures, persisted records, schema fields, simulator configuration, or replay output. The accepted journey remains a ten-observation `missing-boundary` result, and application success remains separate evidence.

The minimum property required to revisit the KA10 parser is a directly retained receive-assembly record that binds one source-local input message and word index to `assembled_bits`, `valid_bits`, and last-word state before `DATAI` consumption. The accepted target transaction would also need such a record in its fixed evidence window. No existing pinned or current-upstream trace facility supplies it. Adding simulator instrumentation or rerunning the formal transaction with expanded evidence is a separate decision and was not authorized or performed here.
