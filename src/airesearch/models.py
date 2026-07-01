from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MarketSignal:
    name: str
    value: str
    change: str
    interpretation: str


@dataclass
class CoreEvent:
    title: str
    summary: str
    reason: str
    beneficiaries: list[str]
    risks: list[str]
    importance: int
    confidence: int
    sources: list[str] = field(default_factory=list)
    bullish_stocks: list[str] = field(default_factory=list)
    bearish_stocks: list[str] = field(default_factory=list)


@dataclass
class InvestmentIdea:
    title: str
    action: str
    horizon: str
    success_probability: str
    confidence: int
    risk_level: str
    logic: str
    invalidation: str
    watch_indicators: list[str]
    catalysts: list[str] = field(default_factory=list)
    representative_assets: list[str] = field(default_factory=list)
    pricing_status: str = ""
    position_size: str = ""


@dataclass
class AnalysisSection:
    title: str
    view: str
    opportunities: list[str]
    risks: list[str]
    watch: list[str]


@dataclass
class Report:
    report_type: str
    date: str
    generated_at: datetime
    title: str
    executive_summary: str
    market_view: str
    market_signals: list[MarketSignal]
    core_events: list[CoreEvent]
    investment_ideas: list[InvestmentIdea]
    action_checklist: list[str]
    risk_warnings: list[str]
    source_note: str
    analysis_sections: list[AnalysisSection] = field(default_factory=list)
    planned_time: str = ""
    schedule_status: str = ""
    trigger: str = ""
