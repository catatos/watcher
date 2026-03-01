from __future__ import annotations

import json
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
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def _collect_matches(text: str, candidates: list[str]) -> list[str]:
    hits: list[str] = []
    for candidate in candidates:
        c = candidate.lower().strip()
        if c and c in text:
            hits.append(c)
    return hits


def _ldjson_blocks(html: str) -> list[str]:
    pattern = re.compile(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
        flags=re.IGNORECASE,
    )
    return [m.group(1).strip() for m in pattern.finditer(html)]


def _normalize_availability(value: str) -> str:
    v = value.strip().lower()
    if "/" in v:
        v = v.rsplit("/", 1)[-1]
    return v


def _collect_offer_availability(node: object, out: list[str]) -> None:
    if isinstance(node, dict):
        availability = node.get("availability")
        if isinstance(availability, str):
            out.append(_normalize_availability(availability))
        for value in node.values():
            _collect_offer_availability(value, out)
        return

    if isinstance(node, list):
        for item in node:
            _collect_offer_availability(item, out)


def _collect_product_availability(node: object, out: list[str]) -> None:
    if isinstance(node, dict):
        node_type = node.get("@type")
        if isinstance(node_type, list):
            is_product = any(str(t).lower() == "product" for t in node_type)
        else:
            is_product = str(node_type).lower() == "product"
        if is_product and "offers" in node:
            _collect_offer_availability(node.get("offers"), out)

        for value in node.values():
            _collect_product_availability(value, out)
        return

    if isinstance(node, list):
        for item in node:
            _collect_product_availability(item, out)


def _structured_availability_status(html: str) -> ParseOutcome | None:
    values: list[str] = []
    for block in _ldjson_blocks(html):
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        _collect_product_availability(parsed, values)

    has_in_stock = "instock" in values
    has_out_of_stock = "outofstock" in values

    if has_in_stock and not has_out_of_stock:
        return ParseOutcome(
            status=StockStatus.IN_STOCK,
            matched_text="structured availability: instock",
        )
    if has_out_of_stock and not has_in_stock:
        return ParseOutcome(
            status=StockStatus.OUT_OF_STOCK,
            matched_text="structured availability: outofstock",
        )
    return None


def parse_availability(html: str, rules: AvailabilityRules, filters: FilterConfig) -> ParseOutcome:
    structured = _structured_availability_status(html)
    if structured is not None:
        return structured

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
