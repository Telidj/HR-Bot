from __future__ import annotations

import re
import threading
from collections import deque
from typing import Deque

import requests


def _normalize_text(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", cleaned).strip()


class TeamsChatHandler:
    def __init__(
        self,
        api_base_url: str,
        max_context_messages: int = 12,
        timeout_seconds: int = 30,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.max_context_messages = max_context_messages
        self.timeout_seconds = timeout_seconds
        self._history: dict[str, Deque[dict]] = {}
        self._lock = threading.Lock()

    def handle_activity(self, activity: dict) -> str:
        text = _normalize_text(activity.get("text", ""))
        if not text:
            return self._help_text()

        command = text.lower()
        conversation_key = self._conversation_key(activity)
        user_id = self._user_id(activity)

        if command in {"help", "/help", "menu", "commands", "/commands"}:
            return self._help_text()

        if command in {"help requests", "help request"}:
            return self._request_help_text()

        if command in {"clear", "/clear", "reset"}:
            with self._lock:
                self._history.pop(conversation_key, None)
            return "Conversation history cleared."

        if command in {"my requests", "requests", "/requests"}:
            return self._list_user_requests(user_id)

        if command.startswith("request "):
            fragment = text[8:].strip()
            if fragment.lower().startswith("details "):
                fragment = fragment[8:].strip()
            return self._get_user_request(user_id, fragment)

        if command.startswith("/"):
            return (
                "I do not recognize that Teams command. Send `help` for chat commands "
                "or ask a normal HR/IT question."
            )

        return self._chat_reply(conversation_key, user_id, text)

    def _chat_reply(self, conversation_key: str, user_id: str, user_text: str) -> str:
        with self._lock:
            history = list(self._history.get(conversation_key, deque()))

        payload_messages = history + [{"role": "user", "content": user_text}]
        payload_messages = payload_messages[-self.max_context_messages :]

        try:
            response = requests.post(
                f"{self.api_base_url}/chat",
                json={"messages": payload_messages},
                headers={"X-User": user_id},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            return self._api_unavailable_message(exc)

        data = self._safe_json(response)
        if response.status_code != 200:
            return self._format_error(response.status_code, data, response.text)

        message = (data.get("message") or {}).get("content", "").strip()
        if not message:
            message = "The assistant returned an unexpected response. Please try again."

        sources = data.get("sources") or []
        if sources:
            lines = []
            for source in sources[:3]:
                source_name = source.get("source", "unknown")
                chunk_id = source.get("chunk_id", "-")
                score = source.get("score")
                if isinstance(score, (float, int)):
                    lines.append(f"- {source_name}#{chunk_id} (score: {score:.2f})")
                else:
                    lines.append(f"- {source_name}#{chunk_id}")
            message = f"{message}\n\nSources:\n" + "\n".join(lines)

        with self._lock:
            queue = self._history.setdefault(conversation_key, deque(maxlen=64))
            queue.append({"role": "user", "content": user_text})
            queue.append({"role": "assistant", "content": message})

        return self._truncate(message)

    def _list_user_requests(self, user_id: str) -> str:
        try:
            response = requests.get(
                f"{self.api_base_url}/requests",
                headers={"X-User": user_id},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            return self._api_unavailable_message(exc)

        data = self._safe_json(response)
        if response.status_code != 200:
            return self._format_error(response.status_code, data, response.text)

        items = data.get("requests") or []
        if not items:
            return "No workflow requests are currently associated with this user."

        lines = ["Your workflow requests:"]
        for item in items[:15]:
            lines.append(
                f"- {item.get('id', '')}: {item.get('type', '')}, "
                f"status={item.get('status', '')}, "
                f"owner={item.get('assigned_to', 'unassigned')}, "
                f"created={self._format_created_at(item.get('created_at', ''))}, "
                f"period={item.get('period_or_date', 'unspecified')}"
            )
        if len(items) > 15:
            lines.append(f"... and {len(items) - 15} more")
        return self._truncate("\n".join(lines))

    def _get_user_request(self, user_id: str, request_id_fragment: str) -> str:
        if not request_id_fragment:
            return "Usage: request <request_id_fragment>"

        try:
            response = requests.get(
                f"{self.api_base_url}/requests",
                headers={"X-User": user_id},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            return self._api_unavailable_message(exc)

        data = self._safe_json(response)
        if response.status_code != 200:
            return self._format_error(response.status_code, data, response.text)

        items = data.get("requests") or []
        matches = self._find_requests(items, request_id_fragment)
        if not matches:
            return "No workflow request matched that id fragment for this user."
        if len(matches) > 1:
            preview = ", ".join(str(item.get("id", "")) for item in matches[:5])
            suffix = "" if len(matches) <= 5 else f", and {len(matches) - 5} more"
            return f"Multiple requests matched. Use more of the id: {preview}{suffix}"

        return self._truncate(self._format_request_details(matches[0]))

    @staticmethod
    def _safe_json(response: requests.Response) -> dict:
        try:
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
        except ValueError:
            return {}

    @staticmethod
    def _format_error(status_code: int, data: dict, raw_text: str) -> str:
        detail = str(data.get("detail") or data.get("message") or "").strip()
        if not detail:
            detail = (raw_text or "").strip()
        if detail:
            return f"Service error ({status_code}): {detail}"
        return f"Service error ({status_code})."

    def _api_unavailable_message(self, exc: requests.RequestException) -> str:
        return (
            "I cannot reach the HR & IT Assistant API right now. "
            f"Make sure the demo API is running at {self.api_base_url}, then try again.\n"
            f"Details: {exc}"
        )

    @staticmethod
    def _find_requests(items: list[dict], request_id_fragment: str) -> list[dict]:
        fragment = request_id_fragment.strip().lower()
        if not fragment:
            return []
        exact_matches = [
            item for item in items if str(item.get("id", "")).strip().lower() == fragment
        ]
        if exact_matches:
            return exact_matches
        return [
            item for item in items if fragment in str(item.get("id", "")).strip().lower()
        ]

    @staticmethod
    def _format_request_details(item: dict) -> str:
        comment = str(item.get("comment", "") or "").strip() or "Not provided"
        return "\n".join(
            [
                "Workflow request details:",
                f"ID: {item.get('id', '')}",
                f"Type: {item.get('type', '')}",
                f"Status: {item.get('status', '')}",
                f"Assigned to: {item.get('assigned_to', 'unassigned')}",
                f"Created at: {TeamsChatHandler._format_created_at(item.get('created_at', ''))}",
                f"Period/date: {item.get('period_or_date', 'unspecified')}",
                f"Comment: {comment}",
            ]
        )

    @staticmethod
    def _format_created_at(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return "unknown"
        return text.replace("T", " ").split(".")[0]

    @staticmethod
    def _conversation_key(activity: dict) -> str:
        conversation = activity.get("conversation") or {}
        conv_id = str(conversation.get("id") or "unknown-conversation")
        from_data = activity.get("from") or {}
        user_id = str(from_data.get("id") or "anonymous")
        return f"{conv_id}:{user_id}"

    @staticmethod
    def _user_id(activity: dict) -> str:
        from_data = activity.get("from") or {}
        return str(from_data.get("id") or "anonymous")

    @staticmethod
    def _truncate(text: str, max_chars: int = 3500) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3] + "..."

    @staticmethod
    def _help_text() -> str:
        return (
            "HR & IT Assistant for Teams\n"
            "Ask HR/IT policy questions or start a workflow request from chat.\n\n"
            "Commands:\n"
            "- help or commands: show this help message\n"
            "- help requests: show request commands\n"
            "- requests: list your workflow requests\n"
            "- request <request_id_fragment>: show request details\n"
            "- clear: clear conversation history\n\n"
            "Examples:\n"
            "- How often are salaries paid?\n"
            "- How do I request VPN access?\n"
            "- I need access to the payroll system\n"
            "- Please replace my broken laptop\n"
            "- I am blocked during onboarding because my account setup is not complete"
        )

    @staticmethod
    def _request_help_text() -> str:
        return (
            "Teams request commands\n"
            "- requests: list your workflow requests\n"
            "- request <request_id_fragment>: show one request\n"
            "- request details <request_id_fragment>: same as request <id>\n\n"
            "Requests can be created from normal chat messages, for example:\n"
            "- I need vacation from 04/10 to 04/12\n"
            "- I need access to the payroll system\n"
            "- Please replace my broken laptop\n"
            "- I am blocked during onboarding"
        )
