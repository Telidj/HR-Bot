import unittest
from unittest.mock import patch

import requests

from teams_ui.admin_handler import TeamsAdminHandler


class StubTeamsAdminHandler(TeamsAdminHandler):
    def __init__(self) -> None:
        super().__init__(
            api_base_url="http://testserver",
            admin_token="demo-admin-token",
            require_login=False,
        )
        self.deleted_document = ""

    def _admin_request(self, method: str, path: str, **kwargs) -> tuple[int, dict, str]:
        if method == "GET" and path == "/admin/documents/Payroll_FAQ.md":
            return 200, {
                "document": {
                    "name": "Payroll_FAQ.md",
                    "owner": "Finance and Payroll Operations",
                    "effective_date": "March 1, 2026",
                    "text": "# Payroll\nSalaries are paid twice per month.",
                    "truncated": False,
                }
            }, ""

        if method == "GET" and path.startswith("/admin/requests"):
            return 200, {
                "requests": [
                    {
                        "id": "abc-123",
                        "type": "Access",
                        "created_by": "alice",
                        "period_or_date": "unspecified",
                        "comment": "I need access to the payroll system",
                        "status": "pending",
                        "assigned_to": "IT Support",
                        "created_at": "2026-05-02T14:00:00.123456+00:00",
                    },
                    {
                        "id": "def-456",
                        "type": "Equipment",
                        "created_by": "bob",
                        "period_or_date": "unspecified",
                        "comment": "My laptop is broken",
                        "status": "pending",
                        "assigned_to": "IT Support",
                        "created_at": "2026-05-02T14:05:00.123456+00:00",
                    },
                    {
                        "id": "abc-789",
                        "type": "Document",
                        "created_by": "alice",
                        "period_or_date": "today",
                        "comment": "I need an employment letter",
                        "status": "done",
                        "assigned_to": "HR",
                        "created_at": "2026-05-02T14:10:00.123456+00:00",
                    },
                ]
            }, ""

        if method == "DELETE" and path == "/admin/documents/Old.md":
            self.deleted_document = "Old.md"
            return 200, {"status": "ok"}, ""

        return 404, {"detail": "not found"}, ""

    def _admin_upload_document(self, file_name: str, file_bytes: bytes) -> tuple[int, dict, str]:
        return 200, {"name": file_name}, ""


def _activity(text: str) -> dict:
    return {
        "text": text,
        "conversation": {"id": "conversation-1"},
        "from": {"id": "admin-user"},
    }


class TeamsAdminHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.handler = StubTeamsAdminHandler()

    def test_docs_preview_command_shows_metadata_and_text(self) -> None:
        reply = self.handler.handle_activity(_activity("docs preview Payroll_FAQ.md"))

        self.assertIn("Document preview: Payroll_FAQ.md", reply)
        self.assertIn("Owner: Finance and Payroll Operations", reply)
        self.assertIn("Effective Date: March 1, 2026", reply)
        self.assertIn("Salaries are paid twice per month.", reply)

    def test_requests_command_filters_by_status_user_and_id(self) -> None:
        reply = self.handler.handle_activity(
            _activity("requests status pending user ali id abc")
        )

        self.assertIn("abc-123", reply)
        self.assertIn("Access", reply)
        self.assertIn("owner=IT Support", reply)
        self.assertIn("created=2026-05-02 14:00:00", reply)
        self.assertNotIn("def-456", reply)
        self.assertNotIn("abc-789", reply)

    def test_request_get_command_shows_full_request_details(self) -> None:
        reply = self.handler.handle_activity(_activity("request get def"))

        self.assertIn("Workflow request details:", reply)
        self.assertIn("ID: def-456", reply)
        self.assertIn("Type: Equipment", reply)
        self.assertIn("User: bob", reply)
        self.assertIn("Assigned to: IT Support", reply)
        self.assertIn("Comment: My laptop is broken", reply)

    def test_request_get_reports_multiple_matches(self) -> None:
        reply = self.handler.handle_activity(_activity("request get abc"))

        self.assertIn("Multiple requests matched", reply)
        self.assertIn("abc-123", reply)
        self.assertIn("abc-789", reply)

    def test_docs_upload_warns_to_rebuild_index(self) -> None:
        reply = self.handler.handle_activity(_activity("docs upload New.md ::: hello"))

        self.assertIn("Document uploaded successfully: New.md", reply)
        self.assertIn("Rebuild the vector index", reply)

    def test_docs_delete_warns_to_rebuild_index(self) -> None:
        reply = self.handler.handle_activity(_activity("docs delete Old.md"))

        self.assertEqual(self.handler.deleted_document, "Old.md")
        self.assertIn("Document deleted: Old.md", reply)
        self.assertIn("Rebuild the vector index", reply)

    def test_help_lists_admin_filter_and_preview_commands(self) -> None:
        reply = self.handler.handle_activity(_activity("help"))

        self.assertIn("docs preview <document_name>", reply)
        self.assertIn("requests [limit] [status <status>] [user <user>] [id <request_id_fragment>]", reply)
        self.assertIn("request get <request_id_fragment>", reply)

    def test_help_docs_lists_document_commands(self) -> None:
        reply = self.handler.handle_activity(_activity("help docs"))

        self.assertIn("Teams admin document commands", reply)
        self.assertIn("docs preview <document_name>", reply)
        self.assertIn("index rebuild", reply)

    def test_help_requests_lists_workflow_commands(self) -> None:
        reply = self.handler.handle_activity(_activity("help requests"))

        self.assertIn("Teams admin workflow request commands", reply)
        self.assertIn("requests 10 status pending", reply)
        self.assertIn("Allowed statuses:", reply)

    def test_unknown_admin_command_points_to_help_topics(self) -> None:
        reply = self.handler.handle_activity(_activity("wat"))

        self.assertIn("I do not recognize that Teams admin command", reply)
        self.assertIn("help docs", reply)
        self.assertIn("help requests", reply)

    def test_login_required_message_is_actionable(self) -> None:
        handler = TeamsAdminHandler(
            api_base_url="http://testserver",
            admin_token="demo-admin-token",
            require_login=True,
        )

        reply = handler.handle_activity(_activity("docs list"))

        self.assertIn("Authentication is required", reply)
        self.assertIn("login <ADMIN_TOKEN>", reply)

    @patch("teams_ui.admin_handler.requests.request")
    def test_admin_api_unavailable_message_is_actionable(self, mock_request) -> None:
        mock_request.side_effect = requests.Timeout("timed out")
        handler = TeamsAdminHandler(
            api_base_url="http://testserver",
            admin_token="demo-admin-token",
            require_login=False,
        )

        reply = handler.handle_activity(_activity("prompt get"))

        self.assertIn("Service error (503)", reply)
        self.assertIn("The HR & IT Assistant API is not reachable", reply)
        self.assertIn("http://testserver", reply)


if __name__ == "__main__":
    unittest.main()
