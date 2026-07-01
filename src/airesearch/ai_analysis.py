from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

import requests

from .config import Settings
from .models import AnalysisSection, CoreEvent, InvestmentIdea, Report
from .news_data import NewsItem


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEEPSEEK_CHAT_COMPLETIONS_URL = "https://api.deepseek.com/chat/completions"


def configured_ai_provider(settings: Settings) -> str:
    provider = (settings.ai_provider or "auto").strip().lower()
    if provider == "deepseek":
        return "deepseek" if settings.deepseek_api_key else "none"
    if provider == "openai":
        return "openai" if settings.openai_api_key else "none"
    if settings.deepseek_api_key:
        return "deepseek"
    if settings.openai_api_key:
        return "openai"
    return "none"


def configured_ai_model(settings: Settings) -> str:
    provider = configured_ai_provider(settings)
    if provider == "deepseek":
        return settings.deepseek_model
    if provider == "openai":
        return settings.openai_model
    return ""


def enhance_report_with_openai(report: Report, settings: Settings, news_items: list[NewsItem]) -> Report:
    provider = configured_ai_provider(settings)
    if provider == "none":
        return report
    if provider == "deepseek":
        return enhance_report_with_deepseek(report, settings, news_items)
    return enhance_report_with_openai_responses(report, settings, news_items)


def enhance_report_with_openai_responses(report: Report, settings: Settings, news_items: list[NewsItem]) -> Report:
    if not settings.openai_api_key:
        return report

    payload = {
        "model": settings.openai_model,
        "instructions": build_instructions(report.report_type),
        "input": build_input(report, news_items),
        "max_output_tokens": 7000,
    }
    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    output_text = extract_output_text(response.json())
    ai_payload = parse_json_object(output_text)
    return merge_ai_payload(report, ai_payload)


