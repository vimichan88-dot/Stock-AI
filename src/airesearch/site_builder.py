from __future__ import annotations

from datetime import datetime
import html
import json
import re
from pathlib import Path


REPORT_LABELS = {
    "morning": "盘前",
    "noon": "午间",
    "close": "收盘",
}


def build_site(reports_root: Path, site_dir: Path, access_token: str) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = site_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    reports = load_reports(reports_root)
    for report in reports:
        detail_path = reports_dir / report_filename(report)
        detail_path.write_text(clean_html(render_report_detail(report, reports, access_token)), encoding="utf-8")

    (site_dir / "index.html").write_text(clean_html(render_index(reports, access_token)), encoding="utf-8")


def clean_html(content: str) -> str:
    return "\n".join(line.rstrip() for line in content.splitlines()) + "\n"


def load_reports(reports_root: Path) -> list[dict]:
    reports = []
    if reports_root.exists():
        for json_file in sorted(reports_root.glob("*/*.json"), reverse=True):
            reports.append(json.loads(json_file.read_text(encoding="utf-8")))
    return sorted(reports, key=report_sort_key, reverse=True)


def report_sort_key(report: dict) -> tuple[str, int]:
    type_order = {"close": 3, "noon": 2, "morning": 1}
    return (report.get("date", ""), type_order.get(report.get("report_type", ""), 0))


def report_filename(report: dict) -> str:
    date = safe_slug(report.get("date", "unknown-date"))
    report_type = safe_slug(report.get("report_type", "report"))
    return f"{date}-{report_type}.html"


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    return slug or "report"


def render_index(reports: list[dict], access_token: str) -> str:
    latest = reports[0] if reports else {}
    report_cards = "\n".join(render_report_card(report).strip() for report in reports)
    latest_panel = render_latest_panel(latest) if latest else "<p class=\"empty\">暂无报告。首次运行 workflow 后会生成内容。</p>"
    market_panel = render_market_panel(latest)
    idea_panel = render_idea_panel(latest)
    action_panel = render_action_panel(latest)
    report_payload = html.escape(json.dumps(search_payload(reports), ensure_ascii=False))

    body = f"""
  <main id="app" class="shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">AI Research Daily</p>
        <h1>AI 投研日报</h1>
        <p class="sub">A 股、港股为主，美股与全球宏观辅助。观点包含置信度、风险和失效条件。</p>
      </div>
      <div class="status-pill">个人专用 MVP</div>
    </header>

    <section class="dashboard">
      {latest_panel}
      {market_panel}
      {idea_panel}
      {action_panel}
    </section>

    <section class="history-head">
      <div>
        <h2>历史报告</h2>
        <p class="sub">按报告类型筛选，或搜索公司、行业、关键词。</p>
      </div>
      <div class="tools">
        <div class="tabs" role="tablist" aria-label="报告类型筛选">
          <button class="tab active" type="button" data-filter="all">全部</button>
          <button class="tab" type="button" data-filter="morning">盘前</button>
          <button class="tab" type="button" data-filter="noon">午间</button>
          <button class="tab" type="button" data-filter="close">收盘</button>
        </div>
        <input id="searchInput" class="search" type="search" placeholder="搜索关键词">
      </div>
    </section>

    <section id="reportGrid" class="report-grid">
      {report_cards or '<p class="empty">暂无报告。</p>'}
    </section>
    <script id="reportData" type="application/json">{report_payload}</script>
  </main>
  <script>
    {index_script()}
  </script>
"""
    return render_page("AI 投研日报", body)


