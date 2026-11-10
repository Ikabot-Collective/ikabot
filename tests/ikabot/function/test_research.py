import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.research import do_it, prepare_research
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN_CITIES = (["111", "222", "333"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}, "333": {"name": "Gamma"}})


def game_city(city_id, academy=True, crystal=900000):
    names = {"111": "Alpha", "222": "Beta", "333": "Gamma"}
    position = [{"building": "townHall", "position": 0}]
    if academy:
        position.append({"building": "academy", "position": 7})
    return {"id": city_id, "name": names[city_id], "position": position, "availableResources": [0, 0, 0, crystal, 0]}


ACADEMIES = [{"cityID": "111", "cityName": "Alpha", "pos": 7}, {"cityID": "222", "cityName": "Beta", "pos": 7}]


@patch("ikabot.function.research.find_academy_cities", return_value=ACADEMIES)
@patch("ikabot.function.research.getCityById", side_effect=lambda session, city_id: game_city(city_id, academy=city_id != "333"))
@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN_CITIES)
class TestPrepareResearch(unittest.TestCase):
    def test_is_registered_for_the_cli(self, *_mocks):
        self.assertIs(_TASK_REGISTRY["research"].prepare, prepare_research)

    def test_without_a_config_uses_every_academy(self, *_mocks):
        self.assertEqual(prepare_research(MagicMock()), {"cities_ids": ["111", "222"], "qty": None})

    def test_a_number_of_experiments_in_one_city(self, *_mocks):
        self.assertEqual(prepare_research(MagicMock(), cities_ids=[111], qty="3"), {"cities_ids": ["111"], "qty": 3})

    def test_turns_a_config_saved_by_an_older_menu_into_ids(self, *_mocks):
        old_single = {
            "mode": "experiment",
            "experiments": {"cityID": 111, "cityName": "Alpha", "pos": 7, "qty": 2},
            "automatic": False,
            "info": "Process: Experiments",
        }
        self.assertEqual(prepare_research(MagicMock(), **old_single), {"cities_ids": ["111"], "qty": 2})
        old_multi = {"mode": "experiment_multi", "cities": ACADEMIES, "info": "Process: Experiments (automatic)"}
        self.assertEqual(prepare_research(MagicMock(), **old_multi), {"cities_ids": ["111", "222"], "qty": None})

    def test_rejects_bad_values(self, *_mocks):
        with self.assertRaisesRegex(ValueError, "cities_ids 333 \\(Gamma\\) has no academy"):
            prepare_research(MagicMock(), cities_ids=["111", "333"])
        with self.assertRaisesRegex(ValueError, "qty works on one city, got 2"):
            prepare_research(MagicMock(), cities_ids=["111", "222"], qty=1)
        with self.assertRaisesRegex(ValueError, "qty needs the city"):
            prepare_research(MagicMock(), qty=1)
        with self.assertRaisesRegex(ValueError, "qty must be at least 1"):
            prepare_research(MagicMock(), cities_ids=["111"], qty=0)
        with self.assertRaisesRegex(ValueError, "cities_ids 999 is not one of your cities"):
            prepare_research(MagicMock(), cities_ids=["999"])

    def test_a_number_of_experiments_needs_the_crystal_for_one(self, _mock_ids, mock_city, _mock_academies):
        mock_city.side_effect = lambda session, city_id: game_city(city_id, crystal=250000)
        with self.assertRaisesRegex(ValueError, "not enough crystal in Alpha for an experiment: 250.000 of 300.000"):
            prepare_research(MagicMock(), cities_ids=["111"], qty=1)
        # the automatic mode waits for the crystal instead
        self.assertEqual(prepare_research(MagicMock(), cities_ids=["111"])["qty"], None)

    def test_none_of_the_cities_has_an_academy(self, _mock_ids, _mock_city, mock_academies):
        mock_academies.return_value = []
        with self.assertRaisesRegex(ValueError, "none of your cities has an academy"):
            prepare_research(MagicMock())


@patch("ikabot.function.research.setInfoSignal")
@patch("ikabot.function.research.getCityById", side_effect=lambda session, city_id: game_city(city_id))
class TestResearchTask(unittest.TestCase):
    @patch("ikabot.function.research.experiment")
    def test_finds_the_academy_for_a_number_of_experiments(self, mock_experiment, *_mocks):
        do_it.__wrapped__(MagicMock(), cities_ids=["222"], qty=2)
        self.assertEqual(mock_experiment.call_args.args[1], {"cityID": "222", "cityName": "Beta", "pos": 7, "qty": 2})
        self.assertIs(mock_experiment.call_args.args[2], False)

    @patch("ikabot.function.research.experiment_multi")
    def test_finds_the_academies_for_the_automatic_mode(self, mock_multi, *_mocks):
        do_it.__wrapped__(MagicMock(), cities_ids=["111", "222"])
        self.assertEqual(mock_multi.call_args.args[1], ACADEMIES)


if __name__ == "__main__":
    unittest.main()
