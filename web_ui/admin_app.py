from __future__ import annotations

import html
import os
from datetime import datetime
from urllib.parse import quote

import requests
import streamlit as st

from .api_client import DemoAPIClient


ENV_ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()
STATUS_FILTER_OPTIONS = ["all", "new", "pending", "approved", "declined", "done"]


def _format_loaded_at(value: datetime) -> str:
    return value.strftime("%H:%M:%S")


def _format_file_size(size_raw: object) -> str:
    try:
        size = int(size_raw)
    except (TypeError, ValueError):
        return "unknown"
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _filter_workflow_requests(
    requests_data: list[dict],
    status_filter: str,
    request_query: str,
    user_query: str,
) -> list[dict]:
    status = (status_filter or "all").strip().lower()
    request_term = (request_query or "").strip().lower()
    user_term = (user_query or "").strip().lower()
    filtered: list[dict] = []
    for item in requests_data:
        item_status = str(item.get("status", "")).strip().lower()
        request_id = str(item.get("id", "")).strip().lower()
        created_by = str(item.get("created_by", "")).strip().lower()
        if status != "all" and item_status != status:
            continue
        if request_term and request_term not in request_id:
            continue
        if user_term and user_term not in created_by:
            continue
        filtered.append(item)
    return filtered


def _format_preview_text(text: str, truncated: bool) -> str:
    cleaned = (text or "").strip()
    if truncated and cleaned:
        return cleaned + "\n\n[Preview truncated]"
    if truncated:
        return "[Preview truncated]"
    return cleaned


def _shorten_request_id(request_id: object, visible_chars: int = 8) -> str:
    text = str(request_id or "").strip()
    if len(text) <= visible_chars:
        return text
    return f"{text[:visible_chars]}..."


