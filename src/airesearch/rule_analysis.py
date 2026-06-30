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
