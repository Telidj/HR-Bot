from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _getenv(names: tuple[str, ...], default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is None:
            continue
        value = value.strip()
        if value:
            return value
    return default


def _getint(
    names: tuple[str, ...],
    default: int,
    min_value: int,
    max_value: int,
) -> int:
    raw = _getenv(names, "")
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, parsed))


def _getbool(names: tuple[str, ...], default: bool) -> bool:
    raw = _getenv(names, "")
    if not raw:
        return default
    return raw.lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class TeamsSettings:
    api_base_url: str
    host: str
    port: int
    chat_port: int
    admin_port: int
    max_context_messages: int
    chat_timeout_seconds: int
    admin_timeout_seconds: int
    chat_webhook_secret: str
    admin_webhook_secret: str
    admin_allowed_users: str
    admin_require_login: bool

    @classmethod
    def from_env(cls) -> "TeamsSettings":
        return cls(
            api_base_url=_getenv(("API_BASE_URL",), "http://127.0.0.1:8000").rstrip("/"),
            host=_getenv(
                ("TEAMS_HOST", "TEAMS_CHAT_HOST", "TEAMS_ADMIN_HOST"),
                "0.0.0.0",
            ),
            port=_getint(("TEAMS_PORT", "TEAMS_CHAT_PORT"), 3978, 1, 65535),
            chat_port=_getint(("TEAMS_CHAT_PORT", "TEAMS_PORT"), 3978, 1, 65535),
            admin_port=_getint(("TEAMS_ADMIN_PORT",), 3979, 1, 65535),
            max_context_messages=_getint(
                ("TEAMS_MAX_CONTEXT", "TEAMS_CHAT_MAX_CONTEXT"), 12, 1, 64
            ),
            chat_timeout_seconds=_getint(
                ("TEAMS_TIMEOUT_SEC", "TEAMS_CHAT_TIMEOUT_SEC"), 90, 1, 180
            ),
            admin_timeout_seconds=_getint(
                ("TEAMS_TIMEOUT_SEC", "TEAMS_ADMIN_TIMEOUT_SEC"), 90, 1, 180
            ),
            chat_webhook_secret=_getenv(
                ("TEAMS_CHAT_WEBHOOK_SECRET", "TEAMS_WEBHOOK_SECRET"),
                "",
            ),
            admin_webhook_secret=_getenv(
                ("TEAMS_ADMIN_WEBHOOK_SECRET", "TEAMS_WEBHOOK_SECRET"),
                "",
            ),
            admin_allowed_users=_getenv(("TEAMS_ADMIN_ALLOWED_USERS",), ""),
            admin_require_login=_getbool(("TEAMS_ADMIN_REQUIRE_LOGIN",), True),
        )
