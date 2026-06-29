from __future__ import annotations

from collections import Counter

from .models import CoreEvent, InvestmentIdea, MarketSignal
from .news_data import NewsItem


POSITIVE_WORDS = ["上涨", "反弹", "创新高", "增持", "获批", "订单", "扩产", "突破", "利好", "增长"]
NEGATIVE_WORDS = ["下跌", "回落", "风险", "调查", "制裁", "亏损", "降价", "减持", "违约", "放缓"]
HIGH_IMPACT_WORDS = ["政策", "央行", "美联储", "业绩", "订单", "出口", "并购", "监管", "关税", "AI", "芯片"]


def build_market_view(signals: list[MarketSignal]) -> str:
    changes = [parse_pct(signal.change) for signal in signals if parse_pct(signal.change) is not None]
    if not changes:
        return "中性。当前市场信号不足，优先等待更多行情和消息验证。"

    average_change = sum(changes) / len(changes)
    positive_count = sum(1 for value in changes if value > 0)
    negative_count = sum(1 for value in changes if value < 0)

    if average_change >= 0.8 and positive_count >= negative_count:
        return "偏积极。主要风险资产同步走强，短线可以提高对顺周期和成长主线的观察权重。"
    if average_change <= -0.8 and negative_count > positive_count:
        return "偏谨慎。多项风险资产承压，今日更应控制追高，优先观察防御和现金流质量。"
    if positive_count > negative_count:
        return "中性偏积极。市场结构仍有机会，但需要区分强势主线和补涨噪音。"
    if negative_count > positive_count:
        return "中性偏谨慎。风险偏好有降温迹象，等待 A/H 股主线重新确认更稳妥。"
    return "中性。市场方向暂不极端，适合以事件和业绩线索做结构筛选。"


def build_core_events(news_items: list[NewsItem], signals: list[MarketSignal]) -> list[CoreEvent]:
    events = [event_from_news(item) for item in news_items]
    events.sort(key=lambda event: (event.importance, event.confidence), reverse=True)

    selected = events[:8]
    selected.insert(0, market_event(signals))
    return selected[:10]


def build_investment_ideas(news_items: list[NewsItem], signals: list[MarketSignal]) -> list[InvestmentIdea]:
    categories = Counter(item.category for item in news_items)
    ideas: list[InvestmentIdea] = []

    if categories["AI"] or has_signal(signals, "纳指", 0):
        ideas.append(
            InvestmentIdea(
                title="跟踪 AI 算力与半导体链条的订单验证",
                action="可分批关注",
                horizon="1-3 个月",
                success_probability="约 60%-70%",
                confidence=68,
                risk_level="中",
                logic="AI 相关消息密度和美股科技风险偏好仍是 A/H 成长主线的重要映射，适合优先观察有业绩验证的环节。",
                invalidation="云厂商资本开支预期下修，核心公司订单低于预期，或纳指科技资产连续走弱。",
                watch_indicators=["纳指 100 ETF", "AI 新闻密度", "半导体订单", "光模块价格"],
                catalysts=["AI 资本开支", "光模块订单", "国产算力政策", "半导体周期回升"],
                representative_assets=["光模块", "服务器", "半导体 ETF", "云计算"],
                pricing_status="热门环节已有较多定价，优先等待订单和业绩兑现。",
                position_size="轻仓到标准仓",
            )
        )

    if categories["新能源"]:
        ideas.append(
            InvestmentIdea(
                title="新能源从总量交易转向结构筛选",
                action="等待确认",
                horizon="3-12 个月",
                success_probability="约 55%-65%",
                confidence=62,
                risk_level="中",
                logic="新能源新闻仍有催化，但产能和价格压力未完全解除，应优先看储能、电网等盈利更稳定的分支。",
                invalidation="产业链价格继续快速下行，招标低于预期，或龙头盈利继续下修。",
                watch_indicators=["储能招标", "电网投资", "组件价格", "锂价"],
                catalysts=["储能项目投运", "电网投资加速", "政策消纳约束", "海外需求恢复"],
                representative_assets=["储能", "电网设备", "电池 ETF", "光伏逆变器"],
                pricing_status="分支差异较大，储能和电网优于产能过剩环节。",
                position_size="轻仓观察",
            )
        )

    if has_signal(signals, "恒生", 1) or categories["港股"]:
        ideas.append(
            InvestmentIdea(
                title="港股科技关注南向资金与美元环境共振",
                action="持有观察",
                horizon="1 个月",
                success_probability="约 55%-65%",
                confidence=60,
                risk_level="中",
                logic="港股弹性取决于美元流动性、平台经济预期和南向资金，适合用趋势确认而非单日波动做决策。",
                invalidation="美元重新走强，恒生科技放量下破，或互联网龙头业绩指引转弱。",
                watch_indicators=["恒生指数", "美元/离岸人民币", "南向资金", "港股科技成交额"],
                catalysts=["美元走弱", "南向资金回流", "互联网平台业绩修复", "政策预期改善"],
                representative_assets=["恒生科技", "港股互联网 ETF", "平台经济龙头"],
                pricing_status="修复交易已有启动，仍需资金持续性确认。",
                position_size="轻仓到标准仓",
            )
        )

    if not ideas:
        ideas.append(
            InvestmentIdea(
                title="数据不足时保持轻仓观察",
                action="等待确认",
                horizon="1 周",
                success_probability="50%-55%",
                confidence=52,
                risk_level="中低",
                logic="当前新闻和行情信号不足以支持明确加仓，先等待更高质量催化或价格确认。",
                invalidation="主要指数放量突破且高质量事件密集出现。",
                watch_indicators=["成交量", "指数趋势", "政策消息", "行业龙头表现"],
                catalysts=["放量突破", "政策确认", "龙头业绩上修"],
                representative_assets=["宽基指数", "高股息", "现金管理"],
                pricing_status="尚未形成高胜率定价信号。",
                position_size="轻仓",
            )
        )

    return ideas[:4]


