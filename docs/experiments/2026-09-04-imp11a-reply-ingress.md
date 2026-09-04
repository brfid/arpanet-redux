# Bounded IMP11-A reply-ingress instrumentation

- **Observed:** 2026-09-04
- **Repository checkpoint:** `68a526da80ef746c391e206f307bbd48be30b0ff`
- **IMP11-A simulator checkpoint:** `c74e7040e186a6ea11d9cd816b94edc235959e27`
- **Accepted build:** `/Users/brf/src/arpanet-redux-lab/results/pdp11-telnet-build-reply-ingress-accepted-build-20260904`
- **Accepted result:** `/Users/brf/src/arpanet-redux-lab/results/pdp11-its-telnet-pdp11-its-reply-ingress-final-20260904T151055Z`
- **Scope:** One observation-only simulator boundary, one exact direct Gate 4H transaction, and one conditional typed observation at `boundary:reply:6`; no guest interpretation, request-egress, KA10 reply-construction, alternate-route, coexistence, failover, browser, schema, or new application claim

## Decision

The bounded experiment passes. Versioned IMP11-A post-store DMA records independently reconstruct the exact reply that IMP 62 presented to Network UNIX host 176. The strict adapter therefore adds one direct `pdp11-imp11a-trace` observation at `boundary:reply:6`.

The accepted direct journey now contains twelve observations and is `complete`; all six request and all six reply boundaries are observed. The application verdict still comes from the existing TELNET, TELSER, remote `:TIME`, correlated IMP, identity, and cleanup evidence. The new packet observation neither supplies nor replaces that verdict.

## Bounded question and stop rule

The accepted [KA10 request-ingress result](2026-09-02-ka10-request-ingress.md) stopped at `boundary:reply:6` because IMP 62 egress and application success did not reveal the exact message stored through the IMP11-A interface. The existing IMP11-A packet diagnostic printed only the first word of each DMA operation, so a complete reply could not be reconstructed from it.

This experiment therefore instrumented only the IMP11-A input DMA boundary. The parser and typed observation were contingent on a fresh trace containing exactly one complete reconstructed message equal to the independently accepted IMP 62 destination-HI reply. A missing, duplicate, incomplete, malformed, non-16-bit, incorrectly converted, or mismatched candidate would have ended the work without weakening the eleven-observation acceptance check.

## Instrumentation

IMP11-A fork commit `c74e7040e186a6ea11d9cd816b94edc235959e27` adds one opt-in `INPUT` category in `PDP11/pdp11_imp.c`. It emits three version-1 record forms:

```text
IMP INPUT-MESSAGE version=1 message=<sequence>
IMP INPUT-DMA version=1 message=<sequence> word=<index> address=<six-octal-digits> wire=<six-octal-digits> guest=<six-octal-digits>
IMP INPUT-COMPLETE version=1 message=<sequence> words=<count>
```

The DMA record is emitted after `Map_WriteW`, using the network-order source word and the value actually passed to PDP-11 memory. Message identity and word identity continue across guest buffer boundaries. Completion is recorded only when the retained message reaches the real final marker. Trace counters and output never change a register, status bit, interrupt, buffer pointer, schedule, payload, conversion, completion, or transport decision.

The run-local PDP-11 configuration enables only `INPUT` and routes debug through the already retained console PTY. The controller fixes the console slice at the same application boundary used for the formal TELNET transaction and records both byte offsets before invoking the adapter.

## Parser and correlation rule

The source-only parser accepts bytes rather than decoded free-form text and recognizes only complete version-1 groups. It requires positive contiguous message identities, contiguous word indices, monotonic source ticks, even 18-bit DMA addresses, 16-bit words, an exact network-to-PDP-11 byte swap for every stored value, a positive exact completion count, and no unfinished message. It rejects any malformed relevant line or unsupported version.

Exactly one reconstructed wire-word sequence in the fixed IMP11-A window must equal the complete destination-HI reply independently parsed from IMP 62. Literal equality covers the short leader and all content; the known fingerprint is derived only afterward. The adapter does not align IMP11-A and H316 simulator ticks.

Synthetic tests cover complete reconstruction across two guest buffers, multiple contiguous messages, a changed guest value, a noncontiguous word, a non-16-bit value, an invalid DMA address, a backward tick, an unknown version, an incomplete message, an incorrect completion count, a message-sequence gap, duplicate exact candidates, a changed reply, and a complete four-source stream round trip. The retained-result command remains compatible with earlier results that do not declare the host-176 source window.

The external simulator built with warnings as errors and passed the focused real-CPU byte-order, retained-surplus, residual-`IWC`, and `ENDMSG` regression. After implementation, `make test` passed all 330 source tests with one expected restricted-environment UDP skip; the runtime shell suite passed with its expected restricted-environment Unix-domain-socket skip.

## Receipt lifecycle finding

Two fresh development builds, `pdp11-telnet-build-reply-ingress-build-20260904` and `pdp11-telnet-build-reply-ingress-build-retry-20260904`, produced the expected guest artifacts but correctly failed receipt validation because the TELNET build log lacked `Goodbye`. Both builders sent `quit` after a fixed delay rather than waiting for the SIMH `sim>` prompt, so the command could be consumed before monitor control returned. The receipt was not weakened.

