# Harness design

## Responsibility

The harness provides isolated resources, exact process ownership, input identity, bounded observation, durable evidence, and complete cleanup. The [test plan](test-plan.md) defines a pass; the [runbook](runbook.md) documents supported commands.

Shell launchers target `/bin/sh` on macOS and Linux. Committed Python controllers require Python 3.11 or newer and use the standard library.

## Per-run isolation

Each run atomically creates a new result directory and a mode-0700 control-socket directory. Existing paths are errors, never overwrite targets. Guest simulators receive distinct media copies.

The reservation helper selects ephemeral UDP port numbers and holds wildcard sockets on each number until launch. It also retains per-user cooperative locks through the run. SIMH cannot inherit pre-bound descriptors, so the helper must release its sockets immediately before simulator bind. A noncooperating process can win that short handoff; an early bind error rejects the run.

Topology-specific `BRFID_*_PORT` variables carry leased values into SIMH through native `%NAME%` expansion. The harness never rewrites a tracked configuration to assign a port.

The pinned `linux-ncp` client creates `/tmp/client.PID` for its short-lived reply socket. The harness records the exact client PID and removes only that path. Moving the socket into the private namespace requires an upstream change.

## Process ownership

Every daemon, simulator, relay, and bounded client is a direct child registered by exact PID. Process names and global kill patterns are not ownership evidence.

Python controller-side ownership is split by responsibility across ordinary `ncc` modules. `ncc.harness_process` owns PTY and IMP processes plus liveness and aggregate shutdown; `ncc.harness_manifest` owns validated manifest append, strict reads, and streamed artifact hashing; `ncc.harness_config` owns the shared UDP-port environment contract and host-106 attach-only configuration; and `ncc.harness_imp` owns recovered-IMP log readiness, watchdog interpretation, and modem-message correlation. `ncc.pdp11_its_harness` owns the shared Network UNIX boot, prompt, evidence, observation-configuration, and cleanup-record behavior. The two-ITS, direct PDP-11, failover, and interactive controllers all import these owners normally; none loads a sibling production script as a module.

Cleanup is idempotent. It sends `TERM`, waits for a bounded interval, sends `KILL` only to a surviving owned child, removes known sockets and media copies, releases port and build leases, and finalizes the manifest. Startup, probes, controller operations, and cleanup all have deadlines.

Failed PTY or IMP launch attempts close their opened descriptors and files, including when manifest recording fails after process creation. Aggregate controller shutdown visits every owned simulator even if one stop or close raises an exception. `cleanup-evidence.txt` adds `cleanup_status=passed|failed` and, on failure, bounded `cleanup_error` text; the survivor-count completion marker is written last, and zero process survivors alone cannot override a recorded cleanup error. Controller shutdown and its cleanup record are protected from repeated catchable signals. The shell exit handler likewise ignores further HUP/INT/TERM while finishing its first termination, preserving the original status. Successful releases clear their live ownership entries, so a failed cleanup retry cannot reuse a stopped PID or remove a subsequently acquired build lease or control directory.

An owned background application controller has a 60-second shutdown allowance, recorded as `process.controller.shutdown-grace-seconds`, because it sequentially stops up to two guest simulators and four IMPs before writing its cleanup evidence. Leaf processes retain their five-second allowance. The terminal-owned NCC operator allows 90 seconds for the whole launcher, covering controller shutdown, auxiliary processes, and the port lease. If the runtime must forcibly kill a controller, it records failed cleanup with a `controller-cleanup:PID` identifier; the controller's disappearance cannot prove release of its delegated simulator resources.

Fault instruments accept packets only from the two leased simulator endpoints. A cut relay forwards both directions until its acknowledged fault boundary, then keeps both ports bound while counting and dropping traffic. A loopback reflector instead returns each valid datagram unchanged to its sender. Each instrument writes its phase boundary, per-direction counters, and unexpected sources before cleanup releases its PID.

The public fault and loopback launchers select explicit scenario profiles over one shared line-scenario lifecycle. That lifecycle owns input verification, the ten-port topology allocation, process order and readiness, evidence capture, transport checks, and cleanup; each profile retains its own scenario identity, instrument, evaluator option, artifact and process names, failure text, and final claim. Each result manifest hashes both its public launcher and the shared lifecycle so the complete orchestration identity remains attributable.

The application-failover controller alone writes its run-local cut request. The relay acknowledges that request atomically and records the same fault timestamp in its state and terminal result. Browser processes have no path to this control channel.

## Input identity

Diagnostic NCP tools are force-built under an external atomic lease. A receipt binds the pinned source revision and executable hashes. Smokes reacquire the lease, verify the receipt, and retain it until cleanup.

Simulator checks require embedded source revisions. Manifests hash the exact executables, configurations, firmware, generic IMP configuration, shared topology, asset manifest, and build receipts used by the run.

