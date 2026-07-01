from __future__ import annotations

from collections import Counter
import re

from .models import AnalysisSection, CoreEvent, InvestmentIdea, MarketSignal
from .news_data import NewsItem


POSITIVE_WORDS = ["上涨", "反弹", "创新高", "增持", "获批", "订单", "扩产", "突破", "利好", "增长", "回流", "中标", "上修", "降息", "放量"]
NEGATIVE_WORDS = ["下跌", "回落", "风险", "调查", "制裁", "亏损", "降价", "减持", "违约", "放缓", "下修", "暴跌", "监管", "关税", "冲突"]
HIGH_IMPACT_WORDS = ["政策", "央行", "美联储", "业绩", "订单", "出口", "并购", "监管", "关税", "AI", "芯片", "算力", "半导体", "南向资金", "人民币", "美债", "黄金", "原油"]


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


def build_analysis_sections(
    market_view: str,
    signals: list[MarketSignal],
    news_items: list[NewsItem],
    ideas: list[InvestmentIdea],
) -> list[AnalysisSection]:
    categories = Counter(item.category for item in news_items)
    strong_signals = strongest_signals(signals)
    idea_titles = [idea.title for idea in ideas[:3]]

    return [
        AnalysisSection(
            title="核心宏观变量",
            view=(
                f"当前总判断为：{market_view} 需要把美元、人民币、VIX、黄金和主要股指放在同一张表里看，"
                "避免只依据单一新闻标题做方向判断。"
            ),
            opportunities=[
                "若风险偏好改善，优先观察 A 股核心资产、港股互联网平台和 AI 算力龙头的资金承接。",
                "若避险升温，黄金、高股息和现金流稳定资产相对更容易获得资金防守配置。",
            ],
            risks=[
                "美元或美债收益率重新走强会压制高估值成长股。",
                "单日指数反弹若缺少成交量配合，容易变成补涨而非趋势切换。",
            ],
            watch=strong_signals[:4] or ["美元指数", "离岸人民币", "VIX", "恒生科技"],
        ),
        AnalysisSection(
            title="利率与固收",
            view="固收信号用于判断权益估值压力和防守资产吸引力；当收益率上行与风险资产走弱同时出现时，需要降低追高力度。",
            opportunities=[
                "收益率下行时，高股息、核心资产和长久期成长板块的估值压力通常缓和。",
                "信用风险没有扩散时，红利 ETF、央国企和现金流稳定资产可作为组合底仓观察。",
            ],
            risks=[
                "收益率快速上行会冲击科技成长和高估值主题。",
                "信用利差或地产链压力扩散时，弱现金流小盘股和高杠杆公司承压更明显。",
            ],
            watch=[signal.name for signal in signals if any(key in signal.name for key in ["债", "收益率", "VIX", "波动"])][:4]
            or ["美债收益率", "中国十年国债", "VIX", "信用利差"],
        ),
        AnalysisSection(
            title="大宗商品与地缘",
            view="商品和汇率线索用于识别通胀、避险和出口链变化。黄金、原油、铜和人民币的组合变化，比单个价格更重要。",
            opportunities=[
                "黄金走强时，黄金矿业、贵金属 ETF 和高股息资产更适合进入观察池。",
                "油价走强时，上游资源、油服和高股息能源股可能受益。",
            ],
            risks=[
                "油价或航运成本上行会压缩航空、化工下游和部分制造业利润。",
                "人民币波动放大时，高外债房企、进口成本敏感公司和高估值成长股风险上升。",
            ],
            watch=[signal.name for signal in signals if any(key in signal.name for key in ["油", "黄金", "铜", "美元", "人民币"])][:4]
            or ["黄金", "WTI 原油", "美元指数", "离岸人民币"],
        ),
        AnalysisSection(
            title="美国权益市场",
            view="美股科技和纳指是 A/H 成长风格的重要外部锚，尤其影响 AI 算力、半导体、云计算和港股科技定价。",
            opportunities=[
                "纳指或费半维持强势时，A/H 的 AI 算力、光模块、服务器和半导体链条更容易获得映射。",
                "若美股上涨由盈利和订单驱动，而非单纯估值扩张，相关产业链的可持续性更高。",
            ],
            risks=[
                "美股科技高位回落会传导到高估值 AI 题材。",
                "若海外云厂商资本开支预期下修，光模块、服务器和算力租赁链条需要快速降温。",
            ],
            watch=[signal.name for signal in signals if any(key in signal.name for key in ["纳指", "标普", "道指", "Nasdaq", "S&P"])][:4]
            or ["纳指 100 ETF", "标普 500", "费城半导体", "美股 AI 龙头"],
        ),
        AnalysisSection(
            title="中国与亚洲权益市场",
            view=(
                f"新闻主题分布显示：AI {categories.get('AI', 0)} 条、港股 {categories.get('港股', 0)} 条、"
                f"A 股 {categories.get('A 股', 0)} 条、新能源 {categories.get('新能源', 0)} 条。"
                "需要区分指数修复、政策催化和产业订单三类驱动。"
            ),
            opportunities=[
                "港股科技关注南向资金、美元环境和平台经济预期的共振。",
                "A 股优先看有订单验证或政策落地的方向，避免只追逐标题热度。",
            ],
            risks=[
                "成交量不足时，主题轮动速度会加快，追高容错率下降。",
                "若政策预期没有后续细则，券商、地产链和高弹性题材容易回吐。",
            ],
            watch=["沪深300", "创业板指", "恒生科技", "南向资金"],
        ),
        AnalysisSection(
            title="机构研究精读",
            view="把机构视角压缩成可执行问题：哪条主线有订单或政策验证，哪条主线只是情绪扩散，什么时候必须承认判断失效。",
            opportunities=idea_titles or ["等待更明确的产业或政策催化"],
            risks=[
                "报告中的股票清单是受益/承压观察池，不等同于买卖指令。",
                "缺少原文细节或财务验证时，个股只能进入复核清单，不能直接提高仓位。",
            ],
            watch=["订单验证", "成交量", "资金流向", "失效条件"],
        ),
    ]


def strongest_signals(signals: list[MarketSignal]) -> list[str]:
    ranked = []
    for signal in signals:
        value = parse_pct(signal.change)
        if value is not None:
            ranked.append((abs(value), signal.name))
    ranked.sort(reverse=True)
    return [name for _, name in ranked]


def event_from_news(item: NewsItem) -> CoreEvent:
    sentiment = sentiment_score(item.title)
    importance = score_news(item)
    direction = "正面催化" if sentiment > 0 else "风险信号" if sentiment < 0 else "重要线索"
    bullish_stocks, bearish_stocks = stock_impact_for(item)
    impact_path = impact_path_for(item)
    verification = verification_points_for(item)
    event_summary = build_event_summary(item, direction)
    event_reason = build_market_impact(item, impact_path, verification)

    return CoreEvent(
        title=item.title,
        summary=event_summary,
        reason=event_reason,
        beneficiaries=beneficiaries_for(item),
        risks=risks_for(item, sentiment),
        importance=importance,
        confidence=confidence_for(item),
        sources=event_sources(item),
        bullish_stocks=bullish_stocks,
        bearish_stocks=bearish_stocks,
    )


def build_event_summary(item: NewsItem, direction: str) -> str:
    category_context = {
        "AI": "AI 链条的有效信息主要集中在算力需求、云厂商资本开支、芯片/光模块订单、服务器出货和应用落地节奏；当前线索提示市场仍在围绕算力景气和硬件订单寻找定价锚。",
        "新能源": "新能源线索需要拆成储能、电网、电池、光伏和整车几个分支看，重点不是板块普涨，而是订单、价格、库存和毛利率是否出现边际改善。",
        "港股": "港股线索的核心在于美元流动性、南向资金和平台经济预期是否共振；如果只有指数反弹但成交和资金没有跟上，持续性要打折。",
        "A 股": "A 股线索需要先判断是政策驱动、成交放大、产业催化还是单纯题材轮动；只有能带来资金聚焦和盈利预期变化的线索才值得提高优先级。",
        "宏观": "宏观线索会通过美元、美债、人民币、黄金、原油和 VIX 影响风险偏好与估值折现率，进而改变 A/H 股成长、资源和高股息资产的相对吸引力。",
        "公告": "公告线索的重点是原文里的订单金额、利润率、履约周期、现金流和可比公司映射，不能只看公告标题。",
    }.get(item.category, "这条线索需要重点判断它是否会改变行业预期、资金关注度和估值弹性。")
    return f"{item.category}方向出现{direction}。{category_context}"


