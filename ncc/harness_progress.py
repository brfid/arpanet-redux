"""Modern controller progress; these records have no acceptance authority."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import TextIO

from ncc.harness_manifest import append_manifest


def printable_record(value: object) -> str:
    return ''.join(character if ' ' <= character <= '~' else '?' for character in str(value))[:1024]


class ControllerProgress:
    def __init__(self, manifest: Path, live_stream: TextIO | None = None) -> None:
        self.manifest = manifest
        self.live_stream = live_stream
        self.sequence = 0
        self.current_stage = 'controller initialization'
        self.current_wait = ''
        self.failed = False

    def emit(self, description: str) -> None:
        self.sequence += 1
        text = printable_record(description)
        append_manifest(self.manifest, f'progress.controller.{self.sequence}', text)
        print(f'[controller] {text}', file=sys.stderr, flush=True)
        if self.live_stream is not None:
            # Losing a progress consumer must not prevent owned-resource cleanup.
            try:
                print(f'[controller] {text}', file=self.live_stream, flush=True)
            except OSError:
                pass

    def stage(self, name: str) -> None:
        self.current_stage = name
        self.current_wait = ''
        self.emit(name)

    def waiting(self, condition: str, timeout: float) -> None:
        self.current_wait = f'waiting up to {timeout:g}s for {condition}'
        self.emit(f'{self.current_stage}: {self.current_wait}')

    def failure(self, error: Exception) -> None:
        description = printable_record(f'{self.current_stage}: {self.current_wait}; {type(error).__name__}: {error}')
        append_manifest(self.manifest, 'failure.controller', description)
        self.failed = True
        self.emit(f'failed: {description}')
