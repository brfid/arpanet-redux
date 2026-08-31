# NCC telemetry and logical-map direction

- **Observed:** 2026-08-30
- **Implementation observed:** A first source-only decoder and event boundary existed; live IMP attachment and display had not yet been implemented
- **Scope:** Surviving Network Control Center material, historical report formats, operator-display model, and an integration path that does not depend on the current number of IMPs

Current product scope and implementation order live in [NCC observability](../ncc.md). This dated note preserves the historical and format evidence that informed them.

## Finding

Enough original NCC software and documentation survives to use the pre-NU Network Control Center as the primary model. Dave Walden's [IMP-code preservation collection](https://www.walden-family.com/impcode/) includes a text listing and concordance for 1971 NCC System 52, the 1972 paper ["The Network Control Center for the ARPA Network"](https://www.walden-family.com/impcode/1972-nmc.pdf), and BBN Technical Information Report 90, ["The Network Control Center Program"](https://www.walden-family.com/impcode/bbn-tir-90-ncc-software.pdf), revised in November 1976. This is substantially stronger evidence than a visual reconstruction based only on later NU descriptions.

The survey did not locate a preserved, buildable release of the final 1980s ARPANET NCC/NOC application. The NU papers survive and are useful for the later architecture, and late packet-switch source also survives in separate collections, but neither is evidence that the operational NU package itself survives. The implementable near-term target is therefore a modern, project-authored receiver that follows the original NCC's data and operator concepts; booting System 52 is a later compatibility project.

## Additional local archive evidence

The operator's local archive includes a photographed September 9, 1977 draft of the *ARPANET Completion Report*. The primary reading copy is `~/Library/Mobile Documents/com~apple~CloudDocs/etext/BBN/ARPANET completion report draft/draft-completion-report-optimizedr.pdf`; repository files do not reproduce its page images or text.

The draft adds operational detail beyond TIR 90. Pages III-304 and III-306 describe minute-by-minute IMP and line status processing, with status retained in 15-minute periods for a daily history. The NCC used topology and missing-report information to distinguish an IMP malfunction from an IMP that had become invisible across a partition, reducing irrelevant logger output and the amount of deduction left to an operator. This supports time-based state, explicit missing observations, and a separation between direct report and inferred failure class.

Pages III-837, III-839, and III-843 describe remote core transfer, verification, loading, DDT-based tests, and centralized expert diagnosis. Pages III-844 and III-845 describe moving Honeywell maintenance responsibility into the NCC by 1975 and credit the changed maintenance approach with reducing average node downtime from about 1.5 percent to about 0.25 percent. These capabilities establish the historical importance of centralized diagnosis, but they do not justify adding mutation or remote-control features to the first project-authored viewer.

The local archive also includes Eric C. Rosen's *The BBN ARPANET Network Measurement Center*, BBN Report No. 3799, April 1978. The containing directory is mistyped as `3779 the bbn arpanet network measurement center`, but the photographed report itself consistently identifies number 3799. The NMC was closely associated with the NCC but was a distinct facility: its dedicated PDP-11 collected IMP performance data while analysis ran on a PDP-10 TENEX system. The report states that its analysis software obtained topology from a control file kept current at the NCC and compared reported neighbor information with that expected record. This independently supports making nominal topology an NCC-owned input rather than reconstructing it opportunistically from whatever traffic happens to appear.

## What the historical NCC actually presented

TIR 90 describes the NCC as a dedicated Honeywell 316 host attached to the BBN IMP in the ordinary host position. It received periodic reports from every IMP, kept a nominal topology, reconciled the two endpoint reports for each line, timed out missing reports, recorded changes, and exported longer-term data to TENEX processes.

The main operator surface was not a continuously redrawn graphical network map. It combined a lightbox and audible alarm, a hard-copy event log, a summary terminal, and a terminal for dumping unrecognized IMP messages. The summary used a compact status alphabet: unknown, directional failure, fully down, up, and directional loopback. The lightbox selected banks of IMPs, lines, and important hosts, flashed changed elements, distinguished IMP, line, and host alarms by sound, and required an operator acknowledgement before returning to the next-highest-priority condition.

This suggests a hybrid display rather than a literal imitation of one artifact: use the stable mid-1970s logical map as the spatial index, then apply the NCC's state alphabet, alarm priority, event log, and acknowledgement behavior as the live operational layer.

## Visual reference

Fidler and Currie's ["The Production and Interpretation of ARPANET Maps"](https://doi.org/10.1109/MAHC.2015.16) and ["Infrastructure, Representation, and Historiography in BBN's Arpanet Maps"](https://doi.org/10.1109/MAHC.2015.69) establish several useful constraints after visual inspection of their reproduced maps:

- The layout is logical rather than geographic. Link connectivity is stable and legible; physical distance is intentionally absent.
- The subnet is primary. IMPs and TIPs sit on the main graph, while host machines attach as labeled leaves.
- The visual language is monochrome, low-ink, orthogonal where convenient, and label-heavy. It depends on different node shapes more than color.
- The 1973 map uses larger host ovals, while the March 1974 and later maps compact hosts into rectangular labels and distinguish IMP, TIP, Pluribus IMP, and satellite links in a legend. The latter is the appropriate family for this project.
- The maps are deliberately static snapshots and flatten utilization. Realtime traffic, alarms, and recency should therefore be optional overlays that do not move nodes or replace the underlying map grammar.

