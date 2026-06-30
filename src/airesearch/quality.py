from __future__ import annotations

from .models import Report


def validate_report(report: Report) -> list[str]:
    warnings: list[str] = []

    if not report.market_signals:
        warnings.append("缺少市场指标。")
    if len(report.core_events) < 3:
        warnings.append("核心事件少于 3 条。")
    if not report.investment_ideas:
        warnings.append("缺少投资机会。")
    if not report.action_checklist:
        warnings.append("缺少行动清单。")
    if not report.risk_warnings:
        warnings.append("缺少风险提示。")
    if len(report.analysis_sections) < 6:
        warnings.append("专题研究模块少于 6 个。")

    for idx, event in enumerate(report.core_events, start=1):
        if not event.sources:
            warnings.append(f"核心事件 {idx} 缺少来源。")
        if event.importance < 0 or event.importance > 100:
            warnings.append(f"核心事件 {idx} 重要程度超出 0-100。")
        if event.confidence < 0 or event.confidence > 100:
            warnings.append(f"核心事件 {idx} 置信度超出 0-100。")
        if not event.bullish_stocks:
            warnings.append(f"核心事件 {idx} 缺少利好股票清单。")
        if not event.bearish_stocks:
            warnings.append(f"核心事件 {idx} 缺少利空股票清单。")
        if len(event.summary) < 40:
            warnings.append(f"核心事件 {idx} 最新动态过短。")
        if len(event.reason) < 80:
            warnings.append(f"核心事件 {idx} 市场影响分析过短。")

    for idx, idea in enumerate(report.investment_ideas, start=1):
        if not idea.invalidation:
            warnings.append(f"投资机会 {idx} 缺少失效条件。")
        if not idea.watch_indicators:
            warnings.append(f"投资机会 {idx} 缺少观察指标。")
        if not idea.catalysts:
            warnings.append(f"投资机会 {idx} 缺少核心催化剂。")
        if not idea.position_size:
            warnings.append(f"投资机会 {idx} 缺少适合仓位。")

    return warnings


def append_quality_note(report: Report, warnings: list[str]) -> Report:
    if not warnings:
        report.source_note = f"{report.source_note}\n\n质量检查：通过基础完整性检查。"
        return report

    joined = "；".join(warnings)
    report.source_note = f"{report.source_note}\n\n质量检查：发现待复核项：{joined}"
    return report