def _format_created_at(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    date_part, _, time_part = text.replace("T", " ").partition(" ")
    if not time_part:
        return date_part
    return f"{date_part} {time_part.split('.')[0]}"


def _truncate_cell(value: object, max_chars: int = 72) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _table_header_cell(label: str) -> str:
    return f'<div class="admin-table-header-cell">{label}</div>'


def _table_body_cell(value: object, *, compact: bool = False) -> str:
    safe_value = html.escape(str(value or ""))
    classes = "admin-table-body-cell"
    if compact:
        classes += " admin-table-body-cell--compact"
    return f'<div class="{classes}"><span>{safe_value}</span></div>'


def main() -> None:
    st.set_page_config(page_title="Administration Console", layout="wide")
    st.title("Administration Console")
    st.caption("Manage prompt configuration, source documents, audit logs, and workflow requests for the demo environment.")
    st.markdown(
        """
        <style>
        .admin-table-header-cell {
            height: 3.45rem;
            box-sizing: border-box;
            display: flex;
            align-items: center;
            padding: 0.52rem 0.62rem;
            border: 1px solid #343946;
            background: #20232b;
            color: #f4f7fb;
            font-weight: 700;
            font-size: 0.92rem;
            line-height: 1.25;
            overflow-wrap: anywhere;
            box-shadow: inset 0 -1px 0 rgba(255, 255, 255, 0.03);
        }

        .admin-table-body-cell {
            height: 5.15rem;
            box-sizing: border-box;
            display: flex;
            align-items: center;
            padding: 0.78rem 0.62rem;
            border-left: 1px solid #232a36;
            border-right: 1px solid #232a36;
            border-bottom: 1px solid #171d27;
            color: #f6f8fc;
            line-height: 1.45;
            overflow-wrap: break-word;
            overflow: hidden;
        }

        .admin-table-body-cell span {
            display: -webkit-box;
            -webkit-box-orient: vertical;
            -webkit-line-clamp: 3;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .admin-table-body-cell--compact span {
            display: block;
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        div[data-testid="stHorizontalBlock"]:has(.admin-table-body-cell) {
            align-items: stretch;
            gap: 0 !important;
            margin: 0 !important;
        }

        .st-key-workflow_request_table {
            row-gap: 0 !important;
        }

        .st-key-workflow_request_table div[data-testid="stVerticalBlock"] {
            gap: 0 !important;
        }

        .st-key-workflow_request_table [data-testid="stElementContainer"] {
            margin: 0 !important;
            padding: 0 !important;
        }

        .st-key-workflow_request_table div[data-testid="stHorizontalBlock"]:has(.admin-table-header-cell),
        .st-key-workflow_request_table div[data-testid="stHorizontalBlock"]:has(.admin-table-body-cell) {
            margin: 0 !important;
            padding: 0 !important;
        }

        div[data-testid="stHorizontalBlock"]:has(.admin-table-body-cell) > div:has([role="combobox"]),
        div[data-testid="stHorizontalBlock"]:has(.admin-table-body-cell) > div:has(button) {
            height: 5.15rem;
            box-sizing: border-box;
            display: flex !important;
            flex-direction: column;
            justify-content: center;
            padding: 1.15rem 0.3rem;
            border-left: 1px solid #232a36;
            border-right: 1px solid #232a36;
            border-bottom: 1px solid #171d27;
            overflow: hidden;
        }

        div[data-testid="stHorizontalBlock"]:has(.admin-table-body-cell) > div:has([role="combobox"]) {
            align-items: stretch;
        }

        div[data-testid="stHorizontalBlock"]:has(.admin-table-body-cell) > div:has(button) {
            align-items: center;
        }

        .st-key-workflow_request_table div[data-testid="stHorizontalBlock"]:has(.admin-table-body-cell) > div:nth-child(9) {
            align-items: center !important;
            justify-content: center !important;
            padding-left: 0.3rem;
            padding-right: 0.3rem;
        }

        div[data-testid="stHorizontalBlock"]:has(.admin-table-body-cell) > div:has([role="combobox"]) > div,
        div[data-testid="stHorizontalBlock"]:has(.admin-table-body-cell) > div:has(button) > div {
            width: 100%;
        }

        div[data-testid="stHorizontalBlock"]:has(.admin-table-body-cell) > div:has(button) [data-testid="stButton"] {
            width: 100%;
            margin: 0;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }

        div[data-testid="stHorizontalBlock"]:has(.admin-table-body-cell) > div:has(button) button {
            width: auto;
            margin: 0 auto !important;
            white-space: nowrap;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    api_client = DemoAPIClient(timeout_seconds=30)

    if "admin_token" not in st.session_state:
        st.session_state.admin_token = ENV_ADMIN_TOKEN
    if "index_rebuild_needed" not in st.session_state:
        st.session_state.index_rebuild_needed = False
    if "documents_loaded_at" not in st.session_state:
        st.session_state.documents_loaded_at = ""
    if "workflow_requests_loaded_at" not in st.session_state:
        st.session_state.workflow_requests_loaded_at = ""

    with st.sidebar:
        st.subheader("Access")
        token = st.text_input(
            "Administrator token",
            type="password",
            value=st.session_state.admin_token,
        )
        if st.button("Save Token"):
            st.session_state.admin_token = token.strip()
        if st.session_state.admin_token:
            st.success("Administrator token is loaded.")
        else:
            st.info("Provide the administrator token to enable privileged actions.")

    token = st.session_state.admin_token

    st.divider()
    st.subheader("System Prompt")
    col_prompt, col_actions = st.columns([3, 1])
    with col_actions:
        if st.button("Load Current Prompt"):
            resp = _admin_request(api_client, "GET", "/admin/system-prompt", token)
            if resp is not None:
                if resp.status_code == 200:
                    st.session_state.system_prompt = resp.json().get("system_prompt", "")
                else:
                    st.error(f"Unable to load the system prompt: {resp.status_code} {resp.text}")

    prompt_value = st.session_state.get("system_prompt", "")
    new_prompt = col_prompt.text_area("System prompt", value=prompt_value, height=240)
    if col_prompt.button("Save Prompt"):
        resp = _admin_request(
            api_client,
            "PUT",
            "/admin/system-prompt",
            token,
            json={"system_prompt": new_prompt},
        )
        if resp is not None:
            if resp.status_code == 200:
                st.success("The system prompt was updated successfully.")
            else:
                st.error(f"Unable to save the system prompt: {resp.status_code} {resp.text}")

    st.divider()
    st.subheader("Knowledge Base Documents")
    col_docs, col_upload = st.columns([3, 1])

    with col_upload:
        uploaded = st.file_uploader("Upload document", type=["txt", "md", "pdf", "docx"])
        if st.button("Upload Document"):
            if not uploaded:
                st.warning("Select a document before uploading.")
            else:
                resp = _admin_request(
                    api_client,
                    "POST",
                    "/admin/documents",
                    token,
                    files={"file": (uploaded.name, uploaded.getvalue())},
                )
                if resp is not None:
                    if resp.status_code == 200:
                        st.success(f"Document uploaded: {uploaded.name}")
                        st.session_state.index_rebuild_needed = True
                        st.warning("Rebuild the vector index before expecting this document in chat answers.")
                    else:
                        st.error(f"Document upload failed: {resp.status_code} {resp.text}")

    if col_docs.button("Refresh Document List"):
        resp = _admin_request(api_client, "GET", "/admin/documents", token)
        if resp is not None:
            if resp.status_code == 200:
                st.session_state.documents = resp.json().get("documents", [])
                st.session_state.documents_loaded_at = _format_loaded_at(datetime.now())
            else:
                st.error(f"Unable to load documents: {resp.status_code} {resp.text}")

    documents = st.session_state.get("documents", [])
    documents_loaded_at = st.session_state.get("documents_loaded_at", "")
    if documents_loaded_at:
        st.caption(f"Document list loaded at {documents_loaded_at}. Click Refresh Document List to refresh.")
    if documents:
        selected_doc = st.selectbox(
            "Preview document",
            options=[doc.get("name", "") for doc in documents],
            index=0,
        )
        if st.button("Load Document Preview"):
            resp = _admin_request(
                api_client,
                "GET",
                f"/admin/documents/{quote(selected_doc)}",
                token,
            )
            if resp is not None:
                if resp.status_code == 200:
                    st.session_state.document_preview = resp.json().get("document", {})
                else:
                    st.error(f"Unable to preview document: {resp.status_code} {resp.text}")

        preview = st.session_state.get("document_preview", {})
        if preview:
            meta_cols = st.columns([2, 2, 1])
            meta_cols[0].metric("Owner", preview.get("owner") or "Not found")
            meta_cols[1].metric("Effective Date", preview.get("effective_date") or "Not found")
            meta_cols[2].metric("Size", f"{preview.get('size', 0)} bytes")
            st.text_area(
                "Document preview",
                value=_format_preview_text(
                    str(preview.get("text", "")),
                    bool(preview.get("truncated", False)),
                ),
                height=260,
                disabled=True,
            )

        doc_header = st.columns([4, 1, 2, 1])
        doc_header[0].markdown("**Document**")
        doc_header[1].markdown("**Size**")
        doc_header[2].markdown("**Modified**")
        doc_header[3].markdown("**Action**")
        for doc in documents:
            name = doc.get("name", "")
            size = doc.get("size", 0)
            modified = doc.get("modified", "")
            row = st.columns([4, 1, 2, 1])
            row[0].write(name)
            row[1].write(_format_file_size(size))
            row[2].write(_format_created_at(modified))
            if row[3].button("Delete", key=f"del-{name}"):
                resp = _admin_request(api_client, "DELETE", f"/admin/documents/{quote(name)}", token)
                if resp is not None:
                    if resp.status_code == 200:
                        st.success(f"Document deleted: {name}")
                        st.session_state.index_rebuild_needed = True
                        st.warning("Rebuild the vector index so deleted content is no longer used in chat answers.")
                    else:
                        st.error(f"Document deletion failed: {resp.status_code} {resp.text}")
    else:
        st.caption("No documents have been loaded yet.")

    st.divider()
    st.subheader("Vector Index")
    if st.session_state.index_rebuild_needed:
        st.warning("Document changes are pending. Rebuild the index to update chat retrieval.")
    if st.button("Rebuild Index"):
        resp = _admin_request(api_client, "POST", "/admin/rebuild-index", token)
        if resp is not None:
            if resp.status_code == 200:
                st.success("The vector index rebuild completed successfully.")
                st.session_state.index_rebuild_needed = False
            else:
                st.error(f"Unable to rebuild the vector index: {resp.status_code} {resp.text}")

    st.divider()
    st.subheader("Conversation Logs")
    st.caption("User text may be masked depending on LOG_USER_TEXT_MODE.")
    limit = st.slider("Log entries", min_value=10, max_value=500, value=100, step=10)
    if st.button("Load Logs"):
        resp = _admin_request(api_client, "GET", f"/admin/logs?limit={limit}", token)
        if resp is not None:
            if resp.status_code == 200:
                st.session_state.logs = resp.json().get("logs", [])
            else:
                st.error(f"Unable to load logs: {resp.status_code} {resp.text}")

    logs = st.session_state.get("logs", [])
    if logs:
        st.dataframe(logs, use_container_width=True)
    else:
        st.caption("No log entries are available.")

    st.divider()
    st.subheader("Workflow Requests")
    req_limit = st.slider(
        "Request entries",
        min_value=10,
        max_value=500,
        value=100,
        step=10,
    )
    if st.button("Load Requests"):
        resp = _admin_request(api_client, "GET", f"/admin/requests?limit={req_limit}", token)
        if resp is not None:
            if resp.status_code == 200:
                st.session_state.workflow_requests = resp.json().get("requests", [])
                st.session_state.workflow_requests_loaded_at = _format_loaded_at(datetime.now())
            else:
                st.error(f"Unable to load workflow requests: {resp.status_code} {resp.text}")

    workflow_requests = st.session_state.get("workflow_requests", [])
    loaded_at = st.session_state.get("workflow_requests_loaded_at", "")
    if loaded_at:
        st.caption(f"Loaded at {loaded_at}. Click Load Requests to refresh.")
    if workflow_requests:
        filter_cols = st.columns([1, 2, 2])
        status_filter = filter_cols[0].selectbox(
            "Status filter",
            options=STATUS_FILTER_OPTIONS,
            index=0,
        )
        request_query = filter_cols[1].text_input("Search request ID")
        user_query = filter_cols[2].text_input("Search user")
        filtered_requests = _filter_workflow_requests(
            workflow_requests,
            status_filter,
            request_query,
            user_query,
        )

        st.caption(
            f"Showing {len(filtered_requests)} of {len(workflow_requests)} loaded requests. "
            "Select a new status and click Update to persist the change."
        )
        table_columns = [1.15, 0.95, 1.05, 0.95, 1.1, 1.35, 1.35, 1.35, 1.2]
        with st.container(key="workflow_request_table", gap=None):
            header_cols = st.columns(table_columns, gap=None, vertical_alignment="center")
            header_labels = [
                "Request ID",
                "Type",
                "User",
                "Current Status",
                "Owner",
                "Created At",
                "Comment",
                "New Status",
                "Action",
            ]
            for col, label in zip(header_cols, header_labels):
                col.markdown(_table_header_cell(label), unsafe_allow_html=True)
            for req in filtered_requests:
                status_options = ["new", "pending", "approved", "declined", "done"]
                current_status = (req.get("status") or "pending").lower()
                status_index = (
                    status_options.index(current_status)
                    if current_status in status_options
                    else 1
                )
                cols = st.columns(table_columns, gap=None, vertical_alignment="center")
                cols[0].markdown(
                    _table_body_cell(_shorten_request_id(req.get("id", "")), compact=True),
                    unsafe_allow_html=True,
                )
                cols[1].markdown(_table_body_cell(req.get("type", ""), compact=True), unsafe_allow_html=True)
                cols[2].markdown(
                    _table_body_cell(_truncate_cell(req.get("created_by", ""), max_chars=28)),
                    unsafe_allow_html=True,
                )
                cols[3].markdown(_table_body_cell(req.get("status", ""), compact=True), unsafe_allow_html=True)
                cols[4].markdown(
                    _table_body_cell(_truncate_cell(req.get("assigned_to", ""), max_chars=28)),
                    unsafe_allow_html=True,
                )
                cols[5].markdown(
                    _table_body_cell(_format_created_at(req.get("created_at", ""))),
                    unsafe_allow_html=True,
                )
                cols[6].markdown(
                    _table_body_cell(_truncate_cell(req.get("comment", ""), max_chars=54)),
                    unsafe_allow_html=True,
                )
                new_status = cols[7].selectbox(
                    "Status",
                    options=status_options,
                    index=status_index,
                    key=f"status-{req.get('id', '')}",
                    label_visibility="collapsed",
                )
                action_left, action_button_col, action_right = cols[8].columns(
                    [1, 2, 1],
                    gap=None,
                    vertical_alignment="center",
                )
                if action_button_col.button("Update", key=f"update-{req.get('id', '')}"):
                    resp = _admin_request(
                        api_client,
                        "PUT",
                        f"/admin/requests/{req.get('id', '')}/status",
                        token,
                        json={"status": new_status},
                    )
                    if resp is not None:
                        if resp.status_code == 200:
                            st.success(f"Workflow request updated: {req.get('id', '')}")
                            req["status"] = new_status
                        else:
                            st.error(f"Workflow update failed: {resp.status_code} {resp.text}")
        if not filtered_requests:
            st.caption("No workflow requests match the current filters.")
    else:
        st.caption("No workflow requests are available.")


def _admin_request(
    api_client: DemoAPIClient,
    method: str,
    path: str,
    token: str | None,
    **kwargs,
) -> requests.Response | None:
    try:
        return api_client.admin_request(method, path, token, **kwargs)
    except requests.RequestException as exc:
        st.error(f"API request failed: {exc}")
        return None


if __name__ == "__main__":
    main()
