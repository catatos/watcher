from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .config import ConfigError, load_config
from .notifier import NotifyError, get_telegram_updates, send_telegram_message
from .state import load_state


logger = logging.getLogger(__name__)


def _load_offset(path: str) -> int | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        offset = raw.get("offset")
        return int(offset) if offset is not None else None
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def _save_offset(path: str, offset: int) -> None:
    Path(path).write_text(json.dumps({"offset": offset}, indent=2), encoding="utf-8")


def tail_log_lines(log_file: str, lines: int = 30) -> str:
    p = Path(log_file)
    if not p.exists():
        return f"Log file not found: {log_file}"

    lines = max(1, min(lines, 200))
    content = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    tail = content[-lines:]
    if not tail:
        return "Log file is empty."

    return "\n".join(tail)


def _parse_logs_count(command: str) -> int:
    parts = command.strip().split()
    if len(parts) < 2:
        return 30
    try:
        return max(1, min(int(parts[1]), 200))
    except ValueError:
        return 30


def _format_status(config_path: str, state_path: str) -> str:
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        return f"Status unavailable (config error): {exc}"

    state = load_state(state_path)
    lines: list[str] = ["WATCHER STATUS"]
    for item in config.items:
        if not item.enabled:
            continue
        item_state = state.items.get(item.id)
        status = item_state.status if item_state else "UNKNOWN"
        lines.append(f"- {item.name}: {status}")

    return "\n".join(lines)


def _help_text() -> str:
    return (
        "Available commands:\n"
        "/status - current status for watched items\n"
        "/logs - last 30 lines from watcher log\n"
        "/logs N - last N lines (max 200)\n"
        "/help - this message"
    )


def _split_chunks(text: str, max_chars: int = 3500) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        split_at = remaining.rfind("\n", 0, max_chars)
        if split_at == -1:
            split_at = max_chars
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


def _dispatch_command(command: str, log_file: str, config_path: str, state_path: str) -> str:
    cmd = command.strip().lower()
    if cmd.startswith("/logs"):
        count = _parse_logs_count(command)
        body = tail_log_lines(log_file, lines=count)
        return f"RECENT LOGS (last {count})\n{body}"
    if cmd.startswith("/status"):
        return _format_status(config_path, state_path)
    return _help_text()


def run_bot_polling(
    bot_token: str,
    allowed_chat_id: str,
    log_file: str,
    config_path: str,
    state_path: str,
    offset_path: str,
) -> None:
    offset = _load_offset(offset_path)
    logger.info("Starting Telegram command polling")

    while True:
        try:
            updates = get_telegram_updates(bot_token=bot_token, offset=offset, timeout_s=25)
        except NotifyError as exc:
            logger.error("Polling error: %s", exc)
            time.sleep(5)
            continue

        for update in updates:
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                offset = update_id + 1

            msg = update.get("message") or update.get("edited_message")
            if not isinstance(msg, dict):
                continue

            text = msg.get("text")
            chat = msg.get("chat", {})
            chat_id = str(chat.get("id", ""))
            if not text or not chat_id:
                continue

            if chat_id != str(allowed_chat_id):
                logger.warning("Ignoring command from unauthorized chat_id=%s", chat_id)
                continue

            response = _dispatch_command(
                command=text,
                log_file=log_file,
                config_path=config_path,
                state_path=state_path,
            )

            for chunk in _split_chunks(response):
                try:
                    send_telegram_message(bot_token, chat_id, chunk)
                except NotifyError as exc:
                    logger.error("Failed to send command response: %s", exc)
                    break

        if offset is not None:
            _save_offset(offset_path, offset)
