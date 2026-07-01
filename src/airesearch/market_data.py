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
    provider: str = "yahoo"
    fallback_symbols: tuple[str, ...] = ()
    min_value: float | None = None
    max_value: float | None = None


@dataclass(frozen=True)
class MarketSnapshot:
    signals: list[MarketSignal]
    source_note: str


INSTRUMENTS = [
    MarketInstrument("上证指数", "s_sh000001", "中国大陆市场基准，观察 A 股整体风险偏好和成交主线", "sina", min_value=2000, max_value=8000),
    MarketInstrument("深成指数", "s_sz399001", "中国大陆深市基准，观察成长制造、科技和消费电子主线", "sina", min_value=5000, max_value=30000),
    MarketInstrument("沪深300", "s_sh000300", "中国大陆核心资产基准，观察权重股和北向/机构风险偏好", "sina", min_value=2000, max_value=10000),
    MarketInstrument("创业板指", "s_sz399006", "中国大陆成长股基准，观察新能源、医药和科技成长方向", "sina", min_value=1000, max_value=8000),
    MarketInstrument("科创50", "s_sh000688", "中国大陆科创板代表指数，观察硬科技、半导体和高端制造成长风格", "sina", min_value=500, max_value=4000),
    MarketInstrument("恒生指数", "rt_hkHSI", "香港市场基准，观察港股风险偏好、南向资金和美元流动性压力", "sina_hk", min_value=10000, max_value=50000),
    MarketInstrument("恒生科技", "rt_hkHSTECH", "香港科技资产代理，观察平台经济和港股成长风格", "sina_hk", min_value=2000, max_value=15000),
    MarketInstrument("标普500", "^GSPC", "美国大盘基准，观察全球风险资产定价", min_value=3000, max_value=12000),
    MarketInstrument("纳斯达克100", "^NDX", "美国科技基准，观察 AI、半导体和高估值成长股映射", min_value=10000, max_value=50000),
    MarketInstrument("道琼斯工业指数", "^DJI", "美国蓝筹基准，观察传统周期和防守资产表现", min_value=20000, max_value=80000),
    MarketInstrument("日经225", "^N225", "日本市场基准，观察亚洲风险偏好和日元相关交易", min_value=20000, max_value=90000),
    MarketInstrument("韩国KOSPI", "^KS11", "韩国市场基准，观察半导体、出口链和亚洲科技风险偏好", min_value=1500, max_value=10000),
    MarketInstrument("欧洲STOXX 600", "^STOXX", "欧洲市场基准，观察全球周期和欧洲风险偏好", min_value=300, max_value=1000),
    MarketInstrument("德国DAX", "^GDAXI", "欧洲制造业和出口链代理，观察全球工业周期", min_value=8000, max_value=40000),
    MarketInstrument("英国富时100", "^FTSE", "欧洲高股息和资源股代理，观察防守与商品链偏好", min_value=5000, max_value=15000),
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
        "中国大陆指数优先来自新浪行情接口，海外市场、商品、汇率等来自 Yahoo Finance chart 免费接口，可能存在延迟、缺口或临时不可用；"
        "投资判断仍需结合交易所、公司公告和券商数据复核。"
    )
    if errors:
        source_note += " 部分指标抓取失败：" + "；".join(errors)

    return MarketSnapshot(signals=signals, source_note=source_note)


def fetch_yahoo_signal(instrument: MarketInstrument, timeout_seconds: int) -> MarketSignal:
    if instrument.provider == "sina":
        signal = fetch_sina_signal(instrument, timeout_seconds)
        validate_signal_value(instrument, parse_float(signal.value))
        return signal
    if instrument.provider == "sina_hk":
        signal = fetch_sina_hk_signal(instrument, timeout_seconds)
        validate_signal_value(instrument, parse_float(signal.value))
        return signal

    errors: list[str] = []
    for symbol in (instrument.symbol, *instrument.fallback_symbols):
        try:
            return fetch_yahoo_signal_for_symbol(instrument, symbol, timeout_seconds)
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")
    raise ValueError("; ".join(errors))


