from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.airesearch.models import MarketSignal
from src.airesearch.ai_analysis import (
    AIOutputError,
    configured_ai_model,
    configured_ai_provider,
    extract_chat_completion_text,
    extract_output_text,
    merge_ai_payload,
    parse_json_object,
    parse_json_object_with_deepseek_repair,
)
from src.airesearch.config import Settings
from src.airesearch.main import append_source_note, current_date_text
from src.airesearch.market_data import INSTRUMENTS, validate_signal_value
from src.airesearch.news_data import NewsItem
from src.airesearch.quality import append_quality_note, validate_report
from src.airesearch.report_builder import build_report
from src.airesearch.report_writer import report_to_markdown
from src.airesearch.rule_analysis import extract_metrics_from_text, is_core_event_candidate
from src.airesearch.site_builder import build_site


class ReportPipelineTests(unittest.TestCase):
    def test_build_report_uses_market_and_news_inputs(self) -> None:
        signals = [
            MarketSignal("上证指数", "4073.90", "+1.16%", "观察 A 股整体风险偏好。"),
            MarketSignal("恒生指数", "23026.68", "+1.57%", "观察港股风险偏好。"),
        ]
        news = [
            NewsItem(
                title="AI 光模块订单继续增长",
                link="https://example.com/ai",
                source="测试源",
                published_at="2026-06-29T09:00:00+08:00",
                category="AI",
                query_name="AI 算力",
            ),
            NewsItem(
                title="储能项目招标规模提升",
                link="https://example.com/storage",
                source="测试源",
                published_at="2026-06-29T09:10:00+08:00",
                category="新能源",
                query_name="新能源",
            ),
            NewsItem(
                title="港股科技南向资金回流",
                link="https://example.com/hk",
                source="测试源",
                published_at="2026-06-29T09:20:00+08:00",
                category="港股",
                query_name="港股科技",
            ),
        ]

        report = build_report(
            "morning",
            "2026-06-29",
            market_signals=signals,
            market_source_note="行情测试来源",
            news_items=news,
            news_source_note="新闻测试来源",
        )

        self.assertEqual(report.market_signals, signals)
        self.assertIn("本次共纳入 3 条新闻线索", report.executive_summary)
        self.assertTrue(any("AI" in event.title for event in report.core_events))
        self.assertTrue(report.investment_ideas[0].catalysts)
        self.assertIn("行情测试来源", report.source_note)
        self.assertIn("新闻测试来源", report.source_note)

    def test_rule_summary_keeps_source_metadata_out_of_latest_update(self) -> None:
        report = build_report(
            "morning",
            "2026-07-01",
            news_items=[
                NewsItem(
                    title="央行开展1000亿元逆回购操作，A股成交额超400亿元",
                    link="https://example.com/pboc",
                    source="测试源",
                    published_at="2026-07-01T09:00:00+08:00",
                    category="宏观",
                    query_name="央行流动性",
                )
            ],
        )

        summary = report.core_events[0].summary

        self.assertIn("可复核事实", summary)
        self.assertIn("1000亿元", summary)
        self.assertNotIn("测试源", summary)
        self.assertNotIn("2026-07-01T09:00:00", summary)
        self.assertNotIn("原始标题", summary)

    def test_metric_extraction_ignores_standalone_years(self) -> None:
        metrics = extract_metrics_from_text("ETF月评（2026年6月）：资金净流出108亿元")

        self.assertIn("108亿元", metrics)
        self.assertNotIn("2026年", metrics)

    def test_market_value_validation_rejects_wrong_hstech_proxy_price(self) -> None:
        hstech = next(item for item in INSTRUMENTS if item.name == "恒生科技")

        with self.assertRaises(ValueError):
            validate_signal_value(hstech, 4.39)
        validate_signal_value(hstech, 4472.23)

    def test_build_site_creates_index_and_detail_pages(self) -> None:
        report_payload = {
            "report_type": "morning",
            "date": "2026-06-29",
            "generated_at": "2026-06-29T09:00:00",
            "title": "2026-06-29 盘前投研日报",
            "executive_summary": "测试摘要",
            "market_view": "中性偏积极",
            "market_signals": [
                {"name": "上证指数", "value": "4073.90", "change": "+1.16%", "interpretation": "测试解读"}
            ],
            "core_events": [
                {
                    "title": "测试事件",
                    "summary": "测试总结",
                    "reason": "测试原因",
                    "beneficiaries": ["AI"],
                    "risks": ["波动"],
                    "bullish_stocks": ["中际旭创(300308)", "新易盛(300502)"],
                    "bearish_stocks": ["高估值题材股"],
                    "importance": 86,
                    "confidence": 72,
                    "sources": ["测试源", "https://example.com/news"],
                }
            ],
            "investment_ideas": [
                {
                    "title": "测试机会",
                    "action": "可分批关注",
                    "horizon": "1 个月",
                    "success_probability": "约 60%-70%",
                    "confidence": 68,
                    "risk_level": "中",
                    "logic": "测试逻辑",
                    "invalidation": "测试失效条件",
                    "watch_indicators": ["成交量"],
                    "catalysts": ["订单"],
                    "representative_assets": ["AI ETF"],
                    "pricing_status": "部分定价",
                    "position_size": "轻仓",
                }
            ],
            "action_checklist": ["测试行动"],
            "risk_warnings": ["测试风险"],
            "source_note": "测试来源说明\n\nAI 模型调用状态：成功调用 deepseek / deepseek-chat，已对规则版报告进行投研增强。",
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports_root = root / "data" / "reports"
            report_dir = reports_root / "2026-06-29"
            report_dir.mkdir(parents=True)
            (report_dir / "morning.json").write_text(json.dumps(report_payload, ensure_ascii=False), encoding="utf-8")

            site_dir = root / "site"
            build_site(reports_root, site_dir, "test-token")

            index_html = (site_dir / "index.html").read_text(encoding="utf-8")
            detail_html = (site_dir / "reports" / "2026-06-29-morning.html").read_text(encoding="utf-8")

        self.assertIn("历史报告", index_html)
        self.assertIn("reports/2026-06-29-morning.html", index_html)
        self.assertIn("全球市场速览", detail_html)
        self.assertIn("中国大陆", detail_html)
        self.assertIn("今日核心事件", detail_html)
        self.assertIn("最新动态", detail_html)
        self.assertIn("市场影响", detail_html)
        self.assertIn("核心催化剂", detail_html)
        self.assertIn("利好股票清单", detail_html)
        self.assertIn("中际旭创(300308)", detail_html)
        self.assertIn("机构视角摘要", detail_html)
        self.assertIn("https://example.com/news", detail_html)
        self.assertIn("AI增强", detail_html)
        self.assertIn("deepseek / deepseek-chat", detail_html)

    def test_site_renders_without_token_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports_root = root / "data" / "reports"
            site_dir = root / "site"
            build_site(reports_root, site_dir, "")

            index_html = (site_dir / "index.html").read_text(encoding="utf-8")

        self.assertIn('<main id="app" class="shell">', index_html)
        self.assertNotIn("unlockForm", index_html)
        self.assertNotIn("REPORT_ACCESS_TOKEN", index_html)

    def test_settings_treats_blank_environment_values_as_unset(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "OPENAI_MODEL": "",
                "REPORT_ACCESS_TOKEN": "   ",
                "EMAIL_PORT": "",
                "TIMEZONE": "",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.openai_model, "gpt-5.2")
        self.assertEqual(settings.ai_provider, "auto")
        self.assertEqual(settings.deepseek_model, "deepseek-chat")
        self.assertEqual(configured_ai_provider(settings), "none")
        self.assertEqual(settings.report_access_token, "dev-token")
        self.assertEqual(settings.email_port, 587)
        self.assertEqual(settings.timezone, "Asia/Shanghai")

    def test_deepseek_provider_is_selected_when_configured(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "AI_PROVIDER": "deepseek",
                "DEEPSEEK_API_KEY": "test-key",
                "DEEPSEEK_MODEL": "deepseek-chat",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(configured_ai_provider(settings), "deepseek")
        self.assertEqual(configured_ai_model(settings), "deepseek-chat")

    def test_forced_deepseek_without_key_is_not_reported_as_ready(self) -> None:
        with patch.dict("os.environ", {"AI_PROVIDER": "deepseek"}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(configured_ai_provider(settings), "none")

    def test_append_source_note_adds_ai_status(self) -> None:
        note = append_source_note("数据来源说明", "AI 模型调用状态：未调用 AI 模型。")
        self.assertIn("数据来源说明", note)
        self.assertIn("AI 模型调用状态", note)

    def test_chat_completion_text_extraction(self) -> None:
        payload = {"choices": [{"message": {"content": "{\"executive_summary\":\"ok\"}"}}]}
        self.assertEqual(extract_chat_completion_text(payload), "{\"executive_summary\":\"ok\"}")

    def test_markdown_places_ai_status_near_top(self) -> None:
        report = build_report("morning", "2026-06-29")
        report.source_note = "AI 模型调用状态：未调用 AI 模型。"
        markdown = report_to_markdown(report)
        top_lines = "\n".join(markdown.splitlines()[:5])
        self.assertIn("AI增强：未调用", top_lines)

    def test_json_parser_tolerates_trailing_commas(self) -> None:
        parsed = parse_json_object('{"executive_summary":"ok","core_events":[{"title":"a",}],}')
        self.assertEqual(parsed["executive_summary"], "ok")
        self.assertEqual(parsed["core_events"][0]["title"], "a")

    def test_deepseek_invalid_json_does_not_trigger_paid_repair_call(self) -> None:
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}, clear=True):
            settings = Settings.from_env()
        with patch("src.airesearch.ai_analysis.requests.post") as post:
            with self.assertRaises(AIOutputError):
                parse_json_object_with_deepseek_repair('{"executive_summary": "ok" "market_view": "bad"}', settings)

        post.assert_not_called()

    def test_openai_payload_parsing_and_merge(self) -> None:
        report = build_report("morning", "2026-06-29")
        output_payload = {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "executive_summary": "AI 增强摘要",
                                    "market_view": "AI 市场判断",
                                    "core_events": [
                                        {
                                            "title": "AI 事件",
                                            "summary": "事件摘要",
                                            "reason": "事件原因",
                                            "beneficiaries": ["AI"],
                                            "risks": ["波动"],
                                            "bullish_stocks": ["中际旭创(300308)"],
                                            "bearish_stocks": ["高估值题材股"],
                                            "importance": 91,
                                            "confidence": 76,
                                            "sources": ["测试源"],
                                        }
                                    ],
                                    "investment_ideas": [
                                        {
                                            "title": "AI 投资机会",
                                            "action": "可分批关注",
                                            "horizon": "1 个月",
                                            "success_probability": "约 60%-70%",
                                            "confidence": 69,
                                            "risk_level": "中",
                                            "logic": "AI 逻辑",
                                            "invalidation": "AI 失效条件",
                                            "watch_indicators": ["订单"],
                                            "catalysts": ["催化剂"],
                                            "representative_assets": ["AI ETF"],
                                            "pricing_status": "部分定价",
                                            "position_size": "轻仓",
                                        }
                                    ],
                                    "action_checklist": ["AI 行动"],
                                    "risk_warnings": ["AI 风险"],
                                    "source_note_append": "AI 仅基于输入生成。",
                                },
                                ensure_ascii=False,
                            ),
                        }
                    ]
                }
            ]
        }

        text = extract_output_text(output_payload)
        parsed = parse_json_object(f"```json\n{text}\n```")
        enhanced = merge_ai_payload(report, parsed)

        self.assertEqual(enhanced.executive_summary, "AI 增强摘要")
        self.assertEqual(enhanced.market_view, "AI 市场判断")
        self.assertEqual(enhanced.core_events[0].importance, 91)
        self.assertEqual(enhanced.core_events[0].bullish_stocks, ["中际旭创(300308)"])
        self.assertEqual(enhanced.core_events[0].bearish_stocks, ["高估值题材股"])
        self.assertEqual(enhanced.investment_ideas[0].title, "AI 投资机会")
        self.assertIn("AI 分析说明", enhanced.source_note)

    def test_quality_check_passes_complete_report(self) -> None:
        signals = [MarketSignal("上证指数", "4073.90", "+1.16%", "测试解读")]
        news = [
            NewsItem(
                title="AI 光模块订单继续增长",
                link="https://example.com/ai",
                source="测试源",
                published_at="2026-06-29T09:00:00+08:00",
                category="AI",
                query_name="AI 算力",
            ),
            NewsItem(
                title="储能项目招标规模提升",
                link="https://example.com/storage",
                source="测试源",
                published_at="2026-06-29T09:10:00+08:00",
                category="新能源",
                query_name="新能源",
            ),
            NewsItem(
                title="港股科技南向资金回流",
                link="https://example.com/hk",
                source="测试源",
                published_at="2026-06-29T09:20:00+08:00",
                category="港股",
                query_name="港股科技",
            ),
        ]
        report = build_report("morning", "2026-06-29", market_signals=signals, news_items=news)
        warnings = validate_report(report)
        checked = append_quality_note(report, warnings)

        self.assertFalse(warnings)
        self.assertIn("质量检查：通过", checked.source_note)

    def test_invalid_timezone_falls_back_to_date_text(self) -> None:
        value = current_date_text("Invalid/Timezone")
        self.assertRegex(value, r"^\d{4}-\d{2}-\d{2}$")

    def test_site_latest_uses_generated_time_and_history_uses_session_order(self) -> None:
        morning_payload = {
            "report_type": "morning",
            "date": "2026-07-02",
            "generated_at": "2026-07-02T02:30:00+08:00",
            "title": "2026-07-02 盘前投研日报",
            "executive_summary": "盘前摘要",
            "market_view": "中性",
            "market_signals": [],
            "core_events": [],
            "investment_ideas": [],
            "action_checklist": [],
            "risk_warnings": [],
            "source_note": "",
            "planned_time": "06:30",
            "schedule_status": "定时生成正常，较计划时间偏差 +0 分钟",
            "trigger": "scheduled",
        }
        close_payload = {
            **morning_payload,
            "report_type": "close",
            "generated_at": "2026-07-02T01:25:00+08:00",
            "title": "2026-07-02 收盘投研日报",
            "executive_summary": "收盘摘要",
            "planned_time": "17:30",
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports_root = root / "data" / "reports" / "2026-07-02"
            reports_root.mkdir(parents=True)
            (reports_root / "morning.json").write_text(json.dumps(morning_payload, ensure_ascii=False), encoding="utf-8")
            (reports_root / "close.json").write_text(json.dumps(close_payload, ensure_ascii=False), encoding="utf-8")

            site_dir = root / "site"
            build_site(root / "data" / "reports", site_dir, "")
            index_html = (site_dir / "index.html").read_text(encoding="utf-8")

        hero_start = index_html.index("hero-panel")
        history_start = index_html.index('id="reportGrid"')
        self.assertLess(index_html.index("盘前投研日报", hero_start), index_html.index("收盘投研日报", hero_start))
        self.assertLess(index_html.index("盘前投研日报", history_start), index_html.index("收盘投研日报", history_start))
        self.assertIn("计划：06:30 北京时间", index_html)
        self.assertIn("触发：定时触发", index_html)

    def test_core_event_filter_rejects_low_value_and_stale_items(self) -> None:
        low_value = NewsItem(
            title="哪些商家接受比特币支付，世界杯周边消费升温",
            link="https://example.com/noise",
            source="Example",
            published_at="2026-07-02T08:00:00+08:00",
            category="宏观",
            query_name="BTC",
        )
        stale = NewsItem(
            title="美国3月CPI数据回顾：通胀压力缓和",
            link="https://example.com/stale",
            source="Example",
            published_at="2026-07-02T08:10:00+08:00",
            category="宏观",
            query_name="CPI",
        )
        useful = NewsItem(
            title="央行开展5000亿元逆回购操作，A股成交额突破1.2万亿元",
            link="https://example.com/useful",
            source="证券时报",
            published_at="2026-07-02T08:20:00+08:00",
            category="宏观",
            query_name="央行流动性",
        )

        self.assertFalse(is_core_event_candidate(low_value))
        self.assertFalse(is_core_event_candidate(stale))
        self.assertTrue(is_core_event_candidate(useful))
        metrics = extract_metrics_from_text(useful.title)
        self.assertIn("5000亿元", metrics)
        self.assertTrue(any("1.2万亿" in metric for metric in metrics))


if __name__ == "__main__":
    unittest.main()