def render_report_detail(report: dict, reports: list[dict], access_token: str) -> str:
    label = REPORT_LABELS.get(report.get("report_type", ""), report.get("report_type", "报告"))
    previous_report, next_report = adjacent_reports(report, reports)
    prev_link = detail_nav_link("上一篇", previous_report)
    next_link = detail_nav_link("下一篇", next_report)

    body = f"""
  <main id="app" class="shell detail-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">{escape(report.get("date", ""))} · {escape(label)}</p>
        <h1>{escape(report.get("title", "AI 投研报告"))}</h1>
        <p class="sub">{escape(report.get("market_view", ""))}</p>
        <p class="sub time-line">生成时间：{escape(format_generated_at(report.get("generated_at", "")))}</p>
      </div>
      <a class="back-link" href="../index.html">返回首页</a>
    </header>

    <section class="detail-layout">
      <article class="report-body">
        <section>
          <h2>今日核心结论</h2>
          <p>{escape(report.get("executive_summary", ""))}</p>
        </section>
        {render_market_overview(report.get("market_signals", []))}
        {render_events_section(report.get("core_events", []))}
        {render_analysis_sections(report.get("analysis_sections", []))}
        {render_ideas_section(report.get("investment_ideas", []))}
        {render_institution_reads(report.get("investment_ideas", []), report.get("market_view", ""))}
        {render_list_section("我的行动清单", report.get("action_checklist", []))}
        {render_list_section("风险提示", report.get("risk_warnings", []))}
        <section>
          <h2>数据来源与可信度说明</h2>
          {render_paragraphs(report.get("source_note", ""))}
        </section>
      </article>
      <aside class="side-rail">
        <div class="rail-block">
          <h2>报告导航</h2>
          <a href="#events">核心事件</a>
          <a href="#ideas">投资机会</a>
          <a href="#risks">风险提示</a>
        </div>
        <div class="rail-block">
          <h2>切换报告</h2>
          {prev_link}
          {next_link}
        </div>
      </aside>
    </section>
  </main>
  <script>
  </script>
"""
    return render_page(report.get("title", "AI 投研报告"), body)


def render_latest_panel(report: dict) -> str:
    label = REPORT_LABELS.get(report.get("report_type", ""), report.get("report_type", "报告"))
    return f"""
      <article class="panel hero-panel">
        <div class="meta">{escape(report.get("date", ""))} · {escape(label)}</div>
        <h2>{escape(report.get("title", "AI 投研报告"))}</h2>
        <p>{escape(report.get("executive_summary", ""))}</p>
        <a class="primary-link report-link" href="reports/{report_filename(report)}">查看完整报告</a>
      </article>
    """


def render_market_panel(report: dict) -> str:
    signals = report.get("market_signals", []) if report else []
    rows = "\n".join(
        f"<li><span>{escape(item.get('name', ''))}</span><strong>{escape(item.get('change', ''))}</strong></li>"
        for item in signals[:5]
    )
    return f"""
      <article class="panel">
        <h2>市场情绪</h2>
        <p class="signal-view">{escape(report.get("market_view", "暂无市场判断") if report else "暂无市场判断")}</p>
        <ul class="signal-list">{rows}</ul>
      </article>
    """


def render_idea_panel(report: dict) -> str:
    ideas = report.get("investment_ideas", []) if report else []
    rows = "\n".join(
        f"<li><strong>{escape(item.get('action', ''))}</strong><span>{escape(item.get('title', ''))}</span></li>"
        for item in ideas[:3]
    )
    return f"""
      <article class="panel">
        <h2>今日主线</h2>
        <ul class="plain-list">{rows}</ul>
      </article>
    """


def render_action_panel(report: dict) -> str:
    actions = report.get("action_checklist", []) if report else []
    rows = "\n".join(f"<li>{escape(item)}</li>" for item in actions[:4])
    return f"""
      <article class="panel">
        <h2>行动清单</h2>
        <ul class="plain-list">{rows}</ul>
      </article>
    """


