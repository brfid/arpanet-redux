"""Guest-console shutdown for disk workspaces; never a memory checkpoint."""

from __future__ import annotations

from pathlib import Path
import re
import time
import uuid

from ncc.guest_workspace import write_json
from ncc.harness_manifest import append_manifest, sha256
from ncc.harness_process import PtyProcess, WRU


UNIX_PROMPT = rb"\r\n# ?"
ITS_COMPLETE = b"SHUTDOWN COMPLETE"


def command(process: PtyProcess, text: str, prompt: bytes = UNIX_PROMPT, timeout: float = 30) -> bytes:
    start = process.position()
    process.cursor = start
    process.send(text + "\r")
    process.expect(prompt, timeout=timeout)
    return process.output_from(start)


def quiet_command(process: PtyProcess, text: str, timeout: float = 30) -> None:
    output = command(process, text, timeout=timeout)
    lines = output.replace(b"\r", b"").split(b"\n")
    if any(line.strip() for line in lines[1:-1]):
        raise RuntimeError(f"guest workspace preparation failed: {output!r}")


def prepare_unix_shutdown(process: PtyProcess, source: Path, manifest: Path) -> str:
    """Compile original stop code while the controller owns a known root shell."""
    program = "/tmp/w" + uuid.uuid4().hex[:8]
    directory = program + ".d"
    guest_source = directory + "/stop.c"
    data = source.read_bytes()
    if any(byte > 127 for byte in data) or b"\x04" in data or b"\n.\n" in data:
        raise ValueError("workspace stop source must be plain ASCII")
    quiet_command(process, f"mkdir {directory}")
    quiet_command(process, f"chdir {directory}")
    process.cursor = process.position()
    process.send(f"ed {guest_source}\r")
    time.sleep(0.2)
    process.send_slow(b"a\r" + data.replace(b"\n", b"\r") + b".\rw\rq\r", delay=0.03)
    process.expect(UNIX_PROMPT, timeout=30)
    uploaded = command(process, "cat stop.c").replace(b"\r", b"")
    prefix, separator, contents = uploaded.partition(b"cat stop.c\n")
    if prefix.strip() or not separator or contents.rstrip(b" ") != data + b"#":
        raise RuntimeError("guest workspace stop source did not survive console upload exactly")
    quiet_command(process, "cc stop.c", timeout=120)
    quiet_command(process, f"mv a.out {program}")
    quiet_command(process, "rm stop.c")
    quiet_command(process, "chdir /")
    quiet_command(process, f"rmdir {directory}")
    append_manifest(manifest, "sha256.workspace-stop-source", sha256(source))
    append_manifest(manifest, "workspace.stop-program", program)
    return program


def stop_its(process: PtyProcess) -> None:
    """Request the guest's bounded shutdown and require its completion marker."""
    start = process.position()
    process.cursor = start

    def step(data: bytes, expected: bytes, timeout: float = 30) -> bool:
        if ITS_COMPLETE in process.output_from(start):
            return True
        # LOCK resets its input after printing the question. Match the paced
        # console interaction, so an answer cannot arrive before that reset.
        time.sleep(0.2)
        process.send_slow(data, delay=0.03)
        which, _ = process.expect_any((ITS_COMPLETE, expected), timeout=timeout)
        return which == 0

    if step(b":lock\r", rb"LOCK\.[0-9]+\r\n_"):
        pass
    elif step(b"5kill", rb"GO DOWN\?\r\n"):
        pass
    else:
        time.sleep(0.2)
        process.send_slow(b"y", delay=0.03)
        which, _ = process.expect_any(
            (ITS_COMPLETE, rb"REPLACE SYS;DOWN MAIL\?\r\n", rb"ENDED BY \^C\r\n"), timeout=30,
        )
        if which == 1:
            if step(b"y", rb"ENDED BY \^C\r\n"):
                which = 0
        if which != 0:
            time.sleep(0.2)
            process.send(b"\x03")
            # Five guest minutes is LOCK's minimum notice. An otherwise idle
            # system can finish immediately. Never replace this with a sleep.
            process.expect(ITS_COMPLETE, timeout=330)
    process.cursor = process.position()
    process.send(WRU)
    process.expect(b"sim> ", timeout=10)
    process.state = "PROMPT"


def stop_unix(process: PtyProcess, program: str, token: str) -> None:
    """Enter single-user operation, stop writers, sync, and stop the CPU."""
    marker = "ARPANET_WS_" + token
    process.cursor = process.position()
    process.send(b"\x7f\r")
    prompt, _ = process.expect_any((UNIX_PROMPT, rb"(?:^|\r\n)\* "), timeout=30)
    if prompt == 1:
        # After remote ITS shutdown the preserved client can remain at its
        # own command prompt. Leave it through its documented command.
        command(process, "bye")
    output = command(process, "echo " + marker)
    if not re.search(rb"\r\n" + marker.encode() + rb"\r\n# ?", output):
        raise RuntimeError("Network UNIX did not return to its root shell; previous save will be retained")
    process.cursor = process.position()
    process.send(WRU)
    process.expect(b"sim> ", timeout=10)
    process.state = "PROMPT"
    command(process, "deposit sr 173030", b"sim> ")
    process.send("continue\r")
    process.state = "RUNNING"
    time.sleep(0.2)
    command(process, "kill -1 1")
    shell = command(process, "echo $$")
    pids = re.findall(rb"(?:^|\r\n)([0-9]{1,5})\r\n", shell)
    if len(pids) != 1 or not 2 <= int(pids[0]) <= 32767:
        raise RuntimeError("single-user shell did not identify its guest process")
    process.cursor = process.position()
    process.send(f"{program} {marker} {int(pids[0])}\r")
    process.expect(rb"\r\n" + marker.encode() + rb"\r\n", timeout=180)
    process.cursor = process.position()
    process.send(WRU)
    process.expect(b"sim> ", timeout=10)
    process.state = "PROMPT"
    queued = command(process, "show queue", b"sim> ")
    if re.search(rb"(?m)^\s*RL(?:[0-9]|\s)", queued):
        raise RuntimeError("PDP-11 disk activity remains queued after guest synchronization")


def save_shutdown_proof(results: Path, manifest: Path, token: str) -> None:
    path = results / "workspace-shutdown.json"
    write_json(path, {
        "format": 1, "run_id": results.name, "lease_token": token,
        "its": "shutdown-complete", "pdp11": "writers-stopped-and-synced",
    })
    append_manifest(manifest, "sha256.workspace-shutdown", sha256(path))