def build_market_impact(item: NewsItem, impact_path: str, verification: str) -> str:
    opportunity = {
        "AI": "机会主要在有订单验证和业绩兑现能力的光模块、服务器、半导体、IDC、云计算环节；风险在于高估值题材股已经提前反映预期。",
        "新能源": "机会更偏向储能、电网设备和盈利稳定的电池龙头；产能过剩、价格战和高负债小票仍是主要风险。",
        "港股": "机会集中在港股科技、互联网平台、高股息和南向资金重仓资产；若美元反弹或南向资金转弱，修复交易容易中断。",
        "A 股": "机会在成交放大时的券商、核心资产、政策受益方向和强产业催化主题；如果缺少量能和政策细则，追高风险会明显上升。",
        "宏观": "机会通常在黄金、能源、高股息和出口链之间切换；对高估值成长股而言，美债收益率和美元走强会形成压制。",
        "公告": "机会取决于公告是否能转化为订单、利润或现金流改善；如果只是形式性公告，市场影响通常较弱。",
    }.get(item.category, "机会需要结合价格反应、成交量和龙头股强弱确认。")
    return f"影响链条：{impact_path}。股票市场影响：{opportunity} 后续需要验证：{verification}。"


def event_sources(item: NewsItem) -> list[str]:
    sources = [f"消息来源：{item.source}", f"检索主题：{item.query_name}", f"原始标题：{item.title}"]
    if item.published_at:
        sources.insert(1, f"发布时间：{item.published_at}")
    if item.link:
        sources.append(item.link)
    return sources


def impact_path_for(item: NewsItem) -> str:
    mapping = {
        "AI": "海外 AI 资本开支或国产算力预期 -> 光模块、服务器、半导体、IDC 等环节订单预期 -> A/H 科技成长风险偏好",
        "新能源": "政策、招标或价格变化 -> 储能、电网、电池、光伏盈利预期 -> 产业链分化而非板块普涨",
        "港股": "美元流动性和南向资金 -> 平台经济、港股科技和高股息资产估值修复 -> 港股成交持续性",
        "A 股": "政策预期和成交量 -> 券商、核心资产、主题成长的弹性 -> 指数能否从反弹转为趋势",
        "宏观": "美元、美债、黄金、原油和人民币变化 -> 全球风险偏好与贴现率 -> A/H 股估值和行业轮动",
        "公告": "公司公告或业绩线索 -> 订单、利润率、现金流或资本开支变化 -> 同产业链估值重估",
    }
    return mapping.get(item.category, "新闻线索 -> 行业预期变化 -> 资金关注度和估值弹性变化")


def verification_points_for(item: NewsItem) -> str:
    mapping = {
        "AI": "云厂商资本开支、订单落地、龙头公司公告、光模块价格和美股 AI 链表现",
        "新能源": "招标规模、组件/电池价格、库存去化、龙头毛利率和海外政策细节",
        "港股": "南向资金净流入、恒生科技成交额、美元指数、平台龙头业绩指引",
        "A 股": "成交额放大、政策细则、北向或机构资金、龙头股相对强弱",
        "宏观": "美债收益率、美元/人民币、黄金原油价格、VIX 和主要股指共振",
        "公告": "公告原文、财务口径、订单金额、履约周期和利润率影响",
    }
    return mapping.get(item.category, "原文细节、成交量、行业龙头反应和后续公告")


def build_event_summary(item: NewsItem, direction: str) -> str:
    category_context = {
        "AI": "这条消息的关键不是泛泛说 AI 热，而是看算力需求、硬件订单、应用层变现或科技指数表现有没有新的边际变化。",
        "新能源": "这条消息需要拆到储能、电网、电池、光伏或整车分支，看订单、价格、库存、招标或政策是否发生变化。",
        "港股": "这条消息重点看港股科技、南向资金、美元流动性和平台经济预期是否出现共振或背离。",
        "A 股": "这条消息重点看政策、成交量、产业催化和板块轮动之间的关系，尤其是强势方向是否有龙头确认。",
        "宏观": "这条消息重点看美元、美债、人民币、黄金、原油、VIX 等宏观变量是否改变市场风险偏好和折现率。",
        "公告": "这条消息重点看公告是否包含订单金额、利润率、履约周期、现金流或上市融资等可落地信息。",
    }.get(item.category, "这条消息需要判断是否改变行业预期、资金关注度和估值弹性。")
    return f"{item.category}方向出现{direction}。{extract_title_facts(item.title)}{category_context}"


def extract_title_facts(title: str) -> str:
    clean_title = clean_news_title(title)
    metrics = list(dict.fromkeys(re.findall(r"(?:涨超|跌超|超|近|约|逾|超过)?\d+(?:\.\d+)?%", clean_title)))
    quoted = list(dict.fromkeys(re.findall(r"[“\"]([^”\"]{2,40})[”\"]", clean_title)))
    clauses = split_title_clauses(clean_title)
    main_clause = clauses[0] if clauses else clean_title
    detail_clauses = [clause for clause in clauses[1:4] if clause != main_clause]

    parts = [f"标题可见事实是：{main_clause}。"]
    if detail_clauses:
        parts.append(f"进一步拆开看，标题还提到：{'；'.join(detail_clauses)}。")
    if metrics:
        parts.append(f"量化信息包括：{'、'.join(metrics)}。")
    if quoted:
        parts.append(f"关键词包括：{'、'.join(quoted[:3])}。")
    return "".join(parts)


def clean_news_title(title: str) -> str:
    title = re.sub(r"\s+-\s+[^-]{2,30}$", "", title.strip())
    return re.sub(r"\s+", " ", title)


def split_title_clauses(title: str) -> list[str]:
    parts = re.split(r"[：:，,；;。|｜]", title)
    clauses = [part.strip(" -_") for part in parts if len(part.strip(" -_")) >= 4]
    if len(clauses) >= 2 and re.search(r"(证券|财经|新闻|日报|时报|见闻)$", clauses[0]) and len(clauses[1]) > len(clauses[0]):
        return [clauses[1], clauses[0], *clauses[2:]]
    return clauses


def build_market_impact(item: NewsItem, impact_path: str, verification: str) -> str:
    direction_text = assess_event_direction(item)
    opportunity = {
        "AI": "如果消息指向算力需求扩张、硬件订单增加或应用加速落地，通常利好光模块、服务器、半导体、IDC、云计算；如果消息指向指数大跌、硬件错配或估值拥挤，则更偏利空高估值 AI 题材，资金会转向有真实订单和利润兑现的龙头。",
        "新能源": "如果消息指向招标增加、价格企稳或政策支持，利好储能、电网设备和盈利稳定的电池龙头；如果指向降价、库存或产能压力，则利空低效光伏组件、高成本电池产能和高负债公司。",
        "港股": "如果消息指向南向资金回流、美元走弱或平台经济预期改善，利好港股科技和互联网平台；如果指向指数收跌、流动性分化或美元走强，说明修复交易持续性不足。",
        "A 股": "如果消息指向成交放大、政策落地或产业催化，利好券商、核心资产和强主题龙头；如果消息指向放量下跌或热门板块回调，短线更偏风险释放，资金可能切到低位或防守方向。",
        "宏观": "如果消息指向美元/美债上行，通常压制高估值成长股；如果黄金、原油或资源品波动加大，资金会在黄金、能源、高股息和出口链之间重新定价。",
        "公告": "如果公告对应订单、利润或现金流改善，才可能形成实质利好；如果只是上市、流程或常规披露，对二级市场通常偏中性。",
    }.get(item.category, "机会需要结合价格反应、成交量和龙头股强弱确认。")
    return f"方向判断：{direction_text}影响链条：{impact_path}。股票市场影响：{opportunity} 后续需要验证：{verification}。"


def assess_event_direction(item: NewsItem) -> str:
    text = item.title.lower()
    negative_hits = ["跌", "下跌", "回调", "承压", "收跌", "流动性", "错配", "风险", "放缓", "降价", "制裁"]
    positive_hits = ["涨", "大涨", "回流", "机遇", "订单", "增长", "突破", "获批", "中标", "上修", "扩产"]
    has_negative = any(word in text for word in negative_hits)
    has_positive = any(word in text for word in positive_hits)
    if has_positive and has_negative:
        return "结构分化，不能简单看多或看空；需要区分受益方向和承压方向。"
    if has_negative:
        return "偏利空或风险释放，短线需要先看相关板块是否继续放量承压。"
    if has_positive:
        return "偏利好，前提是后续能看到订单、资金流或价格表现继续确认。"
    return "偏中性，当前更适合作为观察线索，而不是直接交易信号。"


