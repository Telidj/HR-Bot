import tempfile
import unittest
from pathlib import Path

from workflow import WorkflowService


class WorkflowServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_context = tempfile.TemporaryDirectory(prefix=f'{self._testMethodName}-')
        self.temp_dir = Path(self.temp_context.name)
        self.db_path = self.temp_dir / 'workflow.db'
        self.service = WorkflowService(str(self.db_path))

    def tearDown(self) -> None:
        self.temp_context.cleanup()

    def test_creates_pto_request_for_vacation_dates(self) -> None:
        result = self.service.try_create(
            'I need vacation from 01/04 to 03/04',
            created_by='demo-user',
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'PTO')
        self.assertEqual(result['period_or_date'], 'from 01/04 to 03/04')
        self.assertEqual(result['status'], 'pending')

    def test_creates_pto_request_for_generic_leave_dates(self) -> None:
        result = self.service.try_create(
            'I need leave from 01/04 to 03/04',
            created_by='demo-user',
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'PTO')

    def test_creates_sick_request(self) -> None:
        result = self.service.try_create(
            'I want sick leave tomorrow',
            created_by='demo-user',
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'Sick')
        self.assertEqual(result['period_or_date'], 'tomorrow')

    def test_creates_access_request(self) -> None:
        result = self.service.try_create(
            'I need access to the payroll system',
            created_by='demo-user',
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'Access')
        self.assertEqual(result['assigned_to'], 'IT Support')
        self.assertEqual(result['period_or_date'], 'unspecified')

    def test_creates_equipment_request(self) -> None:
        result = self.service.try_create(
            'Please replace my broken laptop',
            created_by='demo-user',
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'Equipment')
        self.assertEqual(result['assigned_to'], 'IT Support')

    def test_creates_onboarding_blocker_request(self) -> None:
        result = self.service.try_create(
            'I am blocked during onboarding because my account setup is not complete',
            created_by='demo-user',
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'Onboarding')
        self.assertEqual(result['assigned_to'], 'HR Operations')

    def test_vpn_policy_question_does_not_create_access_request(self) -> None:
        result = self.service.try_create(
            'How do I request VPN access?',
            created_by='demo-user',
        )

        self.assertIsNone(result)

    def test_lost_laptop_policy_question_does_not_create_equipment_request(self) -> None:
        result = self.service.try_create(
            'What should I do if my laptop is lost?',
            created_by='demo-user',
        )

        self.assertIsNone(result)

    def test_policy_question_does_not_create_request(self) -> None:
        result = self.service.try_create(
            'Tell me about the vacation policy',
            created_by='demo-user',
        )

        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