The steady-state layout should be explicitly authored or deterministically generated from stored positions. A force-directed layout that shifts whenever an IMP joins would be historically unlike the maps and operationally poor because operators would lose spatial memory.

## Report-format boundary

The report number is version-dependent. The recovered 1973 IMP listing's original trouble-report code is Type 301 and its throughput-report code is Type 302. A preserved 1973 patch sheet changes the trouble-report code to Type 303, and the project's pinned external firmware applies that patch. TIR 90's November 1976 description documents the evolved Type 304 status report and Type 305 throughput report. These formats must not be treated as interchangeable merely because they serve the same functions.

The implementation decodes the original Type 301 and patched Type 303 forms of the one 1973 trouble-report layout, and the distinct Type 302 throughput layout. Trouble reports accept 31 semantic 16-bit words plus an optional pad word. The Type 302 decoder accepts 52 semantic words plus an optional pad word: five local packet/word counter pairs and ten cumulative counter families for each of four real host interfaces. The sender's 16-bit accumulator covers the report code and every semantic payload word, then sends its two's-complement value as the final semantic word; it sends the old-style leader and trailing pad separately. Both decoders therefore require their semantic bodies, including checksum, to sum to zero modulo 16 bits while excluding the leader and pad. They preserve actual on-wire codes and do not turn cumulative throughput counters into rates. They do not copy recovered source or commit raw historical message fixtures; tests construct synthetic words from the documented field layout.

The buffer-count order is taken from the actual indexed memory order in the 1973 listing: free, store-and-forward, reassembly, allocate. This resolves an ambiguity in a nearby prose comment whose middle two terms appear in the opposite order.

Line facts remain endpoint-local at the decoder boundary. One IMP can report its neighbor, down bit, looped bit, routing messages sent, and missed routing messages, but it cannot alone assign the historical plus or minus direction for a complete line. TIR 90 defines the minus endpoint as the lower-numbered IMP and the plus endpoint as the higher-numbered IMP; a topology-aware reducer must pair both endpoint observations before producing that operator state.

## Proposed data flow

```text
IMP 5 host 0
    |
    v
1822/host-interface ingress  ->  versioned report decoder
                                      |
                                      v
                               topology-neutral events
                                      |
                         nominal topology + timeouts
                                      |
                                      v
                           paired network-state reducer
                               |                  |
                               v                  v
                         append-only log      live event stream
                                                  |
                                                  v
                                      logical map + alarm panel
```

Historical observations and modern simulator-process health are separate sources. A stopped simulator may explain why an IMP report disappeared, but it must not silently substitute a modern process check for what the historical network reported.

Events carry a schema version, monotonic sequence, observation time, source IMP, subject, state, and optional details. The decoder currently emits one report event, four host-interface state events, and five line-endpoint state events. None of those events names a remote topology edge; that association belongs to the reducer.

## Proposed integration sequence at the time of this research

1. Decode recorded or synthetic Type 301 word sequences offline and prove deterministic event output. This step is implemented under `ncc/` with unit tests and has no simulator dependency.
2. Define a safe derived run-summary contract and adapt completed harness results into it. This gives a deterministic, read-only evidence console before a new live simulator attachment exists.
3. Define one small nominal-topology document that gives stable node identities, endpoint pairs, display labels, and positions. Reconcile it with the operator's parallel third-IMP work before changing shared simulator configurations or the main controller.
4. Add a completed-run viewer, state history, evidence explanations, and replay. The viewer must distinguish configured facts, historical observations, modern harness observations, and inference.
5. Add bounded live publication of the same normalized events without granting the viewer process-control authority.
6. Add a passive host-interface ingress process and attach it as host 0 of BBN IMP 5 in a dedicated NCC topology. It should receive the firmware's real report messages without controlling simulator lifecycles.
7. Add the topology reducer, report timeouts, event recording, and paired plus/minus line state for genuine IMP reports.
8. Consider booting NCC System 52 only after the modern ingress proves the exact host-interface, report-version, checksum, and device requirements. The H316 simulator currently has packet-switch IMP devices, but an original NCC boot also needs a suitable host-side interface and the NCC's console/lightbox devices or defensible substitutes.

## Parallel-work boundary at the time of this research

The first slice is additive: `ncc/`, its tests, and this note. It does not edit the current IMP pair configurations, controller, Makefile, architecture document, or runbook. The live-topology step should wait until the third IMP/host change is available in committed form, then rebase and add IMP 5 through the topology mechanism that change establishes. This avoids encoding a two-IMP assumption or competing edits to the same orchestration files.

## Open evidence questions

- Compare future genuine reports against independently observable IMP-side state without committing restricted raw logs.
- Determine the minimal 1822 receive/send behavior required for an active NCC host, including RFNM handling and any necessary leader conversion. The passive ingress proof sends only the simulator's required ready flag.
- Decide whether the dedicated topology should initially model the documented BBN path through IMPs 5 and 31 or use the smallest valid route from the project's current network. Historical site identity and the number of simulated hops are separate fidelity decisions.
- Locate primary format documentation for the Type 304/305 generation before adding those decoders.

All historical listings, scanned documents, simulator inputs, captures, and raw logs remain external laboratory material under [`NOTICE.md`](../../NOTICE.md). The repository contains only project-authored interpretation, code, and synthetic tests.
