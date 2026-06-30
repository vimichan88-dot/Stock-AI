from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import Report


def report_to_markdown(report: Report) -> str:
    lines: list[str] = []
    lines.append(f"# {report.title}")
    lines.append("")
    lines.append(f"生成时间：{report.generated_at.strftime('%Y-%m-%d %H:%M:%S')} 北京时间")
    lines.append("")
    lines.append("## 今日核心结论")
    lines.append("")
    lines.append(report.executive_summary)
    lines.append("")
    lines.append(f"市场判断：{report.market_view}")
    lines.append("")
    lines.append("## 全球市场速览")
    lines.append("")
    lines.append("| 指标 | 数值 | 变化 | 解读 |")
    lines.append("|---|---|---|---|")
    for item in report.market_signals:
        lines.append(f"| {item.name} | {item.value} | {item.change} | {item.interpretation} |")
    lines.append("")
    lines.append("## 今日核心事件")
    lines.append("")
    for idx, event in enumerate(report.core_events, start=1):
        lines.append(f"### {idx}. {event.title}")
        lines.append("")
        lines.append(f"- 最新动态：{event.summary}")
        lines.append(f"- 市场影响：{event.reason}")
        lines.append(f"- 受益方向：{'、'.join(event.beneficiaries)}")
        lines.append(f"- 风险观察：{'、'.join(event.risks)}")
        lines.append(f"- 利好股票清单：{'、'.join(event.bullish_stocks) if event.bullish_stocks else '待复核'}")
        lines.append(f"- 利空股票清单：{'、'.join(event.bearish_stocks) if event.bearish_stocks else '待复核'}")
        lines.append(f"- 重要程度：{event.importance}/100")
        lines.append(f"- 置信度：{event.confidence}/100")
        lines.append(f"- 来源：{'、'.join(event.sources)}")
        lines.append("")
    if report.analysis_sections:
        lines.append("## 分主题研究框架")
        lines.append("")
        for section in report.analysis_sections:
            lines.append(f"### {section.title}")
            lines.append("")
            lines.append(f"- 观点：{section.view}")
            lines.append(f"- 机会观察：{'、'.join(section.opportunities)}")
            lines.append(f"- 风险约束：{'、'.join(section.risks)}")
            lines.append(f"- 跟踪指标：{'、'.join(section.watch)}")
            lines.append("")
    lines.append("## 投资机会")
    lines.append("")
    for idea in report.investment_ideas:
        lines.append(f"### {idea.title}")
        lines.append("")
        lines.append(f"- 建议动作：{idea.action}")
        lines.append(f"- 周期：{idea.horizon}")
        lines.append(f"- 成功率判断：{idea.success_probability}")
        lines.append(f"- 置信度：{idea.confidence}/100")
        lines.append(f"- 风险等级：{idea.risk_level}")
        lines.append(f"- 投资逻辑：{idea.logic}")
        if idea.catalysts:
            lines.append(f"- 核心催化剂：{'、'.join(idea.catalysts)}")
        if idea.representative_assets:
            lines.append(f"- 代表行业/ETF/公司：{'、'.join(idea.representative_assets)}")
        if idea.pricing_status:
            lines.append(f"- 定价状态：{idea.pricing_status}")
        if idea.position_size:
            lines.append(f"- 适合仓位：{idea.position_size}")
        lines.append(f"- 失效条件：{idea.invalidation}")
        lines.append(f"- 观察指标：{'、'.join(idea.watch_indicators)}")
        lines.append("")
    lines.append("## 我的行动清单")
    lines.append("")
    for item in report.action_checklist:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 风险提示")
    lines.append("")
    for item in report.risk_warnings:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 数据来源与可信度说明")
    lines.append("")
    lines.append(report.source_note)
    lines.append("")
    return "\n".join(lines)


def save_report(report: Report, output_dir: Path) -> tuple[Path, Path]:
    report_dir = output_dir / report.date
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"{report.report_type}.json"
    md_path = report_dir / f"{report.report_type}.md"

    payload = asdict(report)
    payload["generated_at"] = report.generated_at.isoformat()
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(report_to_markdown(report), encoding="utf-8")
    return json_path, md_path