def render_report_card(report: dict) -> str:
    label = REPORT_LABELS.get(report.get("report_type", ""), report.get("report_type", "报告"))
    ideas = report.get("investment_ideas", [])
    idea_html = "".join(
        f"<li><strong>{escape(item.get('action', ''))}</strong> {escape(item.get('title', ''))}</li>"
        for item in ideas[:3]
    )
    search_text = " ".join(
        [
            report.get("title", ""),
            report.get("executive_summary", ""),
            report.get("market_view", ""),
            " ".join(item.get("title", "") for item in report.get("core_events", [])),
            " ".join(item.get("title", "") for item in ideas),
        ]
    )
    return f"""
      <article class="report-card" data-type="{escape(report.get("report_type", ""))}" data-search="{escape(search_text.lower())}">
        <div class="meta">{escape(report.get("date", ""))} · {escape(label)}</div>
        <h3>{escape(report.get("title", "AI 投研报告"))}</h3>
        <p class="generated-line">生成时间：{escape(format_generated_at(report.get("generated_at", "")))}</p>
        <p>{escape(report.get("executive_summary", ""))}</p>
        <ul>{idea_html}</ul>
        <a class="report-link" href="reports/{report_filename(report)}">打开报告</a>
      </article>
    """


def render_market_overview(signals: list[dict]) -> str:
    groups = [
        ("中国大陆", [item for item in signals if market_signal_group(item) == "mainland"]),
        ("香港市场", [item for item in signals if market_signal_group(item) == "hongkong"]),
        ("美国市场", [item for item in signals if market_signal_group(item) == "us"]),
        ("日韩市场", [item for item in signals if market_signal_group(item) == "jp_kr"]),
        ("欧洲市场", [item for item in signals if market_signal_group(item) == "europe"]),
        ("大宗商品与外汇", [item for item in signals if market_signal_group(item) == "commodity_fx"]),
        ("债券与风险偏好", [item for item in signals if market_signal_group(item) == "rates_risk"]),
    ]
    sections = "\n".join(render_signal_table(title, rows) for title, rows in groups if rows)
    return f"<section><h2>全球市场速览</h2>{sections}</section>"


def market_signal_group(signal: dict) -> str:
    name = str(signal.get("name", ""))
    if any(keyword in name for keyword in ["上证", "沪深", "创业板", "深证", "深成", "科创"]):
        return "mainland"
    if any(keyword in name for keyword in ["恒生", "香港"]):
        return "hongkong"
    if any(keyword in name for keyword in ["标普", "纳斯达克", "纳指", "道琼", "道指"]):
        return "us"
    if any(keyword in name for keyword in ["日经", "韩国", "KOSPI"]):
        return "jp_kr"
    if any(keyword in name for keyword in ["欧洲", "STOXX", "德国", "DAX", "英国", "富时"]):
        return "europe"
    commodity_keywords = ["油", "黄金", "金", "铜", "美元", "人民币", "比特", "以太"]
    rates_keywords = ["债", "收益率", "VIX", "波动"]
    if any(keyword in name for keyword in commodity_keywords):
        return "commodity_fx"
    if any(keyword in name for keyword in rates_keywords):
        return "rates_risk"
    return "index"


def render_signal_table(title: str, signals: list[dict]) -> str:
    rows = "\n".join(
        f"""
          <tr>
            <td>{escape(item.get('name', ''))}</td>
            <td>{escape(item.get('value', ''))}</td>
            <td>{escape(item.get('change', ''))}</td>
          </tr>
        """
        for item in signals
    )
    return f"""
        <div class="market-block">
          <h3>{escape(title)}</h3>
          <div class="table-wrap">
            <table>
              <thead><tr><th>指标</th><th>数值</th><th>变化</th></tr></thead>
              <tbody>{rows}</tbody>
            </table>
          </div>
        </div>
    """


def render_events_section(events: list[dict]) -> str:
    rows = "\n".join(
        render_event_block(idx, event)
        for idx, event in enumerate(events, start=1)
    )
    return f"<section id=\"events\"><h2>今日核心事件</h2>{rows}</section>"


