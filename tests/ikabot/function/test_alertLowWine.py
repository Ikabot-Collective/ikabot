import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.alertLowWine import check_status, prepare_alertLowWine
from ikabot.helpers.decorators import _TASK_REGISTRY


class TestCheckStatus(unittest.TestCase):
    @patch("ikabot.function.alertLowWine.time.strftime", return_value="14:32")
    def test_shows_the_interval_and_the_last_check(self, _mock_time):
        self.assertEqual(check_status(), "Every 60 min, last check 14:32")


@patch("ikabot.function.alertLowWine.requireNotifications")
class TestPrepareAlertLowWine(unittest.TestCase):
    def test_is_registered_for_the_cli(self, _mock_bot):
        self.assertIs(_TASK_REGISTRY["alertLowWine"].prepare, prepare_alertLowWine)

    def test_alert_only(self, _mock_bot):
        self.assertEqual(
            prepare_alertLowWine(MagicMock(), hours="6"),
            {"hours": 6, "auto_transfer": False, "transfer_amount": 0},
        )

    def test_auto_transfer(self, _mock_bot):
        self.assertEqual(
            prepare_alertLowWine(MagicMock(), hours=6, auto_transfer="y", transfer_amount=5000.0),
            {"hours": 6, "auto_transfer": True, "transfer_amount": 5000},
        )

    def test_auto_transfer_needs_an_amount(self, _mock_bot):
        with self.assertRaisesRegex(ValueError, "transfer_amount must be at least 1, got 0"):
            prepare_alertLowWine(MagicMock(), hours=6, auto_transfer=True)

    def test_rejects_zero_hours(self, _mock_bot):
        with self.assertRaisesRegex(ValueError, "hours must be at least 1, got 0"):
            prepare_alertLowWine(MagicMock(), hours=0)

    def test_needs_a_bot(self, mock_bot):
        mock_bot.side_effect = ValueError("Telegram or Discord")
        with self.assertRaisesRegex(ValueError, "Telegram or Discord"):
            prepare_alertLowWine(MagicMock(), hours=6)


if __name__ == "__main__":
    unittest.main()
