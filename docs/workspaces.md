# Persistent guest workspaces

## Scope

A workspace preserves saved files on the direct Network UNIX 176 / ITS 106 pair across complete simulator stop and restart. Each start boots fresh processes from a verified saved disk generation and opens the historical Network UNIX terminal. Programs, unsaved editor buffers, logged-in users, TELNET connections, IMP routing state, and packets in transit are recreated rather than resumed.

The existing `make telnet`, deterministic checks, failover compositions, and formal smokes keep their fresh-image behavior. Workspaces use the direct terminal controller and its existing guest-owned TELNET protocol boundary. The browser remains passive.

## Create and use

Prepare the laboratory and a receipt-bound guest build using the [getting-started guide](getting-started.md), then create a workspace once:

```sh
make workspace-create WORKSPACE=personal
make workspace WORKSPACE=personal
```

Names contain up to 64 letters, digits, underscores, or hyphens and start with a letter or digit. Creation refuses an existing name. `LAB_ROOT=/absolute/path/to/lab` selects another external laboratory. Creation uses `PDP11_INTERACTIVE_BUILD_ROOT` or the currently selected guest build; subsequent starts use the build recorded in the workspace even if the laboratory's selected build changes.

Use the guest shell and preserved TELNET client as described in the [runbook](runbook.md#use-interactive-telnet). Save your editor buffers inside the guests. Control-] ends operator input, requests an ITS shutdown, synchronizes Network UNIX, stops every owned simulator, and publishes a new save only after verification and successful cleanup. ITS can require up to five guest minutes to shut down.

Every invocation retains a new result under `$LAB_ROOT/results/pdp11-its-workspace-RUN_ID`. Supply `RUN_ID` when a stable result name is useful. Source, simulator, build-receipt, firmware, topology, or media mismatches reject the operation; existing saved generations are not upgraded implicitly.

## Inspect and roll back

```sh
make workspace-status WORKSPACE=personal
make workspace-restore WORKSPACE=personal WORKSPACE_GENERATION=GENERATION-ID
```

Status verifies the current save and lists the retained generation identifiers. Restore verifies the selected generation and changes only the current pointer while holding the workspace lease. Other generations remain available, including the save that was current before rollback. Restoring a generation never starts a simulator.

## Storage and failure behavior

Workspace data lives under `$LAB_ROOT/workspaces/NAME`, outside Git and the result-media pruning area. `workspace.json` records the originating laboratory, guest build, and input identities. `generations/ID/generation.json` binds the complete seven-file guest media set, its parent generation, and the successful run's shutdown-proof digest. `current.json` selects one generation. Saved generations are never attached to a running simulator; the launcher stages new writable copies inside that run's result directory.

Publication copies and hashes both guest disk sets, flushes the files and directories, renames the complete generation into place, and atomically replaces the current pointer. A partial generation cannot become current. Previous complete saves remain available after copy failures, interrupted publication, or later rollback. APFS uses filesystem clones where available; other filesystems use full copies, so retained saves consume more space.

A failed or interrupted run does not publish its working disks. Its last complete save remains available, and its working media and logs remain in the failed result for inspection. This is recovery to a completed save, not recovery of work since that save or a guarantee against storage hardware failure.

An atomic directory lease excludes concurrent writers and rollback. The wrapper releases it only before simulator launch or after this invocation's own cleanup evidence proves release of its resources. A host crash, uncatchable termination, or missing cleanup evidence can leave the workspace leased. There is no automatic stale-PID reclamation: inspect the retained run with `make diagnose-run RESULT=/absolute/path`, establish that its owned processes have stopped, and recover the lease explicitly. Never remove a lease merely because an old recorded PID is absent or has changed owners.

## Guest shutdown boundary

The controller uses the retained ITS local console to request shutdown and requires a new `SHUTDOWN COMPLETE` observation before stopping the CPU. Network UNIX enters its single-user mode through the simulator's switch register and the guest's `init`. A small original utility, compiled with the guest's own C compiler during startup, leaves `init`, its waiting shell, and itself alive while stopping other guest processes, synchronizing the filesystems, and reporting a run-specific completion token. The controller then stops the CPU and rejects remaining queued RL disk activity.

The original utility is in [`guest/workspace-stop.c`](../guest/workspace-stop.c). It changes no historical kernel or NCP implementation and deletes its temporary executable when invoked. Controller writes remain in the existing sent logs; operator characters retain their separate terminal transcript. `workspace-shutdown.json` records completion for both guests and the owning lease token. Publication additionally requires the proof's manifest digest, matching parent-media identities, zero owned survivors, successful cleanup, and successful exits from both guest simulators.

Full simulator memory checkpoints and persistent failover/NCC compositions require separate decisions and evidence.
