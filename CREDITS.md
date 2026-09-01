# Credits

ARPANET Redux depends on preserved software, primary documentation, and modern simulator work maintained by many people and institutions.

## Software and preservation projects

- [ARPANET in a Box](https://github.com/obsolescence/arpanet) preserves recovered IMP software, simulator configurations, and prepared guest systems.
- [linux-ncp](https://github.com/larsbrinkhoff/linux-ncp) provides the diagnostic NCP endpoint used to isolate routing and host-interface behavior.
- The [H316 SIMH](https://github.com/larsbrinkhoff/simh), [KA10 SIMH](https://github.com/larsbrinkhoff/ka10-simh), [open-simh](https://github.com/open-simh/simh), and project forks provide the simulators used by the laboratory.
- [PDP-10/ITS](https://github.com/PDP-10/its) and the [SRI/NOSC Network UNIX collection](https://www.tuhs.org/cgi-bin/utree.pl?file=SRI-NOSC) provide the historical guest systems and application sources.
- The [TUHS archive](https://www.tuhs.org/Archive/), [Bitsavers](https://bitsavers.org/), the [Computer History Museum](https://computerhistory.org/), and [Dave Walden's IMP-code collection](https://www.walden-family.com/impcode/) preserve source material used to establish behavior and provenance.

Exact build dependencies and revisions live in [`pins/sources.lock.toml`](pins/sources.lock.toml). Detailed citations stay with the decisions and findings they support in [`docs/adr/`](docs/adr/), [`docs/research/`](docs/research/), and [`docs/experiments/`](docs/experiments/). Redistribution status and release boundaries live in [`NOTICE.md`](NOTICE.md).
