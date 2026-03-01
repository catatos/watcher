# Telegram Stock Watcher

A reusable multi-item stock watcher that checks product pages hourly and sends Telegram alerts when products become available.

## Features

- Multi-item watchlist in `watchlist.yaml`
- Availability states: `IN_STOCK`, `OUT_OF_STOCK`, `UNKNOWN`
- Online-shipping-only filtering (ignores pickup-only results)
- Immediate restock alerts + repeat alerts while still in stock
- In-stock-only Telegram notifications by default
- Persistent state in `state.json` to avoid duplicate alerts
- Terminal + file logging (`logs/watcher.log`)
- Telegram bot command polling (`/status`, `/logs`, `/logs N`)

## Requirements

- Python 3.10+
- Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

If you use `fetch_strategy: "playwright"` for anti-bot protected sites:

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
```

## Environment variables

```bash
export TELEGRAM_BOT_TOKEN="<your-bot-token>"
export TELEGRAM_CHAT_ID="<your-chat-id>"
# Optional: browser cookie for sites that block bots (e.g. Jellycat 403)
export JELLYCAT_COOKIE="<cookie-header-from-browser>"
```

You can also place these in `.env` at the project root:

```bash
TELEGRAM_BOT_TOKEN=<your-bot-token>
TELEGRAM_CHAT_ID=<your-chat-id>
JELLYCAT_COOKIE=<cookie-header-from-browser>
```

## Usage

```bash
python3 watcher.py check-now
python3 watcher.py run-loop
python3 watcher.py test-telegram
python3 watcher.py bot-poll
```

Optional arguments:

```bash
python3 watcher.py check-now --config watchlist.yaml --state state.json
python3 watcher.py check-now --env-file .env
```

## Watchlist config

See `watchlist.yaml` for the schema and sample items.

## Notes

- This watcher evaluates product pages (no checkout simulation).
- Pickup-only inventory is ignored by default.
- `bot-poll` listens for Telegram commands from `TELEGRAM_CHAT_ID` only.
- If a retailer returns HTTP 403, add item-level `request_headers` and optionally
  pass a session cookie via `${ENV_VAR}` in `watchlist.yaml`, or switch item
  `fetch_strategy` to `"playwright"`.
