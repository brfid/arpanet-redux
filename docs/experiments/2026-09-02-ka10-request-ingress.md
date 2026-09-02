# Bounded KA10 request-ingress instrumentation

- **Observed:** 2026-09-02
- **Repository checkpoint:** `5c10bf6487569735556546081bd2f9e3aa735c33`
- **KA10 simulator checkpoint:** `4b59f21d00355a7a917fa7cd54ef8a1123b515b2`
- **Accepted result:** `/Users/brf/src/arpanet-redux-lab/experiments/ka10-host-ingress/results/pdp11-its-telnet-pdp11-its-telnet-ka10-host-ingress-final-20260902T204843Z`
- **Scope:** One observation-only simulator boundary, one exact direct Gate 4H transaction, and one conditional typed observation at `boundary:request:6`; no guest, protocol, application-gate, reply-ingress, failover, coexistence, browser, or schema claim

## Decision

The bounded experiment passes. Versioned KA10 receive-assembly records independently reconstruct the exact request that IMP 6 presented to ITS host 106 and prove that ITS consumed every reconstructed word through `DATAI`. The strict adapter therefore adds one direct `ka10-imp-trace` observation at `boundary:request:6`.

The accepted direct journey now contains eleven observations and remains deliberately incomplete. Its first missing boundary advances to `boundary:reply:6`, host-176 ingress on the reply leg. The application verdict still comes from the existing TELNET, TELSER, remote `:TIME`, correlated IMP, identity, and cleanup evidence; the new packet observation neither supplies nor replaces that verdict.

## Bounded question and stop rule

The preceding [feasibility pass](2026-09-01-ka10-host-ingress-grammar.md) rejected a parser because the old `DATAI` trace did not say which receive message produced a value, whether it was assembled as 32 or 36 bits, how many final bits were valid, or whether an observed assembly was the value the guest consumed. It permitted a revisit only after one fresh target run directly retained all of those properties.

This experiment therefore instrumented only the KA10 NCP-mode IMP input boundary. The parser and typed observation were contingent on a fresh trace independently reconstructing exactly one request equal to the accepted IMP 6 destination-HI transfer. A missing, ambiguous, incomplete, malformed, or mismatched trace would have ended the work without weakening the ten-observation acceptance check.

## Instrumentation

KA10 fork commit `4b59f21d00355a7a917fa7cd54ef8a1123b515b2` adds one opt-in `ASSEMBLY` debug category in `PDP10/kx10_imp.c`. It emits three version-1 record forms:

```text
IMP INPUT-MESSAGE version=1 message=<sequence> bits=<message-bits>
IMP INPUT-ASSEMBLY version=1 message=<sequence> word=<index> message_bits=<message-bits> start=<bit-offset> width=<32-or-36> valid=<valid-bits> last=<0-or-1> value=<12-octal-digits>
IMP INPUT-CONSUME version=1 message=<sequence> word=<index> width=<32-or-36> valid=<valid-bits> last=<0-or-1> value=<12-octal-digits> PC=<octal-program-counter>
```

The first record is emitted only after a complete NCP transport message has arrived. The assembly record is emitted when the device constructs the guest-visible input buffer. The consumption record is emitted by `DATAI` with the value returned to ITS. Trace metadata is written alongside existing state and never changes a status bit, interrupt, buffer, schedule, payload, or transport decision.

The run-local KA10 configuration enables only this category and directs debug output through the already retained console PTY. This is necessary for a fixed live byte window: an exploratory pass directed debug to a dedicated regular file, whose buffered start and end offsets were equal when the controller closed the transaction even though the data flushed during cleanup. That run was rejected as boundary evidence. A subsequent live capture established that the proposed record was sufficient, but retained the old ten-observation sidecar and was not promoted. Only the final parser-enabled run below is the accepted result.

## Parser and correlation rule

The source-only parser accepts bytes rather than decoded free-form text and recognizes only complete version-1 records. It requires contiguous message and word identities, monotonic source ticks, exact message sizes and bit offsets, valid 32- or 36-bit alignment, exact final-word semantics, and a one-to-one assembly/consumption match. It rejects an unknown version, malformed relevant line, interrupted message, changed value, or uncovered message bit.

Reconstruction takes only the high `valid` bits from each left-aligned value proven consumed. The normalization step then accepts only the canonical 96-bit long leader produced by the pinned H316 conversion, including supported flags, address and type ranges, declared data size, and zero negotiated padding. It reverses that conversion to a complete NOSC short message. Exactly one normalized message in the fixed KA10 window must equal the complete destination-HI request in the independently parsed IMP 6 window. The adapter does not align KA10 and H316 simulator ticks.

Synthetic tests cover the accepted reconstruction, a message ending exactly on an assembly-word boundary, changed `DATAI` content, unknown versions, incomplete messages, nonzero long-leader padding, duplicate exact candidates, and a complete three-source stream round trip. The retained-result command is separately tested with and without a KA10 source so old ten-observation results remain compatible.

After the implementation and documentation were complete, `make test` passed all 282 source tests with one expected local-UDP skip in the restricted environment. The runtime shell suite passed with its expected restricted-environment Unix-domain-socket skip.

## Exact run identity

