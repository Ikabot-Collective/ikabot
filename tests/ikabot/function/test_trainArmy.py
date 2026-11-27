import json
import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.trainArmy import do_trainArmy, planTrainings, prepare_trainArmy
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN = (["111", "222", "333"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}, "333": {"name": "Gamma"}})
UNITS = [
    {"identifier": "phalanx", "unit_type_id": 303, "local_name": "Hoplite", "costs": {"citizens": 1, "wood": 30, "sulfur": 22}},
    {"identifier": "archer", "unit_type_id": 313, "local_name": "Archer", "costs": {"citizens": 1, "wood": 30, "sulfur": 25}},
]


def city(city_id, has_building=True):
    if not has_building:
        raise ValueError("{} has no barracks".format(OWN[1][city_id]["name"]))
    return {"id": city_id, "name": OWN[1][city_id]["name"], "pos": "4"}


@patch("ikabot.function.trainArmy.building_units", return_value=UNITS)
@patch("ikabot.function.trainArmy.city_with_building", side_effect=lambda session, city_id, troops: city(city_id, city_id != "333"))
@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN)
class TestPrepareTrainArmy(unittest.TestCase):
    def test_is_registered_for_the_cli(self, *_):
        self.assertIs(_TASK_REGISTRY["trainArmy"].prepare, prepare_trainArmy)

    def test_units_by_identifier_id_or_name(self, *_):
        config = prepare_trainArmy(MagicMock(), city_id=111, type="Troops",
                                   rounds=[{"phalanx": 10, "313": "5"}, {"hoplite": 3, "archer": 0}], repeat="2", replicate_to=[222, 111, "222"])
        self.assertEqual(config, {"city_id": "111", "type": "troops", "rounds": [{"phalanx": 10, "archer": 5}, {"phalanx": 3}],
                                  "repeat": 2, "replicate_to": ["222"]})
        self.assertIsNone(prepare_trainArmy(MagicMock(), city_id=111, type="troops", rounds=[{"phalanx": 1}])["replicate_to"])

    def test_rejects_what_cannot_be_trained(self, *_):
        base = dict(city_id=111, type="troops", rounds=[{"phalanx": 10}])
        bad = [
            (dict(base, type="army"), 'type must be "troops" \\(barracks\\) or "ships" \\(shipyard\\)'),
            (dict(base, city_id=999), "city_id 999 is not one of your cities"),
            (dict(base, city_id=333), "Gamma has no barracks"),
            (dict(base, rounds=[]), "rounds must be a list like"),
            (dict(base, rounds=[{"catapult": 2}]), "rounds\\[0\\] 'catapult' is not trained there. Units: phalanx = Hoplite \\(303\\), archer = Archer \\(313\\)"),
            (dict(base, rounds=[{"phalanx": 2}, {"phalanx": 0}]), "rounds\\[1\\] trains nothing"),
            (dict(base, rounds=[{"phalanx": -1}]), "must be at least 0"),
            (dict(base, repeat=-1), "repeat must be at least 0"),
            (dict(base, replicate_to=[333]), "Gamma has no barracks"),
            (dict(base, replicate_to=222), "replicate_to must be a list"),
        ]
        for config, error in bad:
            with self.subTest(error):
                with self.assertRaisesRegex(ValueError, error):
                    prepare_trainArmy(MagicMock(), **config)

    def test_a_config_saved_by_an_older_menu(self, *_):
        saved = {"city": {"id": "111", "name": "Alpha", "pos": "4", "position": []}, "trainTroops": True,
                 "tranings": [[dict(UNITS[0], cantidad=10), dict(UNITS[1], cantidad=0)], [dict(UNITS[0], cantidad=0), dict(UNITS[1], cantidad=0)]],
                 "replicate": "y", "countRepeat": 1, "cityTrainings": ["111", "222"], "units": [dict(UNITS[0], cantidad=10)]}
        config = prepare_trainArmy(MagicMock(), **json.loads(json.dumps(saved)))
        self.assertEqual(config, {"city_id": "111", "type": "troops", "rounds": [{"phalanx": 10}], "repeat": 1, "replicate_to": ["222"]})


