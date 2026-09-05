# Persistent direct guest disk generations

- **Observed:** 2026-09-05
- **Baseline:** `32319c48507455d2d579a3ae69d2041a249e1c64`
- **Implementation:** generation store `2e68c47685dacc12003bb4bd0150ab02f0f5832c`, operator and guest shutdown `ded54b95c0211c3f7cdecf55ecd081afee48f716`, exact guest-source readback `7ed3d7ac7bac0476e19641b418d8b5be73aad52c`
- **Scope:** Complete saved disks for the existing direct Network UNIX 176 / ITS 106 terminal, with fresh guest and IMP processes on every start

## Findings that shaped the implementation

ITS's normal LOCK shutdown produces a meaningful completion observation before simulator exit. The prepared local console can enter BUGDDT immediately after that observation; blindly sending further LOCK or logout commands then waits in the wrong program. Pacing the confirmation is also necessary because LOCK resets its terminal input after printing its question. External probes `workspace-shutdown-probe-01` through `-04` established the exact sequence; `-04` completed both guest shutdown primitives and cleanup.

The actual Network UNIX shell uses `chdir`, has no `exec` builtin, and its C compiler produces `a.out` without a modern `-o` option. The original stop helper runs beneath init's single-user shell, keeps that shell and init waiting, terminates other processes, unlinks its temporary executable, synchronizes twice with intervening waits, emits a unique completion token, and remains idle until the controller stops the CPU. The controller rejects queued RL activity and requires both simulator exits to succeed before publication.

Development results `pdp11-its-workspace-persistence-dev-01` through `-05` rejected unsupported guest upload, shell, compiler, library, or temporary-file assumptions before saving. `-06` completed ITS shutdown but rejected a retained guest TELNET command prompt instead of a UNIX shell. Leaving that client through its normal `bye` command corrected the boundary. Every failed attempt retained the initial save and released its lease only after proved cleanup.

Clean result `pdp11-its-workspace-persistence-accepted-01-20260905` at `ded54b9` exposed intermittent dropped console characters during source upload. Compilation rejected the damaged file and no generation was published. Revision `7ed3d7a` slows the transfer and reads the complete source back from the guest before compiling; a source test rejects even a one-character change that would still compile. Compiler success alone is not source-identity evidence.

## Saved files and repeated restarts

All result names are relative to `/Users/brf/src/arpanet-redux-lab/results/`. The named workspace is `persistence-proof-20260905`. Files were created, edited, and read only through the real guest interfaces: `/usr/wsproof` through the UNIX shell, and `SYS;WSPROF TEXT` through ITS TECO and DDT `:PRINT` reached over the preserved UNIX TELNET client.

Development `pdp11-its-workspace-persistence-dev-07` created and reread `WORKSPACE_UNIX_A` and `WORKSPACE_ITS_A`, completed guest shutdown, stopped every simulator, and published `fdcb37a6b04544bfaf61cc87dfd0d960` from seed `4597a42cd5d94dc388d9aa5bb3e3bacf`. Development `-08` booted that save, recovered both A values, obtained a new remote `:TIME`, modified and reread both B values, and published `c1fd93c59cd140e8b6a994508db7ed50`. These are explicitly development runs with dirty checkout records, not clean release repetitions.

During `-08`, UNIX `icheck` found no duplicate or missing blocks. `dcheck` reported six directory-link-count discrepancies. Comparing the original seed against the saved root image found exactly the same six inode, entry-count, and link-count triples, so this is retained prepared-image state rather than new save damage. The base-reconstruction note's clean filesystem result concerns its different reconstructed base and does not silently validate this older selected build. The seed and completed saves also contained no allocated zero-link inodes. No filesystem repair was performed.

Two subsequent runs at clean `7ed3d7a` exercised the verified source upload and another complete modification/restart cycle:

| Result | Guest observations | Published generation |
|---|---|---|
| `pdp11-its-workspace-persistence-accepted-02-20260905` | Recovered both B files after the interrupted-publication test, obtained remote `:TIME`, changed and reread both C files, and saved successfully | `a6295105e891415ba7e7b5aa51f3ad68` |
| `pdp11-its-workspace-persistence-accepted-03-20260905` | Recovered both C files and obtained remote `:TIME` through a newly opened guest connection, then saved successfully | `595da7cd466c47279541c598bc1de8fd` |

Strict terminal readback recovered both B values in the first clean run even though neither value appeared in that run's operator input. Both C values were recovered in the second clean run without any sentinel value appearing in operator input. This distinguishes recovered guest output from input echo. Every completed generation verified all seven files, the originating result's starting hashes against its parent, matching shutdown proof and digest, successful guest exits, successful controller and outer cleanup, and a completed terminal stream. The original seven prepared media files still matched the seed hashes exactly.

The first clean terminal stream has SHA-256 `51276338099c7cb24cda1ff867b86681e6ff08159c61dcaaf39af93c85c47ef9`; the second has `cdac4db4f46c9b186374cb61f69a748b2a038a04d0ab3875d5ba1541778ffffa`. The complete readback report `completed-verification.json` has SHA-256 `7321ee314917b872d1898d821e6dc0ae33204a5707ff680171c1deb5a9075232`.

## Failure recovery and boundaries

While `-08` held the workspace lease, a second open and a rollback both failed before modifying the workspace. A separate exact-child experiment at `ded54b9` copied real stopped guest media, then killed only its own publication child with SIGKILL after three of seven files. Current generation `c1fd93c59cd140e8b6a994508db7ed50` remained selected and all seven of its hashes verified. The incomplete `.pending-bf6c424f33724176bbebfcaf0dfaaee8` directory stayed unselectable, and the lease remained present. The parent had just reaped its own publication-only child, which launched no simulators, and explicitly released that token; this is not automatic stale-PID recovery.

The interrupted-publication report has SHA-256 `29d5085a57d745dba7426cf8a652b05528d03a1a0dd52df36ff8cc8ba1a4fdc3`. The public restore command subsequently selected the verified A generation, status reread it and listed all five complete generations, and restore selected the latest C generation again. Both selections released their leases; all generations remained available. `rollback.log` records those operations.

## Verification and limits

The full suite passes 426 source tests and the shell suite. New coverage includes complete disk sets and parent binding, reopened storage, rollback, tampered and symlinked media, partial copy and pointer-publication failure, catchable copy interruption, lease exclusion and token ownership, strict metadata and shutdown records, cleanup uncertainty, source-upload corruption, shell recovery, required guest completion, and queued disk activity. The full-history source guard passes.

The ordinary fresh-image regression `pdp11-its-telnet-workspace-regression-20260905` passed at clean `7ed3d7a`: the preserved client executed remote `:TIME`, both IMPs carried correlated traffic, the direct journey had all twelve observations and state `complete`, and both cleanup layers passed with zero owned survivors. No workspace environment or saved generation supplied that run's media.

Raw results, original exploratory drivers, source-test output, directory-link comparison, concurrent-refusal logs, rollback log, and interrupted-publication evidence remain under the external laboratory, with review artifacts in `reviews/workspaces-20260905/`. No media, executable, historical source, or raw log is published in Git. The [workspace contract](../workspaces.md) owns current operation, [ADR-019](../adr/0019-persistent-direct-guest-disks.md) owns the decision, and [Gate 4L](../test-plan.md#gate-4l-persistent-direct-guest-disks) owns acceptance. Full memory/session suspend, work since the last complete save, storage hardware failure, automatic stale-lease recovery, and persistent NCC/failover compositions are outside this result.
