# AI Research Daily

个人专用 AI 投研日报系统。

第一版目标：

- GitHub Actions 每日三次自动运行
- 生成中文盘前、午间、收盘投研报告
- 生成静态私人报告网页
- PushPlus 微信提醒，邮件备份
- 使用免费公开数据源作为 MVP 输入

## Quick Start

1. 复制 `.env.example` 中的配置到 GitHub Secrets。
2. 在 GitHub 仓库开启 Actions。
3. 在 GitHub Pages 中选择 `site/` 或 Actions 产物作为发布目录。
4. 手动运行一次 `.github/workflows/ai-research-daily.yml` 中的 `AI Research Daily` workflow 验证报告生成。

本地测试：

```powershell
python -m src.airesearch.main --report-type morning
```

生成结果：

```text
data/reports/YYYY-MM-DD/
site/
```

静态网页会生成：

```text
site/index.html
site/reports/YYYY-MM-DD-report-type.html
```

首页包含最新报告仪表盘、市场情绪、行动清单、历史报告筛选和关键词搜索。详情页包含完整报告正文、核心事件、投资机会、风险提示和来源链接。

## Data Sources

MVP 会优先从 Yahoo Finance chart 免费接口抓取上证指数、恒生指数、纳指 100 ETF、黄金 ETF、美元/离岸人民币、美债 10 年收益率、VIX、原油、铜、BTC 和 ETH，并从 Google News RSS 抓取 A 股、港股、AI、新能源、全球宏观和公告线索。免费接口可能延迟或临时失败；失败时系统会回退到示例数据，保证日报、网页和通知链路仍然可生成。

原始新闻会保存到：

```text
data/raw/news/YYYY-MM-DD/
data/raw/announcements/YYYY-MM-DD/
```

报告保存前会执行基础质量检查，覆盖市场信号、核心事件、投资机会、风险提示、来源、失效条件和观察指标完整性。

## Required Secrets

| Name | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes for AI analysis | OpenAI API key. Without it, the system falls back to rule-based analysis. |
| `OPENAI_MODEL` | No | Default model name, currently `gpt-5.2`. |
| `REPORT_ACCESS_TOKEN` | Yes | Token used by the static page gate. |
| `PUSHPLUS_TOKEN` | No | PushPlus token for WeChat notifications. |
| `SERVER_CHAN_KEY` | No | Server 酱 SendKey, backup WeChat notification channel. |
| `EMAIL_TO` | No | Email recipient. |
| `EMAIL_HOST` | No | SMTP host. |
| `EMAIL_PORT` | No | SMTP port. |
| `EMAIL_USER` | No | SMTP user. |
| `EMAIL_PASSWORD` | No | SMTP app password. |

## Note On Privacy

The MVP uses a static token gate for personal convenience. Static pages are not equivalent to server-side authentication. For stronger privacy, upgrade later to Cloudflare Access, a private server, or another authenticated hosting layer.