def market_event(signals: list[MarketSignal]) -> CoreEvent:
    changes = [(signal.name, parse_pct(signal.change)) for signal in signals]
    known_changes = [(name, value) for name, value in changes if value is not None]
    known_changes.sort(key=lambda pair: abs(pair[1]), reverse=True)
    leader = known_changes[0][0] if known_changes else "主要市场"
    gainers = [f"{name}{value:+.2f}%" for name, value in known_changes if value > 0][:3]
    losers = [f"{name}{value:+.2f}%" for name, value in known_changes if value < 0][:3]
    gainer_text = "、".join(gainers) if gainers else "暂无明显上涨领先指标"
    loser_text = "、".join(losers) if losers else "暂无明显下跌领先指标"

    return CoreEvent(
        title="全球风险偏好与 A/H 股交易环境更新",
        summary=(
            f"跨市场行情显示，{leader}波动居前；上涨领先指标包括{gainer_text}，下跌或承压指标包括{loser_text}。"
            "这条事件用于判断今天 A/H 股的外部交易环境：若大陆、港股、美股科技和商品风险资产同步走强，"
            "说明资金风险偏好更友好；若 VIX、美元或美债收益率走强，同时成长指数回落，则需要降低追高。"
        ),
        reason="跨市场行情是判断资金环境和主题持续性的基础输入，能帮助区分指数驱动与行业事件驱动。",
        beneficiaries=["A 股核心资产", "港股科技", "AI 算力", "黄金与避险资产"],
        risks=["外部流动性收紧", "汇率波动", "主题拥挤", "单日行情误读"],
        importance=86,
        confidence=72,
        sources=["Yahoo Finance chart"],
        bullish_stocks=["沪深300ETF(510300)", "恒生科技ETF(513180)", "中际旭创(300308)", "紫金矿业(601899)"],
        bearish_stocks=["高估值纯题材股", "高外债地产股", "弱现金流小盘股", "高拥挤赛道股"],
    )


def stock_impact_for(item: NewsItem) -> tuple[list[str], list[str]]:
    sentiment = sentiment_score(item.title)
    mapping: dict[str, tuple[list[str], list[str]]] = {
        "AI": (
            ["中际旭创(300308)", "新易盛(300502)", "工业富联(601138)", "寒武纪(688256)", "中芯国际(688981)"],
            ["高估值无订单AI题材股", "算力租赁弱现金流公司", "传统低端服务器代工"],
        ),
        "新能源": (
            ["宁德时代(300750)", "阳光电源(300274)", "亿纬锂能(300014)", "特变电工(600089)", "国电南瑞(600406)"],
            ["低效光伏组件企业", "高成本落后电池产能", "高负债新能源小票"],
        ),
        "港股": (
            ["腾讯控股(00700.HK)", "阿里巴巴-W(09988.HK)", "美团-W(03690.HK)", "小米集团-W(01810.HK)"],
            ["高杠杆地产链港股", "成交低迷券商股", "弱基本面小市值港股"],
        ),
        "A股": (
            ["东方财富(300059)", "中信证券(600030)", "贵州茅台(600519)", "宁德时代(300750)"],
            ["高位题材股", "业绩下修公司", "高质押小盘股"],
        ),
        "宏观": (
            ["紫金矿业(601899)", "山东黄金(600547)", "中国海油(600938)", "高股息红利ETF(515180)"],
            ["航空股", "高外债房企", "高估值成长股"],
        ),
        "公告": (
            ["公告涉及公司", "同产业链龙头", "相关ETF"],
            ["同业竞争弱势公司", "订单被替代公司", "高估值无业绩公司"],
        ),
    }
    bullish, bearish = mapping.get(item.category, stock_impact_from_title(item.title))
    if sentiment < 0:
        return bearish[:4], bullish[:4]
    return bullish[:5], bearish[:4]


def stock_impact_from_title(title: str) -> tuple[list[str], list[str]]:
    lowered = title.lower()
    keyword_map = [
        (
            ["ai", "算力", "芯片", "光模块", "半导体", "服务器"],
            ["中际旭创(300308)", "新易盛(300502)", "工业富联(601138)", "寒武纪(688256)", "中芯国际(688981)"],
            ["高估值无订单AI题材股", "算力租赁弱现金流公司", "传统低端服务器代工"],
        ),
        (
            ["新能源", "储能", "光伏", "电池", "电网", "锂"],
            ["宁德时代(300750)", "阳光电源(300274)", "亿纬锂能(300014)", "国电南瑞(600406)", "特变电工(600089)"],
            ["低效光伏组件企业", "高成本落后电池产能", "高负债新能源小票"],
        ),
        (
            ["港股", "恒生", "南向", "阿里", "腾讯", "美团", "小米"],
            ["腾讯控股(00700.HK)", "阿里巴巴-W(09988.HK)", "美团-W(03690.HK)", "小米集团-W(01810.HK)"],
            ["高杠杆地产链港股", "成交低迷券商股", "弱基本面小市值港股"],
        ),
        (
            ["黄金", "原油", "美元", "人民币", "美债", "宏观"],
            ["紫金矿业(601899)", "山东黄金(600547)", "中国海油(600938)", "高股息红利ETF(515180)"],
            ["航空股", "高外债房企", "高估值成长股"],
        ),
    ]
    for keywords, bullish, bearish in keyword_map:
        if any(keyword in lowered for keyword in keywords):
            return bullish, bearish
    return ["相关行业龙头", "产业链ETF", "高景气细分龙头"], ["同业弱势公司", "高估值题材股", "基本面承压公司"]


def score_news(item: NewsItem) -> int:
    score = 50
    title = item.title
    lowered = title.lower()
    score += sum(5 for word in HIGH_IMPACT_WORDS if word.lower() in lowered)
    category_weight = {
        "宏观": 12,
        "A 股": 11,
        "港股": 10,
        "AI": 10,
        "公告": 9,
        "新能源": 8,
    }.get(item.category, 5)
    score += category_weight
    if item.source not in {"Google News", ""}:
        score += 3
    if item.link:
        score += 2
    if any(word in lowered for word in ["突发", "重磅", "首次", "新高", "大涨", "大跌", "暴跌", "监管", "制裁"]):
        score += 7
    score += min(abs(sentiment_score(title)) * 5, 15)
    score += stable_title_variation(title, 9)
    return max(0, min(score, 95))


def confidence_for(item: NewsItem) -> int:
    confidence = 50
    if item.link:
        confidence += 8
    if item.source not in {"Google News", ""}:
        confidence += source_confidence_bonus(item.source)
    if item.published_at:
        confidence += 6
    if any(word in item.title for word in ["据", "称", "传", "或", "可能"]):
        confidence -= 5
    confidence += stable_title_variation(item.title + item.source, 7)
    return max(35, min(confidence, 88))


def source_confidence_bonus(source: str) -> int:
    trusted_keywords = ["财联社", "证券时报", "上海证券报", "中国证券报", "证券日报", "新华社", "央视", "交易所", "公告", "新浪财经"]
    if any(keyword in source for keyword in trusted_keywords):
        return 14
    return 8


def stable_title_variation(text: str, span: int) -> int:
    if span <= 0:
        return 0
    return sum(ord(ch) for ch in text) % span


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


# Clean institutional research overrides.  These definitions intentionally sit at
# the end of the module so report_builder imports the readable, richer versions.
def build_market_view(signals: list[MarketSignal]) -> str:
    changes = [parse_pct(signal.change) for signal in signals if parse_pct(signal.change) is not None]
    if not changes:
        return "中性。行情数据不足，优先等待主要指数、汇率、利率和商品价格给出更清晰的共振信号。"

    average_change = sum(changes) / len(changes)
    positive_count = sum(1 for value in changes if value > 0)
    negative_count = sum(1 for value in changes if value < 0)
    strong_moves = sum(1 for value in changes if abs(value) >= 1)

    if average_change >= 0.6 and positive_count >= negative_count + 2:
        return "中性偏积极。全球风险资产整体偏强，适合把政策、AI算力、港股科技和顺周期资源放入重点观察池。"
    if average_change <= -0.6 and negative_count >= positive_count + 2:
        return "中性偏谨慎。风险资产承压，短线应降低追高，优先看防守资产、现金流质量和事件验证强度。"
    if strong_moves >= 4:
        return "结构分化。资金没有形成单一方向，今天更重要的是识别哪些板块由真实催化驱动，哪些只是情绪轮动。"
    return "中性。市场没有给出极端方向，适合用事件、资金流和产业验证来做结构筛选。"