def render_event_block(idx: int, event: dict) -> str:
    bullish = event.get("bullish_stocks", []) or fallback_stock_list(event, "bullish")
    bearish = event.get("bearish_stocks", []) or fallback_stock_list(event, "bearish")
    return (
        f"""
          <article class="item-block">
            <div class="score-line"><span>重要程度 {escape(str(event.get('importance', '')))} / 100</span><span>置信度 {escape(str(event.get('confidence', '')))} / 100</span></div>
            <h3>{idx}. {escape(event.get('title', ''))}</h3>
            <div class="event-grid">
              <div>
                <strong>最新动态</strong>
                <p>{escape(event.get('summary', ''))}</p>
              </div>
              <div>
                <strong>市场影响</strong>
                <p>{escape(event.get('reason', ''))}</p>
              </div>
            </div>
            <p><strong>受益方向：</strong>{escape(join_items(event.get('beneficiaries', [])))}</p>
            <p><strong>风险观察：</strong>{escape(join_items(event.get('risks', [])))}</p>
            <div class="stock-impact">
              <div><strong>利好股票清单</strong><span>{escape(join_items(bullish) or '待复核')}</span></div>
              <div><strong>利空股票清单</strong><span>{escape(join_items(bearish) or '待复核')}</span></div>
            </div>
            <p class="source-line"><strong>来源：</strong>{render_sources(event.get('sources', []))}</p>
          </article>
        """.strip()
    )


def render_analysis_sections(sections: list[dict]) -> str:
    if not sections:
        return ""
    rows = "\n".join(
        f"""
          <article class="item-block analysis-block">
            <h3>{escape(section.get('title', ''))}</h3>
            <p>{escape(section.get('view', ''))}</p>
            <dl class="idea-facts">
              <div><dt>机会观察</dt><dd>{escape(join_items(section.get('opportunities', [])))}</dd></div>
              <div><dt>风险约束</dt><dd>{escape(join_items(section.get('risks', [])))}</dd></div>
              <div><dt>跟踪指标</dt><dd>{escape(join_items(section.get('watch', [])))}</dd></div>
            </dl>
          </article>
        """.strip()
        for section in sections
    )
    return f"<section id=\"analysis\"><h2>分主题研究框架</h2>{rows}</section>"


def render_ideas_section(ideas: list[dict]) -> str:
    rows = "\n".join(
        f"""
          <article class="item-block">
            <div class="score-line"><span>{escape(idea.get('action', ''))}</span><span>{escape(idea.get('success_probability', ''))}</span><span>置信度 {escape(str(idea.get('confidence', '')))} / 100</span></div>
            <h3>{escape(idea.get('title', ''))}</h3>
            <p>{escape(idea.get('logic', ''))}</p>
            <dl class="idea-facts">
              <div><dt>周期</dt><dd>{escape(idea.get('horizon', ''))}</dd></div>
              <div><dt>风险等级</dt><dd>{escape(idea.get('risk_level', ''))}</dd></div>
              <div><dt>核心催化剂</dt><dd>{escape(join_items(idea.get('catalysts', [])))}</dd></div>
              <div><dt>代表行业/ETF/公司</dt><dd>{escape(join_items(idea.get('representative_assets', [])))}</dd></div>
              <div><dt>定价状态</dt><dd>{escape(idea.get('pricing_status', ''))}</dd></div>
              <div><dt>适合仓位</dt><dd>{escape(idea.get('position_size', ''))}</dd></div>
              <div><dt>失效条件</dt><dd>{escape(idea.get('invalidation', ''))}</dd></div>
              <div><dt>观察指标</dt><dd>{escape(join_items(idea.get('watch_indicators', [])))}</dd></div>
            </dl>
          </article>
        """
        for idea in ideas
    )
    return f"<section id=\"ideas\"><h2>投资机会</h2>{rows}</section>"


def render_institution_reads(ideas: list[dict], market_view: str) -> str:
    rows = "\n".join(
        f"""
          <blockquote class="read-block">
            <h3>{escape(idea.get('title', ''))}</h3>
            <p>{escape(idea.get('logic', ''))}</p>
            <p><strong>配置倾向：</strong>{escape(idea.get('action', ''))}；{escape(idea.get('position_size', ''))}</p>
          </blockquote>
        """.strip()
        for idea in ideas[:4]
    )
    return f"""
        <section>
          <h2>机构视角摘要</h2>
          <p>{escape(market_view)}</p>
          {rows}
        </section>
    """


