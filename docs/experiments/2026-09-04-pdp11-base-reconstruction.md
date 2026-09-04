# Network UNIX base reconstruction, 2026-09-04

## Claim and scope

The supported setup path can build usable Network UNIX base disks from pinned public inputs without copying the previously prepared private pair. Two independent assemblies produced identical unbooted media. A newly populated laboratory compiled the preserved guest applications and passed the unchanged direct Gate 4H. The [base-media page](../pdp11-base.md) owns the current recipe and compatibility contract; this record owns the exact evidence.

Development started from project commit `aa9afe188889a0ada8d4dc3a79f2428655ac4bcb`; implementation and tests are committed in `03c2431`. The tested constructor `scripts/pdp11_base.py` has SHA-256 `bb9ea9b9a2ed86665917b26ab8cfe3761e1172cc356dd5464e70999bd2c60b3c`; the unchanged filesystem injector has SHA-256 `4bdab56ab2649ec00da7b6d2450b14785633ab2904ccef52c721c710470c4ad6`. The external base receipt records both hashes and its exact input lock and output-pin identities. Simulator revisions remain H316 `feb155fbc49333e879ab082d481e6dcce27d2d91`, KA10 `4b59f21d00355a7a917fa7cd54ef8a1123b515b2`, and IMP11-A `c74e7040e186a6ea11d9cd816b94edc235959e27`; Network UNIX remains `464893a99da8e3ac7f90577bc54749fa64bb0966`.

## Retained locations

All paths below are beneath the external laboratory `/Users/brf/src/arpanet-redux-lab`; no source, historical media, executable, or raw log was added to Git.

| Location | Evidence |
|---|---|
| `reviews/base-media-20260904/` | Setup, reconstruction, guest-build, doctor, smoke, source-test, and repeatability records |
| `fresh-base-20260904/` | Fresh runtime source clones from recorded upstream URLs, newly built simulators and Python environment, freshly downloaded TUHS archives |
| `fresh-base-20260904/work/pdp11-base/` | Unbooted reconstructed pair and construction receipt |
| `repeat-base-20260904/work/pdp11-base/` | Independent offline assembly from the verified archive bytes and pinned fresh Network UNIX checkout |
| `fresh-base-20260904/results/pdp11-telnet-build-base-reconstruction-20260904/` | Guest TELNET and NCP daemon compilation, staged sources, intermediate/final media, and receipt |
| `fresh-base-20260904/results/pdp11-its-telnet-base-reconstruction-20260904/` | Passing direct Gate 4H, complete journey, and cleanup records |
| `fresh-base-20260904/results/base-filesystem-utilities-check-20260904/` | Independent guest filesystem inspection on disposable copies |

## Reconstruction and compatibility

The raw tape and RL reference image were fetched anew from the pinned TUHS URLs. Both compressed and decompressed identities matched. The constructor read the root filesystem directly from the raw tape, used the RL-native first block, and installed the pinned kernel, daemons, and device node through the existing project injector. The accepted tape/RK/RL findings in the [original research](../research/imp11a-device.md#v6-base-reproducing-the-pristine-root-filesystem) were not reopened. No third-party installer or tape converter was copied or run.

The two assemblies produced these SHA-256 values:

| Image | SHA-256 |
|---|---|
| `ncp_root.rl01` | `98c1773c90270504fbd12e5858acac98746405fefe8a784fdbc5d1823cf777db` |
| `ncp_swap.rl01` | `c036cbb7553a909f8b8877d4461924307f27ecb66cff928eeeafd569c3887e29` |

Each image is 5,242,880 bytes. A repeated offline build verified the existing pair and matching receipt without rewriting them. Original synthetic filesystem tests cover directory parent-link counts, preserved kernel bytes, and the daemon-facing character device; cache mismatch, invalid decompression, mixed profiles, occupied output, partial assembly failure, path escapes, and concurrent builders all fail closed.

Comparison with the old prepared disks found login state in `/etc/utmp` and nonzero swap data from previous boots. The new pair has its own pins; both original pins remain unchanged. The earlier selected guest receipt at `results/pdp11-telnet-build-reply-ingress-accepted-build-20260904/pdp11-build-receipt.json` still verifies against the strengthened pair check. The main laboratory's prepared disks and selected build were not replaced.

## Fresh setup exposed a nested-checkout bug

The first setup attempt treated the empty `arpanet/src/linux-ncp` submodule directory as a Git checkout because Git reported that it was inside the parent work tree. Selecting the child's revision consequently switched the newly cloned parent before setup failed. The original failure remains in `fresh-setup.log`.

The repair requires the directory's own resolved Git top level to match the intended checkout. Empty nested directories are cloned independently. The repeated setup restored the fresh parent to its pin, cloned both nested runtime dependencies into their own repositories, built all three simulators, and installed the pinned Python dependencies. `fresh-setup-repaired.log` records that run. The regression uses a nested source revision different from its parent's and verifies that both repositories retain their own identities.

## Guest and application evidence

The guest compiled TELNET and its reader companion, then the NCP daemon, using its own V6 toolchain. The existing receipt validator accepted all compiler output, staged sources, final media, source revisions, and simulator identity. The fresh doctor reported every runtime dependency ready and selected the new receipt-bound build.

Direct Gate 4H recorded an open connection, ITS service job `53TLNT`, the ITS greeting, structured remote `:TIME`, correlated traffic through both IMPs in both directions, and twelve journey observations in state `complete` with no missing boundary. The legacy option diagnostic was absent. All four owned simulators exited, no owned process survived, and the outer launcher recorded successful cleanup and exit status zero.

An additional boot of disposable base copies confirmed the kernel and daemon sizes and character device 5,0. The first inspection used incorrect `/etc` paths for the filesystem utilities and reported them missing; that transcript remains under `results/base-filesystem-check-20260904`. Inspection of the preserved root located them in `/bin`. In the corrected independent run, `/bin/icheck /dev/rl0` reported 3008 used and 905 free blocks without duplicate or missing-block diagnostics, and `/bin/dcheck /dev/rl0` reported no directory-link discrepancies. Both inspections synchronized and exited the simulator; neither boot wrote to the pinned base pair.

Source validation passed all 392 tests, with the expected sandbox UDP skip; shell runtime checks passed with their expected Unix-socket sandbox skip. The complete-history source-only guard passed, and changed documentation passed soft-wrap and local-link checks.

## Limits

Reproducibility applies to the unbooted base images, not subsequent guest compilation or session disks. The base pair was validated on macOS with the recorded simulator pins and current direct gate; this run makes no new historical site, addressing, protocol, alternate-route, or browser-authority claim. Later Shoppa and NOSC additions retain the unresolved redistribution boundaries recorded in [NOTICE](../../NOTICE.md). Public acquisition is not permission to publish the resulting disk.
