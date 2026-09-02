# Historical 1975 host and IMP addressing

- **Observed:** 2026-09-02
- **Implementation observed:** No addressing change was made. The repository still configures ITS host `106` on IMP 6, Network UNIX host `176` on IMP 62, diagnostic hosts `076`/`002`/`003`, and the NCC receiver on IMP 5 host 0.
- **Scope:** Whether the project's configured host and IMP addresses correspond to real 1975 ARPANET assignments, what the primary sources say, and what a rework to a dated historical basis would require.

This note is the evidence base for a possible re-addressing. It records the address authority, the per-host findings, the sources that were checked and found not to carry address tables, and the design and sequencing a rework would need. It does not change configuration, and it does not promote any run.

## Finding

The repository's addressing arithmetic is already the historical scheme, and one of the two application hosts is already at a real July 1975 address. The other is at an address that could not have existed in 1975.

- ITS host `106` decodes to host 1 on IMP 6, decimal 70, which is **MIT-DMS** — a PDP-10 running ITS, listed as a SERVER. This is correct as configured and needs no change.
- Network UNIX host `176` decodes to host 1 on IMP 62. The highest IMP number in July 1975 is 58. IMP 62 did not exist, so neither did this address.
- The only July 1975 host whose sole listed operating system is UNIX is **RAND-ISO**, host 1 on IMP 7, decimal 71, octal `107`, a PDP-11/45 listed under Servers. It is the historically supported target for the Network UNIX guest.
- Diagnostic host `076` decodes to host 0 on IMP 62 and is likewise impossible. Hosts `002` and `003` decode to real occupied hosts (ARC-RD and UCSB-MOD75) that were not diagnostic endpoints.
- The NCC receiver sits at host 0 on IMP 5, a slot BBN's IMP 5 never filled. The real Network Control Center host was **BBN-NCC** at host 0 on IMP 40, decimal 40, octal `50`.

## Address authority

The primary source is the *ARPANET Directory*, NIC 32992, July 1975, in the SRI/NIC records at the Computer History Museum (accession 102805037). It carries a Host Addresses table sorted by address, an IMP No./Host No. configuration table sorted by IMP, and a Computer Systems table giving manufacturer, machine, operating system and function per host. No other consulted source combines all of these.

- URL: <https://archive.computerhistory.org/resources/access/text/2021/11/102805037-05-01-acc.pdf>
- sha256: `9b9bf95c75f7e04968fce426b589fa0338951fafb03a706c97ff28e90df0e89b`
- The retrieved copy is 117 pages. Host Addresses begins at page 103 of the printed document; IMP No./Host No. and Computer Systems follow.

The Directory states the encoding directly, on the Host Addresses page: "Decimal Host Address = IMP Number + (decimal 64 x Host Number)". This is exactly the encoding [`ncc/shared_topology.py`](../../ncc/shared_topology.py) already assumes when it validates `host_number` into 0..3, and exactly how the configured `hi1`/`hi2` device choice maps to host slots 0 and 1.

Two documents already in the operator's local corpus corroborate the model independently. BBN Report 2913 (Quarterly Technical Report 7, 1974) describes the IMP's routing tables as structured for up to 63 IMPs and 4 hosts per IMP, plus four fake hosts internal to each IMP — the 6-bit IMP field and 2-bit host field. BBN Technical Information Report 90 (November 1976) documents the NCC program's own lookup routines as `SNAME(imp, text)` returning a five-character site name and `HNAME(imp, host, array)` returning a host name from an IMP number and a host number in 0..3.

## IMP numbers are date-specific

This is the constraint that shapes any rework. Site numbering was reused as nodes moved and were decommissioned, so "the historical address of X" is not a well-formed question; only "the address of X on a stated date" is.

