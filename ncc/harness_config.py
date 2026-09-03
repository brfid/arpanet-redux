"""Shared environment and simulator-configuration harness primitives."""

from __future__ import annotations

import os
from pathlib import Path


PORT_VARIABLES = (
    "BRFID_IMP6_MI_PORT",
    "BRFID_IMP62_MI_PORT",
    "BRFID_IMP6_HI_PORT",
    "BRFID_HOST_A_IMP_PORT",
    "BRFID_IMP62_HI_PORT",
    "BRFID_HOST_B_IMP_PORT",
)


def validate_environment() -> None:
    for name in PORT_VARIABLES:
        value = os.environ.get(name, "")
        if not value.isdigit() or not 1 <= int(value) <= 65535:
            raise ValueError(f"{name} is not a valid UDP port")


def create_host106_attach_config(source: Path, destination: Path) -> None:
    text = source.read_text(encoding="ascii")
    boot_expect = (
        '# Boot the host-106 ITS image and connect its NCP interface to IMP 6.\n'
        'expect -p "DSKDMP" send "L\\e2\\eNITS\\rIMPUS=\\eG\\r" ; continue\n\n'
    )
    if not text.startswith(boot_expect) or not text.endswith("boot ptr\n"):
        raise ValueError("host 106 configuration has an unexpected boot sequence")
    destination.write_text(
        text.removeprefix(boot_expect).removesuffix("boot ptr\n"),
        encoding="ascii",
    )
