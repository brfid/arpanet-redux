# DEC IMP11-A device model

**Status:** Device model implemented and verified in isolation; not yet tested against a live guest driver.

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

## Next steps

1. Assemble a bootable RL01 (or configured boot device) V6 base and splice in the NOSC network kernel and daemon per the smoke-test recipe in [pdp11-network-unix.md](pdp11-network-unix.md).
2. Boot the real `green/unix` kernel against this device and let its actual driver, not a synthetic test program, exercise the register contract.
3. Decide whether and how to publish the device (a public fork of `open-simh`, mirroring how the KA10 fixes live in `github.com/brfid/ka10-simh`) once it has a real guest boot behind it.
