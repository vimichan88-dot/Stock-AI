from __future__ import annotations

import json
import smtplib
import time
from email.message import EmailMessage
from urllib.parse import urlencode
from urllib import request

from .config import Settings
from .models import Report


def build_notification_text(report: Report, report_url: str) -> str:
    ideas = "\n".join(f"- {item.action}：{item.title}（{item.success_probability}）" for item in report.investment_ideas[:3])
    return (
        f"【{report.title}】\n\n"
        f"市场判断：{report.market_view}\n\n"
        f"今日关注：\n{ideas}\n\n"
        f"完整报告：{report_url}\n"
    )


def send_pushplus(settings: Settings, report: Report, report_url: str) -> bool:
    if not settings.pushplus_token:
        return False
    payload = {
        "token": settings.pushplus_token,
        "title": report.title,
        "content": build_notification_text(report, report_url).replace("\n", "<br>"),
        "template": "html",
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        "https://www.pushplus.plus/send",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return post_with_retry(req)


def send_server_chan(settings: Settings, report: Report, report_url: str) -> bool:
    if not settings.server_chan_key:
        return False
    data = urlencode(
        {
            "title": report.title,
            "desp": build_notification_text(report, report_url),
        }
    ).encode("utf-8")
    req = request.Request(
        f"https://sctapi.ftqq.com/{settings.server_chan_key}.send",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    return post_with_retry(req)


def send_email(settings: Settings, report: Report, report_url: str) -> bool:
    if not (settings.email_host and settings.email_user and settings.email_password and settings.email_to):
        return False

    message = EmailMessage()
    message["Subject"] = report.title
    message["From"] = settings.email_user
    message["To"] = settings.email_to
    message.set_content(build_notification_text(report, report_url))

    with smtplib.SMTP(settings.email_host, settings.email_port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(settings.email_user, settings.email_password)
        smtp.send_message(message)
    return True


def post_with_retry(req: request.Request, attempts: int = 3, timeout: int = 20) -> bool:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with request.urlopen(req, timeout=timeout) as response:
                return 200 <= response.status < 300
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(2**attempt)
    if last_error:
        raise last_error
    return False
