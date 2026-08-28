# Asset, provenance, and licensing notice

This repository intentionally excludes third-party source checkouts, disk images, recovered IMP firmware, simulator binaries, generated media, and raw run logs. Source locations and exact revisions are recorded in [`pins/sources.lock.toml`](pins/sources.lock.toml), while known external asset identities are recorded in [`pins/arpanet-assets.sha256`](pins/arpanet-assets.sha256).

The tested ARPANET in a Box revision has no bundle-wide root license, and its prepared assets do not share one clearly stated redistribution grant. The tested `linux-ncp` revision has no root license file. PDP-10/ITS uses mixed, file-scoped terms. SRI/NOSC Network UNIX V6 and its NOSC overlay also lack a root license that can safely be assumed to cover every included file. These are conservative engineering release boundaries, not legal conclusions.

The SIMH command files under [`config/`](config/) are minimal project-specific compositions written for the topologies in this repository. They invoke simulator commands and load external firmware or media at runtime; they do not include those external materials. Their provenance and runtime dependencies are documented in [`config/README.md`](config/README.md).

No license has yet been selected for the original work in this repository. Public visibility does not grant permission to reproduce, distribute, or create derivative works beyond rights supplied by the hosting service's terms. Any future repository license must cover only original work and must not be presented as relicensing fetched or generated third-party material.

Do not publish firmware, guest binaries, disk images, source bundles, container layers, or derived system images until every included component has been reviewed independently. A checksum proves identity, not permission to redistribute.
