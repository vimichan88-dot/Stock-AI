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
) -> Report:
    if not market_signals and not news_items:
        return build_sample_report(report_type, date_text)

    baseline = build_sample_report(report_type, date_text, market_signals, market_source_note)
    signals = market_signals or baseline.market_signals
    news = news_items or []
    core_events = build_core_events(news, signals) if news else baseline.core_events
    ideas = build_investment_ideas(news, signals)
    market_view = build_market_view(signals)
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
        generated_at=datetime.now(),
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
        "morning": "盘前重点是判断昨夜外围市场和今日 A/H 股交易环境。",
        "noon": "午间重点是识别上午市场主线是否延续，以及下午是否需要调整策略。",
        "close": "收盘后重点是复盘全天交易逻辑，并为下一交易日准备观察清单。",
    }.get(report_type, "当前报告重点是识别市场主线、风险和可执行观察项。")

    top_event = core_events[0].title if core_events else "暂无高置信事件"
    top_idea = ideas[0].title if ideas else "保持观察"
    return (
        f"{report_context} 当前市场判断为：{market_view} "
        f"本次共纳入 {news_count} 条新闻线索用于事件筛选，最高优先级事件是“{top_event}”。"
        f" 投资上优先关注“{top_idea}”，同时严格跟踪失效条件和来源可信度。"
    )
