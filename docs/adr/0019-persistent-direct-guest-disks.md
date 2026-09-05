# ADR-019: Preserve direct guest disk generations across restarts

- **Status:** Proposed pending real save/restart acceptance
- **Date:** 2026-09-05
- **Decider:** Brad

## Context

The historical terminal makes useful guest work possible, but every invocation stages disposable copies of prepared media. Files created or modified during a session are retained only inside that result; a later ordinary terminal start does not select them. Named persistent workspaces are the selected next step in laboratory usability.

A disk copy taken while a guest is running can omit buffered writes or capture an inconsistent filesystem. Simulator process exit alone does not establish guest synchronization. A saved CPU image also does not by itself establish that every network device, external transport, and peer can resume consistently. The accepted terminal boundary in [ADR-015](0015-character-oriented-historical-terminal.md) remains authoritative.

## Decision

Add an optional named workspace for the direct Network UNIX 176 / ITS 106 composition. Preserve complete disk generations after proved guest shutdown and successful owned-process cleanup. Boot new guest and IMP processes from writable per-run copies of the selected generation. Keep ordinary terminal starts and formal smokes on their existing fresh prepared media.

Each workspace lives outside Git and records its originating build receipt and pinned runtime identities. A generation binds the complete seven-file guest media set, parent, originating run, and shutdown-proof digest. An exclusive directory lease covers launch, shutdown, publication, and rollback. Copy, hash, and flush every file before renaming a complete generation and atomically replacing the current pointer. Retain previous generations. Do not infer lease recovery from an old PID.

ITS must emit a new shutdown-completion observation. Network UNIX must recover its root shell, enter single-user operation through its existing `init`, stop other writers, complete synchronization, and have no pending RL disk activity at CPU stop. An original small utility is compiled by the guest's own C compiler; no historical kernel or NCP code is modified. Publication additionally requires matching parent-media hashes, successful guest simulator exits, a matching shutdown-proof digest, and successful controller and outer-runtime cleanup.

## Alternatives

- Reuse the last result's disks in place. This provides no stable previous save and makes a failed run mutate the only retained state.
- Copy live disks or rely only on simulator exit. Neither proves the guests finished their disk writes.
- Save and restore all simulator memory immediately. This needs separate evidence for device state, attached transports, and coordinated peer recovery; it is unnecessary for saved files across ordinary reboots.
- Add persistent failover and NCC compositions now. The direct pair provides a smaller acceptance boundary. Broader compositions require their own shutdown and restart evidence.

## Consequences

Saved guest files can become durable laboratory work while acceptance runs remain reproducible. The operator saves editor buffers inside the guests and uses Control-] to save and stop. A failed or interrupted operation retains the previous completed save and the failed result; it cannot promise recovery of work since that save. Retained generations consume disk space, with filesystem clones used where available.

Unsaved buffers, executing programs, logged-in sessions, active TELNET connections, IMP routing state, and packets in transit are not resumed. Input changes require a deliberate migration decision. Browser control, persistent failover, automatic stale-lease reclamation, and full memory checkpoints remain separate work.

The [workspace contract](../workspaces.md) owns commands and recovery. [Gate 4L](../test-plan.md#gate-4l-persistent-direct-guest-disks) owns acceptance.

## Evidence and sources

- [ITS LOCK operator documentation](https://github.com/PDP-10/its/blob/0f7d67997f9f5d30208e117e73272031e74f16b9/doc/_info_/lock.order) and the pinned external `src/syseng/lock.156` define the guest shutdown interface; source and media remain external under [NOTICE](../../NOTICE.md).
- [V6 init source preserved by TUHS](https://www.tuhs.org/cgi-bin/utree.pl?file=V6/usr/source/s1/init.c) documents the single-user switch setting and reset path. The exact prepared Network UNIX guest must separately prove that behavior.
- [V6 shell source preserved by TUHS](https://www.tuhs.org/cgi-bin/utree.pl?file=V6/usr/source/s2/sh.c) and the exact guest compiler establish the supported command and compilation interface.
- [SIMH simulator user's guide](https://opensimh.org/simdocs/simh_doc.html) documents simulator SAVE/RESTORE; that generic facility is not evidence of coordinated network resume.
