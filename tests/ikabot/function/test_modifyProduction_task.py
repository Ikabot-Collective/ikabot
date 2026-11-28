import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.modifyProduction import (
    prepare_modifyAcademyWorkers, prepare_modifyProduction, prepare_modifyTempleWorkers, workers_for,
)
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN = (["111", "222", "333"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}, "333": {"name": "Gamma"}})


def city(city_id):
    buildings = {"111": ["academy", "temple"], "222": ["academy"], "333": []}[city_id]
    return {"id": city_id, "name": OWN[1][city_id]["name"],
            "position": [{"building": b, "position": i + 3} for i, b in enumerate(buildings)]}


class TestWorkers(unittest.TestCase):
    def test_a_percentage_of_the_normal_maximum(self):
        self.assertEqual(workers_for(500, 100, 100), 500)
        self.assertEqual(workers_for(500, 100, 100, use_overcharge=True), 600)
        self.assertEqual(workers_for(500, 100, 50), 250)
        self.assertEqual(workers_for(333, 100, 10), 33)
        self.assertEqual(workers_for(500, 100, 0), 0)


@patch("ikabot.function.modifyProduction.getCityById", side_effect=lambda session, city_id: city(city_id))
@patch("ikabot.function.modifyProduction.getIdsOfCities", return_value=OWN)
@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN)
class TestPrepare(unittest.TestCase):
    def test_registered_for_the_cli(self, *_):
        for name, prepare in (("modifyProduction", prepare_modifyProduction), ("modifyAcademyWorkers", prepare_modifyAcademyWorkers),
                              ("modifyTempleWorkers", prepare_modifyTempleWorkers)):
            self.assertIs(_TASK_REGISTRY[name].prepare, prepare)

    def test_production(self, *_):
        self.assertEqual(prepare_modifyProduction(MagicMock()),
                         {"cities_ids": None, "resources": "both", "percentage": 100, "overcharge": False})
        self.assertEqual(prepare_modifyProduction(MagicMock(), cities_ids=[222, "111", 222], resources="Wood", percentage="60"),
                         {"cities_ids": ["222", "111"], "resources": "wood", "percentage": 60, "overcharge": False})
        bad = [
            (dict(resources="gold"), 'resources must be "wood", "tradegood" or "both"'),
            (dict(percentage=101), "percentage must be at most 100"),
            (dict(percentage=50, overcharge=True), "overcharge needs percentage 100"),
            (dict(cities_ids=[]), "cities_ids must be a non-empty list"),
            (dict(cities_ids=[999]), "999 is not one of your cities"),
        ]
        for config, error in bad:
            with self.subTest(error):
                with self.assertRaisesRegex(ValueError, error):
                    prepare_modifyProduction(MagicMock(), **config)

    def test_academy_and_temple_need_the_building(self, *_):
        self.assertEqual(prepare_modifyAcademyWorkers(MagicMock(), percentage=80), {"cities_ids": None, "percentage": 80})
        self.assertEqual(prepare_modifyTempleWorkers(MagicMock(), cities_ids=[111]), {"cities_ids": ["111"], "percentage": 100})
        with self.assertRaisesRegex(ValueError, "Beta \\(222\\) has no temple"):
            prepare_modifyTempleWorkers(MagicMock(), cities_ids=[111, 222])
        with self.assertRaisesRegex(ValueError, "Gamma \\(333\\) has no academy"):
            prepare_modifyAcademyWorkers(MagicMock(), cities_ids=[333])
        with patch("ikabot.function.modifyProduction.getCityById", side_effect=lambda session, city_id: city("333")):
            with self.assertRaisesRegex(ValueError, "none of your cities has an academy"):
                prepare_modifyAcademyWorkers(MagicMock())


if __name__ == "__main__":
    unittest.main()