def render_list_section(title: str, items: list[str]) -> str:
    section_id = "risks" if title == "风险提示" else ""
    rows = "\n".join(f"<li>{escape(item)}</li>" for item in items)
    return f"<section id=\"{section_id}\"><h2>{escape(title)}</h2><ul class=\"plain-list detail-list\">{rows}</ul></section>"


def render_paragraphs(text: str) -> str:
    return "\n".join(f"<p>{escape(part.strip())}</p>" for part in text.split("\n\n") if part.strip())


def render_sources(sources: list[str]) -> str:
    rendered = []
    for source in sources:
        if source.startswith("http"):
            rendered.append(f"<a href=\"{escape(source)}\" target=\"_blank\" rel=\"noreferrer\">原文链接</a>")
        else:
            rendered.append(escape(source))
    return "、".join(rendered)


def fallback_stock_list(event: dict, side: str) -> list[str]:
    text = " ".join(
        [
            str(event.get("title", "")),
            str(event.get("summary", "")),
            join_items(event.get("beneficiaries", [])),
            join_items(event.get("risks", [])),
        ]
    ).lower()
    stock_map = [
        (
            ["ai", "算力", "芯片", "光模块", "半导体", "服务器"],
            ["中际旭创(300308)", "新易盛(300502)", "工业富联(601138)", "寒武纪(688256)", "中芯国际(688981)"],
            ["高估值无订单AI题材股", "算力租赁弱现金流公司", "传统低端服务器代工"],
        ),
        (
            ["新能源", "储能", "光伏", "电池", "电网"],
            ["宁德时代(300750)", "阳光电源(300274)", "亿纬锂能(300014)", "国电南瑞(600406)"],
            ["低效光伏组件企业", "高成本落后电池产能", "高负债新能源小票"],
        ),
        (
            ["港股", "恒生", "南向", "互联网平台", "平台经济"],
            ["腾讯控股(00700.HK)", "阿里巴巴-W(09988.HK)", "美团-W(03690.HK)", "小米集团-W(01810.HK)"],
            ["高杠杆地产链港股", "成交低迷券商股", "弱基本面小市值港股"],
        ),
        (
            ["黄金", "美元", "原油", "避险", "宏观"],
            ["紫金矿业(601899)", "山东黄金(600547)", "中国海油(600938)", "高股息红利ETF(515180)"],
            ["航空股", "高外债房企", "高估值成长股"],
        ),
    ]
    for keywords, bullish, bearish in stock_map:
        if any(keyword in text for keyword in keywords):
            return bullish if side == "bullish" else bearish
    return ["相关行业龙头", "产业链ETF", "高景气细分龙头"] if side == "bullish" else ["同业弱势公司", "高估值题材股", "基本面承压公司"]


def format_generated_at(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "暂无生成时间"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return text
    if dt.tzinfo is None:
        return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} 北京时间"
    return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} 北京时间"


def detail_nav_link(label: str, report: dict | None) -> str:
    if not report:
        return f"<span class=\"muted-link\">{escape(label)}：无</span>"
    return f"<a class=\"report-link\" href=\"{report_filename(report)}\">{escape(label)}：{escape(report.get('title', '报告'))}</a>"


def adjacent_reports(current: dict, reports: list[dict]) -> tuple[dict | None, dict | None]:
    current_name = report_filename(current)
    names = [report_filename(report) for report in reports]
    if current_name not in names:
        return None, None
    idx = names.index(current_name)
    previous_report = reports[idx + 1] if idx + 1 < len(reports) else None
    next_report = reports[idx - 1] if idx - 1 >= 0 else None
    return previous_report, next_report


def search_payload(reports: list[dict]) -> list[dict]:
    return [
        {
            "title": report.get("title", ""),
            "type": report.get("report_type", ""),
            "date": report.get("date", ""),
            "href": f"reports/{report_filename(report)}",
        }
        for report in reports
    ]


