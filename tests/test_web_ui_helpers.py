import os
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from web_ui.api_client import DemoAPIClient, extract_assistant_sources
from web_ui.admin_app import (
    _filter_workflow_requests,
    _format_created_at as _format_admin_created_at,
    _format_file_size,
    _format_loaded_at,
    _format_preview_text,
    _shorten_request_id as _shorten_admin_request_id,
    _table_body_cell,
    _table_header_cell,
    _truncate_cell,
)
from web_ui.demo_prompts import DEMO_PROMPTS, iter_demo_prompts
from web_ui.streamlit_app import (
    MAX_CONTEXT_MESSAGES,
    _build_chat_message_markup,
    _build_messages_payload,
    _build_typing_message_markup,
    _format_source_name,
    _format_source_score,
    _format_user_request_rows,
)


class WebUIHelperTests(unittest.TestCase):
    def test_extract_assistant_sources_reads_chat_response_sources(self) -> None:
        data = {
            "message": {"role": "assistant", "content": "Salaries are paid twice per month."},
            "sources": [
                {
                    "source": "Payroll_FAQ.md",
                    "chunk_id": 0,
                    "text": "Salaries are paid twice per month.",
                    "score": 0.873,
                }
            ],
        }

        sources = extract_assistant_sources(data)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["source"], "Payroll_FAQ.md")
        self.assertEqual(sources[0]["chunk_id"], 0)
        self.assertAlmostEqual(sources[0]["score"], 0.873)

    def test_extract_assistant_sources_ignores_invalid_payload(self) -> None:
        sources = extract_assistant_sources({"message": {"content": "Hello"}})
        self.assertEqual(sources, [])

    def test_build_messages_payload_keeps_latest_valid_turns(self) -> None:
        history = []
        for idx in range(MAX_CONTEXT_MESSAGES + 3):
            history.append({"role": "user", "content": f"user-{idx}"})
        history.append({"role": "tool", "content": "ignore-me"})
        history.append({"role": "assistant", "content": "assistant-final", "sources": []})

        payload = _build_messages_payload(history, "new-question")

        self.assertEqual(len(payload), MAX_CONTEXT_MESSAGES)
        self.assertEqual(payload[-1], {"role": "user", "content": "new-question"})
        self.assertNotIn({"role": "tool", "content": "ignore-me"}, payload)

    def test_build_chat_message_markup_aligns_user_to_the_right(self) -> None:
        markup = _build_chat_message_markup(
            "user",
            "Hello <world>",
            "data:image/png;base64,user",
        )

        self.assertIn('class="chat-row user-row"', markup)
        self.assertIn('class="chat-stack user-stack"', markup)
        self.assertIn('class="user-bubble">Hello &lt;world&gt;</div>', markup)
        self.assertNotIn("\n", markup)

    def test_build_chat_message_markup_renders_assistant_sources(self) -> None:
        markup = _build_chat_message_markup(
            "assistant",
            "Payroll answer",
            "data:image/png;base64,assistant",
            sources=[
                {
                    "source": "Payroll_FAQ.md",
                    "chunk_id": 0,
                    "score": 0.87,
                    "text": "Employees are paid twice per month.",
                }
            ],
        )

        self.assertIn('class="chat-row assistant-row"', markup)
        self.assertIn("Sources used", markup)
        self.assertIn("Payroll FAQ", markup)
        self.assertIn("Payroll_FAQ.md - chunk 0", markup)
        self.assertIn("Relevance 87%", markup)

    def test_source_metadata_is_human_readable(self) -> None:
        self.assertEqual(_format_source_name("Payroll_FAQ.md"), "Payroll FAQ")
        self.assertEqual(_format_source_name(""), "Source")
        self.assertEqual(_format_source_score(0.873), "Relevance 87%")
        self.assertEqual(_format_source_score("not-a-number"), "Relevance unknown")

    def test_build_chat_message_markup_can_render_typing_cursor(self) -> None:
        markup = _build_chat_message_markup(
            "assistant",
            "Streaming answer",
            "data:image/png;base64,assistant",
            show_cursor=True,
        )

        self.assertIn("typing-caret", markup)

    def test_build_typing_message_markup_renders_typing_bubble(self) -> None:
        markup = _build_typing_message_markup("data:image/png;base64,assistant")

        self.assertIn("typing-bubble", markup)
        self.assertIn("typing-dots", markup)

    def test_demo_prompt_pack_has_expected_size_and_coverage(self) -> None:
        prompts = iter_demo_prompts(DEMO_PROMPTS)

        self.assertEqual(len(prompts), 28)
        self.assertEqual(len(prompts), len(set(prompts)))
        self.assertEqual(len(DEMO_PROMPTS), 8)
        self.assertIn("Hello", prompts)
        self.assertIn("Hi there", prompts)
        self.assertIn("I need access to the payroll system", prompts)
        self.assertIn("Please replace my broken laptop", prompts)
        self.assertIn(
            "I am blocked during onboarding because my account setup is not complete",
            prompts,
        )
        self.assertIn("Write me a poem about dragons.", prompts)
        self.assertIn("What's the weather in Los Angeles today?", prompts)

    def test_demo_api_client_reads_api_base_url_at_init_time(self) -> None:
        original_api_base_url = os.environ.get("API_BASE_URL")
        try:
            os.environ["API_BASE_URL"] = "http://127.0.0.1:8016"
            client = DemoAPIClient()
        finally:
            if original_api_base_url is None:
                os.environ.pop("API_BASE_URL", None)
            else:
                os.environ["API_BASE_URL"] = original_api_base_url

        self.assertEqual(client.api_base_url, "http://127.0.0.1:8016")

    @patch("web_ui.api_client.requests.Session")
    def test_demo_api_client_disables_env_proxies_for_loopback_urls(self, session_factory: MagicMock) -> None:
        session = MagicMock()
        session.request.return_value = object()
        session_factory.return_value = session

        client = DemoAPIClient(api_base_url="http://127.0.0.1:8016")
        client.request("GET", "/health")

        self.assertFalse(session.trust_env)
        session.request.assert_called_once()
        session.close.assert_called_once()

    @patch("web_ui.api_client.requests.Session")
    def test_demo_api_client_keeps_env_proxies_for_remote_urls(self, session_factory: MagicMock) -> None:
        session = MagicMock()
        session.request.return_value = object()
        session_factory.return_value = session

        client = DemoAPIClient(api_base_url="https://demo.example.com")
        client.request("GET", "/health")

        self.assertTrue(session.trust_env)
        session.request.assert_called_once()
        session.close.assert_called_once()

    def test_filter_workflow_requests_matches_status_id_and_user(self) -> None:
        items = [
            {"id": "abc-123", "status": "pending", "created_by": "alice"},
            {"id": "def-456", "status": "approved", "created_by": "bob"},
            {"id": "abc-789", "status": "pending", "created_by": "carol"},
        ]

        filtered = _filter_workflow_requests(
            items,
            status_filter="pending",
            request_query="abc",
            user_query="ali",
        )

        self.assertEqual(filtered, [items[0]])

    def test_format_preview_text_marks_truncated_preview(self) -> None:
        self.assertEqual(
            _format_preview_text("Document body", truncated=True),
            "Document body\n\n[Preview truncated]",
        )

    def test_user_request_rows_hide_raw_payload_noise(self) -> None:
        rows = _format_user_request_rows(
            [
                {
                    "id": "abcdef1234567890",
                    "type": "Access",
                    "status": "pending",
                    "assigned_to": "IT Support",
                    "created_at": "2026-05-02T15:28:17.161947+00:00",
                    "period_or_date": "unspecified",
                    "comment": "I need access to the payroll system",
                }
            ]
        )

        self.assertEqual(
            rows,
            [
                {
                    "Request": "abcdef12...",
                    "Type": "Access",
                    "Status": "pending",
                    "Owner": "IT Support",
                    "Created": "2026-05-02 15:28:17",
                    "Period": "unspecified",
                    "Comment": "I need access to the payroll system",
                }
            ],
        )

    def test_admin_request_cells_are_compact(self) -> None:
        self.assertEqual(_shorten_admin_request_id("abcdef1234567890"), "abcdef12...")
        self.assertEqual(
            _format_admin_created_at("2026-05-02T15:28:17.161947+00:00"),
            "2026-05-02 15:28:17",
        )
        self.assertEqual(_truncate_cell("short", max_chars=10), "short")
        self.assertEqual(_truncate_cell("one two three four", max_chars=10), "one two...")

    def test_loaded_at_label_uses_local_clock_time(self) -> None:
        self.assertEqual(_format_loaded_at(datetime(2026, 5, 2, 19, 42, 10)), "19:42:10")

    def test_file_size_is_compact_for_document_rows(self) -> None:
        self.assertEqual(_format_file_size(512), "512 B")
        self.assertEqual(_format_file_size(20320), "19.8 KB")
        self.assertEqual(_format_file_size("bad"), "unknown")

    def test_table_header_cell_uses_admin_header_class(self) -> None:
        self.assertEqual(
            _table_header_cell("Request ID"),
            '<div class="admin-table-header-cell">Request ID</div>',
        )

    def test_table_body_cell_escapes_visible_values(self) -> None:
        self.assertEqual(
            _table_body_cell("Access <script>"),
            '<div class="admin-table-body-cell"><span>Access &lt;script&gt;</span></div>',
        )
        self.assertEqual(
            _table_body_cell("abcdef12...", compact=True),
            '<div class="admin-table-body-cell admin-table-body-cell--compact"><span>abcdef12...</span></div>',
        )


if __name__ == "__main__":
    unittest.main()
