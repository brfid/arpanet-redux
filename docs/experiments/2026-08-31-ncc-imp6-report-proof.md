# Passive NCC report attribution from IMP 6

## Question

Can the unchanged IMP 6 proof peer originate a genuine 1973 Type 303 trouble report or Type 302 throughput report that reaches the NCC receiver on IMP 5 while retaining independent IMP 6 attribution, checksum-valid body semantics, and a reciprocal local line endpoint?

## Settled starting boundary

The prior IMP 5 proof had established checksum-valid patched Type `0303` and Type `0302` reports whose old-style leaders attributed them to IMP 5. It repeatedly observed `imp:5:line:1` up with neighbor IMP 6, but the 25-second window had no separately attributed IMP 6 report. [ADR-009](../adr/0009-ncc-paired-line-topology-boundary.md) therefore prohibited a reciprocal report-line mapping or a complete-line conclusion.

The preserved 1973 listing initializes the report destination to NCC host 0 on IMP 5, keeps the trouble-report program enabled, and skews scheduled reports by the reporting IMP number. That made a longer bounded observation of the existing two-IMP composition the smallest evidence-producing experiment. No firmware word, simulator source, checked-in IMP command file, formal PDP-11/two-ITS harness, or NCC receiver behavior was changed.

## Exact runs

All generated output and raw simulator logs remain under `/Users/brf/src/arpanet-redux-lab/results`. The repository was clean at `f83fb3c0a7aa0491bb9b21ca4a49cc0b5f65953f`; ARPANET-in-a-Box was clean at `78123c77b20dadd9b5967b184dbcb4195185eea6`; H316 SIMH was clean at `feb155fbc49333e879ab082d481e6dcce27d2d91`, and the executable embedded `feb155fb`. The pinned `mini/impcode.simh` and `mini/impconfig.simh` digests were `bc4870059b9131636a49dec53399b8f654ba5c146bd09c32d48ab65d5309c771` and `b3c4fe408c3ec2515f629eea327f4e2f33f692997d4c45e423853da6d1800d78`.

The external-laboratory runner at `/Users/brf/src/arpanet-redux-lab/work/ncc-imp6-report-proof/run.sh` used the repository's cooperative dual-stack port leases and bounded process cleanup. Canonical run `ncc-imp6-original-20260831T215714Z` records runner SHA-256 `43beafc981f7eb695f7df7b68e61ecd4f020611a23c5c99ab688524db7980aa4` and invoked the original checked-in `config/imp/ncc-proof/imp6.simh`, whose SHA-256 was `9bcc0e672158a87c69b114f92ba09e12b3ed3c8b40de588658badf9dbeeae731`.

```sh
BRFID_NCC_RECEIVER_DURATION=65 BRFID_IMP6_TRIGGER_DELAY=45 BRFID_IMP6_TRIGGER_DURATION=10 /Users/brf/src/arpanet-redux-lab/work/ncc-imp6-report-proof/run.sh /Users/brf/src/arpanet-redux-worktrees/ncc /Users/brf/src/arpanet-redux-lab original ncc-imp6-original-20260831T215714Z
```

The first attempt, `ncc-imp6-control-20260831T215239Z`, stopped before simulator launch because the sandbox denied the port lease; it produced no network evidence. Re-running with loopback permission as `ncc-imp6-control-20260831T215323Z` used an external derivative that enabled IMP 6 HI1 but deliberately sent no host-ready signal. It disproved the intended negative control by receiving independently attributed IMP 6 reports, so its mode-specific harness verdict is failed even though its retained report frames are valid. The canonical `original` run removed that configuration difference and established that neither an enabled IMP 6 host interface nor an explicit trigger was necessary.

## Direct result

The canonical 65-second run sent only the passive receiver's flag-only ready signal to NCC host 0 on IMP 5. It sent no NCP, 1822 application/control, report-request, or IMP 6 host-ready message. After the ordinary firmware route/report skew elapsed, the receiver obtained reports from both IMPs through the configured IMP 6 MI1 to IMP 5 MI1 path and IMP 5 HI1 attachment.

| Direct derived observation | Result |
|---|---:|
| Successful NCC host-ready packets sent | 64 |
| IMP-ready packets received at NCC | 25 |
| Complete messages reassembled | 24 |
| Complete message sizes | 2, 34, and 55 words |
| Patched Type 303 reports attributed to IMP 5 | 6 |
| Type 302 reports attributed to IMP 5 | 5 |
| Patched Type 303 reports attributed to IMP 6 | 5 |
| Type 302 reports attributed to IMP 6 | 4 |
| Validated direct historical events recorded | 119 |

Each accepted report had a regular From-IMP old-style leader with a nonzero source IMP. The adapter used that actual leader field, not configured topology, to attribute the five Type 303 and four Type 302 bodies to IMP 6. Both decoders then required the complete semantic body, including its checksum word but excluding the two leader words and optional pad, to sum to zero modulo 16 bits. A recognized report with a bad body or checksum would have failed the receiver instead of entering `receiver.json` or `historical-events.jsonl`; the receiver completed with status zero and an empty error log.

The direct line pair did not depend on configured peer identity: six IMP 5 Type 303 observations consistently reported `imp:5:line:1` up with neighbor IMP 6, while five independently attributed IMP 6 Type 303 observations consistently reported `imp:6:line:1` up with neighbor IMP 5. This is reciprocal endpoint evidence from one exact run, not a line state inferred from configuration.

The run manifest records `outcome=passed`, `exit_status=0`, clean repository and external-source markers, six leased UDP ports, every child PID, exact hashes, and `cleanup.completed=1`. A post-run dual-stack bind check confirmed that all six IPv4 and IPv6 UDP ports were free, and the cooperative lock root was absent.

## Shared mapping and reducer exercise

Evidence-only checkpoint `4d32996` recorded the exact run before any topology change. Commit `78e8220` then added `first_report_line: 1` and `second_report_line: 1` to the existing shared IMP 5/IMP 6 modem binding and an adapter into the already accepted in-memory `NominalTopology`; it added no second topology schema or reducer.

A read-only check loaded the canonical run's validated `historical-events.jsonl` through the committed shared mapping and reconciled all 119 direct events at the final observation time with a 30-second report interval. The configured line `binding:imp5-mi1-imp6-mi1` reduced to `up`, supported by event 103 (`imp:5:line:1`, neighbor IMP 6) and event 114 (`imp:6:line:1`, neighbor IMP 5). Project-topology fixtures separately exercise agreement, contradiction, one-sided missing evidence, and expired evidence; no derived reducer output is written back to the sidecar or adapted into the accepted completed-run or live-stream contracts.

## Conclusion and limits

The experimental prerequisite in ADR-009 is satisfied. IMP 6 can originate ordinary scheduled patched Type 303 and Type 302 reports through the existing proof network without a firmware change or an active request. The smallest trigger is time: retain the original IMP 6 configuration and observe beyond the earlier 25-second window. The source leader, checksum-valid body, and reciprocal `imp:6:line:1` observation jointly distinguish an independently attributed IMP 6 report from transport arrival or configured-peer identity.

This proof does not identify either IMP as a historical site, reconstruct a historical route, establish a universal relationship between `MI1` and report line 1, turn configured topology into observed evidence, or authorize a durable reducer result or a bridge to the accepted completed-run/controller-live contracts. It justifies adding the two explicit report-line identities to this existing shared modem binding and exercising the already accepted source-only reconciliation rules against that project-authored mapping.
