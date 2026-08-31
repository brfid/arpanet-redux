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

The formal topology is ITS host `106` on IMP 6 and Network UNIX host `176` on IMP 62. The controller waits for both modem and host-link states, the ITS console banner, a responsive local ITS command state, a booted PDP-11, and its preserved NCP before capturing application offsets and starting TELNET. Interpret its result against Gate 4H in the [test plan](test-plan.md); `Connection open` or `SKTRACE` without the service job, structured remote `:TIME`, and correlated traffic on both IMPs is a failure.

Set `RUN_ID` to a unique value when a stable result-directory name is useful. Otherwise the Makefile creates a UTC timestamp plus UUID. A collision is an error; a prior result is never overwritten.

## Read the result

Each smoke creates one directory beneath `$LAB_ROOT/results`. Its run manifest records source revisions, tracked-dirty flags, executable and configuration hashes, allocated ports, platform, timestamps, outcome, and exit status. Console, protocol, and IMP traces remain beside that manifest in the external result directory.

The PDP-11 result additionally retains `application-evidence.txt`, `cleanup-evidence.txt`, the run-local attach-only ITS configuration, PDP-11 IMP device trace, and the receipt hash and path. A completed pass has `outcome=passed`, `exit_status=0`, `surviving_owned_processes=0`, and `cleanup.outer-runtime=passed`; the six recorded ports must be free and their cooperative locks absent after exit.

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

## Cleanup and failures

The launcher owns exact child PIDs and performs bounded cleanup on success, error, timeout, or interruption. It does not terminate processes merely because they share a name. An interrupted run should finish its manifest with a failed outcome and release its private sockets and port locks.

If a smoke reports an early bind error, rerun it with a new `RUN_ID`; a noncooperating local process may have claimed a port during the unavoidable handoff between reservation and SIMH bind. If verification reports a revision, asset, or executable mismatch, repair the external laboratory rather than weakening the pin or source-only check.

On macOS, use the repository launchers rather than upstream wrappers that depend on GNU Screen control-sequence behavior. Every configured peer is pinned to IPv4 loopback to avoid an IPv4/IPv6 mismatch with the diagnostic NCP endpoint.

## Promoting source-built ITS media

Before any source-built ITS media becomes an acceptance input, run `build-its`. It performs the clean upstream build and no-op rebuild under one lease, records the clean-tree and recursive-submodule state, and hashes every promoted runtime output. `smoke-two-its` verifies the receipt and boots an independent media copy. The normative application and readiness requirements are in the [test plan](test-plan.md); current progress is reported only in the [README](../README.md).