The repair waits in order for `sim>`, sends `quit`, then requires `Goodbye` and EOF. A source test proves `quit` cannot be sent before the prompt. The receipt now binds the shared shutdown helper as well as both builders and the V6 filesystem helper, so this lifecycle rule cannot change without invalidating old media. Accepted receipt SHA-256 `b4fa7dd1519b4b658ddf2132a883a3ba57ec4e090f91462c13bc547d310f24dd` binds clean Network UNIX and IMP11-A source identities, the rebuilt simulator, the four project builder files, both successful build logs, base and intermediate media, and final root and swap images.

On macOS, the pinned IMP11-A tree also reproduced the legacy dependency-probe gap already known for the KA10 tree: `make pdp11` left `zlibVersion` undefined, while the explicit system-library link `make pdp11 LDFLAGS_O=-lz` passed. Laboratory setup now supplies that argument only for the two affected simulator targets on Darwin.

## Exact run identity

The accepted run started at `2026-09-04T15:11:18Z` and finished passed at `15:12:54Z`. Its manifest records clean project revision `68a526da80ef746c391e206f307bbd48be30b0ff`; clean ARPANET-in-a-Box, Network UNIX, H316 SIMH, KA10 SIMH, and IMP11-A SIMH revisions `78123c77b20dadd9b5967b184dbcb4195185eea6`, `464893a99da8e3ac7f90577bc54749fa64bb0966`, `feb155fbc49333e879ab082d481e6dcce27d2d91`, `4b59f21d00355a7a917fa7cd54ef8a1123b515b2`, and `c74e7040e186a6ea11d9cd816b94edc235959e27`; and zero tracked dirt for every source.

The H316, KA10, and PDP-11 executable SHA-256 values are `bdbcdffc63ada17c9ec6c7151aba42fd96388ff33d41ec6d42c5b27f47cfb994`, `fbbaa7517ff84333bc6be7b148a1a3e4c43adcd08909b7270c68b157a8e97c98`, and `56e2e790a1bfc4cecc20ea2ffc2285fbccb772343d7d6cc551c2f259dbb92127`. Each binary embedded its pinned source revision. The shared topology SHA-256 remains `aca72d0e14fa70eb7e0af9f86c30612e0de692a766dc7e3500ca768fd2331ad0`; six private UDP ports were leased for the exact composition.

The exact command was:

```sh
make smoke-pdp11-its RUN_ID=pdp11-its-reply-ingress-final-20260904T151055Z PDP11_BUILD_ROOT=/Users/brf/src/arpanet-redux-lab/results/pdp11-telnet-build-reply-ingress-accepted-build-20260904
```

## Exact reconstruction

The fixed IMP11-A transaction window is bytes `100233` through `155851` of `pdp11.console.log`, SHA-256 `97dca685ef8d70cd9325db72e93121aca1e8bf905ec014113085f471a6fd45c8`. Its relevant records parse as 30 complete contiguous messages, sequences 264 through 293. Exactly one message equals the IMP 62 reply: sequence 265, started at IMP11-A tick `6397807256`, completed at tick `6397808100`, and stored 13 words.

The exact network-order words are:

```text
000106 000000 000010 000015 000000 000000 001000 000000 013400 000004 000040 000000 000000
```

The first four words were stored at PDP-11 DMA addresses `123050` through `123056`; the retained continuation was stored at `123564` through `123604`. Every record carries the exact byte-swapped guest value. The complete sequence equals the independently parsed IMP 62 destination-HI transfer and retains reply fingerprint `1963f53ace2b852791ed3c29ce773c676a19ed3566ea2ff7b26267589044f715`.

The other fixed windows are IMP 6 bytes `1160267` through `1436496`, SHA-256 `ff72a448548ff5782fe2b14861dab032e6f33adb230b705dacc3e22e91262d6d`; IMP 62 bytes `1797791` through `2078073`, SHA-256 `63f50a2ea55320ccb717b2b79904821e7ea140440b569742fd0fbcb4ca9af9e2`; and KA10 host-106 bytes `8186` through `59007`, SHA-256 `08b9d16f792c8b76ecba0aa9630d40c34e63b5d424411320cc00337c7877c063`.

## Result and replay

The existing Gate 4H application evidence passed unchanged: Network UNIX printed `Connection open`, ITS recorded service job `53TLNT` from `HST176`, the client received the structured greeting and remote `:TIME`, both IMP traces contained exactly correlated post-probe traffic in both directions, and no legacy option diagnostic appeared.

The sidecar has twelve observations. Every expected request and reply boundary is observed, the diagnosis is `complete`, and `first_boundary_id` is null. Its SHA-256 is `44a25e600a5b2289b0a1b758d48d46976d1bb1b821cad04372d4b52f3bdb0692`. The read-only retained-result adapter consumed only the four manifest-declared byte ranges and reproduced a byte-for-byte identical sidecar with the same digest.

Both cleanup layers passed, the controller recorded `surviving_owned_processes=0`, the final outcome was `passed`, and the manifest exit status was zero. Raw logs, simulator media, generated disks, executables, and the replay sidecar remain outside the repository.

## Limits

This result proves only that the exact direct-route reply observed at IMP 62 egress was written through the simulated IMP11-A interface into host-176 PDP-11 memory. It does not prove which Network UNIX daemon instruction consumed it, how the daemon interpreted it, host-176 request egress, KA10 reply construction, the corresponding alternate-route boundary, a complete IMP11-A or KA10 grammar, a global clock, historical report-line identity, browser control, or a new application verdict. Earlier direct, coexistence, failover, interactive, and historical-terminal results remain immutable under their own accepted evidence windows and contracts.