The ITS receipt binds a clean pinned checkout, recursive submodule state, a current `make EMULATOR=pdp10-ka its` target, a successful no-op rebuild, and the bootstrap and runtime-disk hashes. The two-ITS smoke verifies the receipt and boots independent media copies.

The PDP-11 receipt binds the base images, staged TELNET and NCP-daemon sources, intermediate and final media, build logs, builder hashes, Network UNIX revision, IMP11-A revision, and PDP-11 executable. A smoke revalidates every path and digest before copying final media into its run.

## Persistent disk workspaces

The optional direct terminal workspace selects verified saved disks as the source for the same per-run isolation. `ncc.guest_workspace` owns complete generations, content verification, atomic publication and selection, and exclusive workspace leases. `scripts/workspace.py` verifies the pinned runtime and retained build receipt, launches the existing terminal, and permits publication only after this invocation's parent-media identities, guest shutdown proof, simulator exits, and both cleanup layers agree. `ncc.workspace_shutdown` owns the guest-console shutdown sequence; the original `guest/workspace-stop.c` is compiled inside Network UNIX and stops writers before synchronization.

Saved generations are never attached in place. A failed run retains its working media and leaves the current generation unchanged. Missing cleanup evidence leaves the workspace leased; an old PID alone never authorizes reclamation. These records provide disk-save provenance, not live process, TELNET, or IMP memory state. [Persistent guest workspaces](workspaces.md) owns commands, storage, and the recovery boundary.

## Controller boundary

Controllers distinguish guest execution from simulator prompt and process existence. They drive only known child consoles, record controller writes separately, and do not use a live PID or bound socket as guest readiness.

Application controllers wait for configured modem and host-interface readiness, guest console readiness, and route hold-down before capturing probe offsets. Application assertions use only bytes written after those offsets. Cleanup sends WRU only to a running simulator, sends `quit` only at its prompt, and sends neither to a stopped child.

The direct PDP-11 controller also checks all its launched simulator handles while waiting for a console, IMP log or watchdog condition, or settling interval. A peer exit aborts the wait with that component's exit status; unlaunched guests do not count as failed. Shutdown disables this readiness check before deliberately stopping peers. The existing readiness markers, timeout budgets, boot order, route hold-down, and acceptance windows remain unchanged. This watch covers the direct controller's four simulators, including when that controller is composed with NCC; other controllers and outer auxiliary processes retain their existing readiness checks.

The heterogeneous controller reuses the established KA10 process, PTY, watchdog, and packet-correlation primitives. It boots ITS and Network UNIX in the required order, starts the preserved NCP, opens a bounded TELNET transaction, and records structured application evidence.

The foreground TELNET controller has two explicit modes. The deterministic mode automatically opens the guest client and frames printable commands at the ITS DDT prompt. The human mode stops at the Network UNIX shell and relays bounded seven-bit characters while the guest client owns TELNET behavior. The human adapter blocks the configured octal-034 simulator WRU, reserves Control-] for cleanup, restores local terminal attributes in a `finally` boundary, safely renders output controls, and retains raw directional bytes separately from its filtered human projection. It never hands a simulator PTY directly to the operator.

After application proof, the direct Gate 4H controller fixes both H316 trace-window ends and both live host input-trace ends before invoking the typed journey adapter. The strict versioned KA10 parser pairs each receive assembly with the `DATAI` value consumed by ITS, reconstructs only valid bits, reverses only the canonical long-leader conversion, and requires exactly one full message equal to the IMP 6 request. The strict versioned IMP11-A parser reconstructs only complete post-store DMA groups, validates every 16-bit network-to-PDP-11 word conversion and final count, and requires exactly one full message equal to the IMP 62 reply. Direct trace evidence and harness-derived peer delivery remain separate, and independent simulator ticks are never compared. The reducer observes both guest-ingress boundaries and requires the direct journey to be complete. The controller reads the terminal stream back and records its digest and diagnosis; the sidecar does not gain application-gate authority. Other compositions retain their own accepted windows until separately rerun with this evidence.

## Evidence boundary

The manifest records source and repository revisions, dirty-state flags, executable and configuration hashes, ports, platform, timestamps, outcome, exit status, and cleanup. Structured sidecars retain application facts, direct network observations, reducer support, relay or reflector counters, and typed journey evidence according to the composition.

Evaluators consume declared structured inputs, not arbitrary raw logs. They require the formal application or network claim, exact identities, consistent digests, supported reducer output, successful owned controllers, and both cleanup layers. One evidence plane cannot fill another plane's missing fact.

Raw console, protocol, receiver, and IMP traces remain in the external result directory. The source-only suite covers parsers, reducers, contracts, lifecycle failures, and tempting false positives with synthetic fixtures.

## Launcher termination records

