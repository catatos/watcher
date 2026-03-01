from __future__ import annotations

import json
import os
from pathlib import Path

from .models import (
    AlertsConfig,
    AvailabilityRules,
    FilterConfig,
    ScheduleConfig,
    WatchConfig,
    WatchItem,
)

try:
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    yaml = None


class ConfigError(Exception):
    pass


def _resolve_env_vars(value: str) -> str:
    value = value.strip()
    if value.startswith("${") and value.endswith("}"):
        key = value[2:-1].strip()
        return os.getenv(key, "")
    return value


def _load_rules(raw: dict | None) -> AvailabilityRules:
    raw = raw or {}
    return AvailabilityRules(
        in_stock_keywords=list(raw.get("in_stock_keywords", [])),
        out_of_stock_keywords=list(raw.get("out_of_stock_keywords", [])),
        pickup_only_keywords=list(raw.get("pickup_only_keywords", [])),
        shipping_keywords=list(raw.get("shipping_keywords", [])),
    )


def _load_raw_text(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")

    if yaml is not None:
        try:
            return yaml.safe_load(content) or {}
        except Exception as exc:
            raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    # Fallback when PyYAML is unavailable: accept JSON (valid YAML subset).
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            "PyYAML is not installed, and config is not JSON-compatible YAML. "
            "Install PyYAML or convert watchlist.yaml to JSON format."
        ) from exc


def load_config(path: str | Path) -> WatchConfig:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config not found: {path}")

    data = _load_raw_text(path)

    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ConfigError("'items' must be a non-empty list")

    items: list[WatchItem] = []
    for raw in raw_items:
        raw_headers = dict(raw.get("request_headers", {}))
        headers = {str(k): _resolve_env_vars(str(v)) for k, v in raw_headers.items()}
        item = WatchItem(
            id=str(raw["id"]),
            name=str(raw["name"]),
            url=str(raw["url"]),
            retailer=str(raw.get("retailer", "generic")),
            enabled=bool(raw.get("enabled", True)),
            fetch_strategy=str(raw.get("fetch_strategy", "urllib")),
            request_headers=headers,
            availability_rules=_load_rules(raw.get("availability_rules")),
        )
        items.append(item)

    schedule_raw = data.get("schedule", {})
    alerts_raw = data.get("alerts", {})
    filters_raw = data.get("filters", {})

    schedule = ScheduleConfig(
        check_interval_hours=max(1, int(schedule_raw.get("check_interval_hours", 1))),
        daily_summary_time_local=str(schedule_raw.get("daily_summary_time_local", "20:00")),
    )
    alerts = AlertsConfig(
        repeat_hours_while_in_stock=max(
            1, int(alerts_raw.get("repeat_hours_while_in_stock", 12))
        ),
        telegram_enabled=bool(alerts_raw.get("telegram_enabled", True)),
        send_daily_summary=bool(alerts_raw.get("send_daily_summary", False)),
    )
    filters = FilterConfig(
        online_shipping_only=bool(filters_raw.get("online_shipping_only", True)),
        exclude_pickup_only=bool(filters_raw.get("exclude_pickup_only", True)),
    )

    return WatchConfig(items=items, schedule=schedule, alerts=alerts, filters=filters)
