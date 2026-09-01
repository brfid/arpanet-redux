"""Passive selection between growing and completed NCC display projections."""

from __future__ import annotations

from pathlib import Path

from .coexistence_display import (
    CoexistenceDisplay,
    CoexistenceDisplayError,
    CoexistenceDisplaySnapshot,
)
from .historical_display import (
    HistoricalDisplayError,
    HistoricalDisplayObserver,
    HistoricalDisplaySnapshot,
)
from .shared_topology import (
    SharedTopology,
    SharedTopologyValidationError,
    load_shared_topology,
)


class NccBoardError(ValueError):
    """Raised when the board cannot expose a trustworthy available result."""


class NccBoardPending(NccBoardError):
    """Raised while the named run has no complete historical event header yet."""


class NccBoardDisplay:
    """Expose existing validated live or completed snapshots through one board."""

    def __init__(
        self,
        results_dir: str | Path,
        shared_topology_path: str | Path,
    ) -> None:
        self.results_dir = Path(results_dir)
        self.shared_topology_path = Path(shared_topology_path)
        try:
            self.shared_topology: SharedTopology = load_shared_topology(
                self.shared_topology_path
            )
            self._historical = HistoricalDisplayObserver(
                self.results_dir / "historical-events.jsonl",
                self.shared_topology_path,
                results_dir=self.results_dir,
            )
        except (HistoricalDisplayError, SharedTopologyValidationError) as error:
            raise NccBoardError(str(error)) from error
        self._completed: CoexistenceDisplay | None = None

    @property
    def run_id(self) -> str:
        """Return the expected run identity before its sidecar exists."""

        return self.results_dir.name

    def snapshot(
        self,
    ) -> HistoricalDisplaySnapshot | CoexistenceDisplaySnapshot:
        """Return the strongest currently available existing display snapshot."""

        if self._manifest_is_terminal():
            return self.completed_display().snapshot()
        if not self._historical.stream_path.is_file():
            raise NccBoardPending(
                "waiting for the run's validated historical event stream"
            )
        try:
            return self._historical.snapshot()
        except HistoricalDisplayError as error:
            raise NccBoardError(str(error)) from error

    def completed_display(self) -> CoexistenceDisplay:
        """Return the cached completed adapter only after formal termination."""

        if not self._manifest_is_terminal():
            raise NccBoardPending("validated completed run artifacts are not available")
        if self._completed is None:
            try:
                self._completed = CoexistenceDisplay(
                    self.results_dir,
                    self.shared_topology_path,
                )
            except CoexistenceDisplayError as error:
                raise NccBoardError(str(error)) from error
        return self._completed

    def _manifest_is_terminal(self) -> bool:
        manifest = self.results_dir / "runtime" / "run.env"
        try:
            lines = manifest.read_text(encoding="utf-8").splitlines()
        except (FileNotFoundError, OSError):
            return False
        values: dict[str, str] = {}
        for line in lines:
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value
        return all(
            values.get(key)
            for key in ("finished_utc", "outcome", "exit_status")
        )