def build_core_events(news_items: list[NewsItem], signals: list[MarketSignal]) -> list[CoreEvent]:
    filtered_items = [item for item in news_items if is_core_event_candidate(item)]
    grouped = cluster_news_items(filtered_items)
    events = [event_from_news_group(group) for group in grouped]
    events.sort(key=lambda event: (event.importance, event.confidence), reverse=True)
    return events[:10] or [market_event(signals)]


def cluster_news_items(news_items: list[NewsItem]) -> list[list[NewsItem]]:
    buckets: dict[str, list[NewsItem]] = {}
    for item in sorted(news_items, key=lambda news: news_rank_key_for_event(news), reverse=True):
        key = item.category
        if item.category in {"AI", "半导体"}:
            key = "AI与半导体"
        elif item.category in {"能源电力", "新能源", "资源品"}:
            key = "能源资源"
        elif item.category in {"A股", "港股"}:
            key = item.category
        elif item.category in {"宏观", "日历"}:
            key = "宏观与日历"
        buckets.setdefault(key, []).append(item)

    groups: list[list[NewsItem]] = []
    for items in buckets.values():
        for start in range(0, len(items), 3):
            groups.append(items[start : start + 3])
    return groups


def cluster_news_items(news_items: list[NewsItem]) -> list[list[NewsItem]]:
    buckets: dict[str, list[NewsItem]] = {}
    for item in sorted(news_items, key=lambda news: news_rank_key_for_event(news), reverse=True):
        key = f"{normalized_event_category(item)}:{topic_bucket_for_event(item)}"
        buckets.setdefault(key, []).append(item)

    groups: list[list[NewsItem]] = []
    for items in buckets.values():
        for start in range(0, len(items), 3):
            groups.append(items[start : start + 3])
    return groups


def normalized_event_category(item: NewsItem) -> str:
    category = item.category
    if category in {"AI", "半导体"}:
        return "AI与半导体"
    if category in {"能源电力", "新能源", "资源品"}:
        return "能源资源"
    if category in {"宏观", "日历"}:
        return "宏观与日历"
    return category


def topic_bucket_for_event(item: NewsItem) -> str:
    text = f"{item.title} {item.query_name} {item.category}".lower()
    buckets = [
        ("ai_capex", ["ai", "算力", "gpu", "光模块", "服务器", "pcb", "idc", "token", "云厂商", "资本开支"]),
        ("semiconductor", ["半导体", "芯片", "晶圆", "封装", "存储", "光刻", "eda", "sic", "hbm"]),
        ("liquidity_rates", ["央行", "美联储", "利率", "降息", "加息", "逆回购", "mlf", "cpi", "非农", "pce", "通胀"]),
        ("fx_gold_oil", ["美元", "人民币", "黄金", "白银", "原油", "布伦特", "wti", "opec", "天然气"]),
        ("china_equity_flow", ["a股", "沪深", "科创", "创业板", "成交额", "etf", "北向", "南向", "涨停"]),
        ("hk_tech", ["港股", "恒生", "恒生科技", "腾讯", "阿里", "美团", "小米", "南向"]),
        ("notice_order", ["公告", "订单", "合同", "中标", "回购", "增持", "减持", "业绩", "财报"]),
        ("energy_power", ["电网", "储能", "特高压", "核电", "电力", "光伏", "风电", "锂电", "电池"]),
        ("policy_geo", ["政策", "监管", "关税", "制裁", "出口管制", "地缘", "贸易", "财政"]),
    ]
    for bucket, keywords in buckets:
        if any(keyword in text for keyword in keywords):
            return bucket
    clean = re.sub(r"\W+", "", text)
    return clean[:12] or "misc"


def is_core_event_candidate(item: NewsItem) -> bool:
    text = f"{item.title} {item.query_name} {item.source}".lower()
    low_value_keywords = [
        "世界杯",
        "欧冠",
        "nba",
        "彩票",
        "电影",
        "明星",
        "商家接受比特币",
        "接受比特币支付",
        "employee quits",
        "stock trading app",
        "pinduoduo",
    ]
    if any(keyword.lower() in text for keyword in low_value_keywords):
        return False
    stale_patterns = [r"3月cpi", r"3月份cpi", r"march cpi"]
    if any(re.search(pattern, text) for pattern in stale_patterns):
        return False
    return score_news_v2(item) >= 45


def news_rank_key_for_event(item: NewsItem) -> tuple[int, str]:
    return score_news_v2(item), item.published_at


def event_from_news_group(items: list[NewsItem]) -> CoreEvent:
    lead = items[0]
    category = lead.category
    titles = [clean_news_title_v2(item.title) for item in items]
    title = build_group_title(category, titles)
    summary = build_group_summary(category, items)
    reason = build_group_market_impact(category, items)
    bullish_stocks, bearish_stocks = stock_impact_for_v2(category, " ".join(titles))

    return CoreEvent(
        title=title,
        summary=summary,
        reason=reason,
        beneficiaries=beneficiaries_for_v2(category),
        risks=risks_for_v2(category, " ".join(titles)),
        importance=min(max(score_news_v2(lead) + min(len(items), 3) * 3, 55), 95),
        confidence=confidence_for_v2(items),
        sources=event_sources_v2(items),
        bullish_stocks=bullish_stocks,
        bearish_stocks=bearish_stocks,
    )


def event_from_news(item: NewsItem) -> CoreEvent:
    return event_from_news_group([item])


def build_group_title(category: str, titles: list[str]) -> str:
    lead_fact = titles[0] if titles else category
    if len(lead_fact) > 34:
        lead_fact = lead_fact[:34] + "..."
    return f"{category}：{lead_fact}"


def build_group_summary(category: str, items: list[NewsItem]) -> str:
    facts = [extract_concrete_facts(item.title) for item in items[:3]]
    metrics = extract_metrics_from_text(" ".join(item.title for item in items))
    metric_text = "、".join(metrics[:6]) if metrics else "暂无明确数值，先按可复核事件本身跟踪"
    fact_text = "；".join(deduplicate_texts(facts)[:3])
    implication = category_fact_implication(category)
    return f"可复核事实：{fact_text}。量化线索：{metric_text}。投研解读：{implication}"


def extract_concrete_facts(title: str) -> str:
    clean = clean_news_title_v2(title)
    metrics = extract_metrics_from_text(clean)
    clauses = split_title_clauses_v2(clean)
    if metrics:
        metric_text = "，量化信息包括" + "、".join(metrics[:4])
    else:
        metric_text = ""
    if len(clauses) >= 2:
        return f"{clauses[0]}；同时涉及{'；'.join(clauses[1:3])}{metric_text}"
    return f"{clean}{metric_text}"


def extract_metrics_from_text(text: str) -> list[str]:
    pattern = (
        r"(?:增长|下降|上涨|下跌|大涨|大跌|回落|反弹|超|近|约|达|突破|跌破|升至|降至|净投放|净回笼)?\s*"
        r"\d+(?:\.\d+)?\s*"
        r"(?:%|bp|BP|亿元|亿美元|万亿元|万亿美元|元|美元|人民币|GW|GWh|MW|MWh|万台|万辆|万套|家|个|只|点|倍|年|个月|天)"
    )
    metrics = [metric.strip() for metric in re.findall(pattern, text)]
    extra_patterns = [
        r"\d+(?:\.\d+)?\s*(?:万亿|亿元|亿美元|万股|亿股|万手|亿元人民币|亿港元|亿欧元)",
        r"\d+(?:\.\d+)?\s*(?:GW|GWh|MW|MWh|bp|%)",
        r"\d+(?:\.\d+)?\s*(?:倍|个基点|百分点)",
    ]
    for extra_pattern in extra_patterns:
        metrics.extend(metric.strip() for metric in re.findall(extra_pattern, text))
    return deduplicate_texts([metric for metric in metrics if metric and not is_low_value_metric(metric)])


def is_low_value_metric(metric: str) -> bool:
    normalized = re.sub(r"\s+", "", metric)
    year_match = re.fullmatch(r"(?:20\d{2}|19\d{2})年", normalized)
    return bool(year_match)


