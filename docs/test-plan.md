# Test plan

## Purpose

These gates distinguish a genuinely networked vintage application from simulators that merely boot. A pass requires evidence at the highest layer under test and corroborating evidence that the intended lower-layer route carried it.

Current results are reported only in the [README](../README.md). This document is the normative pass/fail specification.

## Common preconditions

Every integration run must:

- verify the exact source revisions, external-asset hashes, build receipts, simulator identities, and project configuration hashes before launch;
- use independent guest-media workspaces and a newly created result directory;
- allocate a private port and control-socket namespace;
- record exact child PIDs and a run manifest before accepting traffic;
- reject simulator bind, transport, and unrecoverable I/O errors;
- finish with bounded cleanup and no surviving owned process, socket, or port lock.

## Gate 1: Source-only repository

The tracked tree must contain no vintage media, firmware, simulator binary, build output, source checkout, or raw log. Indexed files must remain below the configured size limit, and no indexed blob may match a known external-asset digest. The staged denylist may grow but must not silently discard a digest already protected by `HEAD`.

## Gate 2: Router oracle

Start diagnostic NCP hosts `002` and `003`, H316 IMPs 2 and 3, and adjacent IMP 4 with no attached host. Accept only if:

1. Host `002` receives the third echo reply from host `003`.
2. A request to host `004` fails with `Host is not up.`
3. The trace after that request contains the matching regular packet, RFNM behavior where applicable, and type-7 DEAD response from host `004`.
4. Every identity, lifecycle, and cleanup precondition passes.

## Gate 3: Mixed vintage and diagnostic hosts

Start diagnostic NCP host `076`, IMP 62, IMP 6, and KA10/ITS host `106`. Accept only if:

1. ITS reaches its complete system-console banner and a responsive command state.
2. The diagnostic endpoint receives three echo replies from ITS host `106`.
3. Both IMP logs show traffic on the intended host and modem interfaces after the application probe begins.
4. IMP 6 shows the required long-to-short and short-to-long 1822 leader conversions.
5. Every identity, lifecycle, and cleanup precondition passes.

## Gate 4: Two vintage ITS hosts

Start IMPs 6 and 62 before two independent KA10 guests. Host A must identify as octal `106`; host B must identify as octal `176`. Before host `176` opens an application connection to host `106`, require:

1. Both H316 logs report watchdog lights `077400`, showing the modem path is up.
2. Both H316 logs subsequently report watchdog lights `075400`, showing the attached HI2 host link is up.
3. At least 60 seconds elapse after the later modem-up observation, covering the recovered firmware's peer-route hold-down.
4. Both ITS consoles print the complete `SYSTEM JOB USING THIS CONSOLE` banner.
5. Each guest completes local `:TIME`, including time, date, uptime, and return to the DDT prompt.
6. Both controller states are `RUNNING`, and neither simulator is at `sim>`.

Capture the two IMP log offsets immediately before host `176` issues `:NCPTN 106`. Accept the application proof only if:

1. TELNET reports `Open` and does not subsequently report an explicit close or error before proof completes.
2. Host `106` exposes a unique per-run identity that host `176` recovers through the live remote session.
3. A remote `:TIME` response contains the expected time, date, and uptime structure.
4. Both IMP traces contain matching regular traffic and leader conversion after the captured offsets.
5. Every identity, lifecycle, and cleanup precondition passes.

Boot traffic, reset messages, debugger symbol inspection, a live PID, or a bound UDP socket cannot satisfy this gate. `IMP: Interface-reset msg` is telemetry, not a readiness condition.

## Gate 5: Payload anti-bypass

Generate a unique printable-ASCII sentinel. Inject it only through host A's console or guest application, transfer it using guest NCP, and extract it only through host B's console or guest application. The controller must have no operation that copies the payload between guest workspaces.

Accept only if the recovered sentinel matches the original digest and both IMPs record correlated post-start traffic. A test that writes the sentinel into both guest workspaces fails by construction even if its reported digests match.

## Gate 6: Site integration

After the vintage-to-vintage and payload gates pass, the replacement stage must preserve the external contracts in the [architecture](architecture.md): semantic output, artifact identity, status, build-log identity, exact source provenance, reuse fingerprints, validation, and fail-closed publication.

## Fault injection

For each production-shaped topology, force at least one endpoint or IMP to exit after partial startup and force one readiness timeout. Both cases must produce a bounded nonzero result, a failed manifest, and complete cleanup. A result-directory collision and a noncooperating occupied port must fail without overwriting prior evidence.
