# Existing-laboratory runbook

## Scope

This runbook covers source-only checks from a clean clone and rerunning the committed diagnostic targets in an existing external laboratory. It is not an asset-acquisition or from-scratch bootstrap guide: the historical inputs have unresolved redistribution terms, and the repository does not automate their download.

## Source-only check

Requirements are Git, Make, Python 3.11 or newer, and ordinary POSIX shell tools. From the repository root:

```sh
make test
```

This checks the tracked-file policy and exercises the orchestration helpers without downloading assets or launching simulators.

## Existing external laboratory

Historical and generated materials belong outside the repository. The default layout is:

```text
parent/
  arpanet-redux/       # this repository
  arpanet-redux-lab/
    work/              # third-party checkouts and native builds
    results/           # immutable per-run evidence directories
```

Set `LAB_ROOT=/absolute/path` on any Make invocation to use another location. Existing development installations may therefore retain an older laboratory directory name without changing the repository.

The laboratory must already contain the paths named in [`pins/sources.lock.toml`](../pins/sources.lock.toml) at exactly the recorded revisions, including required nested submodules. Consult each linked upstream project for its own acquisition and build instructions and terms. Do not infer permission to fetch or redistribute an asset from its appearance in a pin file.

The passing diagnostic targets expect these derived tools in the external laboratory:

- a native H316 simulator built from the pinned H316 SIMH source;
- `ncpd` and the NCP applications built from the pinned `linux-ncp` source;
- a native `pdp10-ka` built from the pinned KA10 simulator source;
- the external IMP firmware, base configuration, and ITS guest media identified by [`pins/arpanet-assets.sha256`](../pins/arpanet-assets.sha256).

Use an isolated virtual environment only for optional Python dependencies introduced by a controller. The currently committed source-only tests use the standard library and do not require one.

The production PDP-11 controller also uses only the standard library. Rebuilding the guest media still calls the retained research-phase in-guest builders, which require `pexpect`; select an existing isolated interpreter with `PYTHON=/absolute/path/to/venv/bin/python3` for `build-pdp11-telnet`. The smoke itself does not use that dependency.

## Verify the laboratory

Run identity checks before a simulator smoke:

```sh
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab verify
```

Verification checks source revisions and tracked state, verifies known external assets, force-rebuilds the diagnostic NCP tools, writes a build receipt outside the repository, and confirms that simulator executables identify the pinned revisions.

## Run the passing smokes

The router oracle proves routing plus explicit network failure reporting:

```sh
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab smoke-router
```

The NCC alternate-path fault smoke proves that IMPs 5 and 6 remain observable while their direct line changes from reciprocal `up` to reciprocal `down` evidence. It runs for about 130 seconds so the recovered firmware can emit reports before and after the relay cut:

```sh
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab RUN_ID=UNIQUE-RUN-ID smoke-ncc-alternate-path
```

The target verifies the pinned H316 sources, simulator, firmware, and project inputs; leases ten UDP ports; starts the NCC receiver, three IMPs, and the owned direct-line relay; and performs bounded cleanup. `NCC_DIRECT_FORWARD_SECONDS` and `NCC_ALTERNATE_DURATION` are diagnostic overrides, but the forwarding interval must be positive and shorter than the receiver duration. Interpret the result against the NCC alternate-path line-fault gate in the [test plan](test-plan.md).

The NCC line-loopback smoke reuses that alternate report route, then changes the direct instrument from cross-forwarding to byte-exact self-reflection. It runs for about 130 seconds so both recovered IMPs can report the initial up state and repeat their self-neighbor loop indications:

```sh
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab RUN_ID=UNIQUE-RUN-ID smoke-ncc-line-loopback
```

The target verifies the same pinned inputs, leases ten ports, starts the passive receiver, three IMPs, and the owned reflector, and performs bounded cleanup. `NCC_DIRECT_FORWARD_SECONDS` and `NCC_LOOPBACK_DURATION` are diagnostic overrides with the same ordering constraint. Interpret the result against the NCC alternate-path line-loopback gate in the [test plan](test-plan.md); the reflector phase alone is never accepted as line-state evidence.

The mixed smoke proves that native ITS NCP interoperates with the two-IMP path:

```sh
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab smoke-mixed
```

The two-ITS smoke additionally needs promoted clean media for host `176`. Build from the exact pinned ITS checkout and then run the supported application proof:

```sh
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab build-its
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab smoke-two-its
```

