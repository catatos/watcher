from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class StockStatus(str, Enum):
    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    UNKNOWN = "UNKNOWN"


@dataclass
class AvailabilityRules:
    in_stock_keywords: list[str] = field(default_factory=list)
    out_of_stock_keywords: list[str] = field(default_factory=list)
    pickup_only_keywords: list[str] = field(default_factory=list)
    shipping_keywords: list[str] = field(default_factory=list)


@dataclass
class WatchItem:
    id: str
    name: str
    url: str
    retailer: str
    enabled: bool = True
    fetch_strategy: str = "urllib"
    request_headers: dict[str, str] = field(default_factory=dict)
    availability_rules: AvailabilityRules = field(default_factory=AvailabilityRules)


@dataclass
class ScheduleConfig:
    check_interval_hours: int = 1
    daily_summary_time_local: str = "20:00"


@dataclass
class AlertsConfig:
    repeat_hours_while_in_stock: int = 12
    telegram_enabled: bool = True
    send_daily_summary: bool = False


@dataclass
class FilterConfig:
    online_shipping_only: bool = True
    exclude_pickup_only: bool = True


@dataclass
class WatchConfig:
    items: list[WatchItem]
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    alerts: AlertsConfig = field(default_factory=AlertsConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)


@dataclass
class CheckResult:
    item_id: str
    item_name: str
    url: str
    retailer: str
    status: StockStatus
    matched_text: str
    checked_at: datetime
    error_type: str | None = None
