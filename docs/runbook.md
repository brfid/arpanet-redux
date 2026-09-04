# Runbook

## Scope

Use this runbook to check the source tree, prepare or verify an external laboratory, run supported compositions, and inspect retained results. Make targets are the supported operator surface; the standalone scripts documented under [read-only diagnostics](#use-read-only-diagnostics) are the supported inspection surface. The [fresh-clone guide](getting-started.md) is the shortest path to TELNET or NCC. Several inputs have unresolved redistribution terms, so the setup helper fetches source only from its recorded upstream URLs and requires the operator to supply the exact PDP-11 base media separately.

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

The hook is a convenience, not acceptance evidence. On pushes and pull requests, CI runs `make test` with Python 3.11 and 3.14 on Linux and Python 3.14 on macOS; the Linux 3.11 job also runs the complete-history check from a non-shallow checkout.

## Prepare the laboratory

Keep historical and generated material outside the repository. The default layout is:

```text
parent/
  arpanet-redux/
  arpanet-redux-lab/
    work/       # third-party checkouts and native builds
    results/    # immutable per-run evidence
```

Pass `LAB_ROOT=/absolute/path` to use another location. The laboratory must contain the sources and submodules named in [`pins/sources.lock.toml`](../pins/sources.lock.toml) at the recorded revisions and the assets identified by [`pins/arpanet-assets.sha256`](../pins/arpanet-assets.sha256).

For a fresh lab, fetch the runtime source subset, create the pinned Python environment, and build all three required simulators with:

```sh
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab lab-setup
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab doctor
```

`make lab-setup-plan` describes those writes without performing them. Setup is idempotent for exact clean checkouts and refuses dirty or unrelated directories. It does not acquire the prepared Network UNIX base images; follow the [base-media step](getting-started.md#supply-the-pdp-11-base-media), then rerun the doctor.

On macOS, setup passes `LDFLAGS_O=-lz` to the pinned `ka10-simh` `pdp10-ka` and `imp11a-simh` `pdp11` builds. Those legacy dependency probes can find Homebrew `libpng` without recognizing Apple's system zlib stub, which otherwise leaves `zlibVersion` undefined at link time. The explicit system-library link does not modify either external checkout; `make LAB_ROOT=/absolute/path/to/arpanet-redux-lab verify-binaries` confirms the resulting simulators embed their pinned revisions.

Supported smokes require the appropriate subset of these external inputs:

- a native H316 simulator built from the pinned source;
- `ncpd` and applications built from the pinned `linux-ncp` source;
- a native `pdp10-ka` built from the pinned KA10 source;
- a native PDP-11 simulator built from the pinned IMP11-A fork;
- recovered IMP firmware, the generic IMP configuration, and prepared guest media.

Source-only tests and formal controllers use the Python standard library. Rebuilding the PDP-11 guest media invokes retained research builders that require the versions of `pexpect` and `ptyprocess` pinned in [`requirements-lab.txt`](../requirements-lab.txt). `make lab-setup` installs them in `$LAB_ROOT/.venv`, and Make selects that interpreter automatically; an explicit `PYTHON=/absolute/path/to/venv/bin/python3` remains supported.

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

For PDP-11 compositions, the convenient path creates one new external build directory, verifies its receipt, and selects it for later TELNET and NCC invocations:

```sh
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab build-pdp11-telnet
```

To control the result name explicitly, use one new directory for both the build and later smokes:

```sh
build_root=/absolute/path/to/arpanet-redux-lab/results/pdp11-telnet-build-UNIQUE-ID
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab PYTHON=/absolute/path/to/venv/bin/python3 PDP11_BUILD_ROOT="$build_root" build-pdp11-telnet
```

The build directory is never overwritten. Its receipt binds the base media, staged TELNET and daemon sources, intermediate and final media, build logs, builder hashes, source revisions, and PDP-11 executable identity. Override `PDP11_BASE_ROOT` and `PDP11_BASE_SWAP` if the laboratory does not use the default images under `work/unix-v6-install/images/`. A successful build records its stable external selection under `$LAB_ROOT/state`; select another retained receipt with `make LAB_ROOT="$lab" PDP11_BUILD_ROOT="$build_root" select-pdp11-build`.

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

Allow roughly two minutes for ITS, Network UNIX, and the two IMPs to boot and settle. The line-stable display diagrams the route and reports timed milestones while detailed simulator output stays in the retained result. Run `make TELNET_PREFLIGHT_VERBOSE=1 telnet` when every verified source, asset, simulator revision, and receipt should also be printed. The handoff stops at the real Network UNIX root shell on host 176; it does not open TELNET for you.

Start and use the preserved client with this sequence:

```text
# /usr/bin/telnet
 UNIX User Telnet -- Ver I.5
* connect - -h 106
...
Welcome to ITS!
...
:TIME
...
^ayt
YES
```

The caret in `^ayt` is a literal `^`, the historical client's default command flag, not a Control key chord. Other useful client commands include `^msg`, `^character`, `^close`, and, after closing the connection, `bye`. The client's own `help` command reads its installed help file when available. Press Control-] at any point to stop the complete simulation through bounded controller cleanup.

The controller owns standard input and every simulator PTY but does not parse or generate TELNET protocol. Network UNIX's preserved `telnet` and `usrtelnetin` programs own connection state, character/message modes, local echo, option negotiation, and protocol controls. The adapter forwards seven-bit character input, maps local line feed to carriage return and modern Delete to the guest's backspace, rejects high-bit input, and blocks `Control-\` because octal `034` is the configured SIMH WRU character. Guest escape and other unsafe output controls are rendered visibly instead of being executed by the modern terminal. Project-added `SKTRACE` and `PBTRACE` diagnostics are hidden from the human display but remain exact in the transcript and raw console log.

Each run retains and reads back a strict `terminal-session.jsonl` with exact directional bytes, local safety decisions, cumulative digests, finite limits, and terminal reason. A run that exits before connecting remains a valid terminal lifecycle but records `connection_open=0` and makes no application claim. When a connection opens, the controller requires the no-argument historical client interface, ordered ITS greeting, TELSER job, correlated traffic through both IMPs, stable selected links, and cleanup. `TELNET_MAX_INPUT_BYTES`, `TELNET_MAX_OUTPUT_BYTES`, and `TELNET_MAX_CHUNK_BYTES` are diagnostic limit overrides.

To operate the same preserved client across the accepted application-link fault and alternate route, use the separate four-IMP terminal target:

```sh
make LAB_ROOT="$lab" RUN_ID=UNIQUE-RUN-ID PDP11_INTERACTIVE_BUILD_ROOT="$build_root" telnet-failover
```

Allow roughly five minutes for the larger composition to boot and settle. Invoke `/usr/bin/telnet`, enter `connect - -h 106`, wait for the ITS greeting, enter `:TIME`, and wait for the complete time, date, uptime, and DDT prompt. Press Control-^ once. That byte is a local cut request only in this target and is never sent to Network UNIX. The foreground controller first checks the connected pre-cut transaction, then cuts its run-owned direct relay, waits for the atomic acknowledgement and direct-dead/alternate-ready state, and prints that the IMP 7 route is ready. Enter another `:TIME`, wait for its complete response, and press Control-] to validate and clean up. Do not type during the controller's cut-and-settle interval.

The cut is refused without changing the relay if the first connection and structured `:TIME` are not yet evidenced. The target passes only with exactly one `Connection open`, one accepted cut, a structured `:TIME` on each side of the cut, bidirectional relay and IMP evidence, the ten-observation direct journey, the fourteen-observation alternate journey, clean pinned inputs, and zero surviving owned processes. Its version-2 `terminal-session.jsonl` names both routes and records accepted, refused, or repeated cut controls; its evaluator intentionally makes no NCC-report or report-line claim. `TELNET_FAILOVER_RELAY_DURATION` is a diagnostic upper-bound override, not an acceptance shortcut.

Make uses the explicitly selected receipt-bound build, or discovers the newest directory containing a receipt when no selection exists. The current builder's staged guest source repairs the preserved client's missing `break` after a valid `DONT` negotiation, so the ITS greeting is no longer interrupted by the false `Possible protocol error! command = 376, option = 3.` diagnostic. Explicit older builds remain valid historical evidence and may still print that nonfatal message.

The deterministic line-oriented proof remains separately available:

```sh
make LAB_ROOT="$lab" RUN_ID=UNIQUE-RUN-ID PDP11_INTERACTIVE_BUILD_ROOT="$build_root" telnet-check
```

`make telnet-check` automatically invokes `/usr/bin/telnet - -h 106`, presents the synthetic local `its>` line prompt after connection, and retains the strict ADR-014 `interactive-telnet.jsonl` command/result stream. Enter a prompt-returning command such as `:TIME`; use `/help` for local instructions and `/quit` after at least one command completes. `TELNET_COMMAND_TIMEOUT`, `TELNET_MAX_COMMAND_BYTES`, `TELNET_MAX_COMMANDS`, and `TELNET_MAX_RESPONSE_BYTES` apply only to this deterministic mode.

A new laboratory must first create a verified PDP-11 build as described under [build guest media](#build-guest-media); the successful build is selected automatically. Pass another directory as `PDP11_INTERACTIVE_BUILD_ROOT` for a one-off run. Both human modes support character-at-a-time seven-bit teletype interaction and asynchronous output, but neither claims a cursor-addressed terminal type or safe behavior for full-screen and paged ITS programs. The direct session emits no message journey; the failover session reuses only the already accepted direct and alternate journey grammars. Neither claims a new guest-ingress grammar or gives the browser input or simulator authority.

## Run the NCC operator console

With the standard sibling laboratory and its retained verified PDP-11 build, run either formal application/NCC smoke beside the passive console in one terminal-owned session with:

```sh
make ncc
make ncc-failover
```

Open the printed loopback URL. The convenience targets locate the laboratory beside the primary checkout even when invoked from a dedicated Git worktree, and reuse the retained receipt-bound build selected for the historical terminal. Set `LAB_ROOT`, `RUN_ID`, or `NCC_PDP11_BUILD_ROOT` explicitly for another laboratory, result identity, or verified build. Both commands use the same mid-1970s-style operator console and show the existing progressive historical projection while the result grows. The IMP REPORTS and directional line banks identify source IMPs in a 64-position annunciator; AUTO selects the highest-priority observed condition. Once terminal validation passes, the explicitly modern RUN PROOF bank shows the supported application, journey, failover, and cleanup conclusions. There is no separate report route. Failover still requires the manifest, application facts, verdict digest, relay lifecycle and cut acknowledgement, typed alternate journey, complete historical stream, report sources, and cleanup, and it never uses candidate report-line numbers. Control-C stops the exact harness session through its existing cleanup path. Bank selection and alarm acknowledgement affect only the page; the browser does not own the harness and cannot send guest input, switch a relay, signal a process, restart a component, or mutate a result.

When a scenario completes and the operator closes its console, Make validates and selects that immutable result for replay. An interrupted or failed scenario is never selected.

To run and watch in separate terminals, use:

```sh
make LAB_ROOT="$lab" RUN_ID=watch-demo PDP11_BUILD_ROOT="$build_root" run-ncc
make NCC_RESULT="$lab/results/ncc-pdp11-its-coexistence-watch-demo" watch-ncc
```

To inspect a retained result without starting a simulator, run `make view-ncc` for coexistence or `make view-ncc-failover` for application failover. Each target uses the stable external selection, or discovers the newest completed passing result when no selection exists, and fails immediately when a fresh lab has nothing to replay. Both open the same console with different validated result adapters. Override `NCC_RESULT`, `NCC_FAILOVER_RESULT`, `NCC_VIEW_PORT`, or `NCC_WATCH_PORT` when needed; persist an explicit result with `make NCC_RESULT=/absolute/result select-ncc-result` or `make NCC_FAILOVER_RESULT=/absolute/result select-ncc-failover-result`. Interactive TELNET remains a separate foreground terminal surface; the console does not send input or own that controller.

## Read a result

Every smoke creates one immutable directory under `$LAB_ROOT/results`. The manifest records source and repository revisions, tracked-dirty flags, executable and configuration hashes, allocated ports, platform, timestamps, outcome, exit status, and cleanup. Console, protocol, and IMP traces remain beside it.

| Prefix | Distinct structured artifacts |
|---|---|
| `router-oracle-` and `its-linux-` | Application and IMP logs plus manifest |
| `two-its-telnet-` | Sentinel evidence and direct NCC observation stream |
| `pdp11-its-telnet-` | Application and cleanup evidence, receipt binding, and `message-journey.jsonl` |
| `pdp11-its-interactive-` | Application and cleanup evidence plus the strict `interactive-telnet.jsonl` command/result stream |
| `pdp11-its-terminal-` | Historical terminal lifecycle, application evidence when observed, and exact `terminal-session.jsonl` directional bytes |
| `pdp11-its-interactive-failover-` | Version-2 directional terminal stream, relay and cut acknowledgement, direct and alternate journeys, application evidence, and interactive verdict |
| `ncc-alternate-path-fault-` | `receiver.json`, `historical-events.jsonl`, `direct-relay.json`, and `verdict.json` |
| `ncc-line-loopback-` | `receiver.json`, `historical-events.jsonl`, `direct-reflector.json`, and `verdict.json` |
| `ncc-pdp11-its-coexistence-` | PDP-11 application artifacts plus NCC receiver, historical events, and composition verdict |
| `ncc-pdp11-its-application-failover-` | Coexistence artifacts plus relay state, cut state, pre-cut journey, post-cut journey, and failover verdict |

Use the [test plan](test-plan.md) to evaluate a result. A zero process exit without the required application, network, identity, and cleanup evidence is not a pass. Never edit a retained result or write a reevaluated artifact into it; use a fresh temporary output path.

### Retain and prune results

A retained result holds two different kinds of file. Its evidence — the `runtime/run.env` manifest, `outcome.txt`, console and debug logs, and the structured artifacts listed above — is immutable and is never edited.

Its staged guest media is not evidence. The manifest hashes each image when the run stages it, the simulator then writes to that image for the length of the run, and the retained file therefore matches neither its own manifest entry nor the pristine base it was cloned from. It is reproducible working state, and no accepted result cites it. Prune it when the laboratory needs space: remove the staged `rp03.*` images and leave a short note in the run directory recording what was removed and when. Keep `dskdmp.rim`, which the guest does not write and which still matches its manifest entry. Never prune a build receipt: its `*.rk05`, `*.rl01`, and `*.rl02` files are the built PDP-11 guest media that later runs consume through `select-pdp11-build`, so they are a build product rather than staged working state.

Base media stays under `$LAB_ROOT/work`, and [`pins/`](../pins/) records its provenance, so a pruned composition remains reproducible by rerunning it. Preview the tracked helper's exact removal set before changing the laboratory:

```sh
make LAB_ROOT=/absolute/path/to/arpanet-redux-lab prune-media
```

Preview is the default and never deletes. After reading the listing, explicitly apply the same policy with:

```sh
./scripts/prune-media.py /absolute/path/to/arpanet-redux-lab --apply
```

For a nondefault results directory inside the laboratory, pass `--results-root /absolute/path` to the script or `RESULTS_ROOT=/absolute/path` to the preview target. The helper rejects unknown arguments, symlinked roots and result entries, and staged-media changes detected between its scan and removal; it excludes active or incomplete runs and every directory containing a build receipt. Before unlinking any selected file, it writes and flushes `media-pruned.txt` in every affected result; an existing or unwritable note aborts the whole removal without changing media.

Never delete a directory that an ADR or a dated record cites, whatever it contains. Otherwise a smoke-run directory that produced no `outcome.txt` never completed and may be deleted outright, having no verdict to preserve. Build receipts and read-only trace captures have no outcome by design and are not covered by that rule.

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

The accepted direct-route journey contains twelve observations and is complete. Its versioned KA10 trace proves host-106 request ingress, and its versioned IMP11-A trace proves host-176 reply ingress. The separately accepted failover journey contains fourteen observations and stops at missing `boundary:request:8`; it has neither direct-route host input window and remains unchanged. That explicit gap does not weaken the separate application verdict.

## Handle failures and cleanup

Launchers own exact child PIDs and perform bounded cleanup on success, failure, timeout, or interruption. They never use a process name or global kill pattern as ownership evidence.

If a smoke reports an early bind error, rerun it with a new `RUN_ID`; a noncooperating process may have won the unavoidable handoff between port reservation and SIMH bind. If verification reports a source, asset, receipt, or executable mismatch, repair the external laboratory rather than relaxing the check.

On macOS, use the repository launchers instead of upstream wrappers that depend on GNU Screen control-sequence behavior. Project configurations pin simulator peers to IPv4 loopback to avoid an IPv4/IPv6 mismatch with the diagnostic NCP endpoint.
