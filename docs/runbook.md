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

Set `RUN_ID` to a unique value when a stable result-directory name is useful. Otherwise the Makefile creates a UTC timestamp plus UUID. A collision is an error; a prior result is never overwritten.

## Read the result

Each smoke creates one directory beneath `$LAB_ROOT/results`. Its run manifest records source revisions, tracked-dirty flags, executable and configuration hashes, allocated ports, platform, timestamps, outcome, and exit status. Console, protocol, and IMP traces remain beside that manifest in the external result directory.

Interpret evidence using the [test plan](test-plan.md). A successful process exit without the required application and IMP evidence is not a pass.

## Cleanup and failures

The launcher owns exact child PIDs and performs bounded cleanup on success, error, timeout, or interruption. It does not terminate processes merely because they share a name. An interrupted run should finish its manifest with a failed outcome and release its private sockets and port locks.

If a smoke reports an early bind error, rerun it with a new `RUN_ID`; a noncooperating local process may have claimed a port during the unavoidable handoff between reservation and SIMH bind. If verification reports a revision, asset, or executable mismatch, repair the external laboratory rather than weakening the pin or source-only check.

On macOS, use the repository launchers rather than upstream wrappers that depend on GNU Screen control-sequence behavior. Every configured peer is pinned to IPv4 loopback to avoid an IPv4/IPv6 mismatch with the diagnostic NCP endpoint.

## Promoting source-built ITS media

Before any source-built ITS media becomes an acceptance input, run `build-its`. It performs the clean upstream build and no-op rebuild under one lease, records the clean-tree and recursive-submodule state, and hashes every promoted runtime output. `smoke-two-its` verifies the receipt and boots an independent media copy. The normative application and readiness requirements are in the [test plan](test-plan.md); current progress is reported only in the [README](../README.md).
