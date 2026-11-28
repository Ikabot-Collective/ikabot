import json
import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.attackBarbarians import check_plan, do_it, prepare_attackBarbarians, wait_for_round
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN = (["111", "222"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}})
UNITS = {"303": {"name": "Hoplite", "amount": 100}, "307": {"name": "Ram", "amount": 5}, "305": {"name": "Mortar", "amount": 0}}
ISLAND = {"id": "4415", "x": 50, "y": 60, "barbarians": {"level": 3, "destroyed": 0, "underAttack": 0}}


class TestCheckPlan(unittest.TestCase):
    def test_sorts_the_rounds_and_puts_the_loot_round_last(self):
        plan = [
            {"round": 3, "units": {"303": 10}, "ships": 2},
            {"round": 1, "units": {"Hoplite": "50", "307": 2}},
            {"loot": True, "units": {"303": 5}},
        ]
        self.assertEqual(check_plan(plan, UNITS, 10), [
            {"round": 1, "units": {"303": 50, "307": 2}, "ships": 0, "loot": False},
            {"round": 3, "units": {"303": 10}, "ships": 2, "loot": False},
            {"round": 3, "units": {"303": 5}, "loot": True},
        ])

    def test_rejects_plans_the_city_cannot_send(self):
        bad = [
            ([], "plan must be a list of rounds"),
            ([{"round": 2, "units": {"303": 1}}], "exactly one round 1"),
            ([{"round": 1, "units": {"303": 1}}, {"round": 1, "units": {"303": 1}}], "exactly one round 1"),
            ([{"loot": True, "units": {"303": 1}}], "needs a first round of attack"),
            ([{"round": 1, "units": {"303": 1}}, {"loot": True, "units": {"303": 1}}, {"round": 2, "units": {"303": 1}}],
             "the loot round must be the last one"),
            ([{"round": 1, "units": {"catapult": 1}}], "'catapult' is not a unit of the city. Units: 303 = Hoplite, 307 = Ram"),
            ([{"round": 1, "units": {"303": 0}}], "plan\\[0\\] sends no units"),
            ([{"round": 1, "units": {"303": 60}}, {"round": 2, "units": {"303": 50}}], "the city has 100 Hoplite \\(303\\), the plan sends 110"),
            ([{"round": 1, "units": {"305": 1}}], "the city has 0 Mortar"),
            ([{"round": 1, "units": {"303": 1}, "ships": 11}], "the plan sends 11 ships and the account has 10"),
        ]
        for plan, error in bad:
            with self.subTest(error):
                with self.assertRaisesRegex(ValueError, error):
                    check_plan(plan, UNITS, 10)


@patch("ikabot.function.attackBarbarians.getTotalShips", return_value=10)
@patch("ikabot.function.attackBarbarians.get_units", return_value=UNITS)
@patch("ikabot.function.attackBarbarians.getCityById", return_value={"id": "111"})
@patch("ikabot.function.attackBarbarians.get_island", return_value=ISLAND)
@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN)
class TestPrepareAttackBarbarians(unittest.TestCase):
    def test_is_registered_for_the_cli(self, *_):
        self.assertIs(_TASK_REGISTRY["attackBarbarians"].prepare, prepare_attackBarbarians)

    def test_ids_and_plan(self, *_):
        config = prepare_attackBarbarians(MagicMock(), island_id="50:60", city_id=111, plan=[{"round": 1, "units": {"303": 5}}])
        self.assertEqual(config, {"island_id": "4415", "city_id": "111",
                                  "plan": [{"round": 1, "units": {"303": 5}, "ships": 0, "loot": False}]})

    def test_rejects_other_cities_and_islands_without_barbarians(self, _ids, mock_island, *_):
        with self.assertRaisesRegex(ValueError, "city_id 999 is not one of your cities"):
            prepare_attackBarbarians(MagicMock(), island_id=4415, city_id=999, plan=[{"round": 1, "units": {"303": 5}}])
        mock_island.return_value = {"id": "1", "x": 1, "y": 2}
        with self.assertRaisesRegex(ValueError, "island 1:2 has no barbarian village"):
            prepare_attackBarbarians(MagicMock(), island_id=1, city_id=111, plan=[{"round": 1, "units": {"303": 5}}])

    def test_a_config_saved_by_an_older_menu(self, *_):
        saved = {"island": dict(ISLAND, cities=[]), "city": {"id": "111", "name": "Alpha", "position": []},
                 "babarians_info": {"ships": 3}, "ship_capacity": 500,
                 "plan": [{"units": {"303": 5}, "loot": False, "round": 1, "ships": 1}, {"units": {"307": 1}, "loot": True, "round": 2}]}
        config = prepare_attackBarbarians(MagicMock(), **json.loads(json.dumps(saved)))
        self.assertEqual((config["island_id"], config["city_id"], len(config["plan"])), ("4415", "111", 2))


class TestFixedBugs(unittest.TestCase):
    @patch("ikabot.function.attackBarbarians.wait")
    @patch("ikabot.function.attackBarbarians.getIsland", return_value={"barbarians": {"underAttack": 1}})
    def test_a_later_round_reads_the_island_by_its_id(self, _island, _wait):
        # it used to ask for the island with the city's id
        session = MagicMock()
        wait_for_round(session, {"id": "111"}, ISLAND, 0, 1.0, 2)
        self.assertTrue(session.get.call_args.args[0].endswith("4415"))

    @patch("ikabot.function.attackBarbarians.setInfoSignal")
    @patch("ikabot.function.attackBarbarians.wait_until_attack_is_over")
    @patch("ikabot.function.attackBarbarians.get_barbarians_lv", return_value={"ships": 2})
    @patch("ikabot.function.attackBarbarians.waitForArrival", return_value=10)
    @patch("ikabot.function.attackBarbarians.wait_for_round")
    @patch("ikabot.function.attackBarbarians.load_troops", side_effect=lambda s, c, i, r, u, data, cap, *a: (data, 0, 60))
    @patch("ikabot.function.attackBarbarians.getShipCapacity", return_value=(500, 1000))
    @patch("ikabot.function.attackBarbarians.getCityById", return_value={"id": "111", "x": 50, "y": 60})
    @patch("ikabot.function.attackBarbarians.getIsland", return_value=ISLAND)
    def test_the_loot_round_gets_the_island_and_the_city_in_order(self, *_):
        # loot(session, island, city, ...) was called with the city and the island swapped
        plan = [{"round": 1, "units": {"303": 5}, "ships": 0, "loot": False}, {"round": 2, "units": {"307": 1}, "loot": True}]
        with patch("ikabot.function.attackBarbarians.loot") as mock_loot:
            do_it.__wrapped__(MagicMock(), island_id="4415", city_id="111", plan=plan)
        session, island, city = mock_loot.call_args.args[:3]
        self.assertEqual((island["id"], city["id"]), ("4415", "111"))


if __name__ == "__main__":
    unittest.main()
