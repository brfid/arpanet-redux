# Network UNIX base media

`make build-pdp11-base` reconstructs a deterministic, unbooted RL01 root/swap pair from public, pinned historical inputs. Use it after `make lab-setup`, then run `make build-pdp11-telnet` to compile the guest applications. The [fresh-clone guide](getting-started.md) owns the complete onboarding sequence; this page owns the base-media contract.

## Inputs and construction

| Input | Identity | Use |
|---|---|---|
| Ken Wellsch's preserved `v6.tape.gz` from [TUHS](https://www.tuhs.org/Archive/Distributions/Research/Ken_Wellsch_v6/) | Compressed and uncompressed sizes and SHA-256 in [base-input lock](../pins/pdp11-base-inputs.lock.toml) | Extract the 4000 root-filesystem blocks after the 100-block bootstrap area |
| Tim Shoppa's `unix_v6.rl02.gz` from [TUHS](https://www.tuhs.org/Archive/Distributions/Research/Tim_Shoppa_v6/) | Same lock | Copy only its first 512-byte RL bootstrap block into the external root image |
| `nosc-files/green/unix`, `nosc-files/ncpd/Largedaemon`, and `nosc-files/ncpd/smalldaemon` | Clean `network-unix-v6` revision in [source lock](../pins/sources.lock.toml), with bytes compared to the pinned Git objects | Install the preserved kernel and daemon binaries |

The original [reconstruction research](research/imp11a-device.md#v6-base-reproducing-the-pristine-root-filesystem) established the tape layout, RL bootstrap requirement, root/swap devices, and daemon-facing device number. The supported helper reads the raw decompressed tape directly, avoiding the old tape converter and simulator installation procedure entirely. It uses the repository's existing V6 filesystem injector to add `/green`, `/usr/net/etc/Largedaemon`, `/usr/net/etc/smalldaemon`, and character device `/dev/ncpkernel` (major 5, minor 0, mode 0666). It accounts for the two new directories' parent links, flushes the free-block state, invalidates the cached free-inode list, fixes the filesystem clock at zero, and pads root and zero-filled swap to 5,242,880 bytes each. It never boots the base pair.

The helper is original orchestration. Historical bytes, caches, and constructed media remain external, under the terms described in [NOTICE](../NOTICE.md). It neither vendors an upstream installer nor grants rights to publish a reconstructed disk.

## Output identity and compatibility

The output directory is `$LAB_ROOT/work/pdp11-base/`. It contains `images/ncp_root.rl01`, `images/ncp_swap.rl01`, and `pdp11-base-receipt.json`. The recipe checks both complete images against [reconstructed output pins](../pins/pdp11-reconstructed-base.sha256) before publishing the directory. Its receipt records the archive identities, source revision and per-file hashes, recipe and injector hashes, pin-file hashes, and output hashes. Neither images nor receipt depend on the host's build-time clock; the source-checkout path in the receipt can differ between laboratories.

The old prepared pair remains pinned separately in [legacy base identities](../pins/pdp11-base-assets.sha256). It contains state from earlier boots, including login and swap data, so a fresh reconstruction intentionally has a different identity. Neither legacy pin is replaced. The doctor, guest build preflight, and guest receipt verification accept exactly one complete pair from either profile. Changed images and a root/swap mixture are rejected.

Make chooses reconstructed media when `work/pdp11-base/` exists; otherwise it uses the legacy directory if present. A partial reconstructed directory stays visible as a problem rather than silently falling back. An explicit `PDP11_BASE_ROOT` and `PDP11_BASE_SWAP` pair still overrides that selection. Existing guest receipts remain valid when their original pinned base files and other dependencies remain intact.

## Safe reruns and offline reconstruction

`make build-pdp11-base-plan` reports acquisition URLs, hashes, and destinations without downloading or writing. The builder holds one laboratory lock, validates all inputs, assembles into a temporary directory, verifies both output hashes, and publishes the completed directory. A caught failure removes only its temporary assembly. Existing media and mismatching cache entries are never overwritten. The persistent empty `.pdp11-base.lock` file is a lock rendezvous, not an indication that a builder is still running.

A repeated build verifies the existing pair and its receipt against the current recipe and inputs and leaves them unchanged. To reconstruct without network access, first place the two exact compressed archives in `$LAB_ROOT/cache/pdp11-base/` and prepare the pinned Network UNIX checkout, then run:

```sh
python3 scripts/pdp11_base.py build /absolute/path/to/lab --offline
```

An absent offline archive, changed compressed or decompressed bytes, dirty or wrong source revision, nonmatching output, occupied unreceipted destination, or changed receipt fails with an explanation. Automatic repair never downloads over a bad cache entry or rewrites a retained disk. Preserve a suspect directory for investigation and use a different external `LAB_ROOT` for a clean reconstruction; the doctor prints the next required setup steps. A failed download publishes no cache entry, and a failed assembly publishes no partial pair. An uncatchable process termination may leave a hidden temporary directory, which is never selected as base media.

## Verification boundary

Source-only tests exercise repeatable assembly using original synthetic filesystem data, device placement and directory links, decompression and cache rejection, profile mixing, offline behavior, repository/path boundaries, output publication, occupied destinations, repeated builds, and lock exclusion. Exact external verification must additionally download the recorded archives, reconstruct in a fresh lab, independently repeat the output hashes, compile TELNET and the NCP daemon in the pinned guest, and pass the unchanged [direct TELNET gate](test-plan.md#gate-4h-network-unix-pdp-11-to-its). Hash reproducibility applies to the unbooted base pair; compiled guest disks and running sessions record their own changing media identities in the existing receipts and results.

The [2026-09-04 acceptance record](experiments/2026-09-04-pdp11-base-reconstruction.md) retains the fresh-lab proof, repeat hashes, historical guest filesystem checks, and setup repair.
