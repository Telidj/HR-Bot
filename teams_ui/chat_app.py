from __future__ import annotations

from fastapi.concurrency import run_in_threadpool
from fastapi import FastAPI, Header, HTTPException, Request

from .chat_handler import TeamsChatHandler
from .config import TeamsSettings
from .request_utils import parse_activity
from .security import verify_outgoing_webhook_signature


settings = TeamsSettings.from_env()

app = FastAPI(title="HR & IT Assistant Teams Chat", version="1.0.0")
handler = TeamsChatHandler(
    api_base_url=settings.api_base_url,
    max_context_messages=settings.max_context_messages,
    timeout_seconds=settings.chat_timeout_seconds,
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

    webhook_secret = settings.chat_webhook_secret
    if not verify_outgoing_webhook_signature(raw_body, authorization, webhook_secret):
        raise HTTPException(status_code=401, detail="Unauthorized webhook request")

    activity = parse_activity(raw_body)
    reply_text = await run_in_threadpool(handler.handle_activity, activity)
    return {"type": "message", "text": reply_text}