The accepted run started at `2026-09-02T20:49:04Z` and finished passed at `20:50:50Z`. Its manifest records clean project revision `5c10bf6487569735556546081bd2f9e3aa735c33`; clean ARPANET-in-a-Box, Network UNIX, H316 SIMH, KA10 SIMH, and IMP11-A SIMH revisions `78123c77b20dadd9b5967b184dbcb4195185eea6`, `464893a99da8e3ac7f90577bc54749fa64bb0966`, `feb155fbc49333e879ab082d481e6dcce27d2d91`, `4b59f21d00355a7a917fa7cd54ef8a1123b515b2`, and `2722eef44f68642eaab9f5d4e989ccd26e55e7de`; and zero tracked dirt for every source.

The H316, KA10, and PDP-11 executable SHA-256 values are `bdbcdffc63ada17c9ec6c7151aba42fd96388ff33d41ec6d42c5b27f47cfb994`, `eb1eefaf6c4b27040234665059e9683d9d3c9c2931ed999b39b3ee7bb41fb105`, and `d1d6046647025cc822d90d3ebb2d633d24f9513e03bf2c7eca6dcef75bfe5ae3`. Each binary embedded its pinned source revision. The retained PDP-11 build receipt SHA-256 is `3923f3f58ac445f57f47793d3ce2697735957bedd247542c5fd9fd81b05296b9`; the shared topology SHA-256 remains `aca72d0e14fa70eb7e0af9f86c30612e0de692a766dc7e3500ca768fd2331ad0`. Six private UDP ports were leased for the exact composition.

The exact command was:

```sh
make smoke-pdp11-its LAB_ROOT=/Users/brf/src/arpanet-redux-lab/experiments/ka10-host-ingress PDP11_BUILD_ROOT=/Users/brf/src/arpanet-redux-lab/results/pdp11-telnet-option-fix-build-20260902T002513Z RUN_ID=pdp11-its-telnet-ka10-host-ingress-final-20260902T204843Z
```

## Exact reconstruction

The fixed KA10 transaction window is bytes `8272` through `56480` of `host106.console.log`, SHA-256 `c32cfc11dec1ad50df1fb146f5a4e8a140fc0f7c36400ee32b2c7ef6c6d9d091`. Its 405 relevant records parse as 29 complete contiguous input messages, sequences 7 through 35. Exactly one canonical normalized message equals the IMP 6 request: sequence 7, received at KA10 tick `11544070025` and completely consumed at tick `11545912203`.

Message 7 contains 304 bits. ITS consumed six 36-bit words followed by three 32-bit words; the final word has 24 valid bits. The reconstructed bytes are `0f0000000701003e00000080000000000000000000000008000a000100000400000000170200`: a canonical 96-bit long leader, five zero padding words, and the request data. Reversing the pinned H316 conversion yields these complete 16-bit NOSC words:

```text
000176 000000 000010 000012 000001 000000 002000 000000 000027 001000
```

That sequence equals the independently parsed IMP 6 destination-HI transfer byte for byte and retains request fingerprint `f1d4dba566165c587ee584588aa3ea5091db970185b87bb98f0b7e462bfd4ee4`. Every one of its nine assembly records has an exact matching consumption record. The resulting observation carries source-local sequence 7, the final consumption tick, canonical leader identity `ka10-long-1822-ncp`, source revision `4b59f21d00355a7a917fa7cd54ef8a1123b515b2`, and a direct evidence locator naming the message and receive/consume ticks.

The two unchanged H316 transaction windows are IMP 6 bytes `1169342` through `1426161`, SHA-256 `943da6e827a70db394d690d897b4fe1838df0b3d6f140875d3194ce7faa5cf15`, and IMP 62 bytes `1807536` through `2067245`, SHA-256 `9c34e8b01e1739c4a2d9f697b028509632976e4c5a40e7386bce99f6ded6da32`.

## Result and replay

The existing Gate 4H application evidence passed unchanged: Network UNIX printed `Connection open`, ITS recorded service job `53TLNT` from `HST176`, the client received the structured greeting and remote `:TIME`, and both IMP traces contained exactly correlated post-probe traffic in both directions. No legacy option diagnostic appeared.

The new sidecar has eleven observations. Request boundaries 1 through 6 and reply boundaries 1 through 5 are observed; `boundary:reply:6` is missing. Its SHA-256 is `616e5376195588d3765cb3ca471a320d8232d3f9f8390a21862516c6b33e3205`. The read-only retained-result adapter consumed only the three manifest-declared byte ranges, reproduced eleven observations and the same terminal diagnosis, and generated a byte-for-byte identical sidecar with the same digest.

Both cleanup layers passed, the controller recorded `surviving_owned_processes=0`, the final outcome was `passed`, and the manifest exit status was zero. Raw logs, simulator media, generated disks, executables, and the replay sidecar remain outside the repository.

## Limits

This result proves only that ITS host 106 consumed the exact direct-route request already observed at IMP 6 egress. It does not prove how ITS constructs its reply, host-176 reply ingress, host-176 request egress, the corresponding alternate-route boundary, a complete KA10 or IMP11-A grammar, a global clock, historical report-line identity, browser control, or a new application verdict. Coexistence, failover, interactive, and historical-terminal results remain immutable under their own accepted evidence windows and contracts.
