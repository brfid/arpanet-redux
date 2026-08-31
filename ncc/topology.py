"""Project-authored nominal topology inputs for NCC completed-run summaries."""

from __future__ import annotations

from typing import Any


def two_its_topology() -> dict[str, Any]:
    """Return a fresh nominal topology for the formal two-ITS acceptance run.

    This data deliberately describes configured identities and fixed display
    positions only.  It is not evidence that any component was running.
    """

    return {
        "components": [
            {
                "id": "host:176",
                "kind": "host",
                "label": "ITS 176",
                "position": {"x": 0, "y": 0},
                "endpoints": [{"id": "host:176:hi2", "label": "HI2"}],
            },
            {
                "id": "imp:62",
                "kind": "imp",
                "label": "IMP 62",
                "position": {"x": 1, "y": 0},
                "endpoints": [
                    {"id": "imp:62:hi2", "label": "HI2"},
                    {"id": "imp:62:mi1", "label": "MI1"},
                ],
            },
            {
                "id": "imp:6",
                "kind": "imp",
                "label": "IMP 6",
                "position": {"x": 2, "y": 0},
                "endpoints": [
                    {"id": "imp:6:mi1", "label": "MI1"},
                    {"id": "imp:6:hi2", "label": "HI2"},
                ],
            },
            {
                "id": "host:106",
                "kind": "host",
                "label": "ITS 106",
                "position": {"x": 3, "y": 0},
                "endpoints": [{"id": "host:106:hi2", "label": "HI2"}],
            },
        ],
        "links": [
            {"id": "link:176-62", "endpoints": ["host:176:hi2", "imp:62:hi2"]},
            {"id": "link:62-6", "endpoints": ["imp:62:mi1", "imp:6:mi1"]},
            {"id": "link:6-106", "endpoints": ["imp:6:hi2", "host:106:hi2"]},
        ],
        "routes": [
            {
                "id": "route:host176-to-host106",
                "components": ["host:176", "imp:62", "imp:6", "host:106"],
            }
        ],
    }
