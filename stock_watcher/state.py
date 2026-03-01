from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@dataclass
class ItemState:
    status: str = "UNKNOWN"
    last_alert_at: datetime | None = None
    last_event_hash: str | None = None


@dataclass
class WatcherState:
    items: dict[str, ItemState]
    last_summary_sent_at: datetime | None = None

    @classmethod
    def empty(cls) -> "WatcherState":
        return cls(items={}, last_summary_sent_at=None)


def load_state(path: str | Path) -> WatcherState:
    p = Path(path)
    if not p.exists():
        return WatcherState.empty()

    raw = json.loads(p.read_text(encoding="utf-8"))
    raw_items: dict[str, Any] = raw.get("items", {})
    items: dict[str, ItemState] = {}
    for item_id, item_raw in raw_items.items():
        items[item_id] = ItemState(
            status=str(item_raw.get("status", "UNKNOWN")),
            last_alert_at=_parse_dt(item_raw.get("last_alert_at")),
            last_event_hash=item_raw.get("last_event_hash"),
        )

    return WatcherState(
        items=items,
        last_summary_sent_at=_parse_dt(raw.get("last_summary_sent_at")),
    )


def save_state(path: str | Path, state: WatcherState) -> None:
    p = Path(path)
    payload = {
        "items": {
            item_id: {
                "status": s.status,
                "last_alert_at": _to_iso(s.last_alert_at),
                "last_event_hash": s.last_event_hash,
            }
            for item_id, s in state.items.items()
        },
        "last_summary_sent_at": _to_iso(state.last_summary_sent_at),
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
