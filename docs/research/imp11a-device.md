# DEC IMP11-A device model

**Status:** Device model implemented and verified in isolation; the real NOSC `green/unix` kernel now boots to a login shell against it, with the NCP daemon binary and `/dev/ncpkernel` in place. The daemon itself has not yet been started.

This continues the plan in [PDP-11 Network UNIX as the first heterogeneous host](pdp11-network-unix.md). It records the register-level design and the verification performed so far for the new IMP11-A device.

## Location

The device lives in a local branch (`imp11a-device`) of a clone of [`open-simh/simh`](https://github.com/open-simh/simh) at `a1f57fa3738ed31148d31126ba1a7278ff845c6d`, outside this repository under the laboratory result root, consistent with every other simulator source in this project. It is not yet pushed to a public fork or pinned in `pins/sources.lock.toml`; publishing a fork is a separate decision, not yet made.

New or changed files, all under `PDP11/` except the last:

- `pdp11_imp.c`: the device (new).
- `pdp11_defs.h`: two new interrupt slots, `INT_V_IMPRX`/`INT_V_IMPTX` at BR4 positions 20/21, the first free positions in that priority level's bitmask.
- `pdp11_sys.c`: registers `imp_dev` in `sim_devices[]`.
- `makefile`: adds `pdp11_imp.c` and `H316/h316_udp.c` to the `PDP11` build list, and adds `-DVM_IMPTIP` to `PDP11_OPT` (the shared UDP transport's entire body is conditional on that macro, which is otherwise only set by the H316 target).

## Register map

Reconstructed from the DEC IMP11-A technical manual and from the register-level behavior of the SRI/NOSC "imp11a" kernel driver in the preserved Network UNIX V6 source (register addresses, bit positions, and hardware behavior are historical facts about the physical device, not the driver's expression; no driver source is reproduced here).

Fixed base `0172410`, 12 words (`030` octal / 24 bytes), non-autoconfigured:

| Offset | Register | Notes |
|---|---|---|
| 0 | OWC | output word count, two's-complement |
| 2 | SPO | output start address (low 16 bits) |
| 4 | OSTAT | output status |
| 6 | OMAINT | output maintenance |
| 10-16 | (unused) | real hardware does not decode this range |
| 20 | IWC | input word count, two's-complement |
| 22 | SPI | input start address (low 16 bits) |
| 24 | ISTAT | input status |
| 26 | IMAINT | input maintenance |

Two fixed interrupt vectors, `0124` (output) and `0274` (input). These are not the standard DEC `vec, vec+4` pair that Open SIMH's generic multi-vector DIB assignment loop assumes for a device with `vnum > 1`, so the DIB's `vec` field is left `0` (suppressing that loop) and `imp_reset()` writes `int_vec[IPL_IMPRX][INT_V_IMPRX]` and `int_vec[IPL_IMPTX][INT_V_IMPTX]` directly.

Status-register bits (shared layout, some read-only in one half): `GO` (start), `RST` (self-clearing reset), `IENAB` (interrupt enable), `XMEM` (2-bit extended address, giving 18-bit Unibus DMA addressing from the 16-bit SPO/SPI plus these bits), `OENDMSG` (output: this buffer ends the message), `WRTENBL` (input: enable receive), `HMASRDY` (input: pulse to tell the peer this host is up), `MASRDY` (input, read-only: peer/IMP reports ready), `ENDMSG` (input, read-only: a full message was received), `DONE` (output, read-only: transfer complete), `TIMOUT` (read-only: transfer timeout, not yet driven by any real fault condition).

## Wire protocol

The device reuses the H316 device family's existing UDP transport (`H316/h316_udp.c`: `udp_create`/`udp_send`/`udp_receive`), unchanged, exactly as the KA10 NCP-mode IMP device (`PDP10/kx10_imp.c`) already does to reach an H316 IMP's host port. This is the same shared component the two-ITS gate depends on, MIT-style licensed with a no-name-in-advertising clause, already vendored into both `ka10-simh` and `open-simh`.

The actual UDP payload is a `UDP_PACKET` struct: `magic` (`"H316"`, `htonl`), `sequence` (`htonl`, per-link monotonic), `count` (`htons`, word count of the data that follows), then `count` data words (`htons` each). The device-level convention layered on top, shared with `h316_hi.c` and `kx10_imp.c`, is that the first data word is a flags word (`PFLG_FINAL` = 1, `PFLG_READY` = 2) and the rest is the actual message content. None of this needed to be invented; it was fully determined by reading the existing shared code before writing anything new.

`h316_udp.c`'s "Connect=" UDP mode means each link behaves like a connected socket: it only accepts datagrams from the exact configured remote host and port. This tripped up the first verification attempt (see below) and is worth remembering for any future test harness against this device.

## Verification performed

No guest driver has run against this device yet. What has been verified is that a real CPU-executed bus write (not a debugger register poke, which bypasses the write handler entirely) drives the device correctly, in both directions, using hand-assembled PDP-11 machine code deposited into memory and executed with `step`:

- **Output:** `MOV #imm,@#addr` instructions set SPO/OWC then wrote OSTAT with `GO|OENDMSG|IENAB`. The device read the guest memory word via `Map_ReadW` and transmitted it. The resulting UDP datagram was captured and decoded by hand: magic, sequence (0, first packet on the link), count (2), and both data words (flags `3`, and the exact guest memory content) all matched exactly.
- **Input:** a hand-built `UDP_PACKET` (flags `PFLG_FINAL`, two data words) was sent to the device's attached port from a source bound to the exact configured remote port (required by the "Connect=" filtering above). Guest instructions then wrote SPI/IWC/ISTAT with `GO|WRTENBL|IENAB`. The device's synchronous re-check on that write (not a scheduled poll) picked up the already-queued datagram immediately, `Map_WriteW`'d both data words into the exact requested guest memory addresses, and set ISTAT to `IENAB|ENDMSG`.

The build also passes Open SIMH's own `RegisterSanityCheck` self-test.

## Open questions for guest testing

- Whether the guest ever chains multiple output buffers into one message. The current device treats every buffer with `GO` set as one complete transmission; the historical driver's buffer-chaining behavior (continuation via a buffer-list, referenced in driver comments as tied to a `b_blkno`-style field) is not modeled.
- The exact contract for a short or partial input completion: how much of IWC the guest expects back when fewer bytes arrive than requested. The current device reports the number of words actually delivered.
- `TIMOUT` and the general error-summary bit are defined but nothing yet drives them; the real driver's NXM/error handling has not been exercised.
- No `DEBTAB` (`SET IMP DEBUG`) yet, so diagnosing a future guest-boot failure will need either temporary instrumentation or that gap closed first.

## V6 base: reproducing the pristine root filesystem

The official [SIMH UNIX V6 software kit](https://sourceforge.net/projects/simh/files/Software%20Kits/UNIX%20v6%20for%20the%20PDP-11./) (Caldera/Ancient-UNIX licensed) boots to a login prompt on this same Open SIMH build unmodified: `SET CPU 11/34`, `SET CPU 128K`, `SET CPU NOAUTOCONFIG`, attach its four RK05 images, `BOOT RK0`, then `unix` at the `@` prompt. This confirms the IMP11-A changes above do not disturb the baseline PDP-11 simulator.

Reproducing that same root/source/doc filesystem set from the raw historical distribution tape (rather than the prebuilt kit) turned out to need a different method than the one documented method assumes. The [`eblanton/unix-v6-install`](https://github.com/eblanton/unix-v6-install) reference (`94df669009311ce0e693aa326142732f77796813`, no declared license, used here only as a methodology reference, not copied into any repository) drives this via an in-simulator `tmrk` meta-command that does not exist in Open SIMH; every attempt using it hangs indefinitely on an unmatched `expect "="`.

Its own tape-processing tool (`v6enb`'s `enblock`, converting a raw historical tape image into SIMH's `.tap` container format) still works once its 2001-era C is coaxed past current clang's default-error implicit-function-declaration checks (`-Wno-error=implicit-function-declaration -Wno-error=implicit-int`). The resulting `.tap` file is exactly 12,100 fixed 512-byte tape records plus a tape mark: the first 100 are a raw bootstrap area, then three 4,000-record filesystems back to back (root at tape offset 100, `/usr/source` at 4,100, `/usr/doc` at 8,100). Because a SIMH `.tap` record is just a length-prefixed byte range, those three filesystems can be extracted directly, at the host level, straight into zeroed RK05-sized target files, with no PDP-11 execution involved at all. That reproduced root filesystem boots and logs in identically to the official kit (`rkunix`, root, no password) with the historically correct embedded clock (`Fri Oct 10 12:29:44 EDT 1975`).

This matters here because it is the same technique the remaining work depends on: getting the prelinked `green`/`green47` kernels and the NOSC NCP daemon and applications onto a filesystem this simulator can boot does not require rebuilding anything from source (they are already built), only correctly placing existing bytes.

## Injecting files directly into a V6 filesystem image

Getting the prelinked `green/unix` kernel and the NCP daemon onto a filesystem needed a way to place already-built binaries directly, since there is no source to compile in place and no working in-simulator tape-write path. A minimal V6 filesystem injector implements exactly the on-disk structures in [ino.h/filsys.h](#register-map)'s sibling headers: superblock free-list allocation (including the classic V6 trick where the block about to be handed out is first read as the next free-list chunk), inode allocation by linear scan for `i_mode == 0`, small (direct-block) and large (single-indirect) file writes, and directory-entry insertion.

The first version had a real bug, caught by testing against a live boot rather than only re-reading the bytes with the same tool that wrote them: reusing a deleted (`ino == 0`) directory slot beyond the directory's current logical size wrote valid bytes that the kernel's own directory scan, bounded by the inode's `size` field, never reached. A file placed this way was invisible to `ls`/`open` even though it was genuinely on disk. Fixed by tracking size explicitly and only ever treating a slot as reusable when it falls within `[0, size)`; anything past that must grow `size` by exactly one 16-byte entry, whether or not it also requires a new block.

## Booting `green/unix` under this device

Two more facts had to be pinned down before a boot attempt meant anything, both by disassembling the actual `green/unix` a.out binary rather than guessing, since NOSC's own kernel-config table was not preserved in the archive:

- **`/dev/ncpkernel`'s major number.** `cdevsw` (found in the binary's data segment via its own symbol table entry) is an array of `{open, close, read, write, sgtty}` function-pointer quintuples. Scanning it for the address of `_ncpopen` (the daemon-facing entry point in `ncpio.c`, not the lower-level `_impopen`/`_impread` internal to the driver) lands at index 25, i.e. major **5** — confirming the number already recorded in [pdp11-network-unix.md](pdp11-network-unix.md) independently.
- **Root and swap devices.** The `_rootdev`/`_swapdev` data symbols decode directly to `(1,0)` and `(1,1)`: `bdevsw` entry 1 is the RL driver (`_rlopen` at that slot), so root and swap are both on RL, unit 0 and unit 1 respectively.

Booting the resulting image over Open SIMH's `RK0` failed immediately (`panic: iinit`, `err on dev 1/0`) because attaching the very same bytes as `RK0` presents major 0, not the major-1 RL device the kernel expects — a software-level dispatch mismatch, not a data problem. Attaching as `RL0` instead got further but failed silently at the boot-ROM prompt (`@`) for every filename, including the already-known-good `rkunix`: the disk content's boot block (byte-identical to the RK-formatted image) contains RK-specific low-level disk I/O, which does not work when the CPU is executing it against an RL-attached device. The fix, taken directly from the `eblanton/unix-v6-install` `pristine-rl` script's own logic (copying an RL-native boot block over before use), was to overwrite block 0 with the boot block from the real RL02 reference image (Tim Shoppa's `unix_v6.rl02`, TUHS-hosted, methodology reference only). That RL bootstrap prompts with `!`, not `@`. With that block 0 and a second RL01 unit attached for swap (`err on dev 1/1` without one — `swapdev`, not root, once root itself was reachable), `green` boots cleanly to `login:` and root logs in.

The confirmed-present, confirmed-correct result on a live boot: `/dev/ncpkernel` (`crw-rw-rw- root 5, 0`), `/green` (42,988 bytes, matching the source file exactly), and `/usr/net/etc/Largedaemon` (17,648 bytes, matching exactly). This is the actual NOSC-built kernel — not a synthetic test program — reaching a shell with the new IMP11-A device attached, root and swap on RL, and the NCP daemon binary in place at the path its own `smalldaemon` launcher (recovered by reading its embedded strings) expects.

## Next steps

1. Start `Largedaemon` (or the simpler `smalldaemon` wrapper) against the live `/dev/ncpkernel` and observe what the real driver actually does with the device's registers — this is the point at which the open questions above (buffer chaining, partial-input contract, error handling) get real answers instead of guesses.
2. Wire this into the two-IMP topology (a second `green/unix` instance, or the existing ITS pair) for an actual heterogeneous-host application proof, following the smoke-test recipe in [pdp11-network-unix.md](pdp11-network-unix.md).
3. Decide whether and how to publish the device (a public fork of `open-simh`, mirroring how the KA10 fixes live in `github.com/brfid/ka10-simh`) now that it has a real guest boot behind it.
