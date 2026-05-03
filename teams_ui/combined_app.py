from __future__ import annotations

import os

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from .admin_handler import TeamsAdminHandler
from .chat_handler import TeamsChatHandler
from .config import TeamsSettings
from .request_utils import parse_activity
from .security import verify_outgoing_webhook_signature


settings = TeamsSettings.from_env()

app = FastAPI(title="HR & IT Assistant Teams Gateway", version="1.1.0")

chat_handler = TeamsChatHandler(
    api_base_url=settings.api_base_url,
    max_context_messages=settings.max_context_messages,
    timeout_seconds=settings.chat_timeout_seconds,
)

admin_handler = TeamsAdminHandler(
    api_base_url=settings.api_base_url,
    admin_token=os.getenv("ADMIN_TOKEN", ""),
    allowed_users=settings.admin_allowed_users,
    require_login=settings.admin_require_login,
    timeout_seconds=settings.admin_timeout_seconds,
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/messages/chat")
async def teams_chat_messages(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict:
    raw_body = await request.body()
    if not verify_outgoing_webhook_signature(
        raw_body,
        authorization,
        settings.chat_webhook_secret,
    ):
        raise HTTPException(status_code=401, detail="Unauthorized webhook request")

    activity = parse_activity(raw_body)
    reply_text = await run_in_threadpool(chat_handler.handle_activity, activity)
    return {"type": "message", "text": reply_text}


@app.post("/api/messages/admin")
async def teams_admin_messages(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict:
    raw_body = await request.body()
    if not verify_outgoing_webhook_signature(
        raw_body,
        authorization,
        settings.admin_webhook_secret,
    ):
        raise HTTPException(status_code=401, detail="Unauthorized webhook request")

    activity = parse_activity(raw_body)
    reply_text = await run_in_threadpool(admin_handler.handle_activity, activity)
    return {"type": "message", "text": reply_text}


@app.post("/api/messages")
async def teams_messages_legacy(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict:
    # Legacy chat endpoint for existing webhook configs.
    raw_body = await request.body()
    if not verify_outgoing_webhook_signature(
        raw_body,
        authorization,
        settings.chat_webhook_secret,
    ):
        raise HTTPException(status_code=401, detail="Unauthorized webhook request")

    activity = parse_activity(raw_body)
    reply_text = await run_in_threadpool(chat_handler.handle_activity, activity)
    return {"type": "message", "text": reply_text}
