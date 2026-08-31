# SRI/NOSC Network UNIX V6 as the first heterogeneous host

**Observed through 2026-08-31:** The IMP11-A device, bootable `green/unix` system, live daemon, two-IMP attachment, and guest-built TELNET client were demonstrated. The daemon's RFNM bookkeeping deadlock is fixed, and the apparent IMP 62 relay failure is also fixed: the device now converts PDP-11 little-endian DMA words to the IMP's high-bit-first wire order, so the real RFC crosses both IMPs and reaches ITS. The guest then receives error-in-leader messages attributed to host 106 and TELNET still times out, leaving a narrower historical leader-version/interoperability investigation rather than a routing failure. [The IMP11-A device record](imp11a-device.md) retains the detailed evidence; [workstreams](../workstreams.md) owns the active task.

This research selected SRI/NOSC Network UNIX V6 as the strongest first heterogeneous endpoint. It contains a genuine PDP-11 guest NCP, prelinked daemon binaries, source for guest TELNET and FTP, kernel source for period host/IMP interfaces, and prelinked network kernels. The detailed device and RFC investigation belongs in [the IMP11-A record](imp11a-device.md), not this selection note.

## Prepared source

The experiment used [`pdp11/network-unix-v6` at `464893a`](https://github.com/pdp11/network-unix-v6/tree/464893a99da8e3ac7f90577bc54749fa64bb0966). Active source revisions live in [`pins/`](../../pins/). The corresponding primary archival material is the [TUHS SRI-NOSC collection](https://www.tuhs.org/cgi-bin/utree.pl?file=SRI-NOSC), and [RFC 681](https://www.rfc-editor.org/rfc/rfc681.html) describes the historical system.

The preserved tree includes the modified kernel, NCP daemon, and source for user and server TELNET and FTP. `green/unix` and `green47/unix` are useful prelinked kernels; `Largedaemon` and `smalldaemon` are prelinked, but the TELNET and FTP applications are source-only. The in-guest TELNET build, preservation defect, and header reconciliation are documented in [the IMP11-A record](imp11a-device.md#building-a-guest-telnet-client-from-source). The unlinked TELNET server object remains outside this experiment's scope.

The prelinked IMP11-A path is the shortest guest proof; [the device record](imp11a-device.md#register-map) owns its register map. The source also contains an ACC LH/DH-11 driver, a more maintainable follow-up interface.

## Native feasibility

[Open SIMH at `a1f57fa`](https://github.com/open-simh/simh/tree/a1f57fa3738ed31148d31126ba1a7278ff845c6d) built a native arm64 PDP-11 simulator on the tested Mac without Docker or system changes. The official [SIMH UNIX V6 kit](https://sourceforge.net/projects/simh/files/Software%20Kits/UNIX%20v6%20for%20the%20PDP-11./) booted its RK05 images to a root shell. This proves the base CPU, operating system, and local toolchain; stock Open SIMH does not provide an IMP11-A or ACC device.

The device investigation records how the documented guest registers interoperate with the established H316 transport and READY/NOP semantics.

## First experiment

1. Add a DEC IMP11-A device to a pinned Open SIMH fork using the preserved driver and [DEC IMP11-A manual](https://bitsavers.org/pdf/dec/unibus/IMP11-A_PDP-11_Host_to_IMP_Interface_Feb1975.pdf) as the register contract.
2. Build an RL01 V6 base and transfer selected NOSC files through a V6 `tp` tape; stock V6 provides `tp`, not `tar`.
3. Install the prelinked network kernel and NCP daemon, then create `/dev/ncpkernel` as character major 5.
4. Prove IMP READY/NOP exchange against a diagnostic NCP peer before introducing routing.
5. Replace the peer with the two-IMP path to ITS and run TELNET from the PDP-11 guest.
6. Accept only a command and response captured on the PDP-11 console plus corroborating traffic in both IMP logs.

The experiment diverged from its original mechanics without changing its objective: the filesystem injector placed the existing kernel and daemon directly, the client was built in-guest, and the two-IMP network half completed. The detailed record of those deviations, the fixed wire-ordering defect, and the remaining leader-error response is in [the IMP11-A record](imp11a-device.md); the active next action is in [workstreams](../workstreams.md).

## Alternatives

ELF preserves a genuine NCP and FTP, but its archive uses an ISI/VDH interface and lacks a demonstrated SIMH loader and boot recipe.

The TUHS BBN V6 tree includes an IMP11-A driver, kernel network changes, a guest TCP daemon, and TELNET. It is principally an early BBN TCP/IP system rather than a complete turnkey NCP endpoint, making it a strong later option for TCP over 1822.

Prepared 2.11BSD images are easier to boot but are 1990s and TCP/IP-only. They do not supply the desired period NCP endpoint or a compatible simulated 1822 controller.

## Redistribution boundary

Keep the NOSC tree, guest binaries, generated disks, and logs outside Git. [`NOTICE.md`](../../NOTICE.md) is the sole repository-wide statement of the unresolved licensing boundary; this research recommendation does not imply permission to redistribute the material.
