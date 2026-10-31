import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.autoPirate import prepare_autoPirate
from ikabot.helpers.decorators import _TASK_REGISTRY

FORTRESS_CITY = [{"id": 7665, "name": "Alpha", "position": []}]


@patch("ikabot.function.autoPirate.getPiracyCities", return_value=FORTRESS_CITY)
class TestPrepareAutoPirate(unittest.TestCase):
    def setUp(self):
        patcher = patch("ikabot.function.autoPirate.updateProcessList", return_value=[])
        self.mock_processes = patcher.start()
        self.addCleanup(patcher.stop)

    def test_is_registered_for_the_cli(self, _mock_cities):
        self.assertIs(_TASK_REGISTRY["autoPirate"].prepare, prepare_autoPirate)

    def test_fills_in_the_menu_defaults_and_a_small_city(self, mock_cities):
        config = prepare_autoPirate(MagicMock(), pirateCount=50, pirateMissionChoice=1, autoConvert=True, convertPerMission="all")
        self.assertEqual(
            config,
            {
                "pirateCount": 50,
                "pirateSchedule": False,
                "pirateMissionChoice": 1,
                "pirateMissionDayChoice": None,
                "pirateMissionNightChoice": None,
                "dayStart": 10,
                "dayEnd": 18,
                "nightStart": 19,
                "nightEnd": 9,
                "autoConvert": "y",
                "convertPerMission": "all",
                "maxRandomWaitingTime": 0,
                "piracyCities": [{"id": "7665"}],
            },
        )
        mock_cities.assert_called_once_with(unittest.mock.ANY, 1)

    def test_a_schedule_needs_both_missions_and_checks_the_hardest(self, mock_cities):
        config = prepare_autoPirate(
            MagicMock(), pirateCount=10, pirateSchedule=True, pirateMissionDayChoice=1, pirateMissionNightChoice=5
        )
        self.assertIsNone(config["pirateMissionChoice"])
        self.assertEqual((config["pirateMissionDayChoice"], config["pirateMissionNightChoice"]), (1, 5))
        mock_cities.assert_called_once_with(unittest.mock.ANY, 5)
        with self.assertRaisesRegex(ValueError, "pirateMissionNightChoice must be a whole number, got None"):
            prepare_autoPirate(MagicMock(), pirateCount=10, pirateSchedule="y", pirateMissionDayChoice=1)

    def test_a_saved_config_keeps_only_the_first_city_id(self, _mock_cities):
        config = prepare_autoPirate(
            MagicMock(), pirateCount=5, pirateMissionChoice=2,
            piracyCities=[{"id": "8000", "name": "Beta", "position": ["lots", "of", "data"]}],
        )
        self.assertEqual(config["piracyCities"], [{"id": "8000"}])

    def test_rejects_bad_values(self, _mock_cities):
        with self.assertRaisesRegex(ValueError, "pirateMissionChoice must be at most 9, got 10"):
            prepare_autoPirate(MagicMock(), pirateCount=5, pirateMissionChoice=10)
        with self.assertRaisesRegex(ValueError, "pirateCount must be at least 1, got 0"):
            prepare_autoPirate(MagicMock(), pirateCount=0, pirateMissionChoice=1)
        with self.assertRaisesRegex(ValueError, "dayStart must be at most 23, got 24"):
            prepare_autoPirate(MagicMock(), pirateCount=5, pirateMissionChoice=1, dayStart=24)

    def test_needs_a_fortress(self, mock_cities):
        mock_cities.return_value = []
        with self.assertRaisesRegex(ValueError, "pirate fortress able to do mission 7"):
            prepare_autoPirate(MagicMock(), pirateCount=5, pirateMissionChoice=7)

    def test_rejects_a_second_task_for_the_account(self, mock_cities):
        self.mock_processes.return_value = [
            {"pid": 111, "action": "alertAttacks"},
            {"pid": 20840, "action": "autoPirate"},
        ]
        with self.assertRaisesRegex(ValueError, r"autoPirate is already running for this account \(pid 20840\)"):
            prepare_autoPirate(MagicMock(), pirateCount=1, pirateMissionChoice=1)
        mock_cities.assert_not_called()

    def test_other_tasks_do_not_block_it(self, _mock_cities):
        self.mock_processes.return_value = [{"pid": 111, "action": "alertAttacks"}]
        self.assertEqual(prepare_autoPirate(MagicMock(), pirateCount=1, pirateMissionChoice=1)["pirateCount"], 1)


if __name__ == "__main__":
    unittest.main()
