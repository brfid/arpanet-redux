# Passive NCC throughput-report ingress at IMP 5

## Question

Can the passive NCC receiver distinguish a genuine 1973 Type 302 throughput body from the preceding old-style IMP-to-host leader, decode it without interpreting cumulative counters as rates, and retain it in the validated historical-event record?

## Historical interpretation

The preserved [1973 IMP listing](https://walden-family.com/impcode/c-listing-ps.txt) constructs Type `0302` after the Type 301/303 trouble-report path. Its report loop emits one packet and one word throughput counter for each of five modem lines, then ten traffic-counter families for each of four real host interfaces, before checksum and padding. This establishes a 52-word semantic body and an optional 53rd pad word. Together with the two-word old-style leader documented in [BBN Report 1822](https://walden-family.com/impcode/BBN1822_Jan1976.pdf), that predicts a 55-word padded host-interface message.

The Type 302 field names in `ncc.throughput_report` retain the original directions as cumulative host-to-network, network-to-host, host-to-local-host, local-host-to-host, host-to-IMP, and IMP-to-host counters. The selected evidence does not establish reporting intervals or counter-reset semantics, so the implementation does not derive rates.

No listing text, firmware, packet words, or raw simulator log is committed. The cited sources support the project-authored format interpretation only.

## Controlled run

The bounded 25-second IMP 5 / IMP 6 shared-topology run used the same passive receiver and explicit external event-record path as the prior report-ingress proof. It required at least one decoded trouble report and one decoded throughput report while sending only flag-only host-ready transport packets.

| Direct derived observation | Result |
|---|---:|
| Successful host-ready packets sent | 25 |
| IMP-ready packets received | 10 |
| Complete IMP-to-host messages reassembled | 9 |
| Complete message sizes | 2, 34, and 55 words |
| Patched Type 303 trouble reports decoded | 3 |
| Type 302 throughput reports decoded | 2 |
| Reporting IMP for every decoded report | 5 |
| Line-counter pairs per Type 302 report | 5 |
| Host counter groups per Type 302 report | 4 |
| Direct historical events recorded | 32 |
| Complete event-record lines | 33 (one version-2 header plus 32 events) |

## Result and limits

The complete 55-word frames match the primary-derived Type 302 layout and now produce two direct throughput observations in the same version-2 sidecar as the Type 303 trouble reports. [ADR-008](../adr/0008-ncc-throughput-event-stream-v2.md) records the explicit event-stream compatibility decision.

This does not validate either report checksum, identify a reporting interval, establish counter reset behavior, infer a throughput rate or network condition, decode later Type 304/305 formats, adapt the event stream to the completed-run/controller-live contracts, or establish a historical route for the IMP 6 proof peer.
