import json
import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.constructionList import do_it, plan_construction, prepare_constructionList
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN = (["111", "222", "333"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}, "333": {"name": "Gamma"}})


def building(position, kind, name, level, busy=False):
    return {"position": position, "building": kind, "name": name, "level": level, "isBusy": busy,
            "canUpgrade": True, "isMaxLevel": False}


def city():
    return {
        "id": "111", "name": "Alpha", "availableResources": [1000, 0, 500, 0, 0], "endUpgradeTime": 0,
        "position": [
            building(0, "townHall", "Town Hall", 10),
            building(1, "architect", "Architect's Office", 4, busy=True),
            {"position": 2, "building": "buildingGround land", "name": "empty"},
            building(3, "warehouse", "Warehouse", 7),
        ],
    }


def fake_costs(costs_per_level, last_level=30):
    """getResourcesNeeded with fixed costs per level; records the reducers it was given"""
    seen = []

    def costs(session, city, building, current, final, reducers, time_reduction=0.0):
        seen.append(list(reducers))
        levels = max(0, min(final, last_level) - current)
        building["levelsAvailable"] = levels
        building["constructionTime"] = 60 * levels
        building["constructionTimes"] = [60] * levels
        if building["building"] == "architect":
            reducers[2] += levels
        return [amount * levels for amount in costs_per_level]

    return costs, seen


class TestPlanConstruction(unittest.TestCase):
    def test_each_upgrade_spends_what_the_previous_left(self):
        costs, seen = fake_costs([300, 0, 100, 0, 0])
        with patch("ikabot.function.constructionList.getResourcesNeeded", side_effect=costs):
            plans = plan_construction(MagicMock(), city(), [{"position": 3, "upgradeTo": 9}, {"position": 0, "upgradeTo": 12}])
        # the warehouse: 2 levels cost 600 wood and 200 marble, the city has them
        self.assertEqual((plans[0]["costs"], plans[0]["missing"]), ([600, 0, 200, 0, 0], [0, 0, 0, 0, 0]))
        # the town hall gets what is left: 400 wood and 300 marble for 600 and 200
        self.assertEqual(plans[1]["missing"], [200, 0, 0, 0, 0])
        self.assertEqual(plans[1]["times"], [60, 60])

    def test_cost_reducers_count_the_level_being_built_and_the_planned_ones(self):
        costs, seen = fake_costs([0, 0, 0, 0, 0])
        c = city()
        c["position"][1]["isBusy"] = True
        with patch("ikabot.function.constructionList.getResourcesNeeded", side_effect=costs):
            plan_construction(MagicMock(), c, [{"position": 1, "upgradeTo": 7}, {"position": 3, "upgradeTo": 8}])
        # the architect is at 4 and being expanded to 5; expanding it to 7 lowers the warehouse's costs
        self.assertEqual(seen[0][2], 5)
        self.assertEqual(seen[1][2], 7)

    def test_the_level_is_capped_at_the_last_one(self):
        costs, _ = fake_costs([0, 0, 0, 0, 0], last_level=8)
        with patch("ikabot.function.constructionList.getResourcesNeeded", side_effect=costs):
            plan = plan_construction(MagicMock(), city(), [{"position": 3, "upgradeTo": 20}])[0]
        self.assertEqual((plan["requested"], plan["building"]["upgradeTo"]), (20, 8))


