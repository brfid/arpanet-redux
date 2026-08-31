"""Deterministic replay frames for read-only NCC run summaries."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .run_summary import RunSummary


@dataclass(frozen=True)
class ReplayFrame:
    """One ordered observation and the direct states known after it."""

    sequence: int
    observed_at: str
    observation_id: str
    subject_id: str
    category: str
    state: str
    known_states: Mapping[str, str]


def replay_frames(summary: RunSummary) -> tuple[ReplayFrame, ...]:
    """Replay direct observations in their validated sequence order.

    Derived states are intentionally not recalculated here.  A viewer receives
    those conclusions from the summary and can identify their supporting
    observations without turning the browser into a second reducer.
    """

    known_states: dict[str, str] = {}
    frames: list[ReplayFrame] = []
    for observation in summary.to_dict()["observations"]:
        known_states[observation["subject_id"]] = observation["state"]
        frames.append(
            ReplayFrame(
                sequence=observation["sequence"],
                observed_at=observation["observed_at"],
                observation_id=observation["id"],
                subject_id=observation["subject_id"],
                category=observation["category"],
                state=observation["state"],
                known_states=MappingProxyType(dict(known_states)),
            )
        )
    return tuple(frames)
