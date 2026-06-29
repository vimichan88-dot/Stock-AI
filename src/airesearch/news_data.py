from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
import json
import xml.etree.ElementTree as ET

import requests


@dataclass(frozen=True)
class NewsQuery:
    name: str
    query: str
    category: str


@dataclass(frozen=True)
class NewsItem:
    title: str
    link: str
    source: str
    published_at: str
    category: str
    query_name: str


@dataclass(frozen=True)
class NewsSnapshot:
    items: list[NewsItem]
    source_note: str


NEWS_QUERIES = [
    NewsQuery("A 股政策与市场", "A股 政策 市场 OR 资金流", "A 股"),
    NewsQuery("港股科技", "港股 科技 互联网 南向资金", "港股"),
    NewsQuery("AI 算力", "人工智能 算力 芯片 光模块 云厂商", "AI"),
    NewsQuery("新能源", "新能源 储能 光伏 电池 电网", "新能源"),
    NewsQuery("全球宏观", "美债收益率 美联储 美元 黄金 原油", "宏观"),
]


def fetch_news_snapshot(timeout_seconds: int = 10, per_query_limit: int = 6) -> NewsSnapshot:
    items: list[NewsItem] = []
    errors: list[str] = []

    for news_query in NEWS_QUERIES:
        try:
            items.extend(fetch_google_news_rss(news_query, timeout_seconds, per_query_limit))
        except Exception as exc:
            errors.append(f"{news_query.name}: {exc}")

    items = dedupe_news(items)
    if not items:
        raise RuntimeError("all news sources failed: " + "; ".join(errors))

    source_note = "新闻线索来自 Google News RSS 免费聚合源，标题和来源用于事件筛选，重要事实需回看原文复核。"
    if errors:
        source_note += " 部分新闻查询失败：" + "；".join(errors)

    return NewsSnapshot(items=items, source_note=source_note)


def fetch_google_news_rss(news_query: NewsQuery, timeout_seconds: int, limit: int) -> list[NewsItem]:
    encoded_query = quote_plus(f"{news_query.query} when:1d")
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    response = requests.get(url, timeout=timeout_seconds, headers={"User-Agent": "Stock-AI/0.1"})
    response.raise_for_status()

    root = ET.fromstring(response.content)
    items: list[NewsItem] = []
    for item in root.findall("./channel/item")[:limit]:
        title = text_of(item, "title")
        link = text_of(item, "link")
        source_node = item.find("source")
        source = source_node.text.strip() if source_node is not None and source_node.text else "Google News"
        published_at = normalize_rss_date(text_of(item, "pubDate"))
        if title and link:
            items.append(
                NewsItem(
                    title=title,
                    link=link,
                    source=source,
                    published_at=published_at,
                    category=classify_news_category(title, news_query.category),
                    query_name=news_query.name,
                )
            )
    return items


def save_news_snapshot(snapshot: NewsSnapshot, raw_dir: Path, date_text: str, report_type: str) -> Path:
    output_dir = raw_dir / "news" / date_text
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{report_type}.json"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_note": snapshot.source_note,
        "items": [asdict(item) for item in snapshot.items],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def dedupe_news(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    unique: list[NewsItem] = []
    for item in items:
        key = normalize_title(item.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def normalize_title(title: str) -> str:
    return "".join(ch.lower() for ch in title if ch.isalnum())


def classify_news_category(title: str, fallback: str) -> str:
    lowered = title.lower()
    category_keywords = [
        ("AI", ["ai", "人工智能", "算力", "芯片", "光模块", "半导体", "云"]),
        ("新能源", ["新能源", "储能", "光伏", "电池", "电网", "锂", "风电"]),
        ("港股", ["港股", "恒生", "南向", "阿里巴巴", "美团", "港股通"]),
        ("A 股", ["a股", "涨停", "上证", "深证", "创业板", "科创", "etf"]),
        ("宏观", ["美联储", "美债", "美元", "黄金", "原油", "汇率", "央行"]),
        ("公告", ["公告", "8-k", "业绩", "募集说明书", "披露"]),
    ]
    for category, keywords in category_keywords:
        if any(keyword in lowered for keyword in keywords):
            return category
    return fallback


def normalize_rss_date(value: str) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return value


def text_of(node: ET.Element, tag: str) -> str:
    child = node.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()
