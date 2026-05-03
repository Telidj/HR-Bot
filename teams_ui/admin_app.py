from __future__ import annotations

import os

from fastapi.concurrency import run_in_threadpool
from fastapi import FastAPI, Header, HTTPException, Request

from .admin_handler import TeamsAdminHandler
from .config import TeamsSettings
from .request_utils import parse_activity
from .security import verify_outgoing_webhook_signature


settings = TeamsSettings.from_env()

app = FastAPI(title="HR & IT Assistant Teams Admin", version="1.0.0")
handler = TeamsAdminHandler(
    api_base_url=settings.api_base_url,
    admin_token=os.getenv("ADMIN_TOKEN", ""),
    allowed_users=settings.admin_allowed_users,
    require_login=settings.admin_require_login,
    timeout_seconds=settings.admin_timeout_seconds,
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/messages")
async def teams_messages(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict:
    raw_body = await request.body()

    webhook_secret = settings.admin_webhook_secret
    if not verify_outgoing_webhook_signature(raw_body, authorization, webhook_secret):
        raise HTTPException(status_code=401, detail="Unauthorized webhook request")

    activity = parse_activity(raw_body)
    reply_text = await run_in_threadpool(handler.handle_activity, activity)
    return {"type": "message", "text": reply_text}
