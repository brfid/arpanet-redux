# NCC message-journey adapter exercise

- **Observed:** 2026-08-31
- **NCC adapter checkpoint:** `93db949`
- **TELNET evidence checkpoint:** `2ddfddc`
- **External result:** `/Users/brf/src/arpanet-redux-lab/results/imp11a-telnet-ka10-trace-20260831T131616Z`
- **Scope:** Read-only exercise of the narrow H316 trace adapter against an existing exact run; no simulator rerun and no persisted NCC contract

## Question

Can the source-only H316 adapter recover safe, directly observed message boundaries from the motivating PDP-11-to-ITS transaction without copying raw logs into the repository or assuming that simulator ticks from different processes share a clock?

## Method

The exercise read only the external IMP 62 console log with `ncc.h316_journey.parse_h316_trace`. It selected complete literal `HI2` transfers, computed SHA-256 fingerprints over the recovered 16-bit words in network order, and decoded only the established NOSC short 1822/NCP fields. The raw log, simulator configurations, media, and binaries remained in the external laboratory.

No KA10 or IMP11-A log parser was inferred from this run. Those sources retain typed construction seams until their complete extraction grammar is independently proven.

## Direct derived results

- One five-word inbound `HI2` transfer decoded as the RST request on NCP control link 0. Its safe correlation fingerprint is `517bb4edb1b2cd5b6dddbe16fef5469cd94d4d95dfd085dab56f2ea1b2597378`.
- One ten-word inbound `HI2` transfer carried the subsequent RFC-bearing request. Its safe correlation fingerprint is `09cbf41d4b5005dc5d5b878612d9b34f2906eea91bc010b9e88b06b86291683b`.
- Two byte-identical seven-word outbound `HI2` transfers decoded as RRP replies on NCP control link 0. Their safe correlation fingerprint is `578156352c847df170a0a2d6a6edc1fc4ff9b048aaf1d056e5ad15945721512d`.

These are direct observations at IMP 62's host interface only. The TELNET research note owns the separately established cross-IMP and KA10 interpretation of the run.

## Diagnostic consequence

The adapter can supply the IMP 62 host-ingress and host-egress boundaries without retaining message content. If both repeated RRP transfers are supplied to one expected boundary, the reducer correctly reports ambiguity rather than silently treating them as one observation. A future harness must therefore bound the exact transaction or retain transport identity that selects the intended transfer; digest equality alone is not a safe deduplication rule.

The H316 observation is upstream of the still-open guest input-decoding boundary. It shows that a valid RRP reached IMP 62's host egress, but it does not prove that the PDP-11 device presented the returned leader bytes in the order expected by the guest daemon.

## Limits and next action

This exercise does not prove a complete journey because it emits no direct KA10 or IMP11-A observations and does not turn the TELNET research driver into a formal harness. The next bounded integration is for a promoted heterogeneous harness to own the run manifest, port leases, cleanup, application verdict, exact transaction window, and typed observations at every configured route boundary. Any persisted journey result or bridge into the accepted completed-run or controller-live contracts still requires an explicit compatibility decision.
