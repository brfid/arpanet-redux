# SRI/NOSC Network UNIX V6 as the first heterogeneous host

**Status:** In progress. Steps 1 through 3 of [First experiment](#first-experiment) are done: the IMP11-A device model exists and is verified, and the prelinked `green/unix` kernel plus the `Largedaemon` NCP daemon binary are installed on a filesystem this device boots. `green/unix` reaches a login shell with root and swap on RL. See [imp11a-device.md](imp11a-device.md) for the full record. Steps 4 through 6 (actually starting the daemon, proving IMP READY/NOP, and the two-IMP route to ITS) have not started.

SRI/NOSC Network UNIX V6 is the strongest first heterogeneous endpoint found for ARPANET Redux. It contains a genuine PDP-11 guest NCP, daemon binaries, guest TELNET and FTP, kernel source for period host/IMP interfaces, and prelinked network kernels. The simulator device model and disk assembly this once called "the remaining critical path" are done; the remaining critical path is now starting the daemon and proving an actual NCP exchange.

## Prepared source

Use [`pdp11/network-unix-v6` at `464893a`](https://github.com/pdp11/network-unix-v6/tree/464893a99da8e3ac7f90577bc54749fa64bb0966). The corresponding primary archival material is the [TUHS SRI-NOSC collection](https://www.tuhs.org/cgi-bin/utree.pl?file=SRI-NOSC), and [RFC 681](https://www.rfc-editor.org/rfc/rfc681.html) describes the historical system.

The preserved tree includes the modified kernel, NCP daemon, user and server TELNET, FTP, and binaries. Two prelinked kernels are useful starting points: `green/unix`, configured for `rl`, `dh`, and `imp`, and `green47/unix`. The prelinked path avoids rebuilding the historical kernel before the controller works.

Those kernels expect a DEC IMP11-A at CSR `0172410`, output vector `0124`, and input vector `0274`. The source also contains an ACC LH/DH-11 driver whose CSR layout at `0167600` resembles the Unibus-oriented register model in the pinned KA10 simulator's [`PDP10/kx10_imp.c`](https://github.com/larsbrinkhoff/ka10-simh/blob/b45fedc048c4a064aae6f771156349e78b3c21e8/PDP10/kx10_imp.c). The prelinked IMP11-A path is the shortest guest proof; ACC is the more maintainable follow-up.

## Native feasibility

[Open SIMH at `a1f57fa`](https://github.com/open-simh/simh/tree/a1f57fa3738ed31148d31126ba1a7278ff845c6d) built a native arm64 PDP-11 simulator on the tested Mac without Docker or system changes. The official [SIMH UNIX V6 kit](https://sourceforge.net/projects/simh/files/Software%20Kits/UNIX%20v6%20for%20the%20PDP-11./) booted its RK05 images to a root shell. This proves the base CPU, operating system, and local toolchain; stock Open SIMH does not provide an IMP11-A or ACC device.

The H316-side datagram framing can be adapted conceptually from the existing simulator transport. The new PDP-11 controller should implement the documented guest registers while interoperating with the already proven READY/NOP and datagram semantics.

## First experiment

1. Add a DEC IMP11-A device to a pinned Open SIMH fork using the preserved driver and [DEC IMP11-A manual](https://bitsavers.org/pdf/dec/unibus/IMP11-A_PDP-11_Host_to_IMP_Interface_Feb1975.pdf) as the register contract.
2. Build an RL01 V6 base and transfer selected NOSC files through a V6 `tp` tape; stock V6 provides `tp`, not `tar`.
3. Install the prelinked network kernel, NCP daemon, and TELNET client, then create `/dev/ncpkernel` as character major 5.
4. Prove IMP READY/NOP exchange against a diagnostic NCP peer before introducing routing.
5. Replace the peer with the two-IMP path to ITS and run TELNET from the PDP-11 guest.
6. Accept only a command and response captured on the PDP-11 console plus corroborating traffic in both IMP logs.

Step 2 did not go through a V6 `tp` tape in the end: the kernel and daemon are already-built binaries, so a from-scratch V6 filesystem injector places them directly (`scripts/research/v6fs.py`), and the RL01 base is a direct byte-level extraction of the real distribution tape rather than a `tp` transfer onto a freshly built filesystem. See [imp11a-device.md](imp11a-device.md) for why, and for exactly how steps 1 through 3 were actually done.

## Alternatives

ELF preserves a genuine NCP and FTP, but its archive uses an ISI/VDH interface and lacks a demonstrated SIMH loader and boot recipe.

The TUHS BBN V6 tree includes an IMP11-A driver, kernel network changes, a guest TCP daemon, and TELNET. It is principally an early BBN TCP/IP system rather than a complete turnkey NCP endpoint, making it a strong later option for TCP over 1822.

Prepared 2.11BSD images are easier to boot but are 1990s and TCP/IP-only. They do not supply the desired period NCP endpoint or a compatible simulated 1822 controller.

## Redistribution boundary

Keep the NOSC tree, guest binaries, generated disks, and logs outside Git. [`NOTICE.md`](../../NOTICE.md) is the sole repository-wide statement of the unresolved licensing boundary; this research recommendation does not imply permission to redistribute the material.
