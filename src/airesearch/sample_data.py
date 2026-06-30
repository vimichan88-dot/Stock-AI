from __future__ import annotations

from datetime import datetime

from .models import CoreEvent, InvestmentIdea, MarketSignal, Report


def build_sample_report(
    report_type: str,
    date_text: str,
    market_signals: list[MarketSignal] | None = None,
    source_note: str | None = None,
) -> Report:
    labels = {
        "morning": "盘前投研日报",
        "noon": "午盘快报",
        "close": "收盘复盘与明日展望",
    }
    title = labels.get(report_type, "AI 投研报告")

    return Report(
        report_type=report_type,
        date=date_text,
        generated_at=datetime.now(),
        title=f"{date_text} {title}",
        executive_summary=(
            "这是 MVP 骨架生成的示例报告。正式版本会接入行情、公告、新闻、宏观数据和 AI "
            "分析链路，输出事实、预期、判断分离的个人投研报告。"
        ),
        market_view="中性偏积极。A 股和港股以结构性机会为主，美股与全球流动性作为风险偏好锚。",
        market_signals=market_signals or [
            MarketSignal("A 股", "待接入", "待接入", "关注政策预期、成交量和主线持续性。"),
            MarketSignal("港股", "待接入", "待接入", "关注南向资金、美元和美债收益率变化。"),
            MarketSignal("美股科技", "待接入", "待接入", "关注 AI 资本开支、半导体景气和估值拥挤度。"),
            MarketSignal("黄金/美元", "待接入", "待接入", "作为全球风险偏好和流动性辅助指标。"),
        ],
        core_events=[
            CoreEvent(
                title="AI 算力链仍是重点观察主线",
                summary="正式版会从新闻、公告、行情和资金流中判断算力链是否继续强化。",
                reason="AI 资本开支、国产替代、云厂商订单和光模块需求共同决定中期景气。",
                beneficiaries=["服务器", "光模块", "液冷", "PCB", "IDC"],
                risks=["估值拥挤", "资本开支低于预期", "美债收益率上行压制成长股"],
                importance=88,
                confidence=70,
                sources=["MVP 示例"],
                bullish_stocks=["中际旭创(300308)", "新易盛(300502)", "工业富联(601138)", "寒武纪(688256)"],
                bearish_stocks=["高估值无订单AI题材股", "算力租赁弱现金流公司", "传统低端服务器代工"],
            ),
            CoreEvent(
                title="新能源进入分化阶段",
                summary="正式版会区分光伏、储能、电网、锂电和新能源车的景气位置。",
                reason="产能出清、政策催化和价格企稳的速度不同，不能笼统看多或看空。",
                beneficiaries=["储能", "电网设备", "优质电池龙头"],
                risks=["价格战", "海外政策变化", "库存去化慢于预期"],
                importance=80,
                confidence=65,
                sources=["MVP 示例"],
                bullish_stocks=["宁德时代(300750)", "阳光电源(300274)", "国电南瑞(600406)", "特变电工(600089)"],
                bearish_stocks=["低效光伏组件企业", "高成本落后电池产能", "高负债新能源小票"],
            ),
        ],
        investment_ideas=[
            InvestmentIdea(
                title="分批关注 AI 算力链龙头与 ETF",
                action="可分批关注",
                horizon="1-3 个月",
                success_probability="约 60%-70%",
                confidence=68,
                risk_level="中",
                logic="产业趋势较强，但短期受估值、拥挤度和海外利率影响。",
                invalidation="云厂商资本开支预期下修，核心公司业绩低于预期，或美债收益率快速上行。",
                watch_indicators=["AI capex", "半导体订单", "港股科技成交额", "美债收益率"],
                catalysts=["云厂商资本开支", "光模块订单", "国产算力政策"],
                representative_assets=["AI 算力链", "半导体 ETF", "光模块龙头"],
                pricing_status="部分被市场定价，等待业绩验证。",
                position_size="轻仓到标准仓",
            ),
            InvestmentIdea(
                title="等待新能源主链出清确认，优先观察储能和电网",
                action="等待确认",
                horizon="3-12 个月",
                success_probability="约 55%-65%",
                confidence=62,
                risk_level="中",
                logic="新能源不是没有机会，而是需要从产能过剩环节切换到盈利更确定环节。",
                invalidation="行业价格继续快速下行，龙头盈利继续下修。",
                watch_indicators=["组件价格", "锂价", "储能招标", "电网投资"],
                catalysts=["储能招标", "电网投资", "政策支持"],
                representative_assets=["储能", "电网设备", "优质电池龙头"],
                pricing_status="尚未充分确认，需等待价格和盈利信号。",
                position_size="轻仓观察",
            ),
        ],
        action_checklist=[
            "每天先看市场真正交易的是流动性、政策还是产业景气。",
            "重点观察 AI 算力链是否有业绩和订单验证。",
            "新能源方向先做结构区分，避免把全产业链当作同一个交易。",
        ],
        risk_warnings=[
            "免费数据源可能延迟或失败，正式报告必须标注来源可信度。",
            "AI 生成观点不能替代独立判断，所有建议都需要失效条件。",
            "短期强势主题可能已被充分定价，追高需谨慎。",
        ],
        source_note=source_note
        or "当前为 MVP 示例数据。接入真实数据源后，每条重要事件将附来源、时间和可信度。",
    )