The clean build is intentionally separate from the smoke and can take a long time. `build-its` holds the build/use lease while it cleans the generated output, builds `EMULATOR=pdp10-ka its`, repeats the target as a no-op rebuild, and writes the receipt. Receipt creation fails unless the pinned source and initialized submodules are clean, the target is up to date, and all five promoted runtime files exist. The smoke holds the same lease while it verifies and copies those files, so a cooperating rebuild cannot replace a running input.

The heterogeneous PDP-11 gate uses a unique external build directory for its receipt-bound media. Use the same explicit build path for the build and smoke invocations:

```sh
build_root=/absolute/path/to/arpanet-redux-lab/results/pdp11-telnet-build-UNIQUE-ID
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab PYTHON=/absolute/path/to/venv/bin/python3 PDP11_BUILD_ROOT="$build_root" build-pdp11-telnet
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab RUN_ID=UNIQUE-RUN-ID PDP11_BUILD_ROOT="$build_root" smoke-pdp11-its
```

The default base media paths are `$LAB_ROOT/work/unix-v6-install/images/ncp_root.rl01` and `ncp_swap.rl01`; override `PDP11_BASE_ROOT` and `PDP11_BASE_SWAP` when the laboratory uses another prepared base. The build creates its directory atomically and never overwrites an earlier one. Its receipt binds both base images, the pinned Network UNIX and IMP11-A revisions, the embedded PDP-11 revision and executable hash, exact staged TELNET and daemon sources, the intermediate and final media, build logs, and builder hashes. `smoke-pdp11-its` holds the same build/use lease, verifies the receipt and all source, asset, binary, firmware, and configuration identities, then copies the final guest media into a new run directory before launch.

The formal topology is ITS host `106` on IMP 6 and Network UNIX host `176` on IMP 62. The controller validates `config/topologies/pdp11-its-telnet.json`, waits for both modem and host-link states, the ITS console banner, a responsive local ITS command state, a booted PDP-11, and its preserved NCP before capturing application offsets and starting TELNET. After the application evidence passes, it fixes both H316 trace-window end offsets and emits a typed `message-journey.jsonl`. Interpret its result against Gate 4H in the [test plan](test-plan.md); `Connection open` or `SKTRACE` without the service job, structured remote `:TIME`, correlated traffic on both IMPs, and a reducer-verified sidecar is a failure.

The integrated NCC/application smoke reuses the same receipt-bound PDP-11 build. It preserves the NCC triangle on IMP 6 MI1/MI2, moves only the application cable to MI3, adds hosts `176` and `106` plus IMP 62 to the same lifecycle, and keeps the passive receiver on IMP 5 host 0:

```sh
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab RUN_ID=UNIQUE-RUN-ID PDP11_BUILD_ROOT="$build_root" smoke-ncc-pdp11-its
```

The target verifies the five external source trees, three simulators, mixed assets, build receipt, firmware, topology, and configurations; leases fourteen UDP ports; starts the receiver and IMPs 5/7 under the outer runtime; delegates IMPs 6/62 and both guests to the existing application controller; retains both existing sidecars; and evaluates the combined result after bounded cleanup. Its default receiver duration is 150 seconds. Interpret it against the NCC-observed heterogeneous coexistence gate in the [test plan](test-plan.md). The target proves one application and NCC composition, not application rerouting through IMPs 5 or 7.

The dedicated NCC worktree provides shorter operator aliases without changing that lifecycle. `run-ncc` delegates to the same formal smoke and still requires the receipt-bound PDP-11 build root. Give the run a stable identity so a second terminal can name its growing result exactly:

```sh
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab RUN_ID=watch-demo PDP11_BUILD_ROOT="$build_root" run-ncc
```

After that run creates `historical-events.jsonl`, a second terminal can open the passive polling view over the genuine growing sidecar:

```sh
make NCC_RESULT=/absolute/path/to/arpanet-redux-lab/results/ncc-pdp11-its-coexistence-watch-demo watch-ncc
```

`watch-ncc` shows historical reports and in-memory line reconciliation while the harness runs; it does not control the harness, infer application traffic, or make the completed composition claim. Once the smoke passes, stop the watcher with Control-C and open the completed evidence-composed desk with the same result path:

```sh
make NCC_RESULT=/absolute/path/to/arpanet-redux-lab/results/ncc-pdp11-its-coexistence-watch-demo view-ncc
```

