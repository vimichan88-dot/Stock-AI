from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

import requests

from .config import Settings
from .models import CoreEvent, InvestmentIdea, Report
from .news_data import NewsItem


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def enhance_report_with_openai(report: Report, settings: Settings, news_items: list[NewsItem]) -> Report:
    if not settings.openai_api_key:
        return report

    payload = {
        "model": settings.openai_model,
        "instructions": build_instructions(report.report_type),
        "input": build_input(report, news_items),
        "max_output_tokens": 5000,
    }
    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=90,
    )
    response.raise_for_status()
    output_text = extract_output_text(response.json())
    ai_payload = parse_json_object(output_text)
    return merge_ai_payload(report, ai_payload)


def build_instructions(report_type: str) -> str:
    report_focus = {
        "morning": "盘前投研日报：重点分析昨夜全球市场、今日 A/H 股机会和风险。",
        "noon": "午盘快报：重点分析上午异动、资金流和下午策略。",
        "close": "收盘复盘：重点分析全天交易逻辑、公告线索和明日展望。",
    }.get(report_type, "中文投研报告：重点分析市场主线、机会、风险和行动清单。")

    return (
        "你是个人 AI 投研助理，写中文机构投研风格报告。"
        "必须区分事实、预期和判断；不要编造不存在的数据；只基于输入的行情、新闻标题、来源和规则报告分析。"
        "每个投资建议必须包含动作、周期、成功率、置信度、风险等级、核心逻辑、催化剂、代表资产、定价状态、仓位、失效条件和观察指标。"
        "输出必须是单个 JSON 对象，不要 Markdown，不要代码块。"
        f"报告类型：{report_focus}"
    )


def build_input(report: Report, news_items: list[NewsItem]) -> str:
    compact_report = asdict(report)
    compact_report["generated_at"] = report.generated_at.isoformat()
    compact_news = [asdict(item) for item in news_items[:35]]

    required_schema = {
        "executive_summary": "string",
        "market_view": "string",
        "core_events": [
            {
                "title": "string",
                "summary": "string",
                "reason": "string",
                "beneficiaries": ["string"],
                "risks": ["string"],
                "importance": "integer 0-100",
                "confidence": "integer 0-100",
                "sources": ["string"],
            }
        ],
        "investment_ideas": [
            {
                "title": "string",
                "action": "可分批关注|持有观察|事件驱动可参与|谨慎追高|等待确认|降低关注|回避",
                "horizon": "string",
                "success_probability": "string",
                "confidence": "integer 0-100",
                "risk_level": "低|中低|中|中高|高",
                "logic": "string",
                "invalidation": "string",
                "watch_indicators": ["string"],
                "catalysts": ["string"],
                "representative_assets": ["string"],
                "pricing_status": "string",
                "position_size": "轻仓|标准仓|偏重|观察",
            }
        ],
        "action_checklist": ["string"],
        "risk_warnings": ["string"],
        "source_note_append": "string",
    }

    return json.dumps(
        {
            "task": "在规则版报告基础上升级为更完整、更审慎的中文投研报告 JSON。",
            "required_schema": required_schema,
            "rule_report": compact_report,
            "news_items": compact_news,
            "quality_rules": [
                "保留可复核来源，不把单一传闻作为投资依据。",
                "核心事件最多 10 条，按重要性排序。",
                "投资机会最多 5 条，必须有失效条件和观察指标。",
                "如果输入证据不足，明确写等待确认，不要强行看多。",
            ],
        },
        ensure_ascii=False,
    )


def extract_output_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]

    texts: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                texts.append(text)
    return "\n".join(texts)


def parse_json_object(text: str) -> dict[str, Any]:
    clean_text = text.strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
        clean_text = re.sub(r"\s*```$", "", clean_text)

    try:
        parsed = json.loads(clean_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean_text, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))

    if not isinstance(parsed, dict):
        raise ValueError("OpenAI response JSON must be an object")
    return parsed


def merge_ai_payload(report: Report, payload: dict[str, Any]) -> Report:
    core_events = [coerce_core_event(item) for item in payload.get("core_events", []) if isinstance(item, dict)]
    investment_ideas = [
        coerce_investment_idea(item) for item in payload.get("investment_ideas", []) if isinstance(item, dict)
    ]
    source_note_append = str(payload.get("source_note_append", "")).strip()
    source_note = report.source_note
    if source_note_append:
        source_note = f"{source_note}\n\nAI 分析说明：{source_note_append}"

    return Report(
        report_type=report.report_type,
        date=report.date,
        generated_at=report.generated_at,
        title=report.title,
        executive_summary=coerce_text(payload.get("executive_summary"), report.executive_summary),
        market_view=coerce_text(payload.get("market_view"), report.market_view),
        market_signals=report.market_signals,
        core_events=core_events or report.core_events,
        investment_ideas=investment_ideas or report.investment_ideas,
        action_checklist=coerce_text_list(payload.get("action_checklist")) or report.action_checklist,
        risk_warnings=coerce_text_list(payload.get("risk_warnings")) or report.risk_warnings,
        source_note=source_note,
    )


def coerce_core_event(item: dict[str, Any]) -> CoreEvent:
    return CoreEvent(
        title=coerce_text(item.get("title"), "未命名事件"),
        summary=coerce_text(item.get("summary"), ""),
        reason=coerce_text(item.get("reason"), ""),
        beneficiaries=coerce_text_list(item.get("beneficiaries")),
        risks=coerce_text_list(item.get("risks")),
        importance=coerce_score(item.get("importance"), 60),
        confidence=coerce_score(item.get("confidence"), 60),
        sources=coerce_text_list(item.get("sources")),
    )


def coerce_investment_idea(item: dict[str, Any]) -> InvestmentIdea:
    return InvestmentIdea(
        title=coerce_text(item.get("title"), "未命名机会"),
        action=coerce_text(item.get("action"), "等待确认"),
        horizon=coerce_text(item.get("horizon"), "1 个月"),
        success_probability=coerce_text(item.get("success_probability"), "50%-60%"),
        confidence=coerce_score(item.get("confidence"), 55),
        risk_level=coerce_text(item.get("risk_level"), "中"),
        logic=coerce_text(item.get("logic"), ""),
        invalidation=coerce_text(item.get("invalidation"), ""),
        watch_indicators=coerce_text_list(item.get("watch_indicators")),
        catalysts=coerce_text_list(item.get("catalysts")),
        representative_assets=coerce_text_list(item.get("representative_assets")),
        pricing_status=coerce_text(item.get("pricing_status"), ""),
        position_size=coerce_text(item.get("position_size"), ""),
    )


def coerce_text(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def coerce_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def coerce_score(value: Any, fallback: int) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(0, min(score, 100))