def enhance_report_with_deepseek(report: Report, settings: Settings, news_items: list[NewsItem]) -> Report:
    if not settings.deepseek_api_key:
        return report

    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": build_instructions(report.report_type)},
            {"role": "user", "content": build_input(report, news_items)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 8192,
    }
    response = requests.post(
        DEEPSEEK_CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    output_text = extract_chat_completion_text(response.json())
    ai_payload = parse_json_object_with_deepseek_repair(output_text, settings)
    return merge_ai_payload(report, ai_payload)


def parse_json_object_with_deepseek_repair(text: str, settings: Settings) -> dict[str, Any]:
    try:
        return parse_json_object(text)
    except json.JSONDecodeError as first_error:
        repaired_text = repair_json_with_deepseek(text, settings, str(first_error))
        try:
            return parse_json_object(repaired_text)
        except json.JSONDecodeError as second_error:
            raise ValueError(
                f"DeepSeek returned invalid JSON and repair also failed. "
                f"Original error: {first_error}; repair error: {second_error}"
            ) from second_error


def repair_json_with_deepseek(text: str, settings: Settings, error_message: str) -> str:
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是 JSON 修复器。只输出一个合法 JSON 对象，不要 Markdown，不要解释。"
                    "保留原文已有字段和内容；如果末尾被截断，合理补齐括号、引号、逗号和数组结构。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"下面 JSON 解析失败，错误是：{error_message}\n"
                    "请修复为合法 JSON 对象：\n"
                    f"{text}"
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_tokens": 8192,
    }
    response = requests.post(
        DEEPSEEK_CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    return extract_chat_completion_text(response.json())


def build_instructions(report_type: str) -> str:
    report_focus = {
        "morning": "盘前投研日报：重点分析昨夜全球市场、未来24小时催化、今日A/H股机会和风险。",
        "noon": "午盘快报：重点分析上午异动、资金流、主线持续性和下午策略。",
        "close": "收盘复盘：重点分析全天交易逻辑、公告线索、明日展望和后续观察指标。",
    }.get(report_type, "中文机构投研报告：重点分析市场主线、机会、风险和行动清单。")

    return (
        "你不是新闻编辑，而是一支由首席宏观经济学家、全球资产配置专家、科技产业分析师、能源电力分析师、"
        "半导体与AI分析师、基金经理、量化策略分析师和地缘政治分析师组成的投研团队。"
        "目标不是堆砌新闻，而是帮助读者理解全球经济、产业资本流向、股票市场机会和未来3个月至3年的主线。"
        "必须严格基于输入证据包，不得编造不存在的数据；如果证据不足，要明确写等待确认。"
        "每个核心事件都必须回答：发生了什么、为什么现在发生、谁受益、谁受损、A股/港股/美股分别意味着什么、"
        "短期和中期影响、风险、持续观察指标。必须区分事实、市场预期和你的判断。"
        "输出必须是单个JSON对象，不要Markdown，不要代码块。"
        f"报告类型：{report_focus}"
    )


def build_input(report: Report, news_items: list[NewsItem]) -> str:
    compact_report = asdict(report)
    compact_report["generated_at"] = report.generated_at.isoformat()
    compact_news = [asdict(item) for item in news_items[:60]]

    required_schema = {
        "executive_summary": "string，300-600字，直接给核心结论",
        "market_view": "string，说明全球资本今天真正交易什么",
        "core_events": [
            {
                "title": "string",
                "summary": "string，具体说明发生了什么，必须尽量包含量化信息或具体公司/政策/指数",
                "reason": "string，详细解释市场影响、A股/港股/美股映射、短中期影响和机会风险",
                "beneficiaries": ["string"],
                "risks": ["string"],
                "bullish_stocks": ["string，具体A股/H股/美股/ETF或明确股票类别"],
                "bearish_stocks": ["string，具体A股/H股/美股/ETF或明确股票类别"],
                "importance": "integer 0-100，按真实重要性拉开差距",
                "confidence": "integer 0-100，按来源可靠性和证据完整性拉开差距",
                "sources": ["string，保留输入来源或链接"],
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
                "pricing_status": "string，说明哪些已定价，哪些还有预期差",
                "position_size": "轻仓|标准仓|偏重|观察",
            }
        ],
        "analysis_sections": [
            {
                "title": "string",
                "view": "string",
                "opportunities": ["string"],
                "risks": ["string"],
                "watch": ["string"],
            }
        ],
        "action_checklist": ["string"],
        "risk_warnings": ["string"],
        "source_note_append": "string",
    }

    return json.dumps(
        {
            "task": "在规则版报告和证据包基础上，升级为机构投研风格中文日报JSON。",
            "required_schema": required_schema,
            "rule_report": compact_report,
            "evidence_packet": {
                "market_snapshot": compact_report.get("market_signals", []),
                "news_items": compact_news,
                "coverage_hint": [
                    "全球宏观与央行",
                    "全球风险资产",
                    "A股政策与资金",
                    "港股科技与南向",
                    "美股AI与云资本开支",
                    "AI算力产业链",
                    "半导体国产替代",
                    "能源电力与储能",
                    "新能源车与电池",
                    "创新药与医疗",
                    "军工航天低空",
                    "大宗商品与资源",
                    "上市公司公告",
                    "未来7天事件日历",
                ],
            },
            "quality_rules": [
                "不要复制媒体标题，必须提炼成投研语言。",
                "核心事件最多10条，按重要程度排序，重要程度和置信度必须有差异。",
                "最新动态必须具体，不能写泛泛提示；如果标题没有量化信息，就说明可复核事实是什么。",
                "市场影响必须解释利好还是利空、为什么、传导链条是什么、A股/港股/美股如何映射。",
                "每条核心事件必须分别给出利好和利空股票清单；不能写待复核。",
                "analysis_sections至少覆盖：十大事件逻辑、全球市场复盘、产业趋势、资金流向、政策公告、未来7天、投资机会行动清单。",
                "投资机会必须给出催化剂、观察指标、定价状态、仓位和失效条件。",
                "如果证据不足，明确写等待确认，不能硬编数字。",
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


def extract_chat_completion_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    return content if isinstance(content, str) else ""


def parse_json_object(text: str) -> dict[str, Any]:
    clean_text = text.strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
        clean_text = re.sub(r"\s*```$", "", clean_text)
    clean_text = clean_json_text(clean_text)

    try:
        parsed = json.loads(clean_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean_text, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(clean_json_text(match.group(0)))

    if not isinstance(parsed, dict):
        raise ValueError("AI response JSON must be an object")
    return parsed


def clean_json_text(text: str) -> str:
    text = text.strip().lstrip("\ufeff")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text


def merge_ai_payload(report: Report, payload: dict[str, Any]) -> Report:
    core_events = [coerce_core_event(item) for item in payload.get("core_events", []) if isinstance(item, dict)]
    investment_ideas = [
        coerce_investment_idea(item) for item in payload.get("investment_ideas", []) if isinstance(item, dict)
    ]
    analysis_sections = [
        coerce_analysis_section(item) for item in payload.get("analysis_sections", []) if isinstance(item, dict)
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
        analysis_sections=analysis_sections or report.analysis_sections,
    )


def coerce_core_event(item: dict[str, Any]) -> CoreEvent:
    bullish_fallback, bearish_fallback = fallback_stock_lists(item)
    return CoreEvent(
        title=coerce_text(item.get("title"), "未命名事件"),
        summary=coerce_text(item.get("summary"), ""),
        reason=coerce_text(item.get("reason"), ""),
        beneficiaries=coerce_text_list(item.get("beneficiaries")),
        risks=coerce_text_list(item.get("risks")),
        importance=coerce_score(item.get("importance"), 60),
        confidence=coerce_score(item.get("confidence"), 60),
        sources=coerce_text_list(item.get("sources")),
        bullish_stocks=coerce_text_list(item.get("bullish_stocks")) or bullish_fallback,
        bearish_stocks=coerce_text_list(item.get("bearish_stocks")) or bearish_fallback,
    )


def coerce_investment_idea(item: dict[str, Any]) -> InvestmentIdea:
    return InvestmentIdea(
        title=coerce_text(item.get("title"), "未命名机会"),
        action=coerce_text(item.get("action"), "等待确认"),
        horizon=coerce_text(item.get("horizon"), "1个月"),
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


def coerce_analysis_section(item: dict[str, Any]) -> AnalysisSection:
    return AnalysisSection(
        title=coerce_text(item.get("title"), "未命名分析模块"),
        view=coerce_text(item.get("view"), ""),
        opportunities=coerce_text_list(item.get("opportunities")),
        risks=coerce_text_list(item.get("risks")),
        watch=coerce_text_list(item.get("watch")),
    )


def fallback_stock_lists(item: dict[str, Any]) -> tuple[list[str], list[str]]:
    text = " ".join(
        [
            str(item.get("title", "")),
            str(item.get("summary", "")),
            " ".join(coerce_text_list(item.get("beneficiaries"))),
            " ".join(coerce_text_list(item.get("risks"))),
        ]
    ).lower()
    mappings = [
        (
            ["ai", "算力", "芯片", "光模块", "半导体", "服务器"],
            ["中际旭创(300308)", "新易盛(300502)", "工业富联(601138)", "寒武纪(688256)", "中芯国际(688981)"],
            ["高估值无订单AI题材股", "算力租赁弱现金流公司", "低端服务器代工企业"],
        ),
        (
            ["新能源", "储能", "光伏", "电池", "电网", "电力"],
            ["宁德时代(300750)", "阳光电源(300274)", "亿纬锂能(300014)", "国电南瑞(600406)", "特变电工(600089)"],
            ["低效光伏组件企业", "高成本落后电池产能", "高负债新能源小票"],
        ),
        (
            ["港股", "恒生", "南向", "互联网", "平台"],
            ["腾讯控股(00700.HK)", "阿里巴巴-W(09988.HK)", "美团-W(03690.HK)", "小米集团-W(01810.HK)"],
            ["高杠杆地产链港股", "成交低迷券商股", "弱基本面小市值港股"],
        ),
        (
            ["黄金", "原油", "美元", "人民币", "美债", "宏观"],
            ["紫金矿业(601899)", "山东黄金(600547)", "中国海油(600938)", "红利ETF(515180)"],
            ["航空股", "高外债房企", "高估值成长股"],
        ),
    ]
    for keywords, bullish, bearish in mappings:
        if any(keyword in text for keyword in keywords):
            return bullish, bearish
    return ["相关行业龙头", "产业链ETF", "高景气细分龙头"], ["同业弱势公司", "高估值题材股", "基本面承压公司"]


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