def render_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fa;
      --panel: #ffffff;
      --text: #1f2933;
      --muted: #64748b;
      --line: #d8dee8;
      --accent: #0f766e;
      --accent-weak: #e5f3f1;
      --warn: #b45309;
      --danger: #b42318;
      --shadow: 0 10px 28px rgba(15, 23, 42, 0.07);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ max-width: 100%; overflow-x: hidden; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .shell {{ width: 100%; max-width: 1180px; margin: 0 auto; padding: 28px 18px 64px; }}
    .topbar {{ display: flex; justify-content: space-between; gap: 24px; align-items: flex-end; padding: 18px 0 24px; border-bottom: 1px solid var(--line); }}
    .eyebrow {{ margin: 0 0 8px; color: var(--warn); font-size: 13px; font-weight: 800; letter-spacing: 0; }}
    h1 {{ margin: 0; font-size: 30px; line-height: 1.2; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; line-height: 1.35; letter-spacing: 0; }}
    h3 {{ margin: 8px 0 10px; font-size: 17px; line-height: 1.35; letter-spacing: 0; }}
    p {{ line-height: 1.75; }}
    .sub {{ margin: 8px 0 0; color: var(--muted); }}
    .status-pill, .meta {{ color: var(--warn); font-size: 14px; font-weight: 800; }}
    .status-pill {{ color: #fff; background: var(--accent); padding: 8px 10px; border-radius: 6px; white-space: nowrap; }}
    .dashboard {{ display: grid; grid-template-columns: 1.4fr 1fr; gap: 14px; margin-top: 20px; }}
    .panel, .report-card, .item-block {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; box-shadow: var(--shadow); }}
    .panel {{ padding: 18px; }}
    .hero-panel {{ grid-row: span 2; }}
    .hero-panel h2 {{ font-size: 23px; }}
    .primary-link, .report-link, .back-link {{ display: inline-flex; align-items: center; min-height: 36px; font-weight: 800; }}
    .signal-list, .plain-list {{ list-style: none; padding: 0; margin: 0; }}
    .signal-list li {{ display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--line); }}
    .signal-list li:last-child {{ border-bottom: 0; }}
    .signal-list strong {{ color: var(--accent); white-space: nowrap; }}
    .plain-list li {{ padding: 7px 0; line-height: 1.55; }}
    .plain-list strong {{ color: var(--accent); margin-right: 6px; }}
    .history-head {{ display: flex; justify-content: space-between; gap: 18px; align-items: flex-end; margin-top: 30px; padding-top: 24px; border-top: 1px solid var(--line); }}
    .tools {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }}
    .tabs {{ display: flex; gap: 6px; }}
    .tab {{ height: 38px; border: 1px solid var(--line); background: #fff; color: var(--text); border-radius: 6px; padding: 0 12px; cursor: pointer; font-weight: 700; }}
    .tab.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    .search {{ width: 220px; height: 38px; border: 1px solid var(--line); border-radius: 6px; padding: 0 10px; font-size: 15px; }}
    .report-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); gap: 14px; margin-top: 16px; }}
    .report-card {{ padding: 18px; display: flex; flex-direction: column; min-height: 260px; }}
    .generated-line {{ margin: 6px 0 0; color: var(--muted); font-size: 13px; }}
    .report-card p {{ color: var(--muted); }}
    .report-card ul {{ padding-left: 18px; margin: 8px 0 12px; }}
    .report-card .report-link {{ margin-top: auto; }}
    .detail-layout {{ display: grid; grid-template-columns: minmax(0, 1fr) 260px; gap: 18px; margin-top: 20px; align-items: start; }}
    .report-body {{ display: grid; gap: 18px; min-width: 0; }}
    .report-body > section {{ background: transparent; border-bottom: 1px solid var(--line); padding-bottom: 18px; }}
    .item-block {{ padding: 16px; margin: 12px 0; box-shadow: none; min-width: 0; overflow-wrap: anywhere; }}
    .score-line {{ display: flex; gap: 8px; flex-wrap: wrap; color: var(--warn); font-size: 13px; font-weight: 800; }}
    .event-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 12px 0; }}
    .event-grid div {{ border-left: 4px solid var(--accent); background: #fff; padding: 10px 12px; }}
    .event-grid strong {{ color: var(--warn); }}
    .event-grid p {{ margin: 6px 0 0; }}
    .market-block {{ margin: 12px 0 18px; }}
    .market-block h3 {{ margin: 0 0 8px; color: var(--warn); }}
    .stock-impact {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 12px 0; }}
    .stock-impact div {{ border: 1px solid var(--line); border-radius: 8px; background: #fff; padding: 10px; }}
    .stock-impact strong {{ display: block; color: var(--warn); margin-bottom: 6px; }}
    .stock-impact span {{ line-height: 1.55; }}
    .read-block {{ margin: 12px 0; padding: 12px 14px; border-left: 5px solid var(--line); background: #fff; color: var(--text); }}
    .read-block h3 {{ margin-top: 0; }}
    .table-wrap {{ max-width: 100%; overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: #fff; }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; line-height: 1.55; overflow-wrap: anywhere; word-break: break-word; }}
    th {{ background: var(--accent-weak); color: #134e4a; font-size: 14px; }}
    .idea-facts {{ display: grid; gap: 8px; margin: 12px 0 0; }}
    .idea-facts div {{ display: grid; grid-template-columns: 130px 1fr; gap: 10px; }}
    dt {{ color: var(--muted); font-weight: 800; }}
    dd {{ margin: 0; line-height: 1.55; }}
    .side-rail {{ position: sticky; top: 16px; display: grid; gap: 12px; }}
    .rail-block {{ border: 1px solid var(--line); border-radius: 8px; background: #fff; padding: 14px; }}
    .rail-block a, .muted-link {{ display: block; padding: 8px 0; line-height: 1.4; }}
    .muted-link {{ color: var(--muted); }}
    .empty {{ color: var(--muted); }}
    .source-line {{ overflow-wrap: anywhere; }}
    @media (max-width: 860px) {{
      .topbar, .history-head {{ display: block; }}
      .status-pill {{ display: inline-flex; margin-top: 14px; }}
      .dashboard, .detail-layout {{ grid-template-columns: 1fr; }}
      .side-rail {{ position: static; }}
      .tools {{ justify-content: flex-start; margin-top: 14px; }}
      .search {{ width: min(100%, 320px); }}
    }}
    @media (max-width: 560px) {{
      .shell {{ padding: 20px 14px 48px; }}
      h1 {{ font-size: 24px; }}
      .tabs {{ width: 100%; display: grid; grid-template-columns: repeat(4, 1fr); }}
      .tab {{ padding: 0 6px; }}
      .search {{ width: 100%; }}
      .idea-facts div {{ grid-template-columns: 1fr; gap: 3px; }}
      .event-grid {{ grid-template-columns: 1fr; }}
      .stock-impact {{ grid-template-columns: 1fr; }}
      th, td {{ padding: 8px 7px; font-size: 13px; }}
      .score-line span {{ width: 100%; }}
    }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def index_script() -> str:
    return """
    const tabs = [...document.querySelectorAll(".tab")];
    const cards = [...document.querySelectorAll(".report-card")];
    const searchInput = document.getElementById("searchInput");
    let activeFilter = "all";
    function applyFilters() {
      const query = (searchInput.value || "").trim().toLowerCase();
      cards.forEach((card) => {
        const typeMatch = activeFilter === "all" || card.dataset.type === activeFilter;
        const searchMatch = !query || card.dataset.search.includes(query);
        card.hidden = !(typeMatch && searchMatch);
      });
    }
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        tabs.forEach((item) => item.classList.remove("active"));
        tab.classList.add("active");
        activeFilter = tab.dataset.filter;
        applyFilters();
      });
    });
    searchInput.addEventListener("input", applyFilters);
    applyFilters();
    """


def join_items(items: list[str]) -> str:
    return "、".join(str(item) for item in items)


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)
