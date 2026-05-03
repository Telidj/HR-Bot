from __future__ import annotations

import json

from fastapi import HTTPException


def parse_activity(raw_body: bytes) -> dict:
    try:
        activity = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    if not isinstance(activity, dict):
        raise HTTPException(status_code=400, detail="Invalid activity payload")
    return activity
