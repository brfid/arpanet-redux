# ADR-001: Replace the vintage host spool with a two-IMP ARPANET path

- **Status:** Accepted for baseline implementation after phase-one feasibility testing
- **Date:** 2026-08-28
- **Decider:** Brad
- **Scope:** Research and isolated smoke testing only; no implementation changes to `brfid.gitlab.io`

## Executive finding

The proposed host–IMP–IMP–host pipeline is feasible on the current Apple Silicon Mac. I built native arm64 H316 and KA10 simulators, ran the recovered 1973 IMP firmware, proved routing and failure reporting through two IMPs, booted a KA10/ITS guest with native NCP and a working 1822 interface, and completed three end-to-end NCP echo exchanges between that ITS guest and a diagnostic NCP host through exactly two IMPs.

The best first production-shaped topology is two KA10/PDP-10 guests running ITS: octal host `106` on IMP 6 and octal host `176` on IMP 62. This is the shortest path to an honest vintage host interface on both ends. It is less visually diverse than two different computer families, but it avoids the modern bridge used by the available WAITS integration and the missing SIMH host-controller work that blocks the otherwise interesting PDP-11 Network Unix and VAX/BSD candidates.

The network mechanism is no longer the principal risk. The remaining phase-two work is to build and package the second ITS monitor cleanly, prove vintage-to-vintage application traffic, choose a guest program for moving and transforming the bio payload, and turn the native experiment into pinned production images. The currently prepared host-126 disk set is not turnkey, but current ITS source already defines the correct generic KA machine at address `176`, and an isolated guest successfully assembled that monitor in about 30 seconds.

The accepted baseline is two KA10/ITS endpoints, with `linux-ncp` retained only as a deterministic diagnostic oracle. The user explicitly chose to bring up this same-family pair first and pursue a more interesting heterogeneous endpoint after the initial two-host network works.

## Constraints observed

- The original site checkout was inspected read-only. It was clean at commit `22c7824e602a8f6e68ada967667a58b04d51f097` when phase one began.
- During the research, unrelated working-tree edits appeared and continued changing in the site checkout, including CI, publication, and image-manifest work. This phase-one work did not create, alter, stage, or revert any of them.
- All downloads, builds, copied disks, processes, and raw logs live under the external `$LAB_ROOT` sister directory or an isolated task work directory.
- Python-only support used `$LAB_ROOT/.venv` with `pexpect 4.9.0`. Nothing was installed into system Python or system directories.
- The Docker client is present, but the local Docker daemon was not accessible to this task. All meaningful smoke tests therefore used native arm64 binaries built from source.

## Current pipeline

The current “vintage pipeline” is two console-driven computer builds connected by the modern host filesystem, not a network:

```text
site.yaml + resume.yaml
  -> host Python emits build/vintage/bio.vintage.yaml
  -> pexpect drives VAX 11/780 / 4.3BSD
  -> guest compiles bradman.c, runs troff, and uuencodes brad.bio.uu
  -> host bind mount acts as the spool transfer
  -> pexpect drives PDP-11/73 / 2.11BSD
  -> guest uudecodes and runs nroff
  -> build/vintage/brad.bio.txt
  -> semantic validation, build log, status, reuse validation, Hugo publication
```

The sequential handoff is explicit in `scripts/vintage-runner.sh`: `stage_b_vax()` writes `brad.bio.uu`, then `stage_a_pdp11()` reads it. The VAX configuration disables `xu`, `tq`, and `dmc`; the PDP-11 configuration disables `xq`. The repository instructions also explicitly require host-spool transfer because the PDP-11 kernel has no working Ethernet.

This design has several strong properties worth keeping: state-aware pexpect control, immutable production image pins, manual image promotion, exact input and implementation fingerprints, fail-closed fast reuse, semantic output validation, and exact provenance.

## Clean replacement seam

The safest seam begins after `generate_vintage_yaml()` creates `build/vintage/bio.vintage.yaml` and ends before final artifact validation. Replace only the two current computer stages with one network orchestration stage.