def fetch_yahoo_signal_for_symbol(instrument: MarketInstrument, symbol: str, timeout_seconds: int) -> MarketSignal:
    encoded_symbol = quote(symbol, safe="")
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
    validate_signal_value(instrument, latest)

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


def validate_signal_value(instrument: MarketInstrument, value: float | None) -> None:
    if value is None:
        raise ValueError("missing latest value")
    if instrument.min_value is not None and value < instrument.min_value:
        raise ValueError(f"value {value:.2f} below expected range for {instrument.name}")
    if instrument.max_value is not None and value > instrument.max_value:
        raise ValueError(f"value {value:.2f} above expected range for {instrument.name}")


def fetch_sina_signal(instrument: MarketInstrument, timeout_seconds: int) -> MarketSignal:
    encoded_symbol = quote(instrument.symbol, safe="")
    url = f"https://hq.sinajs.cn/list={encoded_symbol}"
    response = requests.get(
        url,
        timeout=timeout_seconds,
        headers={
            "User-Agent": "Mozilla/5.0 Stock-AI/0.1",
            "Referer": "https://finance.sina.com.cn/",
        },
    )
    response.raise_for_status()
    text = response.content.decode("gb18030", errors="ignore")
    if '=""' in text or '"' not in text:
        raise ValueError("empty Sina quote result")

    quote_text = text.split('"', 2)[1]
    parts = [part.strip() for part in quote_text.split(",")]
    if len(parts) < 4:
        raise ValueError("invalid Sina quote result")

    latest = parse_float(parts[1])
    change = parse_float(parts[2])
    pct = parse_float(parts[3])
    if latest is None:
        raise ValueError("missing Sina latest value")

    if pct is not None:
        sign = "+" if pct >= 0 else ""
        change_text = f"{sign}{pct:.2f}%"
    elif change is not None:
        sign = "+" if change >= 0 else ""
        change_text = f"{sign}{change:.2f}"
    else:
        change_text = "暂无前值"

    return MarketSignal(
        name=instrument.name,
        value=f"{latest:.2f}",
        change=change_text,
        interpretation=f"{instrument.interpretation}，数据源新浪行情。",
    )


def fetch_sina_hk_signal(instrument: MarketInstrument, timeout_seconds: int) -> MarketSignal:
    encoded_symbol = quote(instrument.symbol, safe="")
    url = f"https://hq.sinajs.cn/list={encoded_symbol}"
    response = requests.get(
        url,
        timeout=timeout_seconds,
        headers={
            "User-Agent": "Mozilla/5.0 Stock-AI/0.1",
            "Referer": "https://finance.sina.com.cn/",
        },
    )
    response.raise_for_status()
    text = response.content.decode("gb18030", errors="ignore")
    if '=""' in text or '"' not in text:
        raise ValueError("empty Sina HK quote result")

    quote_text = text.split('"', 2)[1]
    parts = [part.strip() for part in quote_text.split(",")]
    if len(parts) < 9:
        raise ValueError("invalid Sina HK quote result")

    latest = parse_float(parts[6])
    change = parse_float(parts[7])
    pct = parse_float(parts[8])
    if latest is None:
        raise ValueError("missing Sina HK latest value")

    if pct is not None:
        sign = "+" if pct >= 0 else ""
        change_text = f"{sign}{pct:.2f}%"
    elif change is not None:
        sign = "+" if change >= 0 else ""
        change_text = f"{sign}{change:.2f}"
    else:
        change_text = "暂无前值"

    date_text = parts[17] if len(parts) > 17 else ""
    time_text = parts[18] if len(parts) > 18 else ""
    time_note = f"，最新时间 {date_text} {time_text}".rstrip() if date_text else ""

    return MarketSignal(
        name=instrument.name,
        value=f"{latest:.2f}",
        change=change_text,
        interpretation=f"{instrument.interpretation}{time_note}，数据源新浪港股行情。",
    )


def parse_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
