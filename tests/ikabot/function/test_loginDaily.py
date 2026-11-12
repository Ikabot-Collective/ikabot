import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.loginDaily import TASK_FUNCTIONS, prepare_loginDaily
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN_CITIES = (["111", "222"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}})


@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN_CITIES)
class TestPrepareLoginDaily(unittest.TestCase):
    def test_is_registered_for_the_cli(self, _mock_ids):
        self.assertIs(_TASK_REGISTRY["loginDaily"].prepare, prepare_loginDaily)

    def test_only_the_wine_city_is_required(self, _mock_ids):
        self.assertEqual(
            prepare_loginDaily(MagicMock(), wine_city=111),
            {
                "wine_city": "111",
                "wood_city": None,
                "luxury_city": None,
                "favour_tasks": [],
                "collect_ambrosia": False,
            },
        )

    def test_takes_ids_and_short_task_keys(self, _mock_ids):
        config = prepare_loginDaily(
            MagicMock(),
            wine_city="111",
            wood_city="222",
            luxury_city=222,
            favour_tasks=["look", "Resource", "look"],
            collect_ambrosia="y",
        )
        self.assertEqual(config["wood_city"], "222")
        self.assertEqual(config["luxury_city"], "222")
        self.assertEqual(config["favour_tasks"], ["look", "resource"])
        self.assertIs(config["collect_ambrosia"], True)

    def test_all_selects_every_task(self, _mock_ids):
        config = prepare_loginDaily(MagicMock(), wine_city=111, favour_tasks="all")
        self.assertEqual(config["favour_tasks"], list(TASK_FUNCTIONS))

    def test_accepts_a_config_saved_by_an_older_menu(self, _mock_ids):
        config = prepare_loginDaily(
            MagicMock(),
            wine_city={"id": 111, "name": "Alpha", "position": []},
            wood_city={"id": 222, "name": "Beta"},
            luxury_city=None,
            favour_tasks=["Collect resource favour", "Look at hightscore/shop/inventory", "Complete 2/all tasks"],
            collect_ambrosia=True,
        )
        self.assertEqual(config["wine_city"], "111")
        self.assertEqual(config["wood_city"], "222")
        self.assertEqual(config["favour_tasks"], ["resource", "look", "complete"])

    def test_rejects_bad_values(self, _mock_ids):
        with self.assertRaisesRegex(ValueError, "wine_city 999 is not one of your cities. Your cities: 111 \\(Alpha\\)"):
            prepare_loginDaily(MagicMock(), wine_city=999)
        with self.assertRaisesRegex(ValueError, "luxury_city must be an id"):
            prepare_loginDaily(MagicMock(), wine_city=111, luxury_city="Beta")
        with self.assertRaisesRegex(ValueError, "unknown task 'highscore', use resource, look, online, complete"):
            prepare_loginDaily(MagicMock(), wine_city=111, favour_tasks=["highscore"])
        with self.assertRaisesRegex(ValueError, 'favour_tasks must be a list of tasks or "all"'):
            prepare_loginDaily(MagicMock(), wine_city=111, favour_tasks="look")


if __name__ == "__main__":
    unittest.main()
