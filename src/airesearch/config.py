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
            openai_api_key=env_text("OPENAI_API_KEY"),
            openai_model=env_text("OPENAI_MODEL", "gpt-5.2"),
            report_access_token=env_text("REPORT_ACCESS_TOKEN", "dev-token"),
            pushplus_token=env_text("PUSHPLUS_TOKEN"),
            server_chan_key=env_text("SERVER_CHAN_KEY"),
            email_host=env_text("EMAIL_HOST"),
            email_port=int(env_text("EMAIL_PORT", "587")),
            email_user=env_text("EMAIL_USER"),
            email_password=env_text("EMAIL_PASSWORD"),
            email_to=env_text("EMAIL_TO"),
            report_base_url=env_text("REPORT_BASE_URL"),
            timezone=env_text("TIMEZONE", "Asia/Shanghai"),
        )


def env_text(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped or default
