# Passive NCC historical-event record at IMP 5

## Question

Can the passive NCC report-ingress proof write a replayable, validated record of direct historical observations without adding raw frames, simulator control, topology inference, or an incompatible change to the accepted completed-run/live-stream contracts?

## Controlled run

The 25-second IMP 5 / IMP 6 shared-topology run used the same project-authored passive receiver as the report-ingress experiment. In addition to its derived proof result, it was given an explicit run identity and a new external JSON Lines path for `ncc.historical_events`. It sent only the required flag-only host-ready transport packets and wrote no packet words or simulator log into the record.

| Direct derived observation | Result |
|---|---:|
| Successful host-ready packets sent | 25 |
| IMP-ready packets received | 10 |
| Complete IMP-to-host messages reassembled | 9 |
| Decoded patched Type 303 trouble reports | 3 |
| Direct events recorded | 30 |
| Complete record lines | 31 (one header plus 30 events) |
| Reporting IMP in every event | 5 |
| Event forms | IMP report, host-interface state, line-endpoint state |

The record header preserved the supplied run identity, the shared topology and host-interface binding identities, a project-authored nominal topology snapshot, and project-authored receiver provenance. The complete event prefix read back successfully under the sidecar validator and replayed direct subject state in sequence.

## Result and limits

This proves that a genuine passive report run can yield a bounded, replayable direct-event record while keeping the version-1 completed-run and controller live-stream contracts unchanged. [ADR-007](../adr/0007-ncc-historical-event-stream.md) defines the sidecar boundary and its validation rules.

The record does not contain an application verdict, simulator process state, raw historical traffic, checksum validation, a Type 302 decoder, paired-line inference, timeouts, or a historical route assertion for the IMP 6 proof peer. A future bridge to a completed-run summary or controller live stream requires a separate compatibility decision.
