from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
import json
import re
import xml.etree.ElementTree as ET

import requests


@dataclass(frozen=True)
class NewsQuery:
    name: str
    query: str
    category: str
    tier: str = "新闻"


@dataclass(frozen=True)
class NewsItem:
    title: str
    link: str
    source: str
    published_at: str
    category: str
    query_name: str
    tier: str = "新闻"


@dataclass(frozen=True)
class NewsSnapshot:
    items: list[NewsItem]
    source_note: str


NEWS_QUERIES = [
    NewsQuery("全球宏观与央行", "美联储 OR 欧洲央行 OR 日本央行 OR 美债收益率 OR 美元 OR 人民币 OR CPI OR PCE OR 非农", "宏观", "宏观"),
    NewsQuery("全球风险资产", "纳斯达克 OR 标普500 OR 日经225 OR 欧洲股市 OR 黄金 OR 原油 OR 铜 OR 比特币", "宏观", "行情"),
    NewsQuery("A股政策与资金", "A股 政策 OR 证监会 OR 央行 OR 财政部 OR 成交额 OR ETF OR 北向资金", "A股", "政策"),
    NewsQuery("中国科技与硬科技", "科创板 OR 半导体 OR 芯片 OR 国产替代 OR 光刻机 OR 存储芯片 OR 算力", "半导体", "产业"),
    NewsQuery("港股科技与南向", "港股 科技 OR 恒生科技 OR 南向资金 OR 腾讯 OR 阿里巴巴 OR 美团 OR 小米", "港股", "资金"),
    NewsQuery("美股AI与云资本开支", "AI capital expenditure OR Nvidia OR Microsoft Azure OR Amazon AWS OR Google cloud OR AI data center", "AI", "海外"),
    NewsQuery("AI算力产业链", "人工智能 算力 OR 光模块 OR 服务器 OR 液冷 OR IDC OR GPU OR 云厂商 资本开支", "AI", "产业"),
    NewsQuery("机器人与智能制造", "机器人 OR 人形机器人 OR 工业母机 OR 自动化 OR 智能制造", "机器人", "产业"),
    NewsQuery("能源电力与储能", "储能 OR 电网 OR 特高压 OR 风电 OR 光伏 OR 核电 OR 电力设备 OR 新型电力系统", "能源电力", "产业"),
    NewsQuery("新能源车与电池", "新能源汽车 OR 动力电池 OR 锂电池 OR 固态电池 OR 充电桩 OR 宁德时代 OR 比亚迪", "新能源", "产业"),
    NewsQuery("创新药与医疗", "创新药 OR GLP-1 OR 医药政策 OR FDA OR 港股医药 OR CXO", "医药", "产业"),
    NewsQuery("军工航天低空", "军工 OR 商业航天 OR 低空经济 OR 无人机 OR 卫星互联网", "高端制造", "产业"),
    NewsQuery("大宗商品与资源", "黄金 OR 白银 OR 铜 OR 原油 OR 天然气 OR 煤炭 OR 稀土 OR 锂价", "资源品", "商品"),
    NewsQuery("上市公司公告线索", "业绩预告 OR 重大合同 OR 回购 OR 增持 OR 减持 OR 并购重组 OR 定增", "公告", "公告"),
    NewsQuery("未来7天事件日历", "财经日历 OR 经济数据 OR 财报 OR 央行会议 OR 行业大会 OR 新品发布 未来一周", "日历", "日历"),
]


def fetch_news_snapshot(timeout_seconds: int = 10, per_query_limit: int = 5) -> NewsSnapshot:
    items: list[NewsItem] = []
    errors: list[str] = []

    for news_query in NEWS_QUERIES:
        try:
            items.extend(fetch_google_news_rss(news_query, timeout_seconds, per_query_limit))
        except Exception as exc:
            errors.append(f"{news_query.name}: {exc}")

    items = rank_and_dedupe_news(items)
    if not items:
        raise RuntimeError("all news sources failed: " + "; ".join(errors))

    source_note = (
        "新闻证据包来自 Google News RSS 的多主题检索矩阵，覆盖全球宏观、A股、港股、美股科技、"
        "AI算力、半导体、能源电力、资源品、公告和未来事件日历。报告会把标题、来源、发布时间、"
        "检索主题作为可复核证据；涉及投资结论时仍需回看原文和公司公告。"
    )
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
                    tier=news_query.tier,
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


def rank_and_dedupe_news(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    unique: list[NewsItem] = []
    for item in sorted(items, key=news_rank_key, reverse=True):
        key = normalize_title(item.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def dedupe_news(items: list[NewsItem]) -> list[NewsItem]:
    return rank_and_dedupe_news(items)


def news_rank_key(item: NewsItem) -> tuple[int, str]:
    title = item.title.lower()
    score = 0
    score += {
        "宏观": 12,
        "A股": 11,
        "港股": 10,
        "AI": 11,
        "半导体": 10,
        "能源电力": 9,
        "公告": 9,
        "日历": 7,
    }.get(item.category, 6)
    score += {
        "宏观": 5,
        "政策": 5,
        "公告": 5,
        "资金": 4,
        "海外": 4,
        "产业": 3,
        "日历": 2,
    }.get(item.tier, 1)
    high_signal_words = [
        "央行",
        "美联储",
        "政策",
        "财报",
        "业绩",
        "订单",
        "合同",
        "资本开支",
        "制裁",
        "关税",
        "并购",
        "回购",
        "增持",
        "减持",
        "突破",
        "大涨",
        "大跌",
        "创新高",
    ]
    score += sum(3 for word in high_signal_words if word.lower() in title)
    if item.source and item.source != "Google News":
        score += 3
    if item.published_at:
        score += 2
    return score, item.published_at


def normalize_title(title: str) -> str:
    clean = re.sub(r"\s+-\s+[^-]{2,40}$", "", title)
    return "".join(ch.lower() for ch in clean if ch.isalnum())


def classify_news_category(title: str, fallback: str) -> str:
    lowered = title.lower()
    category_keywords = [
        ("AI", ["ai", "人工智能", "算力", "gpu", "光模块", "数据中心", "云厂商", "服务器", "nvidia"]),
        ("半导体", ["半导体", "芯片", "晶圆", "光刻机", "存储", "封测", "国产替代"]),
        ("能源电力", ["储能", "电网", "特高压", "核电", "风电", "电力设备", "新型电力系统"]),
        ("新能源", ["新能源", "锂电", "电池", "光伏", "汽车", "充电桩", "固态电池"]),
        ("港股", ["港股", "恒生", "南向", "腾讯", "阿里巴巴", "美团", "小米"]),
        ("A股", ["a股", "上证", "深成", "创业板", "科创", "北向", "证监会", "成交额"]),
        ("宏观", ["美联储", "美债", "美元", "人民币", "黄金", "原油", "央行", "通胀", "cpi", "pce"]),
        ("公告", ["公告", "8-k", "业绩", "合同", "回购", "增持", "减持", "并购", "定增"]),
        ("日历", ["日历", "会议", "财报", "未来一周", "发布会", "经济数据"]),
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