def build_action_checklist(ideas: list[InvestmentIdea], events: list[CoreEvent]) -> list[str]:
    checklist = [
        "先确认今天交易的是流动性、政策、业绩还是产业催化。",
        "只把重要性高且来源可复核的事件放入重点跟踪列表。",
    ]
    for idea in ideas[:3]:
        checklist.append(f"{idea.action}：{idea.title}，观察 {'、'.join(idea.watch_indicators[:3])}。")
    if events:
        checklist.append(f"优先复核最高分事件：{events[0].title}。")
    return checklist


def build_risk_warnings(signals: list[MarketSignal], news_items: list[NewsItem]) -> list[str]:
    warnings = [
        "免费行情和 RSS 聚合源可能延迟或缺失，关键结论需要回看原始来源。",
        "AI 或规则生成观点不能替代独立判断，所有建议都必须结合仓位和失效条件。",
    ]
    if any((parse_pct(signal.change) or 0) <= -1.5 for signal in signals):
        warnings.append("部分资产单日跌幅较大，短线风险偏好可能低于新闻标题呈现的乐观程度。")
    if sum(1 for item in news_items if sentiment_score(item.title) < 0) >= 3:
        warnings.append("负面新闻密度上升，需警惕政策、盈利或外部流动性风险扩散。")
    return warnings


def event_from_news(item: NewsItem) -> CoreEvent:
    sentiment = sentiment_score(item.title)
    importance = score_news(item)
    direction = "正面催化" if sentiment > 0 else "风险信号" if sentiment < 0 else "重要线索"

    return CoreEvent(
        title=item.title,
        summary=f"{item.category}方向出现{direction}，需要结合原文与市场反应判断持续性。",
        reason=f"该线索来自 {item.source}，属于“{item.query_name}”监控范围；标题涉及的主题可能影响相关行业风险偏好。",
        beneficiaries=beneficiaries_for(item),
        risks=risks_for(item, sentiment),
        importance=importance,
        confidence=confidence_for(item),
        sources=[item.source, item.link],
    )


def market_event(signals: list[MarketSignal]) -> CoreEvent:
    changes = [(signal.name, parse_pct(signal.change)) for signal in signals]
    known_changes = [(name, value) for name, value in changes if value is not None]
    known_changes.sort(key=lambda pair: abs(pair[1]), reverse=True)
    leader = known_changes[0][0] if known_changes else "主要市场"

    return CoreEvent(
        title="全球风险偏好与 A/H 股交易环境更新",
        summary=f"{leader}波动居前，需结合 A 股、港股、美股科技、黄金和汇率判断今日风险偏好。",
        reason="跨市场行情是判断资金环境和主题持续性的基础输入，能帮助区分指数驱动与行业事件驱动。",
        beneficiaries=["A 股核心资产", "港股科技", "AI 算力", "黄金与避险资产"],
        risks=["外部流动性收紧", "汇率波动", "主题拥挤", "单日行情误读"],
        importance=86,
        confidence=72,
        sources=["Yahoo Finance chart"],
    )


def score_news(item: NewsItem) -> int:
    score = 58
    title = item.title
    score += sum(7 for word in HIGH_IMPACT_WORDS if word.lower() in title.lower())
    if item.category in {"AI", "A 股", "港股", "新能源"}:
        score += 8
    if item.source not in {"Google News", ""}:
        score += 4
    score += abs(sentiment_score(title)) * 4
    return max(0, min(score, 95))


def confidence_for(item: NewsItem) -> int:
    confidence = 58
    if item.link:
        confidence += 8
    if item.source not in {"Google News", ""}:
        confidence += 8
    if item.published_at:
        confidence += 5
    return min(confidence, 82)


def sentiment_score(text: str) -> int:
    lowered = text.lower()
    positive = sum(1 for word in POSITIVE_WORDS if word.lower() in lowered)
    negative = sum(1 for word in NEGATIVE_WORDS if word.lower() in lowered)
    return positive - negative


def beneficiaries_for(item: NewsItem) -> list[str]:
    mapping = {
        "AI": ["服务器", "光模块", "半导体", "云计算", "IDC"],
        "新能源": ["储能", "电网设备", "电池", "新能源车", "光伏"],
        "港股": ["港股科技", "互联网平台", "高股息", "南向资金重仓"],
        "A 股": ["券商", "核心资产", "政策受益行业", "成交活跃主题"],
        "宏观": ["黄金", "美元资产", "高股息", "出口链"],
        "公告": ["公告涉及公司", "相关产业链", "同业龙头"],
    }
    return mapping.get(item.category, ["相关行业", "龙头公司"])


def risks_for(item: NewsItem, sentiment: int) -> list[str]:
    base = ["消息反转", "市场已充分定价", "来源细节需复核"]
    if sentiment < 0:
        return ["风险继续扩散", "盈利预期下修", "流动性压力"] + base[:1]
    return base


def has_signal(signals: list[MarketSignal], name_part: str, threshold: float) -> bool:
    for signal in signals:
        value = parse_pct(signal.change)
        if name_part in signal.name and value is not None and value >= threshold:
            return True
    return False


def parse_pct(value: str) -> float | None:
    if not value.endswith("%"):
        return None
    try:
        return float(value.rstrip("%+"))
    except ValueError:
        return None
