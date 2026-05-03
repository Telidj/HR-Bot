from __future__ import annotations

import base64
import binascii
import hashlib
import hmac


def verify_outgoing_webhook_signature(
    raw_body: bytes,
    authorization_header: str | None,
    webhook_secret: str,
) -> bool:
    """
    Validate Microsoft Teams outgoing webhook signature.

    If `webhook_secret` is empty, signature verification is skipped.
    """
    secret = (webhook_secret or "").strip()
    if not secret:
        return True

    if not authorization_header:
        return False

    signature = authorization_header.strip()
    if signature.lower().startswith("hmac "):
        signature = signature[5:].strip()
    if not signature:
        return False

    try:
        key = base64.b64decode(secret)
    except (binascii.Error, ValueError):
        # Fallback for plain text secrets.
        key = secret.encode("utf-8")

    digest = hmac.new(key, raw_body, hashlib.sha256).digest()
    expected_signature = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected_signature, signature)
