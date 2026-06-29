from __future__ import annotations

from dataclasses import dataclass

from .market_data import MarketInstrument, fetch_yahoo_signal
from .models import MarketSignal


@dataclass(frozen=True)
class MacroSnapshot:
    signals: list[MarketSignal]
    source_note: str


MACRO_INSTRUMENTS = [
    MarketInstrument("美债 10 年收益率", "^TNX", "观察全球折现率和成长股估值压力"),
    MarketInstrument("VIX 波动率", "^VIX", "观察美股风险偏好和避险需求"),
    MarketInstrument("WTI 原油", "CL=F", "观察通胀预期、能源链和地缘风险"),
    MarketInstrument("COMEX 铜", "HG=F", "观察全球制造业需求和顺周期预期"),
    MarketInstrument("比特币", "BTC-USD", "观察全球流动性和高风险资产偏好"),
    MarketInstrument("以太坊", "ETH-USD", "观察加密资产风险偏好"),
]


def fetch_macro_snapshot(timeout_seconds: int = 8) -> MacroSnapshot:
    signals: list[MarketSignal] = []
    errors: list[str] = []

    for instrument in MACRO_INSTRUMENTS:
        try:
            signals.append(fetch_yahoo_signal(instrument, timeout_seconds))
        except Exception as exc:
            errors.append(f"{instrument.name}: {exc}")

    if not signals:
        raise RuntimeError("all macro proxy sources failed: " + "; ".join(errors))

    source_note = (
        "宏观代理指标来自 Yahoo Finance 免费接口，覆盖美债、波动率、商品和加密资产；"
        "这些是资金环境代理变量，不等同于官方宏观统计。"
    )
    if errors:
        source_note += " 部分宏观指标抓取失败：" + "；".join(errors)

    return MacroSnapshot(signals=signals, source_note=source_note)
