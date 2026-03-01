from __future__ import annotations

import argparse
import logging
import os
import sys
import time

from .bot_commands import run_bot_polling
from .config import ConfigError, load_config
from .engine import EngineOptions, check_item, maybe_send_daily_summary, process_results
from .env_loader import load_dotenv_file
from .logging_setup import setup_logging
from .notifier import NotifyError, send_telegram_message
from .state import load_state, save_state


logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Telegram stock watcher")
    parser.add_argument(
        "command",
        choices=["check-now", "run-loop", "test-telegram", "summarize", "bot-poll"],
        help="Command to execute",
    )
    parser.add_argument("--config", default="watchlist.yaml", help="Path to watchlist YAML")
    parser.add_argument("--state", default="state.json", help="Path to state JSON")
    parser.add_argument("--log-file", default="logs/watcher.log", help="Path to log file")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to .env file for TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID/etc",
    )
    parser.add_argument(
        "--bot-offset-file",
        default=".telegram_bot_offset.json",
        help="Path to Telegram bot polling offset state",
    )
    return parser


def _engine_options() -> EngineOptions:
    return EngineOptions(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    )


def _run_check(config_path: str, state_path: str, options: EngineOptions, send_summary: bool) -> int:
    config = load_config(config_path)
    state = load_state(state_path)

    results = []
    for item in config.items:
        if not item.enabled:
            continue
        result = check_item(item, config)
        results.append(result)
        time.sleep(1.0)

    process_results(results, state, config, options)

    if send_summary and config.alerts.send_daily_summary:
        maybe_send_daily_summary(state, config, options)

    save_state(state_path, state)
    return 0


def _run_loop(config_path: str, state_path: str, options: EngineOptions) -> int:
    config = load_config(config_path)
    sleep_seconds = max(60, int(config.schedule.check_interval_hours * 3600))

    logger.info("Starting run loop with interval=%ss", sleep_seconds)
    while True:
        state = load_state(state_path)
        results = []
        for item in config.items:
            if not item.enabled:
                continue
            result = check_item(item, config)
            results.append(result)
            time.sleep(1.0)

        process_results(results, state, config, options)
        if config.alerts.send_daily_summary:
            maybe_send_daily_summary(state, config, options)
        save_state(state_path, state)
        logger.info("Sleeping for %s seconds", sleep_seconds)
        time.sleep(sleep_seconds)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    load_dotenv_file(args.env_file)
    setup_logging(log_file=args.log_file)

    try:
        options = _engine_options()
        if args.command == "test-telegram":
            if not options.bot_token or not options.chat_id:
                logger.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
                return 2
            send_telegram_message(
                options.bot_token,
                options.chat_id,
                "✅ 测试成功～Telegram 提醒已连通",
            )
            logger.info("Test Telegram message sent")
            return 0

        if args.command == "check-now":
            return _run_check(args.config, args.state, options, send_summary=True)

        if args.command == "summarize":
            config = load_config(args.config)
            if not config.alerts.send_daily_summary:
                logger.info("Daily summaries are disabled in config.alerts.send_daily_summary")
                return 0
            state = load_state(args.state)
            sent = maybe_send_daily_summary(state, config, options)
            save_state(args.state, state)
            logger.info("Daily summary sent=%s", sent)
            return 0

        if args.command == "bot-poll":
            if not options.bot_token or not options.chat_id:
                logger.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
                return 2
            run_bot_polling(
                bot_token=options.bot_token,
                allowed_chat_id=options.chat_id,
                log_file=args.log_file,
                config_path=args.config,
                state_path=args.state,
                offset_path=args.bot_offset_file,
            )
            return 0

        if args.command == "run-loop":
            return _run_loop(args.config, args.state, options)

        parser.print_help()
        return 1
    except ConfigError as exc:
        logger.error("Config error: %s", exc)
        return 2
    except NotifyError as exc:
        logger.error("Notifier error: %s", exc)
        return 3
    except KeyboardInterrupt:
        logger.info("Interrupted")
        return 130
    except Exception as exc:  # pragma: no cover
        logger.exception("Fatal error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
