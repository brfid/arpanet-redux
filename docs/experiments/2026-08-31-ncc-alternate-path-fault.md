# Alternate-path observation of a direct IMP line fault

## Question

Can the passive NCC receiver continue obtaining independently attributed reports from IMPs 5 and 6 while their directly mapped line changes from up to down, so the existing paired-line reducer can be exercised against a genuine complete-line fault rather than missing or stale evidence?

## Experimental boundary

The prior two-IMP composition could not answer this question because IMP 6's direct line to IMP 5 was also its only route to NCC host 0. The external-laboratory experiment therefore added one configured test peer, IMP 7, and two live alternate modem links to form an IMP 5 / IMP 6 / IMP 7 triangle. It retained the proven IMP 5 HI1 attachment to the passive receiver and the explicit IMP 5 line 1 / IMP 6 line 1 mapping on the direct edge. The alternate modem bindings deliberately carried no report-line identities.

A project-authored two-ended UDP relay occupied the direct cable's two remote endpoints. During the control it forwarded every datagram in both directions. During the fault run it remained bound but stopped forwarding after 45 seconds, so the direct cable could fail without stopping either IMP, the receiver, or either alternate link. The relay recorded its phase boundary and directional forwarded/dropped counters. It did not inspect or modify packet content.

All helper files, generated results, simulator logs, and the derivative three-IMP composition remain under `/Users/brf/src/arpanet-redux-lab`. No firmware, simulator source, accepted controller contract, formal PDP-11/two-ITS harness, or repository topology changed for this checkpoint.

## Exact identity

Both runs used a clean repository at `7a146bc9e88120dbe98a569a05bc3a52f439fa42`, clean ARPANET-in-a-Box source at `78123c77b20dadd9b5967b184dbcb4195185eea6`, and clean H316 SIMH source at `feb155fbc49333e879ab082d481e6dcce27d2d91`. The H316 executable SHA-256 was `bdbcdffc63ada17c9ec6c7151aba42fd96388ff33d41ec6d42c5b27f47cfb994`; the pinned firmware and base-configuration SHA-256 values remained `bc4870059b9131636a49dec53399b8f654ba5c146bd09c32d48ab65d5309c771` and `b3c4fe408c3ec2515f629eea327f4e2f33f692997d4c45e423853da6d1800d78`.

The external shared topology SHA-256 was `c70991ec79f245b04af42c26847821f69cb076253442e0e8801e4960ece3cd2a`. The IMP 5, IMP 6, and IMP 7 command-file SHA-256 values were `c4ff6a2a8548c8768c8704010e97995442e582e4563aa9110bbfad6b417ae25d`, `863914c01873990c2f440e7c6b6c97a20265a84dc8642cede56171c0c0bf92b7`, and `8b4b4c9617b50a97095567a2e7ab250a86cf16d23d77ed8c76c9d31edc47fda7`. The runner, analysis, and relay SHA-256 values were `7d80ef68e54800eca28b68bf692a5ac5894e3d55da2cc92a244d0995a084471b`, `48831140d53d50ada9fd959a257c82d0bff7dced4532c9fb7745490637699f8f`, and `0c2bb2f8d3e4c9b12dadfc80572e19b252ca1b8bc72023c8207c9a16f38c9e34`.

Each run leased ten distinct dual-stack UDP ports, retained exact child PIDs, verified sources, assets, and simulator identity before launch, and used the repository receiver and historical-event recorder without modification.

## Forwarding control

Exact run `ncc-alternate-control-20260831T224154Z` used this entry point:

```sh
BRFID_NCC_RECEIVER_DURATION=130 BRFID_DIRECT_FORWARD_SECONDS=45 /Users/brf/src/arpanet-redux-lab/work/ncc-alternate-path-fault/run.sh /Users/brf/src/arpanet-redux-worktrees/network /Users/brf/src/arpanet-redux-lab control ncc-alternate-control-20260831T224154Z
```

The relay remained in its forwarding phase for the complete observation. It forwarded 1,928 IMP 5-to-IMP 6 datagrams and 1,916 IMP 6-to-IMP 5 datagrams, dropped none, and received no unexpected source. The checksum-valid decoded stream contained 13 Type 303 trouble reports attributed by old-style leader to IMP 5, 12 attributed to IMP 6, and 12 attributed to IMP 7. The existing reducer classified the final fresh direct pair as `up`, supported by sequences 377 and 388. The run manifest records `outcome=passed`, `exit_status=0`, and `cleanup.completed=1`.