The evidence is in two documents already held locally. The July 1975 Directory gives IMP 3 as UCSB. BBN TIR 90's sample ARPA NETWORK SUMMARY of November 1976 gives SITE 3 as NUC, alongside SITE 1 UCLA, SITE 2 SRI-5, SITE 4 UTAH and SITE 5 BBN. The same TIR 90 line table shows a RAND-to-NELC circuit that does not correspond to anything in the July 1975 Directory, where NELC has no host at all.

A rework must therefore name one dated snapshot as its authority in the schema itself, not merely in prose. July 1975 (NIC 32992) is the natural choice for this project because it is contemporary with the recovered 1973 IMP firmware's operating era, sits inside the pre-1976 short-leader regime the project depends on, and is the only located source carrying address, site, machine, operating system and service status together.

## Per-host findings

### ITS guest — already correct

Host `106` on IMP 6, host slot 1, decimal 70, is MIT-DMS. The Directory's Servers table gives it as a PDP-10 running ITS, accounts contact S. Pitkin, described as a research facility providing MDL. The same entry notes that MIT-DMS ran SURVEY, which monitored network host availability and response time — so pairing this host with a monitoring surface, as the project's NCC compositions do, has a historical warrant rather than being only an aesthetic choice.

The promoted guest image already greets with `MIT Dynamic Modelling PDP-10`. Address, machine, operating system and greeting all agree with the source. No change is required, and none should be made.

| Host/IMP | Decimal | Octal | Hostname | Computer | Op sys | Status |
|---|---|---|---|---|---|---|
| 0/6 | 6 | 6 | MIT-DEVMULTICS | H-68/80 | MULTICS | Server, limited |
| 1/6 | 70 | 106 | MIT-DMS | PDP-10 | ITS | Server |
| 2/6 | 134 | 206 | MIT-AI | PDP-10 | ITS | Server, limited |
| 3/6 | 198 | 306 | MIT-ML | PDP-10 | ITS | Server, limited |

All four host slots on IMP 6 were occupied in July 1975. Note one scan defect worth carrying forward: the IMP No./Host No. table renders MIT-ML's decimal address as 196 while the Host Addresses table gives 198, and 3 × 64 + 6 = 198. Any registry built from this source should carry the arithmetic check that catches exactly this class of transcription error.

### Network UNIX guest — impossible address, one supported target

Host `176` decodes to host 1 on IMP 62. The July 1975 Directory's highest IMP number is 58, with NYU at 0/58 and BNL at 1/58; there is no IMP 59 through 63. This is not a numbering gap. BBN Report 3063 (Quarterly Technical Report 1, 1975) states the network had 56 nodes, 24 of them TIPs, at the end of the first week of the second quarter, and the same report describes BBN as still studying what expansion beyond 63 nodes would require.

The Directory lists exactly three PDP-11s with UNIX among their operating systems.

| Host/IMP | Decimal | Octal | Hostname | Computer | Op sys | Function |
|---|---|---|---|---|---|---|
| 1/7 | 71 | 107 | RAND-ISO | PDP-11/45 | UNIX | Server. Very large data bases, intelligent terminals. "Not yet up as a Server" |
| 0/1 | 1 | 1 | UCLA-ATS | PDP-11/45 | ANTS, ELF, UCLA-VMM, UNIX | Network analysis and modeling |
| 1/34 | 98 | 142 | UCB | PDP-11/40 | ELF, DOS, RSX11-M, UNIX | Speech and graphics protocol research |

**RAND-ISO, host 1 on IMP 7, octal `107`** is the recommended target. It is the only entry whose sole listed operating system is UNIX, it is a PDP-11/45, and it is listed under Servers — which matches what the project's guest actually is, since it both originates and accepts TELNET.

Two properties make the move cheap. The PDP-11 does not know its own address: [`docs/research/imp11a-device.md`](imp11a-device.md) records that `176` is simply the address IMP 62's `hi2` has carried since an ITS guest occupied that port, and the guest never self-identifies. And IMP 7 is already instantiated in the project's NCC compositions, so the number is not new to the topology — it merely stops being arbitrary. The functional change is one line in the IMP configuration the PDP-11 attaches to; no guest media rebuild is involved.

