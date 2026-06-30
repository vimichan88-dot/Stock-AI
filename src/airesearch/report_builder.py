from __future__ import annotations

from datetime import datetime

from .models import MarketSignal, Report
from .news_data import NewsItem
from .rule_analysis import (
    build_action_checklist,
    build_analysis_sections,
    build_core_events,
    build_investment_ideas,
    build_market_view,
    build_risk_warnings,
)
from .sample_data import build_sample_report


def build_report(
    report_type: str,
    date_text: str,
    market_signals: list[MarketSignal] | None = None,
    market_source_note: str | None = None,
    news_items: list[NewsItem] | None = None,
    news_source_note: str | None = None,
    generated_at: datetime | None = None,
) -> Report:
    if not market_signals and not news_items:
        return build_sample_report(report_type, date_text)

    baseline = build_sample_report(report_type, date_text, market_signals, market_source_note)
    signals = market_signals or baseline.market_signals
    news = news_items or []
    market_view = build_market_view(signals)
    core_events = build_core_events(news, signals) if news else baseline.core_events
    ideas = build_investment_ideas(news, signals)
    analysis_sections = build_analysis_sections(market_view, signals, news, ideas)

    source_notes = []
    if market_source_note:
        source_notes.append(market_source_note)
    if news_source_note:
        source_notes.append(news_source_note)
    if not source_notes:
        source_notes.append(baseline.source_note)

    return Report(
        report_type=report_type,
        date=date_text,
        generated_at=generated_at or datetime.now(),
        title=baseline.title,
        executive_summary=build_executive_summary(report_type, market_view, core_events, ideas, len(news)),
        market_view=market_view,
        market_signals=signals,
        core_events=core_events,
        investment_ideas=ideas,
        action_checklist=build_action_checklist(ideas, core_events),
        risk_warnings=build_risk_warnings(signals, news),
        source_note="\n\n".join(source_notes),
        analysis_sections=analysis_sections,
    )


def build_executive_summary(report_type: str, market_view: str, core_events: list, ideas: list, news_count: int) -> str:
    report_context = {
        "morning": "盘前重点是把昨夜全球风险偏好、政策线索和今日A/H股可能交易的主线先排出优先级。",
        "noon": "午间重点是判断上午行情到底是资金主线、政策催化、产业催化，还是单纯情绪轮动。",
        "close": "盘后重点是复盘全天资金真正交易的变量，并为下一个交易日准备观察清单。",
    }.get(report_type, "当前报告重点是识别市场主线、风险和可执行观察项。")

    top_event = core_events[0].title if core_events else "暂无高置信事件"
    top_idea = ideas[0].title if ideas else "保持观察"
    return (
        f"{report_context} 当前市场总判断为：{market_view} "
        f"本次共纳入 {news_count} 条新闻线索和公告线索，最高优先级事件是“{top_event}”。"
        f" 投资上优先关注“{top_idea}”，但所有股票清单都应先作为研究和复核池，"
        "只有在订单、资金流、价格反应或政策细则继续验证后才适合提高仓位。"
    )
