# PDP-11 Network UNIX as the first heterogeneous host

**Status:** Recommended follow-on after the two-ITS application gate

SRI/NOSC Network UNIX V6 is the strongest first heterogeneous endpoint for the host–IMP–IMP–host laboratory. It contains a genuine PDP-11 guest NCP, NCP daemon binaries, guest TELNET and FTP, kernel source for two period host/IMP interfaces, and prelinked network kernels. The remaining critical path is one simulator device model plus disk assembly; `linux-ncp` may remain a diagnostic oracle but cannot satisfy the vintage-host acceptance gate.

## Recommended source and pin

Use [`pdp11/network-unix-v6`](https://github.com/pdp11/network-unix-v6) at revision `464893a99da8e3ac7f90577bc54749fa64bb0966`. The corresponding primary archival tree is available through the [TUHS SRI-NOSC collection](https://www.tuhs.org/cgi-bin/utree.pl?file=SRI-NOSC), and [RFC 681](https://www.rfc-editor.org/rfc/rfc681.html) describes the system historically.

The preserved `nosc.tar` tree includes the modified kernel, NCP daemon, user/server TELNET and FTP, and binaries. Two prelinked kernels are especially useful: `green/unix` is 42,988 bytes and configured for `rl`, `dh`, and `imp`; `green47/unix` is 39,128 bytes. `ncpd/Largedaemon` is 17,648 bytes.

The prelinked kernels expect a DEC IMP11-A at CSR `0172410`, output vector `0124`, and input vector `0274`. This is the shortest route to a first guest proof because it avoids rebuilding the historical kernel before the controller works.

The source also contains an ACC LH/DH-11 driver. Its CSR layout at `0167600` matches the Unibus-oriented register model already present in [`PDP10/kx10_imp.c`](https://github.com/larsbrinkhoff/ka10-simh/blob/b45fedc048c4a064aae6f771156349e78b3c21e8/PDP10/kx10_imp.c). An ACC build is therefore the more maintainable follow-on after the prelinked IMP11-A path establishes the guest and disk recipe.

## Native feasibility

[Open SIMH](https://github.com/open-simh/simh) revision `a1f57fa3738ed31148d31126ba1a7278ff845c6d` built a native Mach-O arm64 PDP-11 simulator on the current Apple-silicon host without Docker, package installation, or system changes. The official 1.5 MiB [SIMH UNIX V6 software kit](https://sourceforge.net/projects/simh/files/Software%20Kits/UNIX%20v6%20for%20the%20PDP-11./) booted its RK05 images to a root shell. This proves the base CPU, OS, and local toolchain; stock Open SIMH does not contain an IMP11-A or ACC device.

The H316-side UDP framing can be adapted from the pinned KA10 simulator fork's [`H316` source](https://github.com/larsbrinkhoff/ka10-simh/tree/b45fedc048c4a064aae6f771156349e78b3c21e8/H316). Its file header carries a permissive MIT-like notice with a no-name-in-advertising condition. The PDP-11 controller should implement the documented guest registers while reusing the already proven READY/NOP and datagram transport semantics.

## First smoke test

1. Fork pinned Open SIMH in the external lab and implement the DEC IMP11-A register set from the preserved driver and the [DEC IMP11-A manual](https://bitsavers.org/pdf/dec/unibus/IMP11-A_PDP-11_Host_to_IMP_Interface_Feb1975.pdf), using the existing H316 UDP framing for the simulator-to-IMP cable.
2. Build an RL01 V6 base. [`eblanton/unix-v6-install`](https://github.com/eblanton/unix-v6-install/tree/94df669009311ce0e693aa326142732f77796813) is a useful automated SIMH/Expect reference, but it has no declared license and should not be copied into this repository without review.
3. Repack selected NOSC files as a V6 `tp` tape and install `green/unix`, `Largedaemon`, and the TELNET client. A direct tar attachment is not sufficient because stock V6 provides `tp`, not `tar`.
4. Boot `green/unix`, create `/dev/ncpkernel` as character major 5, and prove IMP READY/NOP exchange with a temporary `linux-ncp` peer.
5. Replace that peer with the two-IMP route to ITS, start the PDP-11 guest NCP daemon, and run the guest TELNET client with the octal ITS host address.
6. Accept only a command and response captured on the PDP-11 console plus corroborating traffic in both IMP logs. A host-side `linux-ncp` transaction remains an oracle, not a heterogeneous-host pass.

## Alternatives considered

ELF preserves a genuine NCP and FTP, but its archive uses an ISI/VDH interface and lacks a demonstrated SIMH loader and boot recipe. It is a deeper archaeology project.

The TUHS BBN V6 tree contains an IMP11-A driver, kernel network changes, a guest TCP daemon, and TELNET. The preserved distribution is principally an early BBN TCP/IP system rather than a complete turnkey NCP endpoint; it is a strong later option for an ITS TCP-over-1822 demonstration.

Prepared 2.11BSD images are easy to boot but are 1990s and TCP/IP-only. They do not provide the desired period NCP endpoint or a compatible simulated 1822 controller.

## Redistribution boundary

The Network UNIX repository and NOSC overlay do not declare a root license. The underlying Research UNIX V6 base has the Caldera BSD-style grant, but that grant must not be assumed to cover the SRI/NOSC additions. Keep source trees, guest binaries, generated disks, and logs outside Git and do not publish them until provenance and redistribution rights are reviewed.
