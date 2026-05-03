from __future__ import annotations

import re
from urllib.parse import quote

import requests


VALID_STATUSES = {"new", "pending", "approved", "declined", "done"}


def _normalize_text(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _parse_allowed_users(raw: str) -> set[str]:
    values = [item.strip() for item in (raw or "").split(",")]
    return {item for item in values if item}


class TeamsAdminHandler:
    def __init__(
        self,
        api_base_url: str,
        admin_token: str,
        allowed_users: str = "",
        require_login: bool = True,
        timeout_seconds: int = 30,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.admin_token = admin_token.strip()
        self.allowed_users = _parse_allowed_users(allowed_users)
        self.require_login = require_login
        self.timeout_seconds = timeout_seconds
        self._authenticated_sessions: set[str] = set()

    def handle_activity(self, activity: dict) -> str:
        user_id = self._user_id(activity)
        session_id = self._session_id(activity)
        text = _normalize_text(activity.get("text", ""))
        command = text.lower()

        if self.allowed_users and user_id not in self.allowed_users:
            return "Administrator access is not available for this Teams user."

        if not text:
            return self._help_text(is_authenticated=session_id in self._authenticated_sessions)

        if command in {"help", "/help", "menu", "commands", "/commands"}:
            return self._help_text(is_authenticated=session_id in self._authenticated_sessions)

        if command in {"help docs", "help documents"}:
            return self._docs_help_text()

        if command in {"help requests", "help request"}:
            return self._requests_help_text()

        if command.startswith("login "):
            provided = text[6:].strip()
            if not self.admin_token:
                return "Administrator access is not configured for this environment."
            if provided != self.admin_token:
                return "Administrator authentication failed. Please verify the token and try again."
            self._authenticated_sessions.add(session_id)
            return "Administrator session authenticated successfully."

        if command == "logout":
            self._authenticated_sessions.discard(session_id)
            return "Administrator session signed out."

        if self.require_login and session_id not in self._authenticated_sessions:
            return (
                "Authentication is required before running Teams admin commands. "
                "Use: login <ADMIN_TOKEN>. Send `help` to see available commands."
            )

        if command == "prompt get":
            return self._prompt_get()

        if command.startswith("prompt set "):
            return self._prompt_set(text[11:].strip())

        if command == "docs list":
            return self._docs_list()

        if command.startswith("docs preview "):
            return self._docs_preview(text[13:].strip())

        if command.startswith("docs upload "):
            return self._docs_upload(text[12:].strip())

        if command.startswith("docs delete "):
            return self._docs_delete(text[12:].strip())

        if command == "index rebuild":
            return self._index_rebuild()

        if command.startswith("logs"):
            limit = self._optional_int_arg(text, default=20)
            return self._logs(limit)

        if command.startswith("requests"):
            parsed = self._parse_requests_command(text)
            if parsed.get("error"):
                return str(parsed["error"])
            return self._requests(
                limit=int(parsed["limit"]),
                status_filter=str(parsed["status"]),
                user_filter=str(parsed["user"]),
                request_id_filter=str(parsed["id"]),
            )

        if command.startswith("request get "):
            return self._request_details(text[12:].strip())

        if command.startswith("request details "):
            return self._request_details(text[16:].strip())

        if command.startswith("request update "):
            return self._request_update(text[15:].strip())

        return (
            "I do not recognize that Teams admin command. Send `help`, `help docs`, "
            "or `help requests` for supported commands."
        )

    def _prompt_get(self) -> str:
        status, data, raw = self._admin_request("GET", "/admin/system-prompt")
        if status != 200:
            return self._format_error(status, data, raw)
        prompt = (data.get("system_prompt") or "").strip()
        if not prompt:
            return "The system prompt is currently empty."
        return self._truncate(f"Current system prompt:\n{prompt}")

    def _prompt_set(self, value: str) -> str:
        if not value:
            return "Usage: prompt set <new prompt text>"
        status, data, raw = self._admin_request(
            "PUT",
            "/admin/system-prompt",
            json={"system_prompt": value},
        )
        if status != 200:
            return self._format_error(status, data, raw)
        return "System prompt updated successfully."

    def _docs_list(self) -> str:
        status, data, raw = self._admin_request("GET", "/admin/documents")
        if status != 200:
            return self._format_error(status, data, raw)
        docs = data.get("documents") or []
        if not docs:
            return "No documents are currently available."
        lines = ["Knowledge base documents:"]
        for item in docs[:30]:
            lines.append(f"- {item.get('name', '')} ({item.get('size', 0)} bytes)")
        if len(docs) > 30:
            lines.append(f"... and {len(docs) - 30} more")
        return self._truncate("\n".join(lines))

    def _docs_preview(self, doc_name: str) -> str:
        if not doc_name:
            return "Usage: docs preview <document_name>"
        encoded = quote(doc_name, safe="")
        status, data, raw = self._admin_request("GET", f"/admin/documents/{encoded}")
        if status != 200:
            return self._format_error(status, data, raw)
        doc = data.get("document") or {}
        name = doc.get("name") or doc_name
        owner = doc.get("owner") or "Not found"
        effective_date = doc.get("effective_date") or "Not found"
        text = self._compact_preview(doc.get("text", ""))
        lines = [
            f"Document preview: {name}",
            f"Owner: {owner}",
            f"Effective Date: {effective_date}",
        ]
        if text:
            lines.extend(["", text])
        if doc.get("truncated"):
            lines.append("[Preview truncated]")
        return self._truncate("\n".join(lines))

    def _docs_upload(self, payload: str) -> str:
        if ":::" not in payload:
            return "Usage: docs upload <file_name> ::: <content>"

        name, content = payload.split(":::", maxsplit=1)
        file_name = name.strip()
        body = content.strip()
        if not file_name:
            return "A file name is required."
        if not body:
            return "Document content cannot be empty."

        if "." not in file_name:
            file_name = f"{file_name}.txt"

        status, data, raw = self._admin_upload_document(
            file_name=file_name,
            file_bytes=body.encode("utf-8"),
        )
        if status != 200:
            return self._format_error(status, data, raw)
        stored_name = data.get("name") or file_name
        return (
            f"Document uploaded successfully: {stored_name}\n"
            "Rebuild the vector index before expecting this document in chat answers."
        )

    def _docs_delete(self, doc_name: str) -> str:
        if not doc_name:
            return "Usage: docs delete <document_name>"
        encoded = quote(doc_name, safe="")
        status, data, raw = self._admin_request("DELETE", f"/admin/documents/{encoded}")
        if status != 200:
            return self._format_error(status, data, raw)
        return (
            f"Document deleted: {doc_name}\n"
            "Rebuild the vector index so deleted content is no longer used in chat answers."
        )

    def _index_rebuild(self) -> str:
        status, data, raw = self._admin_request("POST", "/admin/rebuild-index")
        if status != 200:
            return self._format_error(status, data, raw)
        return "The vector index was rebuilt successfully."

    def _logs(self, limit: int) -> str:
        status, data, raw = self._admin_request("GET", f"/admin/logs?limit={limit}")
        if status != 200:
            return self._format_error(status, data, raw)
        logs = data.get("logs") or []
        if not logs:
            return "No log entries are available."
        lines = ["Recent conversation logs:"]
        for item in logs[:20]:
            ts = item.get("ts", "")
            intent = item.get("intent", "")
            user = item.get("user", "[not stored]")
            mode = item.get("user_text_mode", "unknown")
            lines.append(f"- [{ts}] intent={intent} user={user} user_text_mode={mode}")
        if len(logs) > 20:
            lines.append(f"... and {len(logs) - 20} more")
        return self._truncate("\n".join(lines))

    def _requests(
        self,
        limit: int,
        status_filter: str = "",
        user_filter: str = "",
        request_id_filter: str = "",
    ) -> str:
        has_filters = bool(status_filter or user_filter or request_id_filter)
        load_limit = max(limit, 200) if has_filters else limit
        status, data, raw = self._admin_request("GET", f"/admin/requests?limit={load_limit}")
        if status != 200:
            return self._format_error(status, data, raw)
        items = data.get("requests") or []
        if not items:
            return "No workflow requests are currently available."
        filtered = self._filter_requests(
            items,
            status_filter=status_filter,
            user_filter=user_filter,
            request_id_filter=request_id_filter,
        )
        if not filtered:
            return "No workflow requests match the current filters."

        lines = [f"Workflow requests (showing {min(len(filtered), limit)} of {len(filtered)} matches):"]
        for item in filtered[:limit]:
            lines.append(
                f"- {item.get('id', '')}: {item.get('type', '')}, "
                f"user={item.get('created_by', '')}, "
                f"status={item.get('status', '')}, "
                f"owner={item.get('assigned_to', 'unassigned')}, "
                f"created={self._format_created_at(item.get('created_at', ''))}"
            )
        if len(filtered) > limit:
            lines.append(f"... and {len(filtered) - limit} more")
        return self._truncate("\n".join(lines))

    def _request_details(self, request_id_fragment: str) -> str:
        if not request_id_fragment:
            return "Usage: request get <request_id_fragment>"

        status, data, raw = self._admin_request("GET", "/admin/requests?limit=500")
        if status != 200:
            return self._format_error(status, data, raw)
        items = data.get("requests") or []
        matches = self._find_requests(items, request_id_fragment)
        if not matches:
            return "No workflow request matched that id fragment."
        if len(matches) > 1:
            preview = ", ".join(str(item.get("id", "")) for item in matches[:5])
            suffix = "" if len(matches) <= 5 else f", and {len(matches) - 5} more"
            return f"Multiple requests matched. Use more of the id: {preview}{suffix}"

        return self._truncate(self._format_request_details(matches[0]))

    def _request_update(self, payload: str) -> str:
        parts = payload.split()
        if len(parts) != 2:
            return "Usage: request update <request_id> <status>"
        request_id, status = parts[0].strip(), parts[1].strip().lower()
        if status not in VALID_STATUSES:
            valid = ", ".join(sorted(VALID_STATUSES))
            return f"Invalid status. Allowed values: {valid}"
        code, data, raw = self._admin_request(
            "PUT",
            f"/admin/requests/{request_id}/status",
            json={"status": status},
        )
        if code != 200:
            return self._format_error(code, data, raw)
        return f"Request {request_id} updated to {status}."

    def _admin_request(self, method: str, path: str, **kwargs) -> tuple[int, dict, str]:
        if not self.admin_token:
            return 500, {"detail": "Administrator access is not configured for this environment."}, ""

        url = f"{self.api_base_url}{path}"
        try:
            response = requests.request(
                method,
                url,
                headers={"X-Admin-Token": self.admin_token},
                timeout=self.timeout_seconds,
                **kwargs,
            )
        except requests.RequestException as exc:
            return 503, {"detail": self._api_unavailable_detail(exc)}, ""

        data = self._safe_json(response)
        return response.status_code, data, response.text

    def _admin_upload_document(self, file_name: str, file_bytes: bytes) -> tuple[int, dict, str]:
        if not self.admin_token:
            return 500, {"detail": "Administrator access is not configured for this environment."}, ""

        url = f"{self.api_base_url}/admin/documents"
        try:
            response = requests.post(
                url,
                headers={"X-Admin-Token": self.admin_token},
                files={"file": (file_name, file_bytes)},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            return 503, {"detail": self._api_unavailable_detail(exc)}, ""

        data = self._safe_json(response)
        return response.status_code, data, response.text

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

    def _api_unavailable_detail(self, exc: requests.RequestException) -> str:
        return (
            "The HR & IT Assistant API is not reachable from the Teams admin gateway. "
            f"Make sure the demo API is running at {self.api_base_url}, then try again. "
            f"Details: {exc}"
        )

    @staticmethod
    def _optional_int_arg(text: str, default: int) -> int:
        parts = text.split(maxsplit=1)
        if len(parts) == 1:
            return default
        try:
            parsed = int(parts[1].strip())
            return max(1, min(parsed, 500))
        except ValueError:
            return default

    @staticmethod
    def _parse_requests_command(text: str) -> dict:
        parts = text.split()
        result = {"limit": 20, "status": "", "user": "", "id": "", "error": ""}
        idx = 1
        if len(parts) > idx:
            try:
                result["limit"] = max(1, min(int(parts[idx]), 500))
                idx += 1
            except ValueError:
                pass

        while idx < len(parts):
            key = parts[idx].lower()
            if key not in {"status", "user", "id"}:
                result["error"] = (
                    "Usage: requests [limit] [status <status>] [user <user>] [id <request_id_fragment>]"
                )
                return result
            if idx + 1 >= len(parts):
                result["error"] = (
                    "Usage: requests [limit] [status <status>] [user <user>] [id <request_id_fragment>]"
                )
                return result
            value = parts[idx + 1].strip()
            if key == "status" and value.lower() not in VALID_STATUSES:
                valid = ", ".join(sorted(VALID_STATUSES))
                result["error"] = f"Invalid status. Allowed values: {valid}"
                return result
            result[key] = value
            idx += 2
        return result

    @staticmethod
    def _filter_requests(
        items: list[dict],
        status_filter: str = "",
        user_filter: str = "",
        request_id_filter: str = "",
    ) -> list[dict]:
        status = (status_filter or "").strip().lower()
        user = (user_filter or "").strip().lower()
        request_id = (request_id_filter or "").strip().lower()
        filtered: list[dict] = []
        for item in items:
            item_status = str(item.get("status", "")).strip().lower()
            item_user = str(item.get("created_by", "")).strip().lower()
            item_id = str(item.get("id", "")).strip().lower()
            if status and item_status != status:
                continue
            if user and user not in item_user:
                continue
            if request_id and request_id not in item_id:
                continue
            filtered.append(item)
        return filtered

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
                f"User: {item.get('created_by', '')}",
                f"Status: {item.get('status', '')}",
                f"Assigned to: {item.get('assigned_to', 'unassigned')}",
                f"Created at: {TeamsAdminHandler._format_created_at(item.get('created_at', ''))}",
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
    def _compact_preview(text: str, max_chars: int = 1200) -> str:
        cleaned = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[: max_chars - 3].rstrip() + "..."

    @staticmethod
    def _truncate(text: str, max_chars: int = 3500) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3] + "..."

    @staticmethod
    def _user_id(activity: dict) -> str:
        from_data = activity.get("from") or {}
        return str(from_data.get("id") or "unknown-user")

    @staticmethod
    def _session_id(activity: dict) -> str:
        conversation = activity.get("conversation") or {}
        conv_id = str(conversation.get("id") or "unknown-conversation")
        user_id = TeamsAdminHandler._user_id(activity)
        return f"{conv_id}:{user_id}"

    @staticmethod
    def _help_text(is_authenticated: bool) -> str:
        auth_state = "authenticated" if is_authenticated else "not authenticated"
        return (
            f"HR & IT Assistant for Teams: Admin Console ({auth_state})\n"
            "Authentication:\n"
            "- login <ADMIN_TOKEN>\n"
            "- logout\n\n"
            "Help:\n"
            "- help docs\n"
            "- help requests\n\n"
            "Core commands:\n"
            "- prompt get\n"
            "- prompt set <text>\n"
            "- docs list\n"
            "- docs preview <document_name>\n"
            "- docs upload <file_name> ::: <content>\n"
            "- docs delete <document_name>\n"
            "- index rebuild\n"
            "- logs [limit]\n"
            "- requests [limit] [status <status>] [user <user>] [id <request_id_fragment>]\n"
            "- request get <request_id_fragment>\n"
            "- request update <request_id> <status>"
        )

    @staticmethod
    def _docs_help_text() -> str:
        return (
            "Teams admin document commands\n"
            "- docs list: show uploaded knowledge base documents\n"
            "- docs preview <document_name>: show owner, effective date, and preview text\n"
            "- docs upload <file_name> ::: <content>: upload a small text document\n"
            "- docs delete <document_name>: delete a document\n"
            "- index rebuild: refresh retrieval after uploading or deleting documents"
        )

    @staticmethod
    def _requests_help_text() -> str:
        valid = ", ".join(sorted(VALID_STATUSES))
        return (
            "Teams admin workflow request commands\n"
            "- requests: show recent workflow requests\n"
            "- requests 10 status pending: show pending requests\n"
            "- requests 20 user alice: filter by user\n"
            "- requests 20 id abc123: filter by request id fragment\n"
            "- request get <request_id_fragment>: show request details\n"
            "- request update <request_id> <status>: update status\n"
            f"Allowed statuses: {valid}"
        )
