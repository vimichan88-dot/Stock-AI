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
    MarketInstrument("上证指数", "000001.SS", "中国大陆市场基准，观察 A 股整体风险偏好和成交主线"),
    MarketInstrument("沪深300", "000300.SS", "中国大陆核心资产基准，观察权重股和北向/机构风险偏好"),
    MarketInstrument("创业板指", "399006.SZ", "中国大陆成长股基准，观察新能源、医药和科技成长方向"),
    MarketInstrument("科创50", "000688.SS", "中国大陆科创板代表指数，观察硬科技、半导体和高端制造成长风格"),
    MarketInstrument("恒生指数", "^HSI", "香港市场基准，观察港股风险偏好、南向资金和美元流动性压力"),
    MarketInstrument("恒生科技", "3033.HK", "香港科技资产代理，观察平台经济和港股成长风格"),
    MarketInstrument("标普500", "^GSPC", "美国大盘基准，观察全球风险资产定价"),
    MarketInstrument("纳斯达克100", "^NDX", "美国科技基准，观察 AI、半导体和高估值成长股映射"),
    MarketInstrument("道琼斯工业指数", "^DJI", "美国蓝筹基准，观察传统周期和防守资产表现"),
    MarketInstrument("日经225", "^N225", "日本市场基准，观察亚洲风险偏好和日元相关交易"),
    MarketInstrument("韩国KOSPI", "^KS11", "韩国市场基准，观察半导体、出口链和亚洲科技风险偏好"),
    MarketInstrument("欧洲STOXX 600", "^STOXX", "欧洲市场基准，观察全球周期和欧洲风险偏好"),
    MarketInstrument("德国DAX", "^GDAXI", "欧洲制造业和出口链代理，观察全球工业周期"),
    MarketInstrument("英国富时100", "^FTSE", "欧洲高股息和资源股代理，观察防守与商品链偏好"),
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