`view-ncc` detects the project's adjacent external laboratory and defaults to its retained canonical coexistence result, so the dedicated NCC worktree can preview that result with just `make view-ncc`. Override `NCC_RESULT`, `NCC_VIEW_PORT`, or `NCC_WATCH_PORT` when using another result or loopback port.

Set `RUN_ID` to a unique value when a stable result-directory name is useful. Otherwise the Makefile creates a UTC timestamp plus UUID. A collision is an error; a prior result is never overwritten.

## Read the result

Each smoke creates one directory beneath `$LAB_ROOT/results`. Its run manifest records source revisions, tracked-dirty flags, executable and configuration hashes, allocated ports, platform, timestamps, outcome, and exit status. Console, protocol, and IMP traces remain beside that manifest in the external result directory.

An NCC alternate-path result is named `ncc-alternate-path-fault-<run-id>`. `verdict.json` records every acceptance check, report counts by source IMP, post-cut report counts for IMPs 5 and 6, relay forward/drop counts, and the direct line's pre-cut and final supporting event sequences. `direct-relay.json`, `receiver.json`, and `historical-events.jsonl` are its structured direct inputs. A pass additionally requires `outcome=passed`, `exit_status=0`, both owned controllers to exit successfully, `cleanup.completed=1`, and no transport error in any IMP log. Do not edit a result or rerun the evaluator into its directory; write any read-only reevaluation to a separate temporary path.

An NCC loopback result is named `ncc-line-loopback-<run-id>`. Its `verdict.json` additionally retains each raw final direct endpoint, its self-neighbor, post-loop report counts, reflector forward/reflection counts, and pre-loop/final reducer support. `direct-reflector.json`, `receiver.json`, and `historical-events.jsonl` are its structured direct inputs. The same manifest, controller-exit, cleanup, transport, and immutability requirements apply.

The PDP-11 result additionally retains `application-evidence.txt`, `cleanup-evidence.txt`, `message-journey.jsonl`, the run-local attach-only ITS configuration, PDP-11 IMP device trace, and the receipt hash and path. Its manifest binds the shared topology, exact trace-window end offsets, sidecar digest, observation count, diagnosis, and first unresolved boundary. The accepted bounded extraction contains ten observations and terminates `missing-boundary` at `boundary:request:6`; that explicit lack of host-106 ingress evidence does not replace or weaken the separate passing application verdict. A completed pass has `outcome=passed`, `exit_status=0`, `surviving_owned_processes=0`, and `cleanup.outer-runtime=passed`; the six recorded ports must be free and their cooperative locks absent after exit.

An integrated result is named `ncc-pdp11-its-coexistence-<run-id>`. It adds `receiver.json`, `historical-events.jsonl`, and `verdict.json` to the formal PDP-11 artifacts. The verdict requires the application and typed journey to pass unchanged, both report forms from IMPs 5, 6, 7, and 62, one fresh reciprocal `up` reduction for the already mapped IMP 5 / IMP 6 direct line, clean identities, and both cleanup layers. The receiver outlives the application controller, so later teardown events may make the final progressive line view down or stale; use the verdict's exact supporting sequences for the accepted coexistence claim and keep later direct observations visible rather than rewriting them. Fourteen recorded ports and their cooperative locks must be free after exit.

Interpret evidence using the [test plan](test-plan.md). A successful process exit without the required application and IMP evidence is not a pass.

## Summarize a completed two-ITS result

Each formal two-ITS run writes `ncc-observations.jsonl` into its external result directory. The controller flushes only its existing lifecycle and application observations to that append-only stream; it does not add simulator control or new raw-log parsing. A passive snapshot command can inspect the current direct state without modifying the run or requiring external evidence locators:

```sh
python3 scripts/ncc-live-snapshot.py /absolute/path/to/arpanet-redux-lab/results/two-its-telnet-<run-id>/ncc-observations.jsonl
```

The snapshot preserves configured topology and the last direct state while marking old observations stale. It has no gate-verdict or process-control authority.

The read-only NCC adapter reads the formal manifest, controller outcome, and sentinel evidence from an existing two-ITS result. It never launches or controls simulators, parses raw logs, or modifies the result directory. Redirect its JSON output outside the immutable result directory when a saved summary is useful:

```sh
python3 scripts/ncc-summarize-two-its.py /absolute/path/to/arpanet-redux-lab/results/two-its-telnet-<run-id> > /tmp/two-its-ncc-summary.json
python3 scripts/ncc-render-summary.py /tmp/two-its-ncc-summary.json > /tmp/two-its-ncc-viewer.html
```

