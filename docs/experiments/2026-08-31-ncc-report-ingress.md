# Passive NCC report ingress at IMP 5

## Question

Can the project-authored passive host-interface receiver separate the pre-1976 two-word IMP-to-host leader from a completed report, attribute the report to its reporting IMP, and decode the report body without changing the simulator or sending application traffic?

## Historical interpretation

[BBN Report 1822](https://walden-family.com/impcode/BBN1822_Jan1976.pdf), Appendix A, retains the old-style two-word IMP-to-host leader and defines its source-host and source-IMP fields. Its fake-host mapping makes a source-host field of `3` represent host `255` when the From-IMP bit is set. [RFC 533](https://www.rfc-editor.org/rfc/rfc533.html) records the July 1973 change that made the old leader's message identifier twelve bits wide.

The preserved [1973 IMP listing](https://walden-family.com/impcode/c-listing-ps.txt) constructs the original trouble report with body code `0301`. Its accompanying [1973 patch sheet](https://walden-family.com/impcode/a-patches-ps.txt) changes that code to `0303`. The project pin's external `mini/impcode.simh` applies the same patch after its initial firmware load. The adapter therefore accepts those two codes as forms of the one 31-word 1973 trouble-report layout, but retains the received code in `TroubleReport.message_type` and event details; it does not normalize `0303` to `0301`.

No source text, firmware, packet words, simulator log, or patch content is copied into the repository. The links support the project-authored format interpretation only.

## Controlled run

The 25-second loopback run used the shared `IMP 5` host-0 / `IMP 6` MI1-peer topology. The receiver bound before the two pinned H316 instances started, sent only flag-only host-ready transport packets, and wrote a derived result outside the repository. It neither sent an NCP or 1822 application/control message nor controlled either simulator after launch.

| Direct derived observation | Result |
|---|---:|
| Successful host-ready packets sent | 25 |
| IMP-ready packets received | 10 |
| Complete IMP-to-host messages reassembled | 9 |
| Completed message sizes | 2, 34, and 55 words |
| Decoded trouble reports | 3 |
| Decoded trouble-report code | `0303` |
| Attributed reporting IMP | 5 |
| Direct events per decoded report | 10 |

The 34-word messages comprise the two leader words and the 32-word padded trouble-report form. Their leader identified a regular From-IMP message from fake host 255 on IMP 5. The 55-word messages began with Type 302 and remain opaque; this experiment does not define a throughput-report decoder.

## Result and limits

This is successful evidence for the full passive ingress seam: transport reassembly, old-style leader decoding, source-IMP attribution, patched Type 303 trouble-report decoding, and topology-neutral event production all occurred in one exact run. It validates the selected old-leader interpretation against both primary documentation and the configured firmware.

It does not establish the trouble-report checksum algorithm, independently validate every decoded report field against IMP state, persist reports for replay, decode Type 302 throughput, establish a historical location or route for the IMP 6 proof peer, or provide an active NCC host implementation. Those remain distinct tasks.
