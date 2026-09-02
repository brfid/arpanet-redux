"""Passive selection between growing and completed NCC display projections."""

from __future__ import annotations

from pathlib import Path

from .coexistence_display import (
    CoexistenceDisplay,
    CoexistenceDisplayError,
    CoexistenceDisplaySnapshot,
)
from .failover_display import (
    FailoverDisplay,
    FailoverDisplayError,
    FailoverDisplaySnapshot,
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

    _COEXISTENCE_TOPOLOGY = "ncc-pdp11-its-coexistence"
    _FAILOVER_TOPOLOGY = "ncc-pdp11-its-application-failover"
    _HISTORICAL_LINE_TOPOLOGIES = {
        "ncc-alternate-path-fault",
        "ncc-line-loopback",
    }

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
        self._failover: FailoverDisplay | None = None

    @property
    def run_id(self) -> str:
        """Return the expected run identity before its sidecar exists."""

        return self.results_dir.name

    def snapshot(
        self,
    ) -> HistoricalDisplaySnapshot | CoexistenceDisplaySnapshot | FailoverDisplaySnapshot:
        """Return the strongest currently available existing display snapshot."""

        manifest = self._terminal_manifest()
        if manifest is not None:
            topology = manifest.get("topology")
            if topology == self._COEXISTENCE_TOPOLOGY:
                return self._coexistence_display().snapshot()
            if topology == self._FAILOVER_TOPOLOGY:
                return self.failover_display().snapshot()
            if topology in self._HISTORICAL_LINE_TOPOLOGIES:
                snapshot = self._historical_snapshot()
                if snapshot.mode != "completed":
                    status = snapshot.to_dict()["completion"]["status"]
                    raise NccBoardError(
                        "terminal historical-line result did not validate its "
                        f"completed summary ({status})"
                    )
                return snapshot
            raise NccBoardError(
                f"terminal result has unsupported board topology {topology!r}"
            )
        if not self._historical.stream_path.is_file():
            raise NccBoardPending(
                "waiting for the run's validated historical event stream"
            )
        return self._historical_snapshot()

    def _historical_snapshot(self) -> HistoricalDisplaySnapshot:
        """Return the existing historical projection with one error boundary."""

        try:
            return self._historical.snapshot()
        except HistoricalDisplayError as error:
            raise NccBoardError(str(error)) from error

    def _coexistence_display(self) -> CoexistenceDisplay:
        """Return the validated coexistence projection when applicable."""

        manifest = self._terminal_manifest()
        if manifest is None:
            raise NccBoardPending("validated completed run artifacts are not available")
        if manifest.get("topology") != self._COEXISTENCE_TOPOLOGY:
            raise NccBoardError(
                "the coexistence projection is available only for a validated "
                "NCC/PDP-11/ITS coexistence result"
            )
        if self._completed is None:
            try:
                self._completed = CoexistenceDisplay(
                    self.results_dir,
                    self.shared_topology_path,
                )
            except CoexistenceDisplayError as error:
                raise NccBoardError(str(error)) from error
        return self._completed

    def failover_display(self) -> FailoverDisplay:
        """Return the validated passive failover projection when applicable."""

        manifest = self._terminal_manifest()
        if manifest is None:
            raise NccBoardPending("validated completed run artifacts are not available")
        if manifest.get("topology") != self._FAILOVER_TOPOLOGY:
            raise NccBoardError(
                "the failover console projection is available only for a validated "
                "NCC/PDP-11/ITS application failover result"
            )
        if self._failover is None:
            try:
                self._failover = FailoverDisplay(
                    self.results_dir,
                    self.shared_topology_path,
                )
            except FailoverDisplayError as error:
                raise NccBoardError(str(error)) from error
        return self._failover

    def _terminal_manifest(self) -> dict[str, str] | None:
        """Return the manifest only after its three terminal fields are present."""

        manifest = self.results_dir / "runtime" / "run.env"
        try:
            lines = manifest.read_text(encoding="utf-8").splitlines()
        except (FileNotFoundError, OSError):
            return None
        values: dict[str, str] = {}
        for line in lines:
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value
        if all(values.get(key) for key in ("finished_utc", "outcome", "exit_status")):
            return values
        return None