A derived summary reports a failed formal run without valid application evidence as incomplete; it does not turn missing evidence into a network-down claim. The static viewer provides fixed-topology, gate, provenance, and observation-replay views without opening external evidence locators. See [NCC observability](ncc.md) for the contract boundary.

## Extract a typed journey from a retained PDP-11 result

The read-only journey adapter accepts a completed passing formal Gate 4H result and writes a new sidecar only at the explicit output path. It validates the retained manifest, reads each H316 trace from the recorded application start offset through its retained file size, binds the slices to exact offsets and SHA-256 digests, and uses the same topology, extractor, stream writer, and reducer as the formal controller. It never changes the result directory or launches a simulator:

```sh
python3 scripts/ncc-extract-pdp11-its-journey.py /absolute/path/to/arpanet-redux-lab/results/pdp11-its-telnet-<run-id> config/topologies/pdp11-its-telnet.json /tmp/pdp11-its-message-journey.jsonl
```

The command prints the run identity, observation count, terminal state, and first unresolved boundary. For the accepted Gate 4H trace shape, expect ten observations, `missing-boundary`, and `boundary:request:6`. Choose a fresh output path because the recorder refuses to overwrite an existing file. Retained laboratory results are read-only inputs; never write the derived sidecar back into one.

## View a growing typed message journey

The passive journey display watches one `message-journey.jsonl`, binds an HTTP server only to `127.0.0.1`, and accepts GET and HEAD only. It re-reads and validates the complete JSONL prefix on each browser request, invokes the existing Python reducer, and sends the browser a resolved presentation snapshot. It does not parse raw traces, modify the sidecar or result directory, align independent simulator clocks, or control a guest, IMP, controller, or external network endpoint:

```sh
python3 scripts/ncc-serve-journey.py /absolute/path/to/arpanet-redux-lab/results/pdp11-its-telnet-<run-id>/message-journey.jsonl
```

Open the printed loopback URL in a local browser. The fixed route and all twelve request/reply boundary sockets are configured expectations, not evidence. Direct H316 trace observations, harness-derived connected-peer observations, and in-memory reducer states use separate labels; the observation tape retains emission order and source-local identities without claiming a common clock. An interrupted final record is ignored and displayed as tail status until its terminating newline arrives. A terminal page means the persisted diagnosis exactly matched the reducer, not that every boundary was observed or that a new completed-run verdict exists. The accepted Gate 4H sidecar should show ten observations, `missing-boundary`, and first unresolved `boundary:request:6`.

The same command accepts `message-journey.jsonl` from an integrated `ncc-pdp11-its-coexistence-<run-id>` result. It still projects only the named application route and its typed evidence; the additional NCC components remain in the shared topology but do not become journey observations.

To view a retained result that predates formal sidecar emission, first use the read-only extraction command above with a fresh temporary output path, then pass that temporary sidecar to `ncc-serve-journey.py`. Never write derived output into the retained result directory.

## Summarize a completed NCC historical-line result

The historical-line adapter accepts only a supported alternate-path fault or line-loopback result. It reads the terminal manifest, validated historical-event sidecar, formal verdict, and explicitly supplied shared topology; it re-runs the source-only reducer in memory and requires exact agreement with the verdict's pre-transition and final support. It does not read raw logs, launch a simulator, or modify the result directory.

From the repository checkout, derive a version-2 completed summary and render it outside the immutable result directory:

```sh
python3 scripts/ncc-summarize-historical-line.py /absolute/path/to/arpanet-redux-lab/results/ncc-alternate-path-fault-<run-id> --topology config/topologies/ncc-alternate-path-fault.json > /tmp/ncc-historical-line-summary.json
python3 scripts/ncc-render-summary.py /tmp/ncc-historical-line-summary.json > /tmp/ncc-historical-line-viewer.html
```

The same command accepts `ncc-line-loopback-<run-id>` with the same shared topology input. A pass is evidence-closed over the final reciprocal line observations and the supported evaluator outcome. Unmapped alternate bindings remain configured topology only, and any manifest, topology digest, lifecycle, verdict, reducer-state, or supporting-sequence disagreement fails closed.

## View a growing NCC historical-event sidecar

The passive display watches `historical-events.jsonl` in an existing result directory, binds an HTTP server only to `127.0.0.1`, and accepts GET and HEAD only. It re-reads and validates the complete JSONL prefix on each browser request; it does not write to the result, read raw logs, or control a receiver, relay, reflector, controller, or simulator. From the repository checkout, serve a fault or loopback result with the shared three-IMP topology:

