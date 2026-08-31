# Genuine two-ended NCC line loopback

## Question

Can the alternate-path NCC composition elicit repeated, checksum-valid firmware `looped` observations from both explicitly mapped endpoints of the IMP 5 / IMP 6 direct line without synthesizing a report payload, and does the current paired-line reducer interpret that genuine report shape correctly?

## Primary mechanism evidence

The pinned H316 simulator at `feb155fbc49333e879ab082d481e6dcce27d2d91` exposes both interface and attached-line loopback controls in [`H316/h316_mi.c`](https://github.com/larsbrinkhoff/simh/blob/feb155fbc49333e879ab082d481e6dcce27d2d91/H316/h316_mi.c), and its bundled [`imploop.cmd`](https://github.com/larsbrinkhoff/simh/blob/feb155fbc49333e879ab082d481e6dcce27d2d91/H316/tests/imploop.cmd), [`imploopl.cmd`](https://github.com/larsbrinkhoff/simh/blob/feb155fbc49333e879ab082d481e6dcce27d2d91/H316/tests/imploopl.cmd), and [`imploop4l.cmd`](https://github.com/larsbrinkhoff/simh/blob/feb155fbc49333e879ab082d481e6dcce27d2d91/H316/tests/imploop4l.cmd) compositions exercise those paths. A read-only inspection of the preserved 1973 firmware listing at the same pinned revision established the report semantics used for this experiment: an incoming routing message records its source as the line neighbor; when that source is the local IMP number, the firmware recognizes the line as looped and later encodes the loop indication in its Type 303 trouble report. The expected genuine endpoint shape is therefore `state="looped"` with `neighbor_imp` equal to the reporting IMP itself, not the configured peer at the far end of the nominal cable.

This document paraphrases behavior needed to interpret the run and links to the exact upstream simulator inputs. It includes no simulator source, recovered firmware text, or other third-party material. The redistribution boundary in [`NOTICE.md`](../../NOTICE.md) remains unchanged.

## Experimental boundary

The experiment reused the committed three-IMP topology and command files from the accepted alternate-path fault gate at repository revision `7f418ea67dc452f50ee1bee7985c7c1ff951f187`. IMPs 5 and 6 retained their explicit reciprocal line-1 mapping, IMP 7 retained the two unmapped alternate modem links, and the passive receiver remained attached to IMP 5 as host 0. This preserved a route for IMP 6's reports after its direct traffic stopped reaching IMP 5.

A project-authored external-laboratory relay occupied the direct cable's two remote UDP endpoints. During the control it forwarded every datagram to the opposite IMP. During the loop run it forwarded for 45 seconds and then returned each endpoint's outgoing datagram, byte for byte, to that same endpoint through the same relay socket. It recorded the exact phase boundary and directional counters, rejected unexpected sources, and neither inspected nor modified packet content. The reflection therefore supplied line-level loopback input while leaving all report construction, leader attribution, body contents, and checksums to the recovered firmware and existing receiver.

All helper files, generated results, simulator logs, firmware, and simulator inputs remain under `/Users/brf/src/arpanet-redux-lab`. No repository decoder, event schema, topology, command file, accepted harness, or reducer changed before either run.

## Exact identity

Both runs used clean repository revision `7f418ea67dc452f50ee1bee7985c7c1ff951f187`, clean ARPANET-in-a-Box source `78123c77b20dadd9b5967b184dbcb4195185eea6`, and clean H316 SIMH source `feb155fbc49333e879ab082d481e6dcce27d2d91`. The H316 executable SHA-256 was `bdbcdffc63ada17c9ec6c7151aba42fd96388ff33d41ec6d42c5b27f47cfb994`; the firmware and base-configuration SHA-256 values were `bc4870059b9131636a49dec53399b8f654ba5c146bd09c32d48ab65d5309c771` and `b3c4fe408c3ec2515f629eea327f4e2f33f692997d4c45e423853da6d1800d78`.

The committed shared-topology SHA-256 was `0132a4350cea8b93624b18573bacc56302d922b1f896dda4c2e83403c670f806`. The committed IMP 5, IMP 6, and IMP 7 command-file SHA-256 values were `eb57f423646f1d7a98b42d46f015348cb7c1fa10528ead40a9621b6b91c00855`, `923d9a6dceb36f4adb31c72120582f676639927510237ecb57a6c2dc6a319c44`, and `726e96786b81dd46a7ae6c253af4439ee7acfc01c3c05393bc9cc6b1bb400f51`. The external runner, analyzer, and reflector SHA-256 values were `f4c1dbde2b680908f7d77235708cffd91161757d03cb4afe344d3800374841cb`, `a2921781962154edf06cc1ff050b07316e8254dddd1a2a0df2cd92e5db63e05e`, and `a666b5180b6bce57a4ff1c3b80a9eb28978e66a38679a5a338d70713701af61e`.

Each run verified sources, assets, and simulator identity before launch; leased ten distinct dual-stack UDP ports; retained exact child PIDs; and used the committed passive receiver and historical-event recorder without modification.

## Forwarding control

Exact run `ncc-line-loopback-control-20260831T232537Z` used this external-laboratory entry point:

```sh
/Users/brf/src/arpanet-redux-lab/work/ncc-line-loopback/run.sh /Users/brf/src/arpanet-redux-worktrees/network /Users/brf/src/arpanet-redux-lab control ncc-line-loopback-control-20260831T232537Z
```

For the full 130-second receiver window, the relay forwarded 1,930 IMP 5-to-IMP 6 datagrams and 1,917 IMP 6-to-IMP 5 datagrams, reflected none, and received no unexpected source. The checksum-valid receiver stream contained 75 complete messages and 404 direct events: 13, 12, and 12 trouble reports from IMPs 5, 6, and 7, plus 12, 11, and 11 throughput reports. The final fresh direct pair remained `up`, supported by sequences 377 and 388. Every structured check passed, and the manifest records `outcome=passed`, `exit_status=0`, and `cleanup.completed=1`.

## Two-ended reflection

Exact run `ncc-line-loopback-experiment-20260831T232858Z` used the same inputs with mode `loop`:

```sh
/Users/brf/src/arpanet-redux-lab/work/ncc-line-loopback/run.sh /Users/brf/src/arpanet-redux-worktrees/network /Users/brf/src/arpanet-redux-lab loop ncc-line-loopback-experiment-20260831T232858Z
```

The relay changed from forwarding to self-reflection at `2026-08-31T23:29:50.658217Z`. Before that boundary it forwarded 540 datagrams from IMP 5 and 537 from IMP 6. Afterward it reflected 1,260 and 1,262 datagrams respectively and received no unexpected source. The last fresh pre-loop pair was `up`: IMP 6 sequence 80 named IMP 5, and IMP 5 sequence 90 named IMP 6.

The transition was observable rather than instantaneous. The first post-boundary snapshots reported `down` with no neighbor, followed by `down` snapshots that had learned the local IMP as neighbor. The first explicit loop indications then arrived at `2026-08-31T23:30:13.058546Z` from IMP 6 as sequence 199 with `neighbor_imp=6`, and at `2026-08-31T23:30:13.064211Z` from IMP 5 as sequence 209 with `neighbor_imp=5`. Each IMP produced that exact looped-to-self shape seven times. Their final direct observations were IMP 5 sequence 397 and IMP 6 sequence 419.

Ten post-loop trouble reports from each of IMPs 5 and 6 reached the receiver, in addition to continued IMP 7 reports. Because the relay was returning every direct datagram to its source, the later IMP 6 reports could reach NCC only through the configured IMP 6-to-IMP 7-to-IMP 5 alternate route. The complete receiver result contained 77 messages and 424 direct events: 14, 13, and 12 trouble reports from IMPs 5, 6, and 7, plus 12, 11, and 11 throughput reports. The receiver and relay both exited zero.

The exact child PIDs were absent after bounded cleanup, none of the ten leased ports remained open, and the cooperative port-lock root was empty for both the control and loop runs.

## Reducer mismatch exposed by the exact run

The loop run's structured verdict intentionally failed one check. Its raw endpoint check passed, but the existing reducer classified final sequences 397 and 419 as `contradictory` rather than `looped`. The reducer currently requires every non-unknown endpoint observation to name the configured remote peer; the genuine firmware loop signature instead names the reporting IMP itself.

This is not missing evidence, a simulated report, or a reason to relax peer validation generally. Each event has an independently attributed source IMP, explicit mapped report-line number, checksum-valid Type 303 body, direct loop state, self-neighbor value, and reciprocal observation from the other configured endpoint. A present third-party neighbor must remain contradictory, as must a self-neighbor on a state for which the firmware evidence does not establish that meaning.

The next checkpoint is a narrow source-only reconciliation decision and focused tests: for an explicitly mapped endpoint, `looped` may match only when its reported neighbor equals its own source IMP. The configured topology should continue to identify the reciprocal pair but must not substitute the remote peer into the observation. The immutable failed result can then be re-read under the accepted rule without modifying its manifest or original verdict. Decoder output, the historical-event schema, and persisted contracts remain out of scope.

## Limits

The experiment proves one bounded project composition, one two-ended reflection method, repeated reciprocal firmware loop indications, and continued alternate-path report delivery. It does not establish that the transient down-to-self form has independent durable meaning, identify IMP 7 or any endpoint as a historical site, infer loopback from silence or topology alone, establish a universal simulator-device-to-report-line mapping, or authorize persisted reducer output. The exploratory loop manifest remains `outcome=failed` because its exact contemporary analyzer correctly exposed the unresolved reducer mismatch; it must not be relabelled after the fact.
