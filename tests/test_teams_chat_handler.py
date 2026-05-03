import unittest
from unittest.mock import patch

import requests

from teams_ui.chat_handler import TeamsChatHandler


class StubResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self) -> dict:
        return self._payload


def _activity(text: str) -> dict:
    return {
        "text": text,
        "conversation": {"id": "conversation-1"},
        "from": {"id": "alice"},
    }


def _requests_payload() -> dict:
    return {
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
            }
        ]
    }


class TeamsChatHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.handler = TeamsChatHandler(api_base_url="http://testserver")

    @patch("teams_ui.chat_handler.requests.get")
    def test_requests_command_shows_owner_and_created_at(self, mock_get) -> None:
        mock_get.return_value = StubResponse(200, _requests_payload())

        reply = self.handler.handle_activity(_activity("requests"))

        self.assertIn("abc-123", reply)
        self.assertIn("owner=IT Support", reply)
        self.assertIn("created=2026-05-02 14:00:00", reply)

    @patch("teams_ui.chat_handler.requests.get")
    def test_request_details_command_shows_full_request(self, mock_get) -> None:
        mock_get.return_value = StubResponse(200, _requests_payload())

        reply = self.handler.handle_activity(_activity("request abc"))

        self.assertIn("Workflow request details:", reply)
        self.assertIn("ID: abc-123", reply)
        self.assertIn("Type: Access", reply)
        self.assertIn("Assigned to: IT Support", reply)
        self.assertIn("Comment: I need access to the payroll system", reply)

    @patch("teams_ui.chat_handler.requests.get")
    def test_request_details_reports_missing_match(self, mock_get) -> None:
        mock_get.return_value = StubResponse(200, _requests_payload())

        reply = self.handler.handle_activity(_activity("request missing"))

        self.assertIn("No workflow request matched", reply)

    def test_help_lists_request_details_command(self) -> None:
        reply = self.handler.handle_activity(_activity("help"))

        self.assertIn("request <request_id_fragment>", reply)
        self.assertIn("I need access to the payroll system", reply)

    def test_help_requests_lists_creation_examples(self) -> None:
        reply = self.handler.handle_activity(_activity("help requests"))

        self.assertIn("Teams request commands", reply)
        self.assertIn("requests: list your workflow requests", reply)
        self.assertIn("Please replace my broken laptop", reply)

    @patch("teams_ui.chat_handler.requests.post")
    def test_unknown_slash_command_is_not_sent_to_assistant(self, mock_post) -> None:
        reply = self.handler.handle_activity(_activity("/not-a-command"))

        self.assertIn("I do not recognize that Teams command", reply)
        mock_post.assert_not_called()

    @patch("teams_ui.chat_handler.requests.get")
    def test_requests_command_reports_api_unavailable_clearly(self, mock_get) -> None:
        mock_get.side_effect = requests.Timeout("timed out")

        reply = self.handler.handle_activity(_activity("requests"))

        self.assertIn("I cannot reach the HR & IT Assistant API", reply)
        self.assertIn("http://testserver", reply)


if __name__ == "__main__":
    unittest.main()
