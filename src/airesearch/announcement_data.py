from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from datetime import datetime, timezone

from .news_data import NewsItem, NewsQuery, dedupe_news, fetch_google_news_rss


@dataclass(frozen=True)
class AnnouncementSnapshot:
    items: list[NewsItem]
    source_note: str


ANNOUNCEMENT_QUERIES = [
    NewsQuery("A 股公告", "site:cninfo.com.cn 公告 AI 新能源 并购 业绩", "公告"),
    NewsQuery("上交所公告", "site:sse.com.cn 公告 上市公司 AI 新能源", "公告"),
    NewsQuery("深交所公告", "site:szse.cn 公告 上市公司 AI 新能源", "公告"),
    NewsQuery("港股公告", "site:hkexnews.hk 公告 科技 新能源 业绩", "公告"),
    NewsQuery("美股 8-K", "site:sec.gov 8-K NVIDIA Microsoft Tesla AI", "公告"),
]


def fetch_announcement_snapshot(timeout_seconds: int = 10, per_query_limit: int = 4) -> AnnouncementSnapshot:
    items: list[NewsItem] = []
    errors: list[str] = []

    for query in ANNOUNCEMENT_QUERIES:
        try:
            items.extend(fetch_google_news_rss(query, timeout_seconds, per_query_limit))
        except Exception as exc:
            errors.append(f"{query.name}: {exc}")

    items = dedupe_news(items)
    if not items:
        raise RuntimeError("all announcement sources failed: " + "; ".join(errors))

    source_note = (
        "公告线索来自 Google News 对巨潮资讯、交易所、港交所披露易和 SEC 的公开索引；"
        "当前阶段只用于发现线索，正式判断必须打开公告原文复核。"
    )
    if errors:
        source_note += " 部分公告查询失败：" + "；".join(errors)
    return AnnouncementSnapshot(items=items, source_note=source_note)


def save_announcement_snapshot(
    snapshot: AnnouncementSnapshot, raw_dir: Path, date_text: str, report_type: str
) -> Path:
    output_dir = raw_dir / "announcements" / date_text
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{report_type}.json"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_note": snapshot.source_note,
        "items": [item.__dict__ for item in snapshot.items],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