def deduplicate_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = re.sub(r"\s+", "", value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(value)
    return result


def category_fact_implication(category: str) -> str:
    return {
        "AI": "重点不是题材热度，而是算力需求、云厂商资本开支、服务器/光模块订单和应用付费能否互相验证；只有订单和业绩跟上，估值扩张才有持续性。",
        "半导体": "先区分周期复苏、国产替代和海外限制三条逻辑；设备材料、先进封装、存储和设计公司的受益顺序不同，交易上要看订单、库存和毛利率拐点。",
        "能源电力": "若线索指向电网投资、储能招标、核电审批或电力市场化，优先看订单确定性和招标价格，避免只买概念不看利润率。",
        "新能源": "核心是价格、库存和海外需求是否改善；如果只是产能扩张，二线高杠杆企业反而可能承压。",
        "港股": "港股机会通常需要美元走弱、南向资金和平台经济预期共振；单条新闻只能作为触发，持续性要看恒生科技成交和龙头回购。",
        "A股": "需要拆成政策、成交额、行业主线、机构资金和权重股贡献，只有多项共振时才适合提高仓位。",
        "宏观": "先判断它影响利率、美元、通胀、商品还是风险偏好，再映射到成长、资源、高股息和港股科技。",
        "公告": "公告只有改变未来收入、利润率、现金流或资本开支路径时才是实质催化，订单金额和履约周期比标题更重要。",
        "日历": "日历事件交易的是预期差；要预先设定高于预期和低于预期时分别影响哪些资产。",
    }.get(category, "判断重点是它是否改变行业景气、资金关注度、盈利预期或估值弹性。")


def build_group_market_impact(category: str, items: list[NewsItem]) -> str:
    title_text = " ".join(item.title for item in items)
    direction = assess_event_direction_v2(title_text)
    facts = deduplicate_texts([extract_concrete_facts(item.title) for item in items[:2]])
    fact_text = "；".join(facts) if facts else clean_news_title_v2(items[0].title)
    metrics = extract_metrics_from_text(title_text)
    metric_text = "、".join(metrics[:5]) if metrics else "暂无直接数值，需用后续价格、订单、成交额或资金流验证"
    watch_text = "、".join(watch_indicators_for_event(category, title_text))
    action_text = action_suggestion_for_event(category, title_text)
    impact = {
        "AI": (
            "如果线索指向资本开支上修、订单兑现或AI应用加速，股票市场通常先交易光模块、服务器、PCB、液冷、IDC和半导体设备。"
            "如果线索指向指数大跌、估值拥挤或订单低于预期，则利空高估值、缺少真实订单的AI题材，资金会转向已有业绩兑现的龙头。"
        ),
        "半导体": (
            "半导体事件对A股映射很强，但必须区分周期复苏和国产替代。设备、材料、封测、存储和先进封装受益逻辑不同；"
            "若海外限制升级，短期可能压制情绪，中期反而强化国产替代订单，但只有公告和业绩验证后才算高置信。"
        ),
        "能源电力": (
            "能源电力的核心机会来自电网投资、储能招标、核电审批和电力市场化。利好通常集中在电网设备、储能系统、变压器、逆变器和运营商；"
            "若招标价格继续下行或产能过剩，低毛利设备商和高负债扩产公司会承压。"
        ),
        "新能源": (
            "新能源需要从总量扩张切换到结构筛选。若价格企稳、库存下降或海外需求改善，电池龙头、储能、逆变器更受益；"
            "若降价和产能过剩继续扩散，光伏组件、二线电池和高杠杆公司仍可能被压估值。"
        ),
        "港股": (
            "港股对美元、美债和南向资金很敏感。若南向持续流入且美元走弱，平台经济、恒生科技和高股息资产更容易修复；"
            "若只是单日反弹而成交没有放大，港股科技的持续性不足，容易回到震荡。"
        ),
        "A股": (
            "A股事件最重要的是看成交额和主线集中度。政策和资金共振时，券商、核心资产、科技成长和主题龙头会受益；"
            "如果只有题材轮动而没有成交配合，高位主题股容易分化，低位防守和红利资产相对占优。"
        ),
        "宏观": (
            "宏观变量通过美元、美债、人民币、商品和风险偏好影响权益估值。利率下行通常利好成长股和港股科技；美元走强、油价或通胀压力上行，"
            "会压制高估值资产，并提高黄金、能源和高股息资产的配置价值。"
        ),
        "公告": (
            "公司公告只有在改变未来收入、利润率、现金流或资本开支路径时才构成实质催化。重大合同、回购增持和业绩上修偏利好；"
            "减持、亏损扩大、订单取消和监管问询偏利空。"
        ),
        "日历": (
            "未来事件日历影响的是预期差。若市场已经充分定价，符合预期未必继续上涨；真正的机会来自数据、财报、政策或发布会结果超出共识。"
        ),
    }.get(category, "市场影响要结合价格反应、成交量和龙头股强弱确认，不能只依据标题判断。")
    return (
        f"方向判断：{direction} 事件内容：{fact_text}。量化跟踪：{metric_text}。"
        f"市场影响分析：{impact} 对股票市场的关键不是消息本身，而是它是否能带来盈利预期、估值折现率或资金流方向的变化。"
        f"观察指标：{watch_text}。投资建议：{action_text}"
    )


def watch_indicators_for_event(category: str, text: str) -> list[str]:
    base = {
        "AI": ["云厂商资本开支指引", "GPU/服务器出货", "光模块订单与价格", "龙头成交额和相对强弱"],
        "半导体": ["设备/材料订单", "晶圆厂资本开支", "存储价格", "国产替代公告"],
        "能源电力": ["电网投资计划", "储能/特高压招标价格", "核电审批节奏", "设备龙头订单"],
        "新能源": ["电池和组件价格", "库存天数", "海外装机/出口", "龙头毛利率"],
        "港股": ["恒生科技成交额", "南向资金净流入", "美元指数", "平台龙头回购"],
        "A股": ["沪深两市成交额", "北向/ETF资金", "主题龙头封单和换手", "政策细则落地"],
        "宏观": ["美元指数", "美债10年收益率", "人民币汇率", "黄金/原油价格"],
        "公告": ["订单金额占收入比例", "毛利率指引", "现金流", "履约周期"],
        "日历": ["市场一致预期", "公布值与预期差", "相关资产开盘反应", "成交量变化"],
    }.get(category, ["成交额", "龙头相对强弱", "资金流向", "后续公告验证"])
    if "黄金" in text:
        return ["现货黄金价格", "实际利率", "美元指数", "央行购金和ETF持仓"]
    if "原油" in text or "油" in text:
        return ["WTI/布伦特油价", "库存数据", "OPEC+供给", "航运和地缘风险"]
    if "央行" in text or "逆回购" in text:
        return ["逆回购规模", "DR007", "国债收益率", "A股成交额"]
    return base


def action_suggestion_for_event(category: str, text: str) -> str:
    if any(word in text for word in NEGATIVE_WORDS):
        return "先降低追高意愿，把相关股票清单作为风险排查池；只有龙头放量企稳且基本面未恶化时再考虑低吸。"
    if any(word in text for word in POSITIVE_WORDS):
        return "可先做研究池和小仓位观察，优先选择有订单、业绩或资金流验证的龙头，避免追逐没有基本面支撑的补涨股。"
    return {
        "宏观": "不直接据此买入，先观察利率、美元和商品价格是否同步确认，再决定成长、资源或高股息的配置倾斜。",
        "日历": "提前列好超预期和低于预期两套交易预案，事件落地前避免过度集中仓位。",
        "公告": "回看公告原文和财务口径，只有订单金额、毛利率或现金流能改变盈利预测时才提高关注。",
    }.get(category, "作为跟踪线索处理，等待价格、成交额和后续权威信息形成三重确认。")


def facts_by_focus_category(news_items: list[NewsItem]) -> list[str]:
    focus_categories = {"AI", "半导体", "能源电力", "新能源", "创新药", "军工", "资源品"}
    ranked = sorted(
        [item for item in news_items if item.category in focus_categories],
        key=lambda item: score_news_v2(item),
        reverse=True,
    )
    return deduplicate_texts([extract_concrete_facts(item.title) for item in ranked[:8]])


def policy_and_notice_facts(news_items: list[NewsItem]) -> list[str]:
    ranked = sorted(
        [
            item
            for item in news_items
            if item.category in {"宏观", "公告", "A股", "日历"}
            or any(keyword in item.title for keyword in ["政策", "央行", "财政", "证监会", "交易所", "公告", "回购", "增持", "减持", "中标"])
        ],
        key=lambda item: score_news_v2(item),
        reverse=True,
    )
    return deduplicate_texts([extract_concrete_facts(item.title) for item in ranked[:8]])


def assess_event_direction_v2(text: str) -> str:
    lowered = text.lower()
    positive_hits = ["上涨", "大涨", "增长", "回流", "订单", "扩产", "突破", "获批", "中标", "上修", "回购", "增持", "创新高"]
    negative_hits = ["下跌", "大跌", "回调", "承压", "减持", "亏损", "下修", "制裁", "关税", "降价", "监管", "问询"]
    has_positive = any(word.lower() in lowered for word in positive_hits)
    has_negative = any(word.lower() in lowered for word in negative_hits)
    if has_positive and has_negative:
        return "结构分化，说明同一主题内部同时存在受益链条和承压链条，需要按环节拆开。"
    if has_positive:
        return "偏利好，但需要继续用订单、资金流、价格反应或政策细则验证。"
    if has_negative:
        return "偏利空或风险释放，短线先看相关板块是否继续放量承压。"
    return "偏中性，更适合作为观察线索，不宜直接当成交易信号。"


def event_sources_v2(items: list[NewsItem]) -> list[str]:
    sources: list[str] = []
    for item in items[:3]:
        parts = [f"消息来源：{item.source or '公开来源'}"]
        if item.published_at:
            parts.append(f"发布时间：{item.published_at}")
        parts.append(f"检索主题：{item.query_name}")
        parts.append(f"原始标题：{item.title}")
        sources.append("；".join(parts))
        if item.link:
            sources.append(item.link)
    return sources


def score_news_v2(item: NewsItem) -> int:
    text = item.title.lower()
    score = 48
    score += {
        "宏观": 14,
        "A股": 12,
        "港股": 11,
        "AI": 12,
        "半导体": 12,
        "能源电力": 10,
        "新能源": 9,
        "资源品": 9,
        "公告": 10,
        "日历": 7,
    }.get(item.category, 6)
    score += {"宏观": 5, "政策": 5, "公告": 5, "资金": 4, "海外": 4, "产业": 3}.get(getattr(item, "tier", ""), 1)
    high_words = ["央行", "美联储", "政策", "业绩", "订单", "合同", "资本开支", "制裁", "关税", "并购", "回购", "增持", "减持", "大涨", "大跌"]
    score += sum(4 for word in high_words if word.lower() in text)
    score += stable_title_variation(item.title + item.source, 8)
    return max(35, min(score, 95))


def confidence_for_v2(items: list[NewsItem]) -> int:
    lead = items[0]
    confidence = 52
    confidence += min(len(items), 3) * 5
    if lead.link:
        confidence += 6
    if lead.source and lead.source != "Google News":
        confidence += source_confidence_bonus_v2(lead.source)
    if lead.published_at:
        confidence += 5
    if any(word in lead.title for word in ["据称", "传", "或", "可能"]):
        confidence -= 6
    confidence += stable_title_variation("".join(item.title for item in items), 6)
    return max(40, min(confidence, 88))


def source_confidence_bonus_v2(source: str) -> int:
    trusted_keywords = ["财联社", "证券时报", "上海证券报", "中国证券报", "证券日报", "新华社", "央视", "交易所", "公告", "新浪财经", "Reuters", "CNBC", "Bloomberg"]
    if any(keyword.lower() in source.lower() for keyword in trusted_keywords):
        return 13
    return 7


def stock_impact_for_v2(category: str, text: str) -> tuple[list[str], list[str]]:
    mapping: dict[str, tuple[list[str], list[str]]] = {
        "AI": (
            ["中际旭创(300308)", "新易盛(300502)", "工业富联(601138)", "寒武纪(688256)", "英伟达(NVDA)"],
            ["高估值无订单AI题材股", "算力租赁弱现金流公司", "低端服务器代工企业"],
        ),
        "半导体": (
            ["中芯国际(688981/00981.HK)", "北方华创(002371)", "中微公司(688012)", "华虹半导体(01347.HK)", "兆易创新(603986)"],
            ["依赖海外先进制程的公司", "高估值低盈利芯片设计股", "库存压力较大的消费芯片公司"],
        ),
        "能源电力": (
            ["国电南瑞(600406)", "特变电工(600089)", "许继电气(000400)", "阳光电源(300274)", "宁德时代(300750)"],
            ["低毛利储能集成商", "高负债扩产设备商", "低效光伏组件企业"],
        ),
        "新能源": (
            ["宁德时代(300750)", "比亚迪(002594/01211.HK)", "亿纬锂能(300014)", "阳光电源(300274)", "固态电池主题ETF"],
            ["低效光伏组件企业", "高成本落后电池产能", "价格战压力较大的整车股"],
        ),
        "港股": (
            ["腾讯控股(00700.HK)", "阿里巴巴-W(09988.HK)", "美团-W(03690.HK)", "小米集团-W(01810.HK)", "恒生科技ETF(513180)"],
            ["高杠杆地产链港股", "成交低迷券商股", "弱基本面小市值港股"],
        ),
        "A股": (
            ["东方财富(300059)", "中信证券(600030)", "沪深300ETF(510300)", "科创50ETF(588000)", "创业板ETF(159915)"],
            ["高位题材股", "业绩下修公司", "高质押小盘股"],
        ),
        "宏观": (
            ["紫金矿业(601899/02899.HK)", "山东黄金(600547)", "中国海油(600938/00883.HK)", "红利ETF(515180)", "黄金ETF(518880)"],
            ["航空股", "高外债房企", "高估值成长股", "进口成本敏感公司"],
        ),
        "公告": (
            ["公告涉及公司", "同产业链龙头", "相关行业ETF"],
            ["订单被替代公司", "同业竞争弱势公司", "减持或业绩下修公司"],
        ),
        "日历": (
            ["宽基ETF", "高股息ETF", "事件相关行业龙头"],
            ["财报高预期高估值公司", "数据敏感高波动主题股", "拥挤交易方向"],
        ),
    }
    bullish, bearish = mapping.get(category, (["相关行业龙头", "产业链ETF", "高景气细分龙头"], ["同业弱势公司", "高估值题材股", "基本面承压公司"]))
    if any(word in text for word in ["下跌", "大跌", "减持", "亏损", "下修", "制裁", "监管", "降价"]):
        defensive_bullish = {
            "AI": ["已有订单和利润兑现的AI龙头", "现金流稳健的服务器/光模块龙头", "半导体设备国产替代龙头", "科技宽基ETF"],
            "半导体": ["国产替代设备材料龙头", "低库存存储链龙头", "半导体ETF防守仓", "现金流稳定芯片龙头"],
            "能源电力": ["电网设备龙头", "高股息电力运营商", "订单确定性较强的储能龙头", "红利ETF"],
            "新能源": ["成本领先电池龙头", "海外需求占比较高龙头", "电网储能龙头", "红利ETF"],
            "港股": ["高股息央国企港股", "现金流稳健平台龙头", "港股红利ETF", "南向重仓低估值龙头"],
            "A股": ["红利ETF", "高股息央国企", "低估值核心资产", "黄金ETF"],
            "宏观": ["黄金ETF", "高股息红利ETF", "能源龙头", "现金流稳定央国企"],
            "公告": ["同业替代受益公司", "订单外溢产业链龙头", "高股息防守资产", "相关行业ETF"],
            "日历": ["低波动红利资产", "黄金ETF", "宽基ETF防守仓", "现金管理工具"],
        }
        return defensive_bullish.get(category, ["防守型高股息资产", "相关替代受益公司", "宽基ETF"]), bearish[:4]
    return bullish[:5], bearish[:4]


def beneficiaries_for_v2(category: str) -> list[str]:
    return {
        "AI": ["光模块", "服务器", "AI芯片", "IDC", "云计算"],
        "半导体": ["国产设备", "材料", "先进封装", "晶圆制造", "存储"],
        "能源电力": ["电网设备", "储能", "特高压", "核电", "电力运营"],
        "新能源": ["电池龙头", "储能", "逆变器", "整车龙头"],
        "港股": ["港股科技", "互联网平台", "高股息", "南向资金重仓"],
        "A股": ["券商", "核心资产", "科技成长", "政策受益行业"],
        "宏观": ["黄金", "能源", "红利资产", "出口链"],
        "公告": ["公告涉及公司", "相关产业链", "同业龙头"],
        "日历": ["预期差交易", "财报超预期公司", "政策受益行业"],
    }.get(category, ["相关行业", "龙头公司"])


def risks_for_v2(category: str, text: str) -> list[str]:
    base = ["消息反转", "市场已充分定价", "来源细节需复核"]
    category_risks = {
        "AI": ["云厂商资本开支低于预期", "订单无法兑现到利润", "估值拥挤"],
        "半导体": ["海外限制升级", "库存周期反复", "国产替代节奏低于预期"],
        "能源电力": ["招标价格下行", "项目投产延迟", "设备毛利率承压"],
        "新能源": ["产能过剩", "价格战", "海外政策扰动"],
        "港股": ["美元走强", "南向资金流入放缓", "平台业绩指引转弱"],
        "A股": ["成交额不足", "政策预期落空", "主题轮动过快"],
        "宏观": ["利率反向波动", "汇率压力", "地缘风险扩散"],
        "公告": ["公告细节不及预期", "履约周期拉长", "利润率低于市场预期"],
        "日历": ["结果不及预期", "预期兑现后回落", "波动放大"],
    }.get(category, [])
    return category_risks[:3] + base[:1]


def build_investment_ideas(news_items: list[NewsItem], signals: list[MarketSignal]) -> list[InvestmentIdea]:
    categories = Counter(item.category for item in news_items)
    ideas: list[InvestmentIdea] = []

    if categories["AI"] or categories["半导体"] or has_signal_v2(signals, "纳斯达克", 0):
        ideas.append(
            InvestmentIdea(
                title="AI算力与半导体链条：从题材热度切到订单验证",
                action="可分批关注",
                horizon="1-3个月",
                success_probability="约60%-70%",
                confidence=70,
                risk_level="中",
                logic="AI主线能否继续扩散，关键不在标题热度，而在云厂商资本开支、服务器出货、光模块订单、国产算力政策和半导体设备订单能否互相验证。",
                invalidation="海外AI龙头回调并伴随资本开支预期下修，或A/H相关公司公告与订单验证低于预期。",
                watch_indicators=["纳斯达克100", "英伟达/博通走势", "光模块订单", "服务器出货", "科创50"],
                catalysts=["云厂商资本开支上修", "国产算力政策", "光模块订单", "半导体设备国产替代"],
                representative_assets=["中际旭创", "工业富联", "寒武纪", "中芯国际", "半导体ETF"],
                pricing_status="热门环节已有较多定价，后续要看订单和业绩能否兑现。",
                position_size="轻仓到标准仓",
            )
        )

    if categories["能源电力"] or categories["新能源"]:
        ideas.append(
            InvestmentIdea(
                title="能源电力：优先电网、储能和盈利质量较稳的环节",
                action="等待确认",
                horizon="3-12个月",
                success_probability="约55%-65%",
                confidence=64,
                risk_level="中",
                logic="新能源从总量扩张进入结构分化，电网投资、储能招标、核电审批和电力市场化比单纯光伏组件扩产更值得跟踪。",
                invalidation="招标价格继续下行、设备毛利率承压，或项目投运进度明显低于预期。",
                watch_indicators=["储能招标", "电网投资", "组件价格", "锂价", "龙头毛利率"],
                catalysts=["电网投资加速", "储能项目落地", "核电审批", "海外需求改善"],
                representative_assets=["国电南瑞", "特变电工", "阳光电源", "宁德时代", "电力设备ETF"],
                pricing_status="电网和储能优于产能过剩环节，仍需等待价格和订单验证。",
                position_size="轻仓观察",
            )
        )

    if categories["港股"] or has_signal_v2(signals, "恒生", 0):
        ideas.append(
            InvestmentIdea(
                title="港股科技：用美元、南向和成交额确认修复持续性",
                action="持有观察",
                horizon="1个月",
                success_probability="约55%-65%",
                confidence=62,
                risk_level="中",
                logic="港股科技的弹性来自美元流动性、南向资金和平台经济预期共振；若只有单日上涨而缺少成交和资金流确认，持续性会打折。",
                invalidation="美元重新走强、恒生科技放量下破，或平台龙头业绩指引转弱。",
                watch_indicators=["恒生科技", "南向资金", "美元/离岸人民币", "平台龙头成交额"],
                catalysts=["美元走弱", "南向资金回流", "平台经济业绩修复", "回购增持"],
                representative_assets=["腾讯控股", "阿里巴巴-W", "美团-W", "小米集团-W", "恒生科技ETF"],
                pricing_status="修复交易已经启动时更要看资金持续性，而不是只看估值低。",
                position_size="轻仓到标准仓",
            )
        )

    ideas.append(
        InvestmentIdea(
            title="宏观对冲：保留黄金、红利和能源作为组合稳定器",
            action="持有观察",
            horizon="1-6个月",
            success_probability="约55%-60%",
            confidence=60,
            risk_level="中低",
            logic="当美元、利率、地缘和商品价格存在不确定性时，黄金、能源和高股息资产可以对冲成长股波动，也能在风险偏好下降时提供组合缓冲。",
            invalidation="实际利率快速上行且黄金跌破关键支撑，或红利资产拥挤导致估值明显透支。",
            watch_indicators=["美债10年收益率", "美元/离岸人民币", "黄金", "WTI原油", "VIX"],
            catalysts=["降息预期升温", "地缘风险", "油价上行", "避险资金流入"],
            representative_assets=["黄金ETF", "紫金矿业", "中国海油", "红利ETF", "高股息央国企"],
            pricing_status="属于组合底仓和对冲仓，不适合按短线题材方式追高。",
            position_size="轻仓到标准仓",
        )
    )

    return ideas[:5]


def build_analysis_sections(
    market_view: str,
    signals: list[MarketSignal],
    news_items: list[NewsItem],
    ideas: list[InvestmentIdea],
) -> list[AnalysisSection]:
    useful_news_items = [item for item in news_items if is_core_event_candidate(item)]
    source_items = useful_news_items or news_items
    categories = Counter(item.category for item in source_items)
    strongest = strongest_signals(signals)
    top_items = sorted(source_items, key=lambda item: score_news_v2(item), reverse=True)[:8]
    top_facts = deduplicate_texts([extract_concrete_facts(item.title) for item in top_items])[:5]
    top_metrics = extract_metrics_from_text(" ".join(item.title for item in top_items))[:8]
    industry_facts = facts_by_focus_category(source_items)
    policy_facts = policy_and_notice_facts(source_items)
    metric_text = "、".join(top_metrics) if top_metrics else "新闻标题层面缺少明确数值，需回看原文、公告和行情确认"

    return [
        AnalysisSection(
            title="今日十大核心事件筛选逻辑",
            view=(
                f"本次筛选不是按媒体标题排序，而是把 {sum(categories.values())} 条线索拆成宏观、资金、产业、公告和日历，再按可验证性、量化信息和资产映射排序。"
                f"当前市场判断：{market_view} 今日靠前的可复核事实包括：{'；'.join(top_facts[:3]) if top_facts else '暂无高置信具体事实'}。"
                f"可直接跟踪的量化线索：{metric_text}。"
            ),
            opportunities=[
                "优先研究同时具备具体事件、量化指标、价格反应和公司/产业链验证的主题。",
                "同一主题内区分真正受益者与情绪扩散对象，只有订单、价格、资金流或政策细则能继续验证时才提高仓位。",
            ],
            risks=["单一标题可能遗漏关键上下文。", "免费聚合源可能延迟，需回看原文和公告。"],
            watch=top_facts[:4] or ["政策细则", "成交额", "龙头股强弱", "资金流向"],
        ),
        AnalysisSection(
            title="全球资本市场复盘",
            view=(
                "全球市场复盘要把指数涨跌和消息线索合并看：若美股科技、港股科技和A股成长同步走强，资金通常在交易AI盈利和流动性改善；"
                "若黄金、美元或能源强于权益，则说明避险、通胀或地缘变量仍在定价。"
                f"今日市场信号中波动较大的指标是：{', '.join(strongest[:5]) if strongest else '暂无足够行情信号'}。"
            ),
            opportunities=[
                "若强势指标集中在美股科技和恒生科技，可优先看AI算力、半导体和互联网平台的跨市场映射。",
                "若强势指标集中在资源、能源或欧洲日本顺周期，则把有价格弹性和出口订单的公司放入观察池。",
            ],
            risks=["单日指数涨跌可能只是情绪修复。", "美元和美债反向波动会快速压制成长股估值。"],
            watch=strongest[:5] or ["标普500", "纳斯达克100", "恒生科技", "沪深300", "日经225"],
        ),
        AnalysisSection(
            title="今日最重要产业趋势",
            view=(
                f"今日产业线索分布：AI {categories.get('AI', 0)} 条、半导体 {categories.get('半导体', 0)} 条、能源电力 {categories.get('能源电力', 0)} 条、新能源 {categories.get('新能源', 0)} 条。"
                f"需要优先研究的不是行业名称，而是具体催化：{'; '.join(industry_facts[:4]) if industry_facts else '今日产业新闻缺少明确高置信催化'}。"
            ),
            opportunities=[idea.title for idea in ideas[:3]] or ["等待更明确的产业催化。"],
            risks=["只看概念容易忽略价格、库存和毛利率。", "产业链中上游和下游的受益方向可能完全相反。"],
            watch=["订单金额", "招标价格", "库存去化", "龙头毛利率", "资本开支"],
        ),
        AnalysisSection(
            title="全球资金流向",
            view=(
                "资金流向必须用美元、人民币、黄金、原油、美债、纳斯达克、恒生科技、沪深300和创业板交叉验证。"
                "如果权益和商品同涨，可能是增长预期；如果黄金和美元同强，往往是风险对冲。"
                f"当前可观察指标：{', '.join(strongest[:6]) if strongest else '等待更多市场数据'}。"
            ),
            opportunities=[
                "美元走弱且美债收益率下行时，港股科技、A股成长和黄金更容易同时受益。",
                "商品走强且股市不弱时，资源品和顺周期资产的胜率提高。",
            ],
            risks=["美元突然走强会压缩新兴市场和高估值成长股估值。", "VIX抬升时主题交易容易快速降温。"],
            watch=["美元/离岸人民币", "美债10年收益率", "黄金", "WTI原油", "VIX"],
        ),
        AnalysisSection(
            title="政策与公告解读",
            view=(
                "政策和公告要看真实目的：稳增长、促消费、扩投资、科技自主、能源安全或资本市场活跃。"
                f"今日政策/公告可复核线索：{'; '.join(policy_facts[:4]) if policy_facts else '暂无高置信政策/公告线索'}。"
                "不同目的对应完全不同的受益公司，不能只按标题判断利好。"
            ),
            opportunities=[
                "稳增长偏利好基建、电网、央国企和高股息。",
                "科技自主偏利好半导体设备材料、国产算力和工业软件。",
            ],
            risks=["政策预期如果没有细则和资金配套，容易兑现后回落。", "公司公告若没有利润率和现金流改善，利好强度有限。"],
            watch=["证监会/央行/财政部文件", "交易所公告", "重大合同", "回购增持", "业绩预告"],
        ),
        AnalysisSection(
            title="未来7天重要事件",
            view="未来一周的经济数据、央行表态、财报、政策会议和产业大会，主要通过预期差影响市场，而不是通过事件本身机械利好利空。",
            opportunities=[
                "数据低于预期但带来降息预期时，成长和黄金可能受益。",
                "财报超预期且指引上修时，龙头公司比概念股更有持续性。",
            ],
            risks=["预期过满时，利好兑现也可能下跌。", "重要会议前后波动会放大，仓位不宜过度集中。"],
            watch=["经济数据", "央行会议", "美股科技财报", "行业大会", "新品发布"],
        ),
        AnalysisSection(
            title="投资机会与行动清单",
            view="从基金经理视角看，当前更适合把机会分成1个月事件交易、3个月产业验证和1年主线配置三层，而不是把所有事件都变成买入建议。",
            opportunities=[
                "1个月：关注有明确催化和价格确认的AI、港股科技、政策受益方向。",
                "3个月：关注订单和业绩能持续验证的半导体、储能、电网。",
                "1年：持续跟踪AI算力国产化、能源安全和高股息资产重估。",
            ],
            risks=["没有失效条件的机会不应提高仓位。", "报告中的股票清单是研究池，不是直接买卖指令。"],
            watch=["今天最强主线", "最值得研究的一家公司", "三大风险", "未来一年主线"],
        ),
    ]


def build_action_checklist(ideas: list[InvestmentIdea], events: list[CoreEvent]) -> list[str]:
    checklist = [
        "先判断今天资金交易的是利率、美元、政策、AI盈利，还是单纯情绪修复。",
        "把最高重要程度的3条核心事件回看原文，确认是否有量化信息、公告细节或权威来源。",
        "每个股票清单只作为研究池，先看订单、业绩、成交额和龙头相对强弱是否验证。",
    ]
    for idea in ideas[:3]:
        checklist.append(f"{idea.action}：{idea.title}；重点观察{'、'.join(idea.watch_indicators[:3])}。")
    if events:
        checklist.append(f"今天最需要复核的事件：{events[0].title}。")
    return checklist


def build_risk_warnings(signals: list[MarketSignal], news_items: list[NewsItem]) -> list[str]:
    warnings = [
        "免费行情和RSS聚合源可能延迟或缺失，关键结论需要回看原始来源、交易所公告和公司披露。",
        "AI或规则生成观点不能替代独立判断，所有建议都必须结合仓位、止损和失效条件。",
        "股票清单代表受益/受损方向，不等同于买卖指令。",
    ]
    if any((parse_pct(signal.change) or 0) <= -1.5 for signal in signals):
        warnings.append("部分资产单日跌幅较大，说明风险偏好可能低于新闻标题呈现的乐观程度。")
    if sum(1 for item in news_items if "减持" in item.title or "下跌" in item.title or "风险" in item.title) >= 3:
        warnings.append("负面线索密度上升，需警惕政策、盈利或外部流动性风险扩散。")
    return warnings


def has_signal_v2(signals: list[MarketSignal], name_part: str, threshold: float) -> bool:
    for signal in signals:
        value = parse_pct(signal.change)
        if name_part in signal.name and value is not None and value >= threshold:
            return True
    return False


def clean_news_title_v2(title: str) -> str:
    title = re.sub(r"\s+-\s+[^-]{2,40}$", "", title.strip())
    return re.sub(r"\s+", " ", title)


def split_title_clauses_v2(title: str) -> list[str]:
    parts = re.split(r"[，,；;。！!：:|]", title)
    clauses = [part.strip(" -_") for part in parts if len(part.strip(" -_")) >= 4]
    return clauses or [title]


def market_event(signals: list[MarketSignal]) -> CoreEvent:
    changes = [(signal.name, parse_pct(signal.change)) for signal in signals]
    known_changes = [(name, value) for name, value in changes if value is not None]
    known_changes.sort(key=lambda pair: abs(pair[1]), reverse=True)
    leader = known_changes[0][0] if known_changes else "主要市场"
    gainers = [f"{name}{value:+.2f}%" for name, value in known_changes if value > 0][:4]
    losers = [f"{name}{value:+.2f}%" for name, value in known_changes if value < 0][:4]
    gainer_text = "、".join(gainers) if gainers else "暂无明显上涨领先指标"
    loser_text = "、".join(losers) if losers else "暂无明显下跌领先指标"

    return CoreEvent(
        title="全球风险偏好与 A/H 股交易环境更新",
        summary=(
            f"跨市场行情显示，{leader}波动居前；上涨领先指标包括{gainer_text}，下跌或承压指标包括{loser_text}。"
            "这不是单纯的行情记录，而是用来判断今天资金更偏向成长、顺周期、防守还是避险。"
        ),
        reason=(
            "市场影响分析：如果大陆、港股、美股科技和商品风险资产同步走强，说明资金风险偏好改善，"
            "A股更容易交易科技成长、券商和核心资产，港股更容易交易恒生科技和平台经济，美股则继续围绕AI盈利和利率预期定价。"
            "如果VIX、美元、美债收益率或黄金走强，同时成长指数回落，说明市场在交易避险或折现率上行，"
            "A/H高估值主题需要降低追高，资金可能转向高股息、黄金、能源和现金流稳定资产。后续验证重点是成交额是否放大、"
            "龙头股是否强于指数、人民币汇率是否稳定，以及海外科技股是否继续支撑A/H科技映射。"
        ),
        beneficiaries=["A股核心资产", "港股科技", "AI算力", "黄金与高股息资产"],
        risks=["外部流动性收紧", "汇率波动", "主题拥挤", "单日行情误读"],
        importance=86,
        confidence=74,
        sources=["公开行情数据：Yahoo Finance / 新浪行情"],
        bullish_stocks=["沪深300ETF(510300)", "恒生科技ETF(513180)", "中际旭创(300308)", "紫金矿业(601899)"],
        bearish_stocks=["高估值纯题材股", "高外债地产股", "弱现金流小盘股", "高拥挤赛道股"],
    )
