from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    report_access_token: str
    pushplus_token: str
    server_chan_key: str
    email_host: str
    email_port: int
    email_user: str
    email_password: str
    email_to: str
    report_base_url: str
    timezone: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.2"),
            report_access_token=os.getenv("REPORT_ACCESS_TOKEN", "dev-token"),
            pushplus_token=os.getenv("PUSHPLUS_TOKEN", ""),
            server_chan_key=os.getenv("SERVER_CHAN_KEY", ""),
            email_host=os.getenv("EMAIL_HOST", ""),
            email_port=int(os.getenv("EMAIL_PORT", "587") or "587"),
            email_user=os.getenv("EMAIL_USER", ""),
            email_password=os.getenv("EMAIL_PASSWORD", ""),
            email_to=os.getenv("EMAIL_TO", ""),
            report_base_url=os.getenv("REPORT_BASE_URL", ""),
            timezone=os.getenv("TIMEZONE", "Asia/Shanghai"),
        )
