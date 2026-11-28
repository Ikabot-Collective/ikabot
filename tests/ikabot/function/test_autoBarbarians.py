import json
import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.autoBarbarians import (
    DEFAULT_SCHEMATICS, check_schematic, loot, ordered_waves, prepare_autoBarbarians,
)
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN = (["111", "222"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}})
UNITS = {uid: {"name": "Unit " + uid, "amount": 500} for uid in ("302", "304", "305", "307", "308", "309", "310", "311")}
ISLAND = {"id": "4415", "x": 50, "y": 60, "barbarians": {"level": 12, "destroyed": 0, "underAttack": 0}}
CUSTOM = [{
    "level": [1, 5],
    "looting": {"units": {"302": 1}},
    "waves": {"1": {"send": [{"units": {"302": 10}}]}, "2": {"send": [{"units": {"302": 5}}, {"from_float": True, "units": {"304": 3}}]}},
}]


class TestSchematic(unittest.TestCase):
    def test_default_and_custom(self):
        self.assertIs(check_schematic("Default"), DEFAULT_SCHEMATICS["WITHOUT_HEPHAESTUS"])
        checked = check_schematic(CUSTOM)[0]
        self.assertEqual(checked["level"], [1, 5])
        self.assertEqual(checked["looting"], {"from_float": False, "units": {"302": 1}})
        # the units each city needs, when the scheme does not say: everything its waves send
        self.assertEqual(checked["needed_units"], {"main": {"302": 15}, "float": {"304": 3}})

    def test_rejects_malformed_schemes(self):
        bad = [
            ("hephaestus", 'schematic must be "default" or a list of levels'),
            ([], 'schematic must be "default" or a list of levels'),
            ([dict(CUSTOM[0], level=[5, 1])], "goes from 5 down to 1"),
            ([dict(CUSTOM[0], waves={})], "waves must be an object"),
            ([dict(CUSTOM[0], waves={"x": {"send": [{"units": {"302": 1}}]}})], "must be a whole number"),
            ([dict(CUSTOM[0], waves={"1": {"send": [{"units": {"hoplite": 1}}]}})], "'hoplite' is not a unit id"),
            ([dict(CUSTOM[0], looting=None)], "looting must be an object"),
        ]
        for value, error in bad:
            with self.subTest(error):
                with self.assertRaisesRegex(ValueError, error):
                    check_schematic(value)

    def test_waves_go_in_battle_order(self):
        # they were sorted as text: wave 10 went before wave 2
        self.assertEqual([wave for wave, _ in ordered_waves({"10": {}, "2": {}, "1": {}})], ["1", "2", "10"])


@patch("ikabot.function.autoBarbarians.get_units", return_value=UNITS)
@patch("ikabot.function.autoBarbarians.getCityById", side_effect=lambda session, city_id: {"id": city_id, "islandId": "4415" if city_id == "222" else "77"})
@patch("ikabot.function.autoBarbarians.get_island", return_value=ISLAND)
@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN)
class TestPrepareAutoBarbarians(unittest.TestCase):
    def test_is_registered_for_the_cli(self, *_):
        self.assertIs(_TASK_REGISTRY["autoBarbarians"].prepare, prepare_autoBarbarians)

    def test_default_scheme(self, *_):
        config = prepare_autoBarbarians(MagicMock(), island_id="50:60", city_id=111, send_notifications="n")
        self.assertEqual(config, {"island_id": "4415", "city_id": "111", "float_city_id": None,
                                  "schematic": "default", "send_notifications": False})

    def test_the_barbarians_level_must_be_in_the_scheme(self, _ids, mock_island, *_):
        mock_island.return_value = dict(ISLAND, barbarians={"level": 45})
        with self.assertRaisesRegex(ValueError, "the barbarians of 50:60 are level 45, the schematic covers levels 1-9, 10-19, 20-29, 30-39"):
            prepare_autoBarbarians(MagicMock(), island_id=4415, city_id=111)

    def test_a_scheme_with_float_sends_needs_a_city_on_the_island(self, _ids, mock_island, *_):
        mock_island.return_value = dict(ISLAND, barbarians={"level": 3})
        with self.assertRaisesRegex(ValueError, "float_city_id is needed"):
            prepare_autoBarbarians(MagicMock(), island_id=4415, city_id=111, schematic=CUSTOM)
        with self.assertRaisesRegex(ValueError, "float_city_id 111 is not on the island 50:60"):
            prepare_autoBarbarians(MagicMock(), island_id=4415, city_id=222, float_city_id=111, schematic=CUSTOM)
        config = prepare_autoBarbarians(MagicMock(), island_id=4415, city_id=111, float_city_id=222, schematic=CUSTOM)
        self.assertEqual((config["float_city_id"], config["schematic"][0]["level"]), ("222", [1, 5]))

    def test_units_the_city_does_not_have(self, _ids, _island, _city, mock_units):
        mock_units.return_value = {"302": {"name": "Swordsman", "amount": 5}}
        with self.assertRaisesRegex(ValueError, "the schematic uses units .*'304'.* that are not units of the city. Units: 302 = Swordsman"):
            prepare_autoBarbarians(MagicMock(), island_id=4415, city_id=111)

    def test_a_config_saved_by_an_older_menu(self, *_):
        saved = {"island": dict(ISLAND, cities=[]), "city": {"id": "111", "position": []}, "float_city": None,
                 "schematic": DEFAULT_SCHEMATICS["WITHOUT_HEPHAESTUS"], "units_data": {"302": {"speed": 1}},
                 "ship_capacity": 500, "send_notifications": True}
        config = prepare_autoBarbarians(MagicMock(), **json.loads(json.dumps(saved)))
        self.assertEqual((config["island_id"], config["city_id"], config["schematic"]), ("4415", "111", "default"))


class TestLoot(unittest.TestCase):
    @patch("ikabot.function.autoBarbarians.wait_for_arrival")
    @patch("ikabot.function.autoBarbarians.get_barbarians_info", return_value=[None, None, [None, {}]])
    @patch("ikabot.function.autoBarbarians.get_send_attack_data", return_value=({}, 1, 600))
    @patch("ikabot.function.autoBarbarians.waitForArrival", return_value=10)
    @patch("ikabot.function.autoBarbarians.get_current_attacks", return_value=[])
    @patch("ikabot.function.autoBarbarians.getIsland", return_value={"id": "4415", "barbarians": {"destroyed": 1}})
    @patch("ikabot.function.autoBarbarians.get_barbarians_lv", side_effect=[{"resources": [100, 0, 0, 0, 0]}, {"resources": [0] * 5}])
    def test_loots_without_a_cooldown_timer(self, *_):
        # with no countdown shown, None - time.time() raised TypeError
        session = MagicMock()
        scheme = {"looting": {"from_float": False, "units": {"302": 1}}}
        loot(session, {"id": "4415"}, {"id": "111"}, scheme, 500, units_data={})
        self.assertEqual(session.post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
