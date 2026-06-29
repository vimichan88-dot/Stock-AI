from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

import requests

from .models import MarketSignal


@dataclass(frozen=True)
class MarketInstrument:
    name: str
    symbol: str
    interpretation: str


@dataclass(frozen=True)
class MarketSnapshot:
    signals: list[MarketSignal]
    source_note: str


INSTRUMENTS = [
    MarketInstrument("上证指数", "000001.SS", "观察 A 股整体风险偏好和成交主线"),
    MarketInstrument("恒生指数", "^HSI", "观察港股风险偏好、南向资金和美元流动性压力"),
    MarketInstrument("纳指 100 ETF", "QQQ", "观察美股科技和 AI 交易拥挤度"),
    MarketInstrument("黄金 ETF", "GLD", "观察避险情绪和实际利率变化"),
    MarketInstrument("美元/离岸人民币", "CNH=X", "观察人民币汇率和外资风险偏好"),
]


def fetch_market_snapshot(timeout_seconds: int = 8) -> MarketSnapshot:
    signals: list[MarketSignal] = []
    errors: list[str] = []

    for instrument in INSTRUMENTS:
        try:
            signals.append(fetch_yahoo_signal(instrument, timeout_seconds))
        except Exception as exc:
            errors.append(f"{instrument.name}: {exc}")

    if not signals:
        raise RuntimeError("all market data sources failed: " + "; ".join(errors))

    source_note = (
        "市场信号来自 Yahoo Finance chart 免费接口，可能存在延迟、缺口或临时不可用；"
        "投资判断仍需结合交易所、公司公告和券商数据复核。"
    )
    if errors:
        source_note += " 部分指标抓取失败：" + "；".join(errors)

    return MarketSnapshot(signals=signals, source_note=source_note)


def fetch_yahoo_signal(instrument: MarketInstrument, timeout_seconds: int) -> MarketSignal:
    encoded_symbol = quote(instrument.symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?range=5d&interval=1d"
    response = requests.get(url, timeout=timeout_seconds, headers={"User-Agent": "Stock-AI/0.1"})
    response.raise_for_status()
    payload = response.json()

    result = payload.get("chart", {}).get("result") or []
    if not result:
        raise ValueError("empty chart result")

    chart = result[0]
    meta = chart.get("meta", {})
    quote_data = chart.get("indicators", {}).get("quote", [{}])[0]
    closes = [value for value in quote_data.get("close", []) if value is not None]
    timestamps = chart.get("timestamp", [])

    latest = closes[-1] if closes else meta.get("regularMarketPrice")
    previous = closes[-2] if len(closes) > 1 else None
    if previous is None:
        previous = meta.get("regularMarketPreviousClose") or meta.get("previousClose") or meta.get("chartPreviousClose")

    if latest is None:
        raise ValueError("missing close prices")

    change_text = "暂无前值"
    if previous:
        pct = (latest - previous) / previous * 100
        sign = "+" if pct >= 0 else ""
        change_text = f"{sign}{pct:.2f}%"

    time_note = ""
    if timestamps:
        time_note = "，最新日期 " + datetime.fromtimestamp(timestamps[-1]).strftime("%Y-%m-%d")

    return MarketSignal(
        name=instrument.name,
        value=f"{latest:.2f}",
        change=change_text,
        interpretation=f"{instrument.interpretation}{time_note}。",
    )
