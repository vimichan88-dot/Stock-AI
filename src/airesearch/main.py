from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from .ai_analysis import configured_ai_model, configured_ai_provider, enhance_report_with_openai
from .announcement_data import fetch_announcement_snapshot, save_announcement_snapshot
from .config import Settings
from .macro_data import fetch_macro_snapshot
from .market_data import fetch_market_snapshot
from .news_data import fetch_news_snapshot, save_news_snapshot
from .notifier import send_email, send_pushplus, send_server_chan
from .quality import append_quality_note, validate_report
from .report_builder import build_report
from .report_writer import save_report
from .site_builder import build_site


ROOT = Path(__file__).resolve().parents[2]
DATA_REPORTS = ROOT / "data" / "reports"
DATA_RAW = ROOT / "data" / "raw"
SITE_DIR = ROOT / "site"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate AI research daily report.")
    parser.add_argument(
        "--report-type",
        choices=["morning", "noon", "close"],
        default="morning",
        help="Report type to generate.",
    )
    parser.add_argument("--date", default="", help="Report date in YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--no-notify", action="store_true", help="Skip PushPlus and email notifications.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Settings.from_env()
    generated_at = current_datetime(settings.timezone)
    date_text = args.date or generated_at.strftime("%Y-%m-%d")

    market_signals = None
    market_source_note = None
    try:
        snapshot = fetch_market_snapshot()
        market_signals = snapshot.signals
        market_source_note = snapshot.source_note
        print(f"Fetched market signals: {len(market_signals)}")
    except Exception as exc:
        print(f"Market data fallback used: {exc}")

    try:
        macro_snapshot = fetch_macro_snapshot()
        market_signals = (market_signals or []) + macro_snapshot.signals
        market_source_note = "\n\n".join(note for note in [market_source_note, macro_snapshot.source_note] if note)
        print(f"Fetched macro signals: {len(macro_snapshot.signals)}")
    except Exception as exc:
        print(f"Macro data fallback used: {exc}")

    news_items = None
    news_source_note = None
    try:
        news_snapshot = fetch_news_snapshot()
        news_items = news_snapshot.items
        news_source_note = news_snapshot.source_note
        raw_news_path = save_news_snapshot(news_snapshot, DATA_RAW, date_text, args.report_type)
        print(f"Fetched news items: {len(news_items)}")
        print(f"Saved raw news: {raw_news_path}")
    except Exception as exc:
        print(f"News data fallback used: {exc}")

    try:
        announcement_snapshot = fetch_announcement_snapshot()
        news_items = (news_items or []) + announcement_snapshot.items
        news_source_note = "\n\n".join(note for note in [news_source_note, announcement_snapshot.source_note] if note)
        raw_announcement_path = save_announcement_snapshot(announcement_snapshot, DATA_RAW, date_text, args.report_type)
        print(f"Fetched announcement items: {len(announcement_snapshot.items)}")
        print(f"Saved raw announcements: {raw_announcement_path}")
    except Exception as exc:
        print(f"Announcement data fallback used: {exc}")

    report = build_report(
        args.report_type,
        date_text,
        market_signals,
        market_source_note,
        news_items,
        news_source_note,
        generated_at=generated_at,
    )
    ai_provider = configured_ai_provider(settings)
    ai_status_note = ""
    if ai_provider != "none":
        try:
            report = enhance_report_with_openai(report, settings, news_items or [])
            ai_model = configured_ai_model(settings)
            ai_status_note = f"AI 模型调用状态：成功调用 {ai_provider} / {ai_model}，已对规则版报告进行投研增强。"
            print(f"AI analysis applied: {ai_provider} / {ai_model}")
        except Exception as exc:
            ai_model = configured_ai_model(settings)
            ai_status_note = (
                f"AI 模型调用状态：调用 {ai_provider} / {ai_model} 失败，已自动退回规则版报告。"
                f"失败原因：{exc}"
            )
            print(f"AI analysis fallback used: {ai_provider} / {ai_model}: {exc}")
    else:
        ai_status_note = (
            "AI 模型调用状态：未调用 AI 模型。未配置可用的 OPENAI_API_KEY 或 DEEPSEEK_API_KEY，"
            "本报告使用行情、新闻、公告和规则引擎生成。"
        )
        print("AI analysis skipped: no OPENAI_API_KEY or DEEPSEEK_API_KEY is configured.")

    report.source_note = append_source_note(report.source_note, ai_status_note)

    quality_warnings = validate_report(report)
    report = append_quality_note(report, quality_warnings)
    if quality_warnings:
        print(f"Quality warnings: {len(quality_warnings)}")
    else:
        print("Quality check passed.")

    json_path, md_path = save_report(report, DATA_REPORTS)
    build_site(DATA_REPORTS, SITE_DIR, settings.report_access_token)

    report_url = settings.report_base_url or "Open site/index.html after GitHub Pages is enabled."
    if settings.report_base_url:
        sep = "&" if "?" in settings.report_base_url else "?"
        report_url = f"{settings.report_base_url}{sep}token={settings.report_access_token}"

    print(f"Saved JSON: {json_path}")
    print(f"Saved Markdown: {md_path}")
    print(f"Built site: {SITE_DIR / 'index.html'}")

    if args.no_notify:
        print("Notifications skipped.")
        return

    try:
        pushed = send_pushplus(settings, report, report_url)
        print(f"PushPlus sent: {pushed}")
    except Exception as exc:
        print(f"PushPlus failed: {exc}")

    try:
        server_chan_sent = send_server_chan(settings, report, report_url)
        print(f"ServerChan sent: {server_chan_sent}")
    except Exception as exc:
        print(f"ServerChan failed: {exc}")

    try:
        emailed = send_email(settings, report, report_url)
        print(f"Email sent: {emailed}")
    except Exception as exc:
        print(f"Email failed: {exc}")


def current_date_text(timezone_name: str) -> str:
    return current_datetime(timezone_name).strftime("%Y-%m-%d")


def append_source_note(source_note: str, note: str) -> str:
    if not note:
        return source_note
    if not source_note:
        return note
    return f"{source_note}\n\n{note}"


def current_datetime(timezone_name: str) -> datetime:
    fixed_timezone = fixed_timezone_for(timezone_name)
    if fixed_timezone is not None:
        return datetime.now(fixed_timezone)
    try:
        return datetime.now(ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError:
        print(f"Invalid TIMEZONE configured: {timezone_name}. Falling back to local time.")
        return datetime.now()


def fixed_timezone_for(timezone_name: str) -> timezone | None:
    offsets = {
        "Asia/Shanghai": 8,
        "Asia/Hong_Kong": 8,
        "Asia/Riyadh": 3,
        "UTC": 0,
    }
    if timezone_name not in offsets:
        return None
    return timezone(timedelta(hours=offsets[timezone_name]), timezone_name)


if __name__ == "__main__":
    main()