### Provenance of the preserved source is a separate question

The pin in [`pins/sources.lock.toml`](../../pins/sources.lock.toml) describes `network-unix-v6` as "SRI/NOSC Network UNIX V6". That naming post-dates the target year. NOSC took that name in 1977. Neither NOSC nor NELC appears as a host in the July 1975 Directory; NUC (Naval Undersea Center) appears only as an organization, with a liaison whose network mailbox was on `UTAH-10`. By November 1976 a RAND-to-NELC line exists in BBN's line table, so the Navy association is real but later than 1975.

The provenance of the preserved source code and the identity of the 1975 host that should run it are independent. A rework should keep them separate and not let the pin's name drive the address.

### Remaining configured addresses

| In the repository | Decodes to | July 1975 | Verdict |
|---|---|---|---|
| NCC receiver, IMP 5 host 0 | 0/5 | Slot vacant. IMP 5 (BBN) carried BBN-11X 1/5, BBN-11XB 2/5, BBN-TENEXA 3/5 | Decide |
| The real NCC | 0/40 | BBN-NCC, decimal 40, octal `50`. NCC-TIP beside it at 2/40, contact A. McKenzie | Available |
| Linux NCP `076` | 0/62 | No such IMP | Impossible |
| Linux NCP `002` | 0/2 | ARC-RD at SRI, a PDP-11/40 running ELF, front-end research for NSW | Occupied |
| Linux NCP `003` | 0/3 | UCSB-MOD75, a server | Occupied |
| Router oracle's hostless IMP 4 | — /4 | Utah. UTAH-10 at 0/4 and UTAH-TIP at 2/4; not hostless | Decide |

The diagnostic endpoint deserves particular care. `linux-ncp` is explicitly not a historical application host, and the README already says so; giving it a real site's address would quietly assert the opposite. The cleaner treatment is to make its synthetic status structural rather than incidental — place it on an IMP number in 59..63, inside the protocol's 6-bit range so the recovered firmware is untroubled, and outside the July 1975 network so no reader can mistake it for a site.

## MIT and RAND were never adjacent

The project's core composition places its two application hosts on IMPs joined by a single modem line. IMP 6 was in Cambridge and IMP 7 was in Santa Monica, and they were not neighbours in any year. BBN TIR 90's November 1976 line table shows MIT-MAC's circuits running to CCA, WPAFB and the MIT TIP, and RAND's running to ISI and NELC.

This is not a reason to reject historical addressing. It is a reason to state which claim the project is making. The repository already separates configured intent from observation, and a two-IMP composition has never claimed to be a historical route. Naming the endpoints correctly while compressing the path between them is defensible provided it is declared. The alternative — modelling a real 1975 path — costs one H316 process per intermediate hop and requires a 1975 line table that the consulted corpus does not contain.

## What the local corpus does and does not contain

`~/src/arpanet-sources` holds 42 PDFs, including the BBN quarterly technical reports, the NCC material, and two partial ARPANET Completion Report scans. Text was extracted from all of them and searched for address and site tables. Recording the negative result here so the search is not repeated.

Useful for addressing:

- BBN Report 3063 (QTR 1, 1975), pages 17 and 19: geographic and logical maps at the start of the second quarter of 1975, plus the 56-node count. The logical map labels every site with its host machine types. It carries no IMP numbers and no host addresses.
- BBN Report 2913 (QTR 7, 1974): the 63-IMP, 4-hosts-per-IMP table structure.
- BBN TIR 90 (November 1976): `SNAME`/`HNAME` semantics, the sample network summary giving SITE 1 through SITE 5, and the line table used above for adjacency.
- BBN Report 2309 (QTR 12, 1972): names the MIT Dynamic Modeling system as an operational host that users relayed through to reach Multics. Colour, not address evidence.