Keep these external contracts unchanged:

- Final reusable bundle names: `brad.bio.txt`, `build.log.html`, and `pipeline-status.json`. The intermediate `brad.bio.uu` is not a reusable or public bundle contract and may disappear.
- Input contract: `name`, `headline`, and `summary` must be nonempty printable ASCII. Name and headline remain exact; the summary remains equal after whitespace normalization.
- Status contract: pipeline name `edcloud-vintage`, result `success`, integer exit code `0`, nonempty build ID, and exact source Git SHA.
- Build-log contract: the HTML title and visible build-ID label must identify the same build.
- Reuse contract: exact source-run URL, exact provenance, current public inputs, and every implementation file that can affect the vintage result remain fingerprinted and fail closed.
- Publication tail: standard and fast modes, bundle validation, Hugo data generation, and public artifact staging remain unchanged.

The repository rules that require separate VAX/PDP-11 state machines and a host UUCP spool would need deliberate revision. The rules for pexpect, image immutability, image promotion, fingerprints, artifact identity, and provenance should remain.

## Accepted decision

Use this topology for the next proof and, if that proof passes, for the replacement pipeline:

```text
host control plane: pexpect injects source into guest A and captures output from guest B

KA10 / ITS host 106
  -> native ITS NCP
  -> KA10 SIMH IMP device, long 1822 leader
  -> H316 IMP 6, recovered 1973 firmware
  -> simulated point-to-point modem line
  -> H316 IMP 62, recovered 1973 firmware
  -> KA10 SIMH IMP device, long 1822 leader
  -> native ITS NCP
  -> KA10 / ITS host 176

host validation plane: existing semantic, provenance, reuse, and publication contracts
```

The control plane may still use pexpect over simulator stdin/stdout, as the current pipeline does. The payload must enter guest A, cross the NCP/1822/IMP/IMP/NCP path, and leave guest B; there should be no host-side file copy between the guests. Loopback UDP is only the simulated cable between emulator devices, not a bypass for the application payload.

Use host `106` octal (70 decimal) on IMP 6 HI2 and host `176` octal (126 decimal) on IMP 62 HI2. A direct MI1-to-MI1 link is sufficient for the production-shaped two-router laboratory; a three-IMP path can be retained as an additional routing regression test.

