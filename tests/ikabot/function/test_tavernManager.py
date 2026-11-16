import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.tavernManager import TavernManager, checked_status, do_tavernManager, prepare_tavernManager
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN_CITIES = (["111", "222"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}})


class TestCheckedStatus(unittest.TestCase):
    @patch("ikabot.function.tavernManager.time.strftime", return_value="15:42")
    def test_shows_the_interval_and_the_last_check(self, _mock_time):
        self.assertEqual(checked_status(2), "Every 2h, last check 15:42")


@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN_CITIES)
class TestPrepareTavernManager(unittest.TestCase):
    def test_is_registered_for_the_cli(self, _mock_ids):
        self.assertIs(_TASK_REGISTRY["tavernManager"].prepare, prepare_tavernManager)

    def test_defaults_to_all_cities_and_errors_only(self, _mock_ids):
        self.assertEqual(
            prepare_tavernManager(MagicMock(), run_hours=4),
            {"run_hours": 4, "cities_ids": None, "notification_mode": 2},
        )

    def test_drops_the_saved_city_data_and_checks_the_ids(self, _mock_ids):
        config = prepare_tavernManager(
            MagicMock(), run_hours=0, cities_ids=[111], cities={"111": {"name": "Old name"}}, check_now=False
        )
        self.assertEqual(config, {"run_hours": 0, "cities_ids": ["111"], "notification_mode": 2})

    def test_rejects_bad_values(self, _mock_ids):
        with self.assertRaisesRegex(ValueError, "run_hours must be at most 24"):
            prepare_tavernManager(MagicMock(), run_hours=25)
        with self.assertRaisesRegex(ValueError, "notification_mode must be at most 3"):
            prepare_tavernManager(MagicMock(), run_hours=4, notification_mode=4)
        with self.assertRaisesRegex(ValueError, "cities_ids 999 is not one of your cities"):
            prepare_tavernManager(MagicMock(), run_hours=4, cities_ids=["999"])


class TestProcessEquilibrium(unittest.TestCase):
    @patch("ikabot.function.tavernManager.wait")
    def test_pauses_between_cities_but_not_before_the_first(self, mock_wait):
        session = MagicMock()
        session.get.side_effect = Exception("offline")  # every city ends as an error, without more requests
        results = TavernManager(session, notification_mode=3).process_equilibrium(["111", "222"], OWN_CITIES[1])
        self.assertEqual([r["status"] for r in results], ["ERROR", "ERROR"])
        mock_wait.assert_called_once_with(3, 4)


@patch("ikabot.function.tavernManager.setInfoSignal")
@patch("ikabot.function.tavernManager.getIdsOfCities", return_value=OWN_CITIES)
@patch("ikabot.function.tavernManager.TavernManager")
class TestTavernManagerTask(unittest.TestCase):
    def test_zero_hours_checks_once_right_away(self, mock_mgr_cls, _mock_ids, _mock_info):
        session = MagicMock()
        do_tavernManager.__wrapped__(session, run_hours=0)
        mock_mgr_cls.return_value.process_equilibrium.assert_called_once_with(["111", "222"], OWN_CITIES[1])
        session.setStatus.assert_called_once()

    @patch("ikabot.function.tavernManager.wait", side_effect=StopIteration)
    def test_the_first_check_comes_before_the_wait(self, _mock_wait, mock_mgr_cls, _mock_ids, _mock_info):
        with self.assertRaises(StopIteration):
            do_tavernManager.__wrapped__(MagicMock(), run_hours=4, cities_ids=["222"])
        mock_mgr_cls.return_value.process_equilibrium.assert_called_once_with(["222"], OWN_CITIES[1])

    @patch("ikabot.function.tavernManager.wait", side_effect=StopIteration)
    def test_the_menu_skips_the_first_check(self, _mock_wait, mock_mgr_cls, _mock_ids, _mock_info):
        with self.assertRaises(StopIteration):
            do_tavernManager.__wrapped__(
                MagicMock(), run_hours=4, cities_ids=["111"], cities=OWN_CITIES[1], check_now=False
            )
        mock_mgr_cls.return_value.process_equilibrium.assert_not_called()


if __name__ == "__main__":
    unittest.main()