```sh
python3 scripts/ncc-serve-historical.py /absolute/path/to/arpanet-redux-lab/results/ncc-alternate-path-fault-<run-id> --topology config/topologies/ncc-alternate-path-fault.json
```

Open the printed loopback URL in a local browser. Use `config/topologies/imp5-ncc-host-interface.json` for an original IMP 5/IMP 6 report result; use `config/topologies/ncc-alternate-path-fault.json` for both alternate-path fault and line-loopback results. An active run stays on the progressive display. Once a supported fault or loopback result has a terminal manifest and verdict, exact agreement between the final in-memory line state/support and the derived version-2 summary redirects the page to the completed viewer. Invalid or disagreeing terminal evidence blocks that handoff visibly.

An integrated coexistence result can be inspected with its seven-component topology:

```sh
python3 scripts/ncc-serve-historical.py /absolute/path/to/arpanet-redux-lab/results/ncc-pdp11-its-coexistence-<run-id> --topology config/topologies/ncc-pdp11-its-coexistence.json
```

That display validates the complete historical sidecar, retains all six unmapped links as configured-only, and reconciles only the mapped IMP 5 / IMP 6 direct line. It deliberately remains in progressive mode after the run because the completed-summary adapter supports only fault and loopback verdicts. Use the completed coexistence desk below when the application, journey, composition verdict, and later receiver tail need one phase-aware handoff.

Retained results in the external laboratory are read-only inputs. Do not copy, normalize, complete, or rewrite their sidecars merely to serve them; an interrupted final record is an explicit display condition, and a completed retained fault or loopback result should hand off without changing any artifact digest.

## View a completed NCC/application coexistence result

The completed coexistence desk accepts only the integrated result shape. It validates the exact shared topology path and digest, terminal manifest and lifecycle, application and cleanup facts, verdict digest and checks, typed journey digest and reducer result, complete historical stream identities, direct Type 303/302 counts, and the verdict's latest observed reciprocal `up` support. It reads no raw simulator log or receiver dump and changes no result artifact:

```sh
python3 scripts/ncc-serve-coexistence.py /absolute/path/to/arpanet-redux-lab/results/ncc-pdp11-its-coexistence-<run-id> --topology config/topologies/ncc-pdp11-its-coexistence.json
```

Open the printed loopback URL in a local browser. The evidence phase rail uses historical-event sequence, not a shared simulator clock. Its amber 322/355 pair is the composition verdict's accepted line support; red or stale later events belong to the post-support receiver tail and do not rewrite the application verdict. The desk explicitly reports that no controller-exit sequence was persisted instead of guessing a teardown boundary.

The judgment ledger should show the application as `passed`, the typed journey as `missing-boundary` with first unresolved `boundary:request:6`, and the mapped line as accepted `up` with a separate run-finish tail reduction. The fixed topology should retain six configured-only links. Select phase markers or journey boundaries to inspect their exact authority; application success never fills an unobserved boundary or assigns traffic to a configured link.

The server binds only `127.0.0.1`, accepts GET and HEAD, and exposes only `/`, `/api/snapshot`, and an empty favicon response. A manifest, digest, identity, lifecycle, report-count, typed-journey, or reducer-support disagreement prevents startup. Retained laboratory results remain read-only; do not repair a failed display by editing or reevaluating its inputs in place.

## Cleanup and failures

The launcher owns exact child PIDs and performs bounded cleanup on success, error, timeout, or interruption. It does not terminate processes merely because they share a name. An interrupted run should finish its manifest with a failed outcome and release its private sockets and port locks.

If a smoke reports an early bind error, rerun it with a new `RUN_ID`; a noncooperating local process may have claimed a port during the unavoidable handoff between reservation and SIMH bind. If verification reports a revision, asset, or executable mismatch, repair the external laboratory rather than weakening the pin or source-only check.

On macOS, use the repository launchers rather than upstream wrappers that depend on GNU Screen control-sequence behavior. Every configured peer is pinned to IPv4 loopback to avoid an IPv4/IPv6 mismatch with the diagnostic NCP endpoint.

## Promoting source-built ITS media

Before any source-built ITS media becomes an acceptance input, run `build-its`. It performs the clean upstream build and no-op rebuild under one lease, records the clean-tree and recursive-submodule state, and hashes every promoted runtime output. `smoke-two-its` verifies the receipt and boots an independent media copy. The normative application and readiness requirements are in the [test plan](test-plan.md); current progress is reported only in the [README](../README.md).
