import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.alertAttacks import check_status, prepare_alertAttacks
from ikabot.helpers.decorators import _TASK_REGISTRY


@patch("ikabot.function.alertAttacks.time.strftime", return_value="14:32")
class TestCheckStatus(unittest.TestCase):
    def test_shows_the_interval_and_the_last_check(self, _mock_time):
        self.assertEqual(check_status(20), "Every 20 min, last check 14:32")

    def test_shows_a_failed_check(self, _mock_time):
        self.assertEqual(check_status(20, failed=True), "Every 20 min, check failed at 14:32")


@patch("ikabot.function.alertAttacks.requireNotifications")
class TestPrepareAlertAttacks(unittest.TestCase):
    def test_is_registered_for_the_cli(self, _mock_bot):
        self.assertIs(_TASK_REGISTRY["alertAttacks"].prepare, prepare_alertAttacks)

    def test_defaults_to_twenty_minutes(self, _mock_bot):
        self.assertEqual(prepare_alertAttacks(MagicMock()), {"minutes": 20})

    def test_minutes_become_a_whole_number(self, _mock_bot):
        self.assertEqual(prepare_alertAttacks(MagicMock(), minutes="15"), {"minutes": 15})
        self.assertEqual(prepare_alertAttacks(MagicMock(), minutes=15.0), {"minutes": 15})

    def test_rejects_less_than_three_minutes(self, _mock_bot):
        with self.assertRaisesRegex(ValueError, "minutes must be at least 3, got 2"):
            prepare_alertAttacks(MagicMock(), minutes=2)

    def test_rejects_a_fraction(self, _mock_bot):
        with self.assertRaisesRegex(ValueError, "minutes must be a whole number"):
            prepare_alertAttacks(MagicMock(), minutes=2.5)

    def test_needs_a_bot(self, mock_bot):
        mock_bot.side_effect = ValueError("this task sends its results to Telegram or Discord")
        with self.assertRaisesRegex(ValueError, "Telegram or Discord"):
            prepare_alertAttacks(MagicMock(), minutes=20)


if __name__ == "__main__":
    unittest.main()