@patch("ikabot.function.trainArmy.sendToBot")
@patch("ikabot.function.trainArmy.setInfoSignal")
@patch("ikabot.function.trainArmy.building_units", return_value=UNITS)
@patch("ikabot.function.trainArmy.city_with_building", side_effect=lambda session, city_id, troops: city(city_id))
class TestTrainTask(unittest.TestCase):
    def run_task(self, **config):
        trained = []

        def plan(session, city_now, trainings, troops):
            trained.append((city_now["id"], [{u["identifier"]: u["cantidad"] for u in training} for training in trainings]))
            return True

        with patch("ikabot.function.trainArmy.planTrainings", side_effect=plan):
            do_trainArmy.__wrapped__(MagicMock(), **config)
        return trained

    def test_repeats_every_round_in_every_city(self, *_):
        # it used to ignore repeat without replicate_to, and to train only the last round, and
        # not in city_id, with it
        rounds = [{"phalanx": 10}, {"archer": 5}]
        trained = self.run_task(city_id="111", type="troops", rounds=rounds, repeat=1, replicate_to=["222"])
        self.assertEqual(trained, [("111", rounds), ("222", rounds), ("111", rounds), ("222", rounds)])

    def test_once_in_one_city(self, *_):
        self.assertEqual(self.run_task(city_id="111", type="troops", rounds=[{"phalanx": 10}]), [("111", [{"phalanx": 10}])])


class TestPlanTrainings(unittest.TestCase):
    @patch("ikabot.function.trainArmy.sendToBot")
    @patch("ikabot.function.trainArmy.train")
    @patch("ikabot.function.trainArmy.waitForTraining")
    @patch("ikabot.function.trainArmy.getCity", side_effect=[
        {"id": "111", "name": "Alpha", "availableResources": [300, 0, 0, 0, 220], "freeCitizens": 100},
        # after the first training: what the 10 hoplites did not use
        {"id": "111", "name": "Alpha", "availableResources": [0, 0, 0, 0, 0], "freeCitizens": 90},
    ])
    def test_trains_what_the_resources_pay_for_and_stops_when_nothing(self, _city, _wait, mock_train, mock_bot):
        trained = []
        mock_train.side_effect = lambda session, city, training, troops: trained.append([u["train"] for u in training])
        trainings = [[dict(UNITS[0], cantidad=25)]]
        self.assertFalse(planTrainings(MagicMock(), {"id": "111", "pos": "4"}, trainings, True))
        # 300 wood and 220 sulfur pay for 10 hoplites; then nothing is left for the other 15
        self.assertEqual(trained, [[10]])
        self.assertIn("Alpha due to lack of resources", mock_bot.call_args.args[1])

    @patch("ikabot.function.trainArmy.sendToBot")
    @patch("ikabot.function.trainArmy.train")
    @patch("ikabot.function.trainArmy.waitForTraining")
    @patch("ikabot.function.trainArmy.getCity", side_effect=[
        {"id": "111", "name": "Alpha", "availableResources": [300, 0, 0, 0, 220], "freeCitizens": 100},
        {"id": "111", "name": "Alpha", "availableResources": [300, 0, 0, 0, 220], "freeCitizens": 100},
        {"id": "111", "name": "Alpha", "availableResources": [300, 0, 0, 0, 220], "freeCitizens": 100},
    ])
    def test_skips_completed_first_round_and_finishes_second_round(self, _city, _wait, mock_train, mock_bot):
        trained = []
        mock_train.side_effect = lambda session, city, training, troops: trained.append([u["train"] for u in training])
        # Round 1 fits in 1 pass (10); Round 2 needs 2 passes (10 + 5)
        trainings = [[dict(UNITS[0], cantidad=10)], [dict(UNITS[0], cantidad=15)]]
        self.assertTrue(planTrainings(MagicMock(), {"id": "111", "pos": "4"}, trainings, True))
        self.assertEqual(trained, [[10], [10], [5]])
        mock_bot.assert_not_called()

    def test_filter_cities_by_resource_matches_int_tradegood(self):
        from ikabot.function.trainArmy import filterCitiesByResource, resourceMapping

        cities = {"1": {"id": 1, "tradegood": 1}, "2": {"id": 2, "tradegood": 2}}
        self.assertEqual(filterCitiesByResource(cities, resourceMapping[1], []), [1])


if __name__ == "__main__":
    unittest.main()
