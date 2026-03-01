from __future__ import annotations

import re
from dataclasses import dataclass

from .models import AvailabilityRules, FilterConfig, StockStatus


@dataclass
class ParseOutcome:
    status: StockStatus
    matched_text: str


DEFAULT_IN_STOCK = [
    "in stock",
    "add to cart",
    "add to bag",
    "ships today",
    "ready to ship",
    "buy now",
]
DEFAULT_OUT_OF_STOCK = [
    "out of stock",
    "sold out",
    "currently unavailable",
    "backordered",
    "backorder",
    "unavailable",
    "notify me when available",
    "join waitlist",
]
DEFAULT_PICKUP_ONLY = [
    "pickup only",
    "in-store only",
    "available for pickup",
    "pick up in store",
]
DEFAULT_SHIPPING = [
    "ship to home",
    "shipping available",
    "delivery available",
    "ready to ship",
    "ships",
]


def _clean_text(html: str) -> str:
    text = re.sub(r"<script[\\s\\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\\s\\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\\s+", " ", text)
    return text.strip().lower()


def _collect_matches(text: str, candidates: list[str]) -> list[str]:
    hits: list[str] = []
    for candidate in candidates:
        c = candidate.lower().strip()
        if c and c in text:
            hits.append(c)
    return hits


def parse_availability(html: str, rules: AvailabilityRules, filters: FilterConfig) -> ParseOutcome:
    text = _clean_text(html)

    in_keywords = DEFAULT_IN_STOCK + rules.in_stock_keywords
    out_keywords = DEFAULT_OUT_OF_STOCK + rules.out_of_stock_keywords
    pickup_keywords = DEFAULT_PICKUP_ONLY + rules.pickup_only_keywords
    shipping_keywords = DEFAULT_SHIPPING + rules.shipping_keywords

    in_hits = _collect_matches(text, in_keywords)
    out_hits = _collect_matches(text, out_keywords)
    pickup_hits = _collect_matches(text, pickup_keywords)
    shipping_hits = _collect_matches(text, shipping_keywords)

    if filters.online_shipping_only and filters.exclude_pickup_only:
        if pickup_hits and not shipping_hits:
            matched = f"pickup-only indicators: {', '.join(sorted(set(pickup_hits)))}"
            return ParseOutcome(status=StockStatus.OUT_OF_STOCK, matched_text=matched)

    # Favor explicit out-of-stock signals to avoid false positives from generic
    # "available" language elsewhere on complex retail pages.
    if out_hits:
        matched = f"out-of-stock indicators: {', '.join(sorted(set(out_hits)))}"
        return ParseOutcome(status=StockStatus.OUT_OF_STOCK, matched_text=matched)

    if in_hits:
        matched = f"in-stock indicators: {', '.join(sorted(set(in_hits)))}"
        return ParseOutcome(status=StockStatus.IN_STOCK, matched_text=matched)

    return ParseOutcome(
        status=StockStatus.UNKNOWN,
        matched_text="no known availability indicators found",
    )
