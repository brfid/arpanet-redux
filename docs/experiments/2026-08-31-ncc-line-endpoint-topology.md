# Passive NCC line-endpoint evidence at IMP 5

## Question

Does the configured IMP 5 / IMP 6 proof path have a directly observed 1973 trouble-report endpoint identity that could later be paired by the topology-aware reducer, without treating the local proof peer as a historical route or inventing evidence from its unreported end?

## Historical interpretation

The preserved [1973 IMP listing](https://walden-family.com/impcode/c-listing-ps.txt) defines five ordered modem-line entries in each trouble report. The passive decoder retains each entry as a source-attributed `line-endpoint.state` event rather than inferring a complete line from one IMP's report. [ADR-006](../adr/0006-ncc-line-reconciliation.md) requires independently observed, matching endpoints before it can classify a complete line.

The shared proof composition connects one modem interface from IMP 5 to an otherwise hostless IMP 6 peer. It is a bounded local test path, not a reconstruction of a historical route or site attachment.

## Controlled run

The bounded 25-second passive run required a complete message, a checksum-validated patched Type `0303` trouble report, and a checksum-validated Type `0302` throughput report. It sent only host-ready transport packets. The generated event record was examined only as validated direct event data; no packet words or simulator output were committed.

| Direct derived observation | Result |
|---|---:|
| Checksum-validated Type 303 trouble reports | 3 |
| Checksum-validated Type 302 throughput reports | 2 |
| Repeated IMP 5 line 1 endpoint state | up, neighbor IMP 6 |
| Repeated IMP 5 lines 2–5 endpoint state | down, no neighbor |
| Independently attributed IMP 6 endpoint reports | 0 |

## Result and limits

Three separate Type 303 reports consistently identify the configured live path as the direct endpoint `imp:5:line:1` toward IMP 6. This validates that the proof's shared modem path produces a source-attributed local report endpoint, and it gives a precise requirement for any future shared-topology report-line identity.

It does not establish the reciprocal `imp:6:line:<number>` endpoint, a complete line state, plus/minus directional state, a historical route, a historical location for the IMP 6 peer, or a bridge into the accepted completed-run or controller-live contracts. The existing reducer must therefore not consume this one-way observation as a paired line.