After a launcher creates `runtime/run.env`, the shared shell runtime retains its own error messages in `runtime/launcher.stderr.log`. Explicit terminal failures use `brfid_fail`; otherwise silent external checks use `brfid_require` with a description and the unchanged command arguments. The latter is only for external commands, since calling a shell function inside a conditional would suppress its `errexit` behavior. Helper errors can be handled successfully by their caller, so the error log alone never establishes the final failure cause. Controller standard input and output remain attached as before, including foreground terminal sessions.

The direct PDP-11 launcher creates the new result and manifest before resolving input directories, acquiring the build lease, or verifying the receipt and simulators. Those preflight failures now retain a stage and terminal record. Usage errors, a refused result collision, an unwritable result, and Make prerequisites that fail before invoking the launcher remain terminal-only; no refused existing result is modified.

Additive `progress.launcher.N` and `progress.controller.N` manifest fields retain bounded printable stage descriptions in each writer's increasing sequence. Controller waits name the console pattern, log marker, watchdog devices, or settling interval and its existing timeout. `failure.controller` retains the stage, awaited condition, exception type, and failure text independently of launcher failure and cleanup. The direct launcher mirrors controller progress to its terminal through an inherited descriptor while retaining the normal controller logs. These are modern execution observations, never a historical readiness or application claim. A last recorded wait does not prove that the run is still active; old runs without these fields remain unknown.

The format-1 manifest has these additive terminal records:

| Field | Meaning |
|---|---|
| `termination.kind` | `exit` or an explicitly handled `signal` |
| `termination.signal` | `HUP`, `INT`, or `TERM`, present only when that launcher trap ran |
| `termination.exit-status` | Launcher status before the exit handler attempts cleanup |
| `failure.reason` | Explicit terminal failure description, handled signal, or an honest fallback when the cause was not recorded; present only for failed runs |
| `cleanup.runtime.attempts` | Number of actual outer-runtime cleanup attempts; repeated calls after success do not add attempts |
| `cleanup.runtime.exit-status` | Final cleanup attempt's result: `0` for success, `1` for failure |
| `cleanup.runtime.failed-resources` | `none`, or space-separated resource identifiers for failures in that final attempt |

The resource identifiers name owned children, the port-lease helper, known socket paths, the private control directory, lease files, or the exclusive lease. Cleanup continues after an individual failure. A failed attempt can be retried; the final status describes the final attempt, and earlier error messages remain in the log. These are retained observations, not current ownership or liveness evidence. Existing scenario-owned `cleanup.outer-runtime` and `cleanup.completed` records remain available to their evaluators and must agree with the final cleanup result.

The exit handler preserves a nonzero launcher status. If the launcher exits zero but cleanup fails, the handler exits one and records a failed run. A manifest-write failure also prevents a zero exit without replacing a prior nonzero exit status. Failure descriptions are limited to 1,024 printable ASCII characters, replacing other bytes with `?`, so error text cannot inject additional manifest records. Raw helper messages remain in the separate log. Manifest initialization claims ownership only after creating a new file; refusal of an existing manifest cannot append a terminal block to that file.

Failures before result/manifest creation remain terminal-only. An uncatchable kill, host crash, or inability to write records can leave an unfinished run; missing records never prove a handled signal or completed cleanup. An exit status such as `130` alone is not a recorded interrupt. These records describe the modern launcher and confer no historical application, packet, or NCC authority.

## Retained-run diagnostics

`ncc.run_diagnostics` reads fixed run-local harness files into an in-memory diagnostic; `scripts/diagnose-run.py` provides text and version-1 JSON output. It keeps the runtime outcome, controller outcome, recorded checkpoints, and two cleanup layers distinct. It neither revalidates a gate nor observes current process or network state. A controller pass cannot override an outer-runtime failure, absent terminal records cannot distinguish an active run from an interrupted one, and absent cleanup evidence cannot prove resource release.

Reads are bounded and restricted to regular files; symlinked inputs, invalid or duplicate fields, unsupported manifest versions, incompatible terminal records, and contradictory cleanup evidence are reported as problems. An unfinished final manifest record can be ignored for checkpoint inspection but cannot produce a completed diagnostic. Input byte ranges and digests identify the exact snapshots read. Error-log tails remain uninterpreted and the text renderer escapes control characters. The report does not load paths from a manifest, execute a recorded command, inspect a guest image, write a result, or acquire NCC verdict authority. See the [runbook](runbook.md#diagnose-a-retained-run) for usage and exit semantics.

## Repository guard

`check-source-only.py` rejects large indexed blobs, known media names and formats, and content matching protected external-asset digests. Staged mode reads candidate files and the candidate manifest from the index and prevents silent denylist shrinkage relative to `HEAD`. Complete-history mode checks material that was committed and later deleted.

See [`NOTICE.md`](../NOTICE.md) before publishing derived material. Third-party inputs and raw results remain in the external laboratory.