Not present anywhere in the corpus:

- Any IMP-number to site table beyond the first five sites.
- Any host address listing. The maps carry site names and machine types only.
- The Completion Report appendices. The draft explicitly points at the table that would settle this — in its description of the TIP `OPEN` command it states that Appendix A lists the host numbers of all sites currently in the network — but neither local scan includes the appendices. The 208-page copy is Chapter III Section 1 only; the 942-page draft ends at Chapter III Section 4.

The July 1975 Directory obtained externally supersedes this gap for the 1975 target year. The Completion Report appendices would still be worth having for other years.

## Where addresses live in this repository

Any rework has to touch four layers. Three are cheap and one is not.

1. **IMP number** — one line per configuration file, `set imp num=<n>` under [`config/imp/`](../../config/imp/). Nothing in the repository constrains the value; [`ncc/shared_topology.py`](../../ncc/shared_topology.py) requires only a positive integer. The real constraint is the firmware's 6-bit field.
2. **Host slot** — which `hi1`/`hi2` device the guest attaches to. Slot 0 is proven in production by the NCC receiver on IMP 5; slot 1 is what both application hosts use.
3. **Guest self-knowledge** — asymmetric. Network UNIX needs nothing. ITS assembles its host number into the monitor and needs a rebuild.
4. **Identifiers and evidence** — the expensive layer, described below.

Addresses are currently spelled into roughly 1,100 identifiers across about 64 files: `host106_work`, `--host106-config`, `host106.console.log`, `host106-attach-only.simh`, `route:host176-to-host106`, `application.network-unix-host106-ready`, and similar, spanning controllers, NCC display modules, log filenames, JSONL event names, route ids and test fixtures. The topology is also declared twice — once in [`config/topologies/`](../../config/topologies/) and again as a literal dict in [`ncc/topology.py`](../../ncc/topology.py).

The ITS re-address mechanism is the one genuinely undocumented step. The `pdp10-its` pin is checked out as `work/its-readdress-src` "for generic KA host 176", and [the two-ITS readiness note](../experiments/2026-08-28-two-its-readiness.md) records that image booting and self-identifying at `176` natively, without the runtime `IMPUS` override the earlier debugger-modified disk required. How the tree was re-addressed is not recorded anywhere in this repository; it exists only as a local modification in the external tree. Documenting it as a build parameter is a precondition for a clean rework.

Evidence invalidation is the unavoidable cost. Acceptance is bound to exact runs with byte-level decodes and log hashes — [`imp11a-device.md`](imp11a-device.md) asserts the guest RST as `000106 000000 000010 000001 000014`, and [the KA10 ingress-grammar note](../experiments/2026-09-01-ka10-host-ingress-grammar.md) pins a debug-log SHA-256. Changing a destination address changes those leader bytes. Gates 3, 4, 4H, 4I, 4J, 5 and both NCC gates would need fresh accepted runs. Per [`AGENTS.md`](../../AGENTS.md) and the configuration boundary's intent-versus-observation rule, existing dated experiment notes must not be edited to match; a re-address is a new composition with new dated experiments.

## Design principles a rework should follow

1. **One dated authority, pinned like any other source.** NIC 32992 belongs in [`pins/`](../../pins/) with its hash, alongside the simulator and guest-software pins, because it becomes an input to what the project claims.
2. **Identity is data, checked against the source.** A machine-readable registry of the Directory's rows, plus a test that refuses any claimed hostname, machine or operating system not matching a row. This expresses the existing "no invented values" rule as code.
3. **Addresses are computed, never typed.** The topology declares `imp_number` and `host_number`; decimal and octal are derived. The arithmetic check is what catches transcription errors like the 196/198 discrepancy noted above.
4. **Identifiers name roles, not addresses.** `its_host` and `unix_host`, so a future re-address touches configuration and nothing else.

A sketch of the topology change:

```json
{
  "address_authority": "nic-32992-1975-07",
  "components": [
    {
      "id": "host:its",
      "kind": "host",
      "imp_number": 6,
      "host_number": 1,
      "simh_device": "hi2",
      "identity": {
        "hostname": "MIT-DMS",
        "computer": "PDP-10",
        "operating_system": "ITS",
        "status": "SERVER"
      }
    },
    {
      "id": "host:unix",
      "kind": "host",
      "imp_number": 7,
      "host_number": 1,
      "simh_device": "hi2",
      "identity": {
        "hostname": "RAND-ISO",
        "computer": "PDP-11/45",
        "operating_system": "UNIX",
        "status": "SERVER"
      }
    }
  ]
}
```

`address_decimal` is `imp_number + 64 * host_number` and `address_octal` is its octal form, both derived and never authored: `host:its` resolves to 70 / `0o106`, `host:unix` to 71 / `0o107`. Each `identity` block validates against the registry row for that IMP and host pair under the named authority. A synthetic component declares no identity and is rejected if it claims one, which is how the diagnostic oracle's status stops depending on a sentence in the README.

## Suggested sequence

Ordered so that every phase before the fifth is behaviour-preserving. Nothing needs re-running until phase 5.

1. Pin NIC 32992 and land this note. No code, no re-runs.
2. Document how ITS gets its address, so `make its` becomes the re-addressing tool, and retire the vestigial `IMPUS=` override in the host boot files. Documentation plus one confirming rebuild.
3. Introduce the registry, the derived-address schema fields and the validation test; collapse the duplicate topology in `ncc/topology.py` onto the JSON. Keep every current number unchanged: the ITS host validates clean immediately and the PDP-11 is marked synthetic pending phase 5.
4. Rename identifiers from addresses to roles. Wide and mechanical, covered by existing tests, and it makes the phase-5 diff readable.
5. Re-address the PDP-11 to RAND-ISO and re-run every affected gate, writing new dated experiments.
6. Settle the remaining identities, then update the README and [`docs/architecture.md`](../architecture.md) and write the ADR recording the change of position.

## Open decisions

- **Does the project now assert historical site identity?** The README and [`docs/architecture.md`](../architecture.md) currently disclaim it. Suggested position: assert host identity, cited and dated; keep topology explicitly a bounded composition. That preserves the existing intent-versus-observation boundary and makes it carry more.
- **Accept the MIT–RAND line, or model a real path?** Suggested: accept it, declared in the topology file itself rather than only in prose, so the claim travels with the data.
- **Where does the NCC receiver live?** Suggested: move it to 0/40. The NCC surface is the part of the project that already grounds itself in dated BBN operational sources, so an address disagreeing with them is the sharpest remaining inconsistency.
- **What address does a synthetic host get?** Suggested: an IMP number in 59..63, so the registry check proves the host is synthetic instead of asserting it.

## Corrections to earlier reasoning in this investigation

- An initial reading suggested the University of Illinois CAC as the natural 1975 home for Network UNIX. The Directory lists ILL-CAC as a PDP-11/20 running ANTS, a terminal concentrator, and ILL-NTS at 1/12 as a separate host. Illinois is not the target; RAND-ISO is.
- The project's `176` is octal. Decimal 176 is octal `260`, which is AFWL-TIP at 2/48 — unrelated, and worth stating because the two readings are easy to confuse when checking this note against the source.

## Related

- [`imp11a-device.md`](imp11a-device.md) — establishes that the PDP-11's address is a property of the IMP port, not the guest.
- [Two-ITS readiness](../experiments/2026-08-28-two-its-readiness.md) — the only record of the natively-built host-`176` ITS image and the `IMPUS` override it replaced.
- [NCC telemetry](2026-08-30-ncc-telemetry.md) — the dated basis for the NCC surface whose receiver address is questioned above.
- [Configuration boundary](../../config/README.md) — the intent-versus-observation rule any re-addressing must respect.
