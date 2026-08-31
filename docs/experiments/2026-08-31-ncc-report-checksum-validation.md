# Passive NCC report-checksum validation at IMP 5

## Question

Can the passive NCC receiver validate the exact 1973 checksum and padding domain for both patched Type `0303` trouble reports and Type `0302` throughput reports without treating the old-style IMP-to-host leader as report data?

## Historical interpretation

The preserved [1973 IMP listing](https://walden-family.com/impcode/c-listing-ps.txt) keeps a 16-bit report accumulator. It includes the report code and every following semantic payload word, transmits the two's-complement accumulator as the checksum, then emits padding through a separate message-termination path. The old-style leader is separately generated as IMP-to-host transport framing; its two-word shape is documented in [BBN Report 1822](https://walden-family.com/impcode/BBN1822_Jan1976.pdf).

The project-authored decoders therefore accept a report only when its semantic body, including the checksum word, sums to zero modulo 16 bits. They exclude the two leader words and any one trailing pad word. This is the same rule for the original Type `0301`, its patched Type `0303` form, and Type `0302`; the on-wire report code remains part of the body and is preserved rather than normalized.

No listing text, firmware, packet words, or raw simulator log is committed. The cited sources support the project-authored checksum interpretation only.

## Controlled run

The bounded 25-second IMP 5 / IMP 6 shared-topology run sent only flag-only host-ready transport packets. The receiver required at least one complete message, trouble report, and throughput report. It rejected a recognized report body if its checksum did not match before recording a direct event.

| Direct derived observation | Result |
|---|---:|
| Successful host-ready packets sent | 25 |
| IMP-ready packets received | 10 |
| Complete IMP-to-host messages reassembled | 9 |
| Complete message sizes | 2, 34, and 55 words |
| Checksum-validated patched Type 303 trouble reports | 3 |
| Checksum-validated Type 302 throughput reports | 2 |
| Reporting IMP for every validated report | 5 |
| Direct historical events recorded | 32 |
| Complete event-record lines | 33 (one version-2 header plus 32 events) |

## Result and limits

The primary-derived 16-bit checksum rule accepted all five genuine report frames in one exact passive run, while excluding their old-style leaders and padding. The direct event stream remains version 2 because checksum validation narrows the ingress acceptance rule but does not introduce a new event form. The temporary generated proof, event stream, and simulator output remained in the external laboratory.

This does not independently correlate every decoded field with IMP state, establish a report interval or counter-reset behavior, infer a throughput rate or network condition, decode later Type 304/305 formats, persist reducer output, adapt the historical stream to the accepted completed-run/controller-live contracts, establish a historical route for the IMP 6 proof peer, or provide an active NCC host implementation.
