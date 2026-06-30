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
from src.airesearch.ai_analysis import extract_output_text, merge_ai_payload, parse_json_object
from src.airesearch.config import Settings
from src.airesearch.main import current_date_text
from src.airesearch.news_data import NewsItem
from src.airesearch.quality import append_quality_note, validate_report
from src.airesearch.report_builder import build_report
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
            "source_note": "测试来源说明",
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
        self.assertEqual(settings.report_access_token, "dev-token")
        self.assertEqual(settings.email_port, 587)
        self.assertEqual(settings.timezone, "Asia/Shanghai")

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


if __name__ == "__main__":
    unittest.main()
