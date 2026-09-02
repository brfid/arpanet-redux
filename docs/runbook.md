# Runbook

## Scope

Use this runbook to check the source tree, run supported compositions in an existing external laboratory, and inspect retained results. Make targets are the supported operator surface; the standalone scripts documented under [read-only diagnostics](#use-read-only-diagnostics) are the supported inspection surface. This runbook does not acquire historical assets or bootstrap the laboratory. Several inputs have unresolved redistribution terms, so obtain and build them under their own instructions and terms.

## Run source checks

Install Git, Make, Python 3.11 or newer, and standard POSIX shell tools. From the repository root, run:

```sh
make test
```

Before publishing a branch, also scan the complete Git history:

```sh
make check-source-history
```

To run the staged-file guard locally, enable the repository hook:

```sh
git config core.hooksPath hooks
```

The hook is a convenience, not acceptance evidence. CI runs the complete-history check from a non-shallow checkout.

## Prepare an existing laboratory

Keep historical and generated material outside the repository. The default layout is:

```text
parent/
  arpanet-redux/
  arpanet-redux-lab/
    work/       # third-party checkouts and native builds
    results/    # immutable per-run evidence
```

Pass `LAB_ROOT=/absolute/path` to use another location. The laboratory must contain the sources and submodules named in [`pins/sources.lock.toml`](../pins/sources.lock.toml) at the recorded revisions and the assets identified by [`pins/arpanet-assets.sha256`](../pins/arpanet-assets.sha256).

Supported smokes require the appropriate subset of these external inputs:

- a native H316 simulator built from the pinned source;
- `ncpd` and applications built from the pinned `linux-ncp` source;
- a native `pdp10-ka` built from the pinned KA10 source;
- a native PDP-11 simulator built from the pinned IMP11-A fork;
- recovered IMP firmware, the generic IMP configuration, and prepared guest media.

Source-only tests and formal controllers use the Python standard library. Rebuilding the PDP-11 guest media invokes retained research builders that require `pexpect`; pass an isolated interpreter as `PYTHON=/absolute/path/to/venv/bin/python3` for that build.

## Verify inputs

Run the broad identity check before simulator work:

```sh
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab verify
```

This target verifies source revisions and tracked state, checks known assets, rebuilds the diagnostic NCP tools under a lease, writes an external build receipt, and checks simulator identities. Each smoke also runs its narrower verification target.

## Build guest media

Before running the two-ITS composition, create a clean ITS build receipt:

```sh
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab build-its
```

The target performs the pinned build and a no-op rebuild under one lease, verifies clean source and recursive submodules, and hashes the five promoted runtime files. The smoke verifies the receipt and boots independent media copies.

For PDP-11 compositions, use one new external build directory for both the build and later smokes:

```sh
build_root=/absolute/path/to/arpanet-redux-lab/results/pdp11-telnet-build-UNIQUE-ID
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab PYTHON=/absolute/path/to/venv/bin/python3 PDP11_BUILD_ROOT="$build_root" build-pdp11-telnet
```

The build directory is never overwritten. Its receipt binds the base media, staged TELNET and daemon sources, intermediate and final media, build logs, builder hashes, source revisions, and PDP-11 executable identity. Override `PDP11_BASE_ROOT` and `PDP11_BASE_SWAP` if the laboratory does not use the default images under `work/unix-v6-install/images/`.

## Run integration smokes

Set `RUN_ID` when you need a stable result name. Otherwise Make creates a UTC timestamp plus UUID. A collision fails; no target overwrites an existing result.

```sh
lab=/absolute/path/to/arpanet-redux-lab

make LAB_ROOT="$lab" smoke-router
make LAB_ROOT="$lab" smoke-mixed
make LAB_ROOT="$lab" RUN_ID=UNIQUE-RUN-ID smoke-two-its
make LAB_ROOT="$lab" RUN_ID=UNIQUE-RUN-ID PDP11_BUILD_ROOT="$build_root" smoke-pdp11-its
make LAB_ROOT="$lab" RUN_ID=UNIQUE-RUN-ID smoke-ncc-alternate-path
make LAB_ROOT="$lab" RUN_ID=UNIQUE-RUN-ID smoke-ncc-line-loopback
make LAB_ROOT="$lab" RUN_ID=UNIQUE-RUN-ID PDP11_BUILD_ROOT="$build_root" smoke-ncc-pdp11-its
make LAB_ROOT="$lab" RUN_ID=UNIQUE-RUN-ID PDP11_BUILD_ROOT="$build_root" smoke-ncc-pdp11-its-failover
```

| Target | Claim | Normative gate |
|---|---|---|
| `smoke-router` | Diagnostic routing and explicit host-dead response | [Gate 2](test-plan.md#gate-2-router-oracle) |
| `smoke-mixed` | ITS NCP interoperability with a diagnostic endpoint | [Gate 3](test-plan.md#gate-3-mixed-vintage-and-diagnostic-hosts) |
| `smoke-two-its` | Two-ITS TELNET and anti-bypass payload | [Gates 4 and 5](test-plan.md#gate-4-two-vintage-its-hosts) |
| `smoke-pdp11-its` | Network UNIX-to-ITS TELNET and typed direct-route journey | [Gate 4H](test-plan.md#gate-4h-network-unix-pdp-11-to-its) |
| `smoke-ncc-alternate-path` | Reciprocal direct line changes from `up` to `down` while both endpoints remain observable | [Line-fault gate](test-plan.md#ncc-alternate-path-line-fault-gate) |
| `smoke-ncc-line-loopback` | Reciprocal direct line changes from `up` to self-neighbor `looped` | [Line-loopback gate](test-plan.md#ncc-alternate-path-line-loopback-gate) |
| `smoke-ncc-pdp11-its` | Accepted heterogeneous application and passive NCC reports coexist | [Coexistence gate](test-plan.md#ncc-observed-heterogeneous-coexistence-gate) |
| `smoke-ncc-pdp11-its-failover` | One TELNET session survives the direct application-cable cut through IMP 7 | [Failover gate](test-plan.md#ncc-observed-application-link-failover-gate) |

The fault and loopback smokes normally run for about 130 seconds. Their duration and forward-phase variables are diagnostic overrides; do not shorten them for acceptance. The failover smoke normally runs for about five minutes and requires the standard receiver and relay intervals.

## Use interactive TELNET

From the repository root, the existing standard laboratory and retained receipt-bound PDP-11 build need only:

```sh
make telnet
```

For another laboratory or an explicitly selected verified build, run:

```sh
make LAB_ROOT="$lab" RUN_ID=UNIQUE-RUN-ID PDP11_INTERACTIVE_BUILD_ROOT="$build_root" telnet
```

Allow roughly two to three minutes for ITS, Network UNIX, and the two IMPs to boot and settle. The default line-stable boot display diagrams the route and reports timed milestones for source preflight, IMP transport, host boot, link readiness, route settling, TELNET connection, evidence validation, and cleanup; it uses no cursor control and keeps detailed simulator output in the retained result. Run `make TELNET_PREFLIGHT_VERBOSE=1 telnet` when every verified source, asset, simulator revision, and receipt should also be printed. When the `its>` prompt appears, enter `:TIME` and press Return; the complete remote response should end at the next `its>` prompt. `/help` describes the local controls and the current interaction boundary, and `/quit` ends the session without sending those words to the guest. At least one command must complete before `/quit` can produce an accepted run.

The standard laboratory default selects receipt-bound build `pdp11-telnet-option-fix-build-20260902T002513Z`. Its staged guest source repairs the preserved client's missing `break` after a valid `DONT` negotiation, so the ITS greeting is no longer interrupted by the false `Possible protocol error! command = 376, option = 3.` diagnostic. Explicit older builds remain valid historical evidence and may still print that nonfatal message.

The target owns standard input and every simulator PTY in one foreground controller. Each accepted line is printable ASCII, is sent by the real Network UNIX `/usr/bin/telnet - -h 106` client with a carriage return, and is captured through the next documented ITS DDT CRLF-plus-asterisk prompt. The controller retains and reads back a strict `interactive-telnet.jsonl` stream, requires correlated IMP traffic in both directions, checks the ITS TELSER job, and performs bounded cleanup. `TELNET_COMMAND_TIMEOUT`, `TELNET_MAX_COMMAND_BYTES`, `TELNET_MAX_COMMANDS`, and `TELNET_MAX_RESPONSE_BYTES` are diagnostic limit overrides.

A new laboratory must first create a verified PDP-11 build as described under [build guest media](#build-guest-media), then pass that directory as `PDP11_INTERACTIVE_BUILD_ROOT`. This first interactive slice supports printable lines that return to the ITS DDT prompt; it does not support full-screen programs, character-at-a-time editing, arbitrary controls, or paging. Do not enter the banner's `?`, `:?`, or `:INFO` suggestions through this controller yet because their output or input behavior is outside that framing proof. The session emits no message journey, claims no unresolved guest-ingress grammar, and gives the browser no input or simulator authority.

## Run the NCC board

To run either formal application/NCC smoke beside the passive board in one terminal-owned session, use:

```sh
make LAB_ROOT="$lab" RUN_ID=watch-demo PDP11_BUILD_ROOT="$build_root" ncc
make LAB_ROOT="$lab" RUN_ID=failover-watch-demo PDP11_BUILD_ROOT="$build_root" ncc-failover
```

Open the printed loopback URL. Both commands show the existing progressive historical projection while the result grows. Coexistence exposes its completed projection and optional `/report` only after terminal validation. Failover waits for the manifest, application facts, verdict digest, relay lifecycle and cut acknowledgement, typed alternate journey, complete historical stream, report sources, and cleanup; it then shows `DIRECT → CUT → VIA IMP 7` without using candidate report-line numbers. Control-C stops the exact harness session through its existing cleanup path. The browser does not own the harness and cannot send guest input, switch a relay, signal a process, restart a component, or mutate a result.

To run and watch in separate terminals, use:

```sh
make LAB_ROOT="$lab" RUN_ID=watch-demo PDP11_BUILD_ROOT="$build_root" run-ncc
make NCC_RESULT="$lab/results/ncc-pdp11-its-coexistence-watch-demo" watch-ncc
```

To inspect a retained canonical result without starting a simulator, run `make view-ncc` for coexistence or `make view-ncc-failover` for application failover. Override `NCC_RESULT`, `NCC_FAILOVER_RESULT`, `NCC_VIEW_PORT`, or `NCC_WATCH_PORT` when needed. Interactive TELNET remains a separate foreground terminal surface; the board does not send input or own that controller.

## Read a result

Every smoke creates one immutable directory under `$LAB_ROOT/results`. The manifest records source and repository revisions, tracked-dirty flags, executable and configuration hashes, allocated ports, platform, timestamps, outcome, exit status, and cleanup. Console, protocol, and IMP traces remain beside it.

| Prefix | Distinct structured artifacts |
|---|---|
| `router-oracle-` and `its-linux-` | Application and IMP logs plus manifest |
| `two-its-telnet-` | Sentinel evidence and direct NCC observation stream |
| `pdp11-its-telnet-` | Application and cleanup evidence, receipt binding, and `message-journey.jsonl` |
| `pdp11-its-interactive-` | Application and cleanup evidence plus the strict `interactive-telnet.jsonl` command/result stream |
| `ncc-alternate-path-fault-` | `receiver.json`, `historical-events.jsonl`, `direct-relay.json`, and `verdict.json` |
| `ncc-line-loopback-` | `receiver.json`, `historical-events.jsonl`, `direct-reflector.json`, and `verdict.json` |
| `ncc-pdp11-its-coexistence-` | PDP-11 application artifacts plus NCC receiver, historical events, and composition verdict |
| `ncc-pdp11-its-application-failover-` | Coexistence artifacts plus relay state, cut state, pre-cut journey, post-cut journey, and failover verdict |

Use the [test plan](test-plan.md) to evaluate a result. A zero process exit without the required application, network, identity, and cleanup evidence is not a pass. Never edit a retained result or write a reevaluated artifact into it; use a fresh temporary output path.

## Use read-only diagnostics

All viewer servers bind `127.0.0.1`, accept GET and HEAD only, and provide no control or mutation route. Adapters validate their inputs and fail closed. Save derived files outside the retained result directory.

Inspect a growing two-ITS observation stream:

```sh
python3 scripts/ncc-live-snapshot.py "$lab/results/two-its-telnet-RUN-ID/ncc-observations.jsonl"
```

Derive and render a completed two-ITS summary:

```sh
python3 scripts/ncc-summarize-two-its.py "$lab/results/two-its-telnet-RUN-ID" > /tmp/two-its-summary.json
python3 scripts/ncc-render-summary.py /tmp/two-its-summary.json > /tmp/two-its-summary.html
```

Extract a typed journey from a retained Gate 4H result, or serve an existing journey:

```sh
python3 scripts/ncc-extract-pdp11-its-journey.py "$lab/results/pdp11-its-telnet-RUN-ID" config/topologies/pdp11-its-telnet.json /tmp/pdp11-its-journey.jsonl
python3 scripts/ncc-serve-journey.py "$lab/results/pdp11-its-telnet-RUN-ID/message-journey.jsonl"
```

Derive and render a supported completed fault or loopback summary:

```sh
python3 scripts/ncc-summarize-historical-line.py "$lab/results/ncc-alternate-path-fault-RUN-ID" --topology config/topologies/ncc-alternate-path-fault.json > /tmp/ncc-line-summary.json
python3 scripts/ncc-render-summary.py /tmp/ncc-line-summary.json > /tmp/ncc-line-summary.html
```

Serve a growing historical sidecar or a completed coexistence desk:

```sh
python3 scripts/ncc-serve-historical.py "$lab/results/ncc-alternate-path-fault-RUN-ID" --topology config/topologies/ncc-alternate-path-fault.json
python3 scripts/ncc-serve-coexistence.py "$lab/results/ncc-pdp11-its-coexistence-RUN-ID" --topology config/topologies/ncc-pdp11-its-coexistence.json
```

The accepted direct-route journey contains ten observations and stops at missing `boundary:request:6`. The accepted failover journey contains fourteen and stops at missing `boundary:request:8`. These explicit gaps do not weaken the separate application verdict.

## Handle failures and cleanup

Launchers own exact child PIDs and perform bounded cleanup on success, failure, timeout, or interruption. They never use a process name or global kill pattern as ownership evidence.

If a smoke reports an early bind error, rerun it with a new `RUN_ID`; a noncooperating process may have won the unavoidable handoff between port reservation and SIMH bind. If verification reports a source, asset, receipt, or executable mismatch, repair the external laboratory rather than relaxing the check.

On macOS, use the repository launchers instead of upstream wrappers that depend on GNU Screen control-sequence behavior. Project configurations pin simulator peers to IPv4 loopback to avoid an IPv4/IPv6 mismatch with the diagnostic NCP endpoint.
