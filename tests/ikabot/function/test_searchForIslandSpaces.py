import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.searchForIslandSpaces import checked_status, prepare_searchForIslandSpaces
from ikabot.helpers.decorators import _TASK_REGISTRY


class TestCheckedStatus(unittest.TestCase):
    @patch("ikabot.function.searchForIslandSpaces.getDateTime", return_value="2026-10-31_11-44-48")
    def test_shows_the_island_coordinates(self, _mock_time):
        self.assertEqual(checked_status(["50:60", "51:62"]), "Checked islands [50:60,51:62] @ 11-44-48")


@patch("ikabot.function.searchForIslandSpaces.requireNotifications")
class TestPrepareSearchForIslandSpaces(unittest.TestCase):
    def test_is_registered_for_the_cli(self, _mock_bot):
        self.assertIs(_TASK_REGISTRY["searchForIslandSpaces"].prepare, prepare_searchForIslandSpaces)

    def test_defaults_to_all_islands_without_fights(self, _mock_bot):
        self.assertEqual(
            prepare_searchForIslandSpaces(MagicMock(), time=30),
            {"time": 30, "islandList": [], "fights": "n"},
        )

    @patch("ikabot.function.searchForIslandSpaces.islandIdFromCoords", return_value="4321")
    def test_accepts_ids_and_coordinates(self, mock_coords, _mock_bot):
        config = prepare_searchForIslandSpaces(
            MagicMock(), time="30", islandList=[1234, "50:60"], fights=True
        )
        self.assertEqual(config, {"time": 30, "islandList": ["1234", "4321"], "fights": "y"})
        self.assertEqual(mock_coords.call_args.args[1], "50:60")

    def test_rejects_less_than_three_minutes(self, _mock_bot):
        with self.assertRaisesRegex(ValueError, "time must be at least 3, got 2"):
            prepare_searchForIslandSpaces(MagicMock(), time=2)

    def test_rejects_a_bad_island(self, _mock_bot):
        with self.assertRaisesRegex(ValueError, "islandList must be an id"):
            prepare_searchForIslandSpaces(MagicMock(), time=30, islandList=["somewhere"])

    def test_needs_a_bot(self, mock_bot):
        mock_bot.side_effect = ValueError("Telegram or Discord")
        with self.assertRaisesRegex(ValueError, "Telegram or Discord"):
            prepare_searchForIslandSpaces(MagicMock(), time=30)


if __name__ == "__main__":
    unittest.main()