Keep [`linux-ncp`](https://github.com/larsbrinkhoff/linux-ncp) outside the production data path. Its maintainer explicitly describes it as a low-quality, test-oriented work in progress, which is exactly why it is useful here: it provides small, observable PING, TELNET, FINGER, and packet-diagnostic tools for separating IMP routing problems from vintage guest problems.

Do not revive the repository's archived VAX–H316–H316–KS10 experiment. That path failed because the selected KS10 `IMP` device emitted an Ethernet/ARP-oriented datagram format while the H316 expected 1822 host-interface framing. The KA10 fork tested here has a purpose-built NCP mode and is the architectural correction, not a retry of the same wiring.

## Resources found

The most useful discovery is [ARPANET in a Box](https://github.com/obsolescence/arpanet/tree/78123c77b20dadd9b5967b184dbcb4195185eea6), an active reconstruction of the circa-1972/73 ARPANET. Its own README calls it work in progress, but it supplies a large set of H316 IMP configurations and recovered firmware, several prepared KA10/ITS disk sets, a WAITS guest, launch scripts, and a network map. Its [project page](https://obsolescence.dev/arpanet_home.html) describes simulated leased lines and the IMPs' self-organizing routing.

The recovered router software has a strong provenance trail. SIMH's [software-kit catalog](https://simh.trailing-edge.com/software.html) publishes demonstration software for the 1973 ARPANET IMP, and the contemporary [resurrection report](https://www.bitsavers.org/pdf/bbn/imp/The_ARPANET_IMP_Program_-_Retrospective_and_Resurrection_201312.pdf) describes OCR recovery of the 1973 listing, recreation of its assembler, and execution on an emulator. The older [H316 IMP documentation](https://opensimh.org/simdocs/h316_imp_doc.html) accurately describes the H316 devices and UDP modem tunnels but still labels its host interface a skeleton; that warning is stale for the newer fork used by ARPANET in a Box and directly contradicted by the working host-interface smoke logs.

The prepared KA10 binary embeds [`ka10-simh` commit `b45fedc0`](https://github.com/larsbrinkhoff/ka10-simh/commit/b45fedc048c4a064aae6f771156349e78b3c21e8), whose change adds NCP mode and an IMP-emulator host attachment. Rebuilding that exact commit produced a native arm64 binary and avoided depending on the bundle's Linux x86-64 executable.

The current [PDP-10/its project](https://github.com/PDP-10/its) is more important for production than any recovered disk snapshot. It provides an automated build, supports `pdp10-ka`, and explicitly makes machine identity and networking configurable. Its [NITS build guidance](https://github.com/PDP-10/its/blob/master/doc/NITS.md) identifies `IMPP`, `IMPUS`, and `NCPP` as the IMP interface, ARPANET address, and NCP settings. At commit `0f7d67997f9f5d30208e117e73272031e74f16b9`, the generic KA configuration already sets `IMPUS==176`, `IMPP==1`, `KAIMP==1`, and `NCPP==1`, exactly matching host 126 on IMP 62.

The [Stanford WAITS SIMH quick-start](https://github.com/timereshared/stanford-waits-simh-quickstart) is the easiest visibly different historical guest. Its [2026 tour](https://timereshared.com/waits-quick-tour-simh/) shows a prepared 1974 snapshot and source/build workflow. It is not the right first network endpoint: ARPANET in a Box explicitly says its WAITS host is connected through a modern Linux bridge rather than WAITS's own NCP. That is useful as a future display guest, but it weakens the exact host–IMP–IMP–host claim.

The [PDP-11 Network Unix V6 archive](https://github.com/pdp11/network-unix-v6) contains historically relevant ARPANET NCP additions and is the strongest future heterogeneous endpoint candidate. It is source material rather than a turnkey SIMH host. The current PDP-11 simulator does not supply the required ACC/CSS/HDH/IMP11-style host-controller integration, so adopting it now would turn this project into emulator device development.

The existing VAX 4.3BSD and PDP-11 2.11BSD guests contain historically relevant networking code, but their current SIMH machine models do not expose a compatible 1822 controller to those kernels. TOPS-10/TOPS-20 and Multics are also historically attractive, but the resources found are either not integrated with this H316 host interface or carry additional distribution constraints. They are research-backlog candidates, not easier first endpoints.

## Candidate comparison

| Pair | Authentic host interfaces | Preparedness | Diversity | Phase-one assessment |
|---|---:|---:|---:|---|
| KA10/ITS + KA10/ITS | Yes, native NCP and long 1822 at both ends | One known-good prepared disk; second monitor can be rebuilt | Low | Recommended first replacement |
| KA10/ITS + Linux NCP | Vintage on one end only | Highest and already passed | Low | Diagnostic oracle, not production |
| KA10/ITS + KA10/WAITS bridge | No on the WAITS side | Prepared guest and bridge | Medium | Defer; the bridge compromises the stated topology |
| KA10/ITS + PDP-11 Network Unix V6 | Potentially yes | Source archive, missing controller integration | High | Best later heterogeneous research target |
| Current VAX/BSD + PDP-11/BSD | No compatible simulated 1822 controllers | Existing pipeline images | High | Cannot be rewired into this topology without emulator work |

## Smoke-test results

### Native build

The bundled host executables are Linux x86-64 and do not run on this arm64 Mac. I rebuilt the H316 simulator from the source already nested under the NCP test project and rebuilt the exact KA10 commit identified by the prepared binary. Both outputs are native Mach-O arm64 executables.

| Component | Source revision | Result |
|---|---|---|
| ARPANET in a Box | `78123c77b20dadd9b5967b184dbcb4195185eea6` | Cloned with required submodules |
| `linux-ncp` | `f76665b3b9aeadd1906c118477727230db3bb8bd` | Native daemon and tools built |
| H316 SIMH fork | `2ccfed85acad83b254a6ed5fdd1c342bcdf3a3dd` | Native arm64 H316 built |
| KA10 SIMH fork | `b45fedc048c4a064aae6f771156349e78b3c21e8` | Native arm64 `pdp10-ka` built |
| Current ITS source inspected | `0f7d67997f9f5d30208e117e73272031e74f16b9` | Correct generic host-176 configuration confirmed |

### IMP-to-IMP routing oracle

Two Linux NCP test hosts attached to two H316 IMPs exchanged three echo requests and replies. A request to a nonexistent third host returned the expected host-dead result. This verified both success and failure paths through recovered IMP code before adding a vintage guest.

```text
NCP PING host 003
Reply from host 003: seq=1 time=123ms
Reply from host 003: seq=2 time=115ms
Reply from host 003: seq=3 time=71ms

Host is not up.
NCP PING host 004
```

The NCP trace shows regular packets, RFNMs, return packets, and a type-7 DEAD response for host `004`.

### Prepared vintage guests

Prepared ITS host `106` booted to `KA ITS 1652 IN OPERATION`, announced `SYSTEM JOB USING THIS CONSOLE`, reset its IMP interface, and exchanged host-interface packets with IMP 6. The H316 trace converted the KA10's 96-bit long leaders to the short leader used internally by the 1973 IMP code and converted replies back for the KA10.

Prepared host `206` (134 decimal) also booted from a fresh isolated disk copy. A timed confirmation reached `KA ITS 1652 IN OPERATION` after 179 seconds under concurrent load. This shows that the KA10 simulator and a second prepared ITS disk set are sound, although both host `106` and host `206` are addressed to different host ports on the same IMP 6 and therefore cannot form the desired two-IMP pair without rebuilding an address.

The prepared host-`176`/126 disk set was not turnkey. Its supplied selector entered `SALVAGER.317` and reported missing user-directory files; an alternate selector produced `FNF`. The failure is specific to that prepared disk/monitor combination rather than to host 126 as a configuration.

### Vintage NCP through exactly two IMPs

The decisive phase-one test attached Linux NCP host `076` to IMP 62, connected IMP 62 directly to IMP 6, and attached KA10/ITS host `106` to IMP 6. After ITS reached operation and reset its interface, the diagnostic endpoint completed three NCP echo exchanges with ITS:

```text
NCP PING host 106
Reply from host 106: seq=1 time=148ms
Reply from host 106: seq=2 time=96ms
Reply from host 106: seq=3 time=109ms
```

For every exchange, the diagnostic NCP logged an ECO request, an RFNM from host `106`, and the matching ERP reply from ITS. The two H316 logs show traffic on both host interfaces and the IMP 6 log shows repeated long-to-short 1822 conversion. This one test exercises the native ITS NCP, KA10 IMP device, UDP-emulated 1822 cable, recovered IMP host interface, recovered routing code, simulated modem line, return path, and diagnostic NCP application.

### Second vintage address

On an isolated copy of the known-good host-`106` disks, the running ITS guest assembled `R126 BIN` from `SYSTEM; ITS` for the generic `KA` machine in 29.48 seconds. The prepared disk's local `SYSTEM; CONFIG` had been changed to address `106`, so that in-guest assembly inherited `106`; this is why the pinned current source tree, whose generic KA block says `176`, is the unambiguous production input.

A boot-time DDT deposit of `176` into `IMPUS` was verified and reached `SYSTEM JOB`, proving that the known-good monitor and emulator operate at the required second address. A subsequent persistent dump retained `IMPUS=176` when reloaded, but stalled after `SALVAGER.317` with the same missing-files behavior as the bundle's existing broken `ITS` selector. That dump is evidence, not a production image. Phase two should use the current source build rather than reconcile this recovered disk snapshot.

The isolated source-build target identified from the upstream dependency graph is:

```text
git submodule update --init --depth 1 tools/itstar tools/dasm tools/sims
make EMULATOR=pdp10-ka MCHN=KA NOVIDEO=1 out/pdp10-ka/stamp/its
```

The required `make`, Clang, and Expect tools are already present, and `NOVIDEO=1` avoids SDL/GTK dependencies. This exact full-disk build was not run during phase one; it is the first phase-two gate.

### macOS-specific findings

The upstream test wrapper uses GNU Screen and sends literal `^M` sequences. macOS Screen 4.00.03 does not interpret those sequences the way that wrapper expects, so the unmodified launcher failed before testing the network. Replacing Screen with exact-PID process orchestration made the test portable and easier to clean up.

Each UDP interface needs a unique local port on macOS. One upstream sample reused a local port for two modem interfaces, which macOS correctly rejected. Pinning all host-interface destinations to `127.0.0.1` also avoided an IPv6/IPv4 mismatch because `linux-ncp` binds an IPv4 socket.

The reliable startup order is diagnostic NCP listeners, H316 IMPs, then vintage hosts. The H316s were throttled at 400 KIPS; prepared KA10 configs retained their 35% throttle. Fixed sleep periods were removed from the final mixed test in favor of waiting for the ITS operational banner, then allowing its NCP interface reset to complete.

## Evidence locations

Raw evidence remains outside the site repository under `$LAB_ROOT/results`:

| Result directory | Meaning |
|---|---|
| `linux-ncp-smoke-ipv4` | Passing router success/dead-host oracle |
| `its-pair-boot-1` | Host `106` boot and KA10-to-H316 1822 exchange; prepared host `176` failure |
| `prepared-host134-smoke-2` | Independent healthy second prepared ITS image |
| `its-linux-two-imp-3` | Passing ITS-to-diagnostic-host exchange through exactly two IMPs |

The key re-addressing and in-guest assembly results are summarized in the second-vintage-address section above; the raw experimental transcript remains external to this source-only repository. Every simulator used for that investigation exited through its SIMH console and returned `Goodbye`; its final configuration opened no network ports.

The clean pass logs include console output, H316 debug traces, diagnostic NCP traces, and application output. Failed iterations were retained separately because they document the Screen, UDP-port, address-radix, startup-order, and boot-time findings rather than being silently discarded.

## Reproducibility pins

The recovered firmware/configuration file `mini/impcode.simh` has SHA-256 `bc4870059b9131636a49dec53399b8f654ba5c146bd09c32d48ab65d5309c771` in the tested checkout.

The known-good host-`106` boot and disk assets have these SHA-256 values:

| File | SHA-256 |
|---|---|
| `dskdmp.rim` | `6950b8c1b5c9fc06296914672a2f857403cbc84e7d1766ddf3b244b9a66e890a` |
| `rp03.0` | `fd3ee3d70625e5074b1e5d2563e5f1b89b3f85f07da166d7b9b07c39cc9eafc4` |
| `rp03.1` | `09ade16bc437f503cd0b37c55acd56722e01bf17bb9d113a54fb548cb58920e2` |
| `rp03.2` | `f581458a8fe70020aa6acd3de3fbc2309258ceedfb00e9e16e21fdd7074c8f5c` |
| `rp03.3` | `7be95ecd54e79aea0a91557b3552e3fd824bbd6481919fd6a1c3b1d19e12c63c` |

These hashes are evidence pins, not permission to redistribute the assets.

## Licensing and release gate

ARPANET in a Box has no bundle-wide root license at the tested revision. The prepared disks, recovered firmware, scripts, nested simulators, and bundled binaries therefore cannot be treated as one uniformly licensed redistributable unit. `linux-ncp` likewise has no root `LICENSE` or `COPYING` file in the tested checkout.

The ITS source project explicitly uses mixed, file-scoped licensing: its root `LICENSE` grants MIT terms only to listed directories and directs readers to `COPYING` for other files. A production image that contains an assembled historical system needs an asset-by-asset release review. This is an engineering release gate, not a legal conclusion.

The safe phase-two policy is to pin fetch sources and checksums, build privately, and avoid committing disk images or publishing container layers to the public registry until that review is complete. If public CI must download assets, record their origin, checksum, and applicable notice separately.

## Trade-off analysis

Two ITS hosts minimize unknowns because the exact KA10 long-leader interface and ITS NCP have now interoperated with the recovered H316 code. The cost is historical sameness: both endpoints are PDP-10/KA10 machines with closely related ITS monitors. For a pipeline whose point is visible historical variety, that is a real aesthetic and educational compromise.

WAITS provides immediate operating-system variety and a rich prepared disk, but its available ARPANET integration terminates NCP in a modern bridge. It would look more diverse while being less faithful at the exact boundary this project is trying to demonstrate.

PDP-11 Network Unix V6 is the most promising honest heterogeneous follow-up. It has period NCP source, and a PDP-11 would echo the current pipeline's machine diversity. It requires a compatible simulated host controller and guest integration before it becomes a pipeline candidate. That work is valuable emulator archaeology, but it should be a separate objective after the two-ITS network and payload contracts are proven.

## Consequences of the proposed decision

- Network feasibility is de-risked without weakening the existing publication contract.
- Production no longer depends on pretending a host bind mount is UUCP; the payload can demonstrably cross recovered packet-switching code.
- The vintage stage becomes a coordinated four-simulator lifecycle instead of two sequential container runs, so exact PID ownership, port allocation, readiness detection, and failure cleanup become first-class contracts.
- Boot time is longer and variable. Readiness must be prompt-driven; a cold ITS start observed in this phase ranged beyond two minutes under load.
- A modern diagnostic endpoint remains in test suites but not in the production route.
- Image creation and redistribution need more care because the most convenient prepared bundle is work in progress and not uniformly licensed.
- The first version sacrifices heterogeneous host families. A later PDP-11 Network Unix endpoint can replace one ITS guest without changing the two-IMP orchestration contract.

## Phase-two acceptance gates

1. Run the pinned generic-KA source target above and produce two immutable, independently bootable KA10/ITS images at octal addresses `106` and `176`; do not promote the debugger deposit or bounded `R126` dump.
2. Start two H316s and both guests with one state-aware orchestrator, unique allocated ports, exact process ownership, and cleanup verified after both success and forced failure.
3. Prove vintage-to-vintage NCP traffic through exactly two IMPs. Require an application-level echo or TELNET transcript plus IMP traces; simulator startup alone is not a pass.
4. Send a generated sentinel payload from guest A to guest B, recover it only from guest B, and compare a host-side hash after the transfer. This prevents accidental host-spool bypass.
5. Choose and automate the guest transformations that replace the current VAX `troff`/uuencode and PDP-11 uudecode/`nroff` roles. The final `brad.bio.txt` must still satisfy the existing semantic contract.
6. Containerize or otherwise package the exact native builds, pin every source revision and disk checksum, and repeat the smoke tests in the intended CI execution environment.
7. Add all orchestrator, machine, and network configuration files to the vintage fingerprint and update the build log to describe the real NCP/1822 route.
8. Complete the asset licensing review before publishing images or disk artifacts.

## Accepted sequence

Bring up and automate the two-KA10/ITS network first. Once it passes the vintage-to-vintage application and payload-integrity gates, keep the same two-IMP orchestration boundary and investigate PDP-11 Network Unix V6 or another honest native-NCP endpoint as the heterogeneous replacement for one KA10.

I recommend the two-ITS path. It preserves an authentic native host interface and recovered IMP data path, is already one packaging step away from a two-vintage-host proof, and creates a stable network contract into which PDP-11 Network Unix or another historical endpoint can later be substituted.
