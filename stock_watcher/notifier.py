from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class NotifyError(Exception):
    pass


def _telegram_api_call(
    bot_token: str,
    method: str,
    params: dict[str, Any] | None = None,
    retries: int = 3,
    backoff_s: float = 1.0,
    timeout_s: int = 30,
) -> dict[str, Any]:
    base_url = f"https://api.telegram.org/bot{bot_token}/{method}"
    encoded = urllib.parse.urlencode(params or {})

    if method == "getUpdates":
        url = f"{base_url}?{encoded}" if encoded else base_url
        req = urllib.request.Request(url)
        data = None
    else:
        req = urllib.request.Request(
            base_url,
            data=encoded.encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = True

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                parsed = json.loads(body)
                if not parsed.get("ok", False):
                    raise NotifyError(f"Telegram API returned non-ok response: {parsed}")
                return parsed
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, NotifyError) as exc:
            last_exc = exc

        if attempt < retries - 1:
            time.sleep(backoff_s * (2**attempt))

    mode = "GET" if method == "getUpdates" else "POST"
    has_data = "with-data" if data else "no-data"
    raise NotifyError(f"Failed Telegram {mode} {method} ({has_data}): {last_exc}")


def send_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
    retries: int = 3,
    backoff_s: float = 1.0,
) -> None:
    _telegram_api_call(
        bot_token=bot_token,
        method="sendMessage",
        params={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        },
        retries=retries,
        backoff_s=backoff_s,
        timeout_s=15,
    )


def get_telegram_updates(
    bot_token: str,
    offset: int | None,
    timeout_s: int = 25,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "timeout": timeout_s,
        "allowed_updates": json.dumps(["message", "edited_message"]),
    }
    if offset is not None:
        params["offset"] = offset

    resp = _telegram_api_call(
        bot_token=bot_token,
        method="getUpdates",
        params=params,
        retries=3,
        backoff_s=1.0,
        timeout_s=timeout_s + 10,
    )
    result = resp.get("result", [])
    if not isinstance(result, list):
        return []
    return [r for r in result if isinstance(r, dict)]
