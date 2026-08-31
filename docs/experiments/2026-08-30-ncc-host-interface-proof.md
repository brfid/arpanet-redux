# NCC host-interface proof at IMP 5

## Question

Can a project-authored, passive NCC receiver attach at host 0 on an H316 configured as IMP 5, maintain the simulator's required ready signal, and receive complete IMP-to-host messages without becoming an NCP/1822 sender or simulator controller?

## Controlled composition

The proof uses the pinned H316 binary and external `mini/` command inputs recorded by the project pins. The project-owned [`ncc.host_interface`](../../ncc/host_interface.py) receiver binds its UDP socket before the simulators start, sends only a flag-only `FINAL|READY` transport packet, and records only packet metadata plus SHA-256 digests of completed messages. It neither sends an NCP or 1822 message nor reads a simulator console or manages a simulator lifecycle.

The shared topology input binds the receiver to IMP 5 host 0/`hi1` and binds IMP 5 `mi1` to a local IMP 6 `mi1` peer. The peer is necessary for the recovered firmware to provide the observed host output. It is a fidelity-minimal, adjacent-IMP composition; it does not recreate a historical site or route.

The checked-in IMP command files load the external generic setup and recovered firmware through `BRFID_H316_MINI_ROOT`. SIMH resolves nested `do` commands beside the project command file rather than from the process working directory, so relying on the latter left the firmware unloaded. This variable makes the external dependency explicit without bringing external files into the repository.

## Result

The final bounded loopback run on 2026-08-30 lasted 25 seconds and satisfied all three shared proof requirements:

| Direct derived observation | Count |
|---|---:|
| Successful host-ready packets sent | 63 |
| IMP-ready packets received | 10 |
| Complete IMP-to-host messages reassembled | 9 |
| Completed message sizes | 2, 34, and 55 words |

No raw packet words or simulator logs are committed. The external laboratory retained those materials; this record retains only the project-authored counts and result shape needed to reproduce the boundary conclusion.

The receiver originally advanced its ready-packet sequence after an unsuccessful early UDP send. That made the H316 correctly reject the first later packet because it expects initial sequence zero. [`PassiveHostIngress`](../../ncc/host_interface.py) now retries the same pending ready packet until the socket reports a successful send, and its regression test covers that startup race.

## Conclusion and limit

This is a successful host-interface transport proof and a successful shared IMP 5/IMP 6 topology composition. It proves that the passive receiver obtains complete opaque IMP output from the configured IMP 5 path and that the shared topology is sufficient to connect the receiver and both simulator interfaces consistently.

It does not yet identify a historical location for the local IMP 6 peer, establish a historical route, interpret the host leader, attribute a report to a source IMP, decode a received Type 301 report, or produce a normalized NCC event. Those are separate historical-format and event-adapter tasks.