## Direct-line cut

Exact run `ncc-alternate-fault-20260831T224448Z` used the same inputs and entry point with mode `fault`:

```sh
BRFID_NCC_RECEIVER_DURATION=130 BRFID_DIRECT_FORWARD_SECONDS=45 /Users/brf/src/arpanet-redux-lab/work/ncc-alternate-path-fault/run.sh /Users/brf/src/arpanet-redux-worktrees/network /Users/brf/src/arpanet-redux-lab fault ncc-alternate-fault-20260831T224448Z
```

The relay cut the direct cable at `2026-08-31T22:45:48.592912Z`. Before that boundary it forwarded 541 datagrams from IMP 5 and 538 from IMP 6; afterward it remained bound while dropping 1,255 and 1,311 datagrams respectively. It saw no unexpected source.

The report stream established a fresh pre-cut `up` pair at sequences 80 and 101. After the cut, nine further trouble reports arrived from each of IMPs 5 and 6, as did continued reports from IMP 7. The first reciprocal direct-line `down` observations were sequence 146 from IMP 5 at `2026-08-31T22:46:00.474958Z` and sequence 157 from IMP 6 at `2026-08-31T22:46:00.487631Z`. Both IMPs then repeated the `down` observation throughout the remaining minute; their final direct observations were sequences 377 and 399. Because the relay was still bound but dropping every direct datagram, an IMP 6 report received after the cut could reach NCC only through the configured IMP 6-to-IMP 7-to-IMP 5 alternate route.

The receiver exited zero with an empty error log after validating each accepted report's actual old-style source leader, complete semantic body, and checksum. It recorded 13 IMP 5, 12 IMP 6, and 12 IMP 7 trouble reports in total. The relay also exited zero. The exact child PIDs were absent after the bounded cleanup; none of the ten ports remained open, and the cooperative port-lock root was absent.

## Reducer mismatch exposed by the exact run

The run-level verdict was intentionally failed even though the network experiment produced reciprocal `down` observations. Every decoded down event had `neighbor_imp=null`, while the current topology matcher requires every non-unknown endpoint state to repeat the configured neighbor. The reducer therefore classified sequences 377 and 399 as `contradictory` rather than passing its own two-down branch.

This is not missing evidence and should not be hidden by weakening the run gate. The direct source IMP, explicit report-line number, state, checksum, and separately established reciprocal mapping are all present. A read-only inspection of the preserved 1973 report construction corroborated the observed behavior: line teardown clears the remembered neighbor before the later trouble-report snapshot is constructed. No source text or copied third-party material is included here; the exact decoded run is the acceptance evidence.

The next checkpoint is therefore a narrow source-only reconciliation decision and test: an absent reported neighbor may be compatible with an explicitly mapped endpoint when the direct state is `down`, while a present wrong neighbor must remain contradictory. That change must not make configured topology substitute for the direct state, permit a one-sided line conclusion, change decoder output, or alter a persisted contract. The retained sidecar can then be re-read without modifying it to prove whether the genuine final pair reduces to `down`.

## Read-only reconciliation after ADR-010

[ADR-010](../adr/0010-ncc-down-report-neighbor-absence.md) accepts only the exact missing-neighbor/down case exposed above. With that source-only rule applied, the unchanged external analysis helper re-read the original topology, relay record, receiver result, and historical-event sidecar from `ncc-alternate-fault-20260831T224448Z`, writing its new derived output outside the immutable result directory. All six analysis checks passed. The same pre-cut support sequences 80 and 101 reduce to `up`, and the same final support sequences 377 and 399 reduce to `down`.

This is a new interpretation under a tested rule, not a relabelled run. The exact run's manifest and original `verdict.json` remain failed, and no byte in its result directory changed. Focused tests additionally prove that a supplied wrong neighbor remains contradictory and that an up report with an absent neighbor is contradictory.

## Limits

The experiment establishes one project-authored fault composition and one observed failover path. It does not identify IMP 7 or either endpoint as a historical site, establish a universal simulator-device-to-report-line relationship, prove loopback behavior, infer that a missing report means down, or authorize durable reducer output. The first fault-run manifest remains `outcome=failed` because its exact accepted analysis rejected the reducer mismatch; it must not be relabelled after the fact.