@patch("ikabot.function.constructionList.getCityById", side_effect=lambda session, city_id: city())
@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN)
class TestPrepareConstructionList(unittest.TestCase):
    def setUp(self):
        costs, _ = fake_costs([100, 0, 0, 0, 0], last_level=25)
        patcher = patch("ikabot.function.constructionList.getResourcesNeeded", side_effect=costs)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_is_registered_for_the_cli(self, *_):
        self.assertIs(_TASK_REGISTRY["constructionList"].prepare, prepare_constructionList)

    def test_buildings_by_position_or_name(self, *_):
        config = prepare_constructionList(
            MagicMock(), city_id=111,
            buildings=[{"position": "townHall", "upgradeTo": 12}, {"position": 3, "upgradeTo": "9",
                                                                  "transport": {"origins": {"2": [222]}}}],
            transport={"origins": {"wood": [222, "333", 222]}, "useFreighters": "y"},
        )
        self.assertEqual(config, {
            "city_id": "111", "expand": True,
            "buildings": [{"position": 0, "upgradeTo": 12},
                          {"position": 3, "upgradeTo": 9, "transport": {"origins": {"marble": ["222"]}, "useFreighters": False, "useRounding": True}}],
            "transport": {"origins": {"wood": ["222", "333"]}, "useFreighters": True, "useRounding": True},
        })

    def test_rejects_what_cannot_be_built(self, *_):
        bad = [
            (dict(buildings=[]), "buildings must be a list like .* Buildings of Alpha: 0 = Town Hall \\(townHall, level 10\\)"),
            (dict(buildings=[{"position": "palace", "upgradeTo": 3}]), "'palace' is not a building of Alpha"),
            (dict(buildings=[{"position": 2, "upgradeTo": 3}]), "2 is not a building of Alpha"),
            (dict(buildings=[{"position": 1, "upgradeTo": 5}]), "Architect's Office is already at level 5"),
            (dict(buildings=[{"position": 3, "upgradeTo": 9}, {"position": "Warehouse", "upgradeTo": 10}]), "already in the list"),
            (dict(buildings=[{"position": 3, "upgradeTo": 40}]), "Warehouse can only be expanded up to level 25"),
            (dict(transport={"origins": {"gold": [222]}}), "unknown resource 'gold'"),
            (dict(transport={"origins": {"wood": [111]}}), "the city cannot send to itself"),
            (dict(transport={"origins": {"wood": [999]}}), "999 is not one of your cities"),
            (dict(transport={"origins": {}}), "transport must be an object like"),
        ]
        for change, error in bad:
            config = dict(dict(city_id=111, buildings=[{"position": 3, "upgradeTo": 9}]), **change)
            with self.subTest(error):
                with self.assertRaisesRegex(ValueError, error):
                    prepare_constructionList(MagicMock(), **config)

    def test_a_config_saved_by_an_older_menu(self, *_):
        saved = {
            "city_id": "111", "city_name": "Alpha",
            "buildings": [dict(building(3, "warehouse", "Warehouse", 7), upgradeTo=9, constructionTimes=[60, 60])],
            "shipments": [{"origins": {0: [{"id": "222", "availableResources": [9] * 5}]}, "missing": [100, 0, 0, 0, 0],
                           "useFreighters": True, "useRounding": False}],
            "expand_overall": True, "wait_resources": True, "construction_queue": [60, 60], "total_time": 120,
        }
        config = prepare_constructionList(MagicMock(), **json.loads(json.dumps(saved)))
        self.assertEqual(config, {"city_id": "111", "expand": True, "buildings": [{"position": 3, "upgradeTo": 9}],
                                  "transport": {"origins": {"wood": ["222"]}, "useFreighters": True, "useRounding": False}})


class SyncThread:
    """runs the shipment right away, so the test sees it"""
    def __init__(self, target, args):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)

    def join(self):
        pass


@patch("ikabot.function.constructionList.setInfoSignal")
@patch("ikabot.function.constructionList.sendToBot")
@patch("ikabot.function.constructionList.getChronosForgeReduction", return_value=(0, 0.0))
@patch("ikabot.function.constructionList.getCityById", side_effect=lambda session, city_id: dict(city(), id=str(city_id)))
class TestConstructionTask(unittest.TestCase):
    def test_sends_only_what_each_upgrade_lacks_and_expands_in_order(self, *_):
        costs, _ = fake_costs([300, 0, 100, 0, 0])
        sent, expanded = [], []
        with patch("ikabot.function.constructionList.getResourcesNeeded", side_effect=costs), \
                patch("ikabot.function.constructionList.threading.Thread", SyncThread), \
                patch("ikabot.function.constructionList.sendResourcesNeeded",
                      side_effect=lambda session, city_id, origins, missing, *a: sent.append(({i: [c["id"] for c in cs] for i, cs in origins.items()}, missing))), \
                patch("ikabot.function.constructionList.expandBuilding",
                      side_effect=lambda session, city_id, b, wait_resources, queue: expanded.append((b["position"], b["upgradeTo"], wait_resources))):
            do_it.__wrapped__(MagicMock(), city_id="111", transport={"origins": {"wood": ["222"], "sulfur": ["333"]}},
                              buildings=[{"position": 3, "upgradeTo": 9}, {"position": 0, "upgradeTo": 13}])
        # the warehouse: 600 wood and 200 marble, the city has them; the town hall then lacks
        # 500 wood and no marble: only wood is sent, from the city chosen for wood
        self.assertEqual(sent, [({0: ["222"]}, [500, 0, 0, 0, 0])])
        self.assertEqual(expanded, [(3, 9, True), (0, 13, True)])


if __name__ == "__main__":
    unittest.main()
