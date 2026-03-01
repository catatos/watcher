from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from .fetcher import BlockedError, FetchError, fetch_url
from .models import CheckResult, StockStatus, WatchConfig, WatchItem
from .notifier import NotifyError, send_telegram_message
from .parser import parse_availability
from .state import ItemState, WatcherState


logger = logging.getLogger(__name__)


@dataclass
class EngineOptions:
    bot_token: str | None
    chat_id: str | None


def _event_hash(item_id: str, status: StockStatus, matched_text: str) -> str:
    src = f"{item_id}|{status.value}|{matched_text}".encode("utf-8")
    return hashlib.sha256(src).hexdigest()


def check_item(item: WatchItem, config: WatchConfig) -> CheckResult:
    checked_at = datetime.now()
    try:
        html = fetch_url(
            item.url,
            extra_headers=item.request_headers,
            strategy=item.fetch_strategy,
        )
        parsed = parse_availability(html, item.availability_rules, config.filters)
        return CheckResult(
            item_id=item.id,
            item_name=item.name,
            url=item.url,
            retailer=item.retailer,
            status=parsed.status,
            matched_text=parsed.matched_text,
            checked_at=checked_at,
        )
    except BlockedError as exc:
        return CheckResult(
            item_id=item.id,
            item_name=item.name,
            url=item.url,
            retailer=item.retailer,
            status=StockStatus.UNKNOWN,
            matched_text=str(exc),
            checked_at=checked_at,
            error_type="BLOCKED",
        )
    except FetchError as exc:
        return CheckResult(
            item_id=item.id,
            item_name=item.name,
            url=item.url,
            retailer=item.retailer,
            status=StockStatus.UNKNOWN,
            matched_text=str(exc),
            checked_at=checked_at,
            error_type="FETCH_ERROR",
        )
    except Exception as exc:
        return CheckResult(
            item_id=item.id,
            item_name=item.name,
            url=item.url,
            retailer=item.retailer,
            status=StockStatus.UNKNOWN,
            matched_text=str(exc),
            checked_at=checked_at,
            error_type="PARSE_ERROR",
        )


def should_send_stock_alert(
    result: CheckResult,
    item_state: ItemState,
    repeat_hours: int,
) -> bool:
    if result.status != StockStatus.IN_STOCK:
        return False

    if item_state.status != StockStatus.IN_STOCK.value:
        return True

    if item_state.last_alert_at is None:
        return True

    return datetime.now() - item_state.last_alert_at >= timedelta(hours=repeat_hours)


def _format_stock_alert(result: CheckResult, repeat_mode: bool) -> str:
    prefix = "🛎️ 有货啦！快去看看～" if not repeat_mode else "💖 仍然有货提醒"
    return (
        f"{prefix}\n"
        f"商品：{result.item_name}\n"
        f"店铺：{result.retailer}\n"
        f"状态：有货\n"
        f"线索：{result.matched_text}\n"
        f"链接：{result.url}\n"
        f"时间：{result.checked_at.strftime('%Y-%m-%d %H:%M:%S')}"
    )


def process_results(
    results: list[CheckResult],
    state: WatcherState,
    config: WatchConfig,
    options: EngineOptions,
) -> None:
    for result in results:
        item_state = state.items.get(result.item_id, ItemState())
        alert_due = should_send_stock_alert(
            result=result,
            item_state=item_state,
            repeat_hours=config.alerts.repeat_hours_while_in_stock,
        )

        event_hash = _event_hash(result.item_id, result.status, result.matched_text)
        repeat_mode = item_state.status == StockStatus.IN_STOCK.value

        logger.info(
            "item=%s status=%s error=%s detail=%s",
            result.item_id,
            result.status.value,
            result.error_type,
            result.matched_text,
        )

        if alert_due and config.alerts.telegram_enabled and options.bot_token and options.chat_id:
            # Deduplicate identical availability events unless repeat window permits alert.
            if event_hash != item_state.last_event_hash or repeat_mode:
                msg = _format_stock_alert(result, repeat_mode=repeat_mode)
                try:
                    send_telegram_message(options.bot_token, options.chat_id, msg)
                    logger.info("Sent Telegram alert for %s", result.item_id)
                    item_state.last_alert_at = datetime.now()
                    item_state.last_event_hash = event_hash
                except NotifyError as exc:
                    logger.error("Failed Telegram alert for %s: %s", result.item_id, exc)

        item_state.status = result.status.value
        state.items[result.item_id] = item_state


def _daily_summary_due(last_sent_at: datetime | None, summary_time_local: str) -> bool:
    now = datetime.now()
    try:
        hour_str, minute_str = summary_time_local.split(":", 1)
        schedule_t = time(hour=int(hour_str), minute=int(minute_str))
    except (ValueError, TypeError):
        schedule_t = time(hour=20, minute=0)

    scheduled_dt = datetime.combine(now.date(), schedule_t)
    if now < scheduled_dt:
        return False

    if last_sent_at is None:
        return True

    return last_sent_at.date() < now.date()


def maybe_send_daily_summary(
    state: WatcherState,
    config: WatchConfig,
    options: EngineOptions,
) -> bool:
    if not _daily_summary_due(state.last_summary_sent_at, config.schedule.daily_summary_time_local):
        return False

    in_stock: list[str] = []
    out_of_stock: list[str] = []
    unknown: list[str] = []

    for item in config.items:
        current = state.items.get(item.id, ItemState())
        if current.status == StockStatus.IN_STOCK.value:
            in_stock.append(item.name)
        elif current.status == StockStatus.OUT_OF_STOCK.value:
            out_of_stock.append(item.name)
        else:
            unknown.append(item.name)

    msg = (
        "📊 每日库存小报\n"
        f"✅ 有货：{len(in_stock)}\n"
        f"❌ 缺货：{len(out_of_stock)}\n"
        f"❓ 未知/异常：{len(unknown)}\n"
        f"🛍️ 有货清单：{', '.join(in_stock) if in_stock else '暂无'}\n"
        f"⚠️ 异常清单：{', '.join(unknown) if unknown else '暂无'}"
    )

    if config.alerts.telegram_enabled and options.bot_token and options.chat_id:
        try:
            send_telegram_message(options.bot_token, options.chat_id, msg)
            state.last_summary_sent_at = datetime.now()
            logger.info("Sent daily summary")
            return True
        except NotifyError as exc:
            logger.error("Failed to send daily summary: %s", exc)
            return False

    return False
