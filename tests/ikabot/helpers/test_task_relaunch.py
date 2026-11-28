"""Exporting a running task (Manage running tasks > save) and relaunching it with --config.
The exported config is what the process list holds:
  - menu launch: the configurator's result through json (decorators._save_task_config)
  - CLI launch: the prepare result (ipc._start_task)
Relaunching sends it through _validate_task_config + prepare again."""
import json
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import ikabot.function.alertAttacks, ikabot.function.alertLowWine, ikabot.function.activateShrine  # noqa
import ikabot.function.consolidateResources, ikabot.function.searchForIslandSpaces  # noqa
import ikabot.function.donationBot, ikabot.function.tavernManager, ikabot.function.autoPirate  # noqa
import ikabot.function.webServer, ikabot.function.loginDaily, ikabot.function.research, ikabot.function.dumpWorld  # noqa
import ikabot.function.sendResources, ikabot.function.activateMiracle, ikabot.function.UpgradeUnits  # noqa
import ikabot.function.distributeResources, ikabot.function.resourceTransportManager  # noqa
import ikabot.function.buyResources, ikabot.function.sellResources, ikabot.function.trainArmy  # noqa
import ikabot.function.trainSpies  # noqa
import ikabot.function.attackBarbarians, ikabot.function.autoBarbarians, ikabot.function.constructionList  # noqa
from ikabot.function.autoBarbarians import DEFAULT_SCHEMATICS
from ikabot.helpers.decorators import _TASK_REGISTRY
from ikabot.helpers.ipc import _validate_task_config

OWN = (["111", "222"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}})
FORTRESS = [{"id": "111", "name": "Alpha", "position": [{"building": "pirateFortress"}]}]
HERMES = {"id": "4415", "wonder": "5", "wonderName": "Temple of Hermes", "wonderActivationLevel": 3, "available": True,
          "ciudad": {"id": "111", "name": "Alpha", "islandId": "4415", "pos": "4"}, "cities": [{"type": "city", "id": 9000}]}

PHALANX = {"identifier": "phalanx", "unit_type_id": 303, "local_name": "Hoplite", "costs": {"citizens": 1, "wood": 30}}
BARBARIANS_ISLAND = {"id": "4415", "x": 50, "y": 60, "barbarians": {"level": 12, "destroyed": 0}}
CITY_UNITS = {uid: {"name": "Unit " + uid, "amount": 500} for uid in ("302", "303", "304", "305", "307", "308", "309", "310", "311")}
BUILDINGS_CITY = {"id": "111", "name": "Alpha", "availableResources": [0] * 5, "position": [
    {"position": 0, "building": "townHall", "name": "Town Hall", "level": 10, "isBusy": False},
    {"position": 1, "building": "warehouse", "name": "Warehouse", "level": 7, "isBusy": False}]}


def all_levels(session, city, building, current, final, reducers, time_reduction=0.0):
    building["levelsAvailable"] = final - current
    building["constructionTimes"] = [60] * (final - current)
    return [0] * 5


MARKET_OFFER = {"precio": 20, "amountAvailable": 5000, "jugadorAComprar": "Seller", "ciudadDestino": "Shop", "resource": "2"}

MENU = {
    "alertAttacks": {"minutes": 20},
    "alertLowWine": {"hours": 6, "auto_transfer": True, "transfer_amount": 5000},
    "activateShrine": {"godids": (2, 4), "mode": 1, "times": 1, "selected_gods": "Dionysus, Plutus", "wait_time": 3},
    "consolidateResources": {"limits": [100, -1, -1, -1, -1], "sourceCityIds": ["111", "222"], "destinationCityId": "222", "intervalInHours": 2, "shipType": 1},
    "searchForIslandSpaces": {"islandList": ["50", "51"], "time": 30, "fights": "y"},
    "donationBot": {"cities_ids": ["111", "222"], "cities_dict": {"111": {"donation_type": "resource", "percentage": 80}, "222": {"donation_type": None, "percentage": None}}, "waiting_time": 1440, "donate_method": 1},
    "tavernManager": {"run_hours": 2, "cities_ids": ["111"], "cities": OWN[1], "notification_mode": 2, "check_now": False},
    "autoPirate": {"pirateCount": 10, "pirateSchedule": False, "pirateMissionChoice": 2, "pirateMissionDayChoice": None, "pirateMissionNightChoice": None,
                   "dayStart": None, "dayEnd": None, "nightStart": None, "nightEnd": None, "autoConvert": "n", "convertPerMission": 0,
                   "maxRandomWaitingTime": 60, "piracyCities": FORTRESS},
    "webServer": {"port": 43000, "local_network_ip": "192.168.0.10"},
    "loginDaily": {"wine_city": "111", "wood_city": "222", "luxury_city": "222", "favour_tasks": ["resource", "look", "online", "complete"], "collect_ambrosia": True},
    "dumpWorld": {"waiting_time": 1.5, "coords": (50, 60), "radius": 15, "shallow": False, "non_empty_islands": True, "show_progress": True},
    "dumpWorld (shallow)": {"waiting_time": 0.5, "coords": None, "radius": None, "shallow": True, "non_empty_islands": False, "show_progress": True},
    "sendResources": {"routes": [{"from": "111", "to": "222", "resources": [1000, 0, 0, 0, 0]},
                                 {"from": "111", "to": "9000", "island": "4415", "resources": [0, 500, 0, 0, 0]}],
                      "useFreighters": False},
    # sendResources started from an older menu, which saved whole cities in each route
    "sendResources (old menu)": {"routes": [[{"id": "111", "name": "Alpha", "position": []}, {"id": "9000", "isOwnCity": False},
                                             "4415", 1000, 0, 0, 0, 0]], "useFreighters": True},
    "research": {"cities_ids": ["111"], "qty": 2},
    "research (automatic)": {"cities_ids": ["111", "222"], "qty": None},
    # research started from an older menu, which saved the academy cities
    "research (old menu)": {"mode": "experiment", "experiments": {"cityID": "111", "cityName": "Alpha", "pos": 7, "qty": 2},
                            "automatic": False, "info": "Process: Experiments"},
    "research (old menu, automatic)": {"mode": "experiment_multi", "cities": [{"cityID": "111", "cityName": "Alpha", "pos": 7}],
                                       "info": "Process: Experiments (automatic)"},
    # a loginDaily started from the menu before this change: full cities and the long names
    "activateMiracle": {"wonder": "5", "iterations": 3},
    # activateMiracle started from an older menu, which saved the whole island
    "activateMiracle (old menu)": {"island": HERMES, "iterations": 3},
    "UpgradeUnits": {"jobs": [{"city_id": "111", "upgrades": [{"unitId": "303", "upgradeType": "offensive", "target": 8}]}]},
    # UpgradeUnits started from an older menu, which saved every level to upgrade
    "UpgradeUnits (old menu)": {"jobs": [{"city_id": "111", "city_name": "Alpha", "position": 5, "tab": "tabUnits", "tasks": [
        {"unit": "Hoplite", "type": "Damage", "from": "5", "to": "6", "unitId": "303", "upgradeType": "offensive"}]}]},
    "distributeResources": {"resource": "wine", "mode": "even", "cities_ids": ["111", "222"], "useFreighters": False},
    "distributeResources (all cities)": {"resource": "crystal", "mode": "even", "cities_ids": None, "useFreighters": True},
    "resourceTransportManager": {"mode": "consolidate", "origin_cities": ["111"], "destination_city": "222", "interval_hours": 2,
                                 "resource_config": [5000, 0, None, None, None], "useFreighters": False, "send_mode": "keep", "notify": "none"},
    "resourceTransportManager (another player)": {"mode": "consolidate", "origin_cities": ["111", "222"], "destination_city": "9000",
                                                  "island": "4415", "interval_hours": 0, "resource_config": [0, 100, 0, 0, 0],
                                                  "useFreighters": True, "send_mode": "send", "notify": "none"},
    "resourceTransportManager (distribute)": {"mode": "distribute", "origin_city": "111", "destination_cities": ["222"], "interval_hours": 0,
                                              "resource_config": [1000, 0, 0, 0, 0], "useFreighters": False, "notify": "none"},
    # resourceTransportManager started from an older menu, which saved whole cities and the island
    "resourceTransportManager (old menu)": {"mode": "consolidate", "info": "Auto-send resources",
                                            "origin_cities": [{"id": "111", "name": "Alpha", "position": []}],
                                            "destination_city": {"id": "222", "name": "Beta", "isOwnCity": True},
                                            "island": {"id": "77", "x": 1, "y": 2, "cities": []}, "interval_hours": 1,
                                            "resource_config": [0, None, None, None, None], "useFreighters": False, "send_mode": 1,
                                            "telegram_enabled": None, "notify_on_start": False},
    "buyResources": {"city_id": "111", "resource": "marble", "amount": 3000, "max_price": 25, "seller_player": None, "seller_city": None},
    "buyResources (one player)": {"city_id": "111", "resource": "wine", "amount": 100, "max_price": 20, "seller_player": "Seller", "seller_city": None},
    # buyResources started from an older menu, which saved the trading post's city and the offers it showed
    "buyResources (old menu)": {"city": {"id": "111", "name": "Alpha", "position": [], "pos": 4, "rango": 10},
                                "offers": [MARKET_OFFER], "amount_to_buy": 300},
    "sellResources": {"mode": "sell_to_offers", "city_id": "111", "resource": "wood", "amount": 300, "min_price": 10, "buyers": ["9000"]},
    "sellResources (anyone)": {"mode": "sell_to_offers", "city_id": "111", "resource": "wine", "amount": 300, "min_price": None, "buyers": None},
    "sellResources (offer)": {"mode": "create_offer", "city_id": "111", "resource": "marble", "amount": 300, "price": 9},
    # sellResources started from an older menu, which saved the trading post's city and the offers it showed
    "sellResources (old menu)": {"mode": "sell_to_offers", "amount_to_sell": 300, "resource_type": 0,
                                 "offers": [["Shop", "Buyer", 5000, 12, 2, 9000]],
                                 "city_to_buy_from": {"id": "111", "name": "Alpha", "position": []}},
    "sellResources (old menu, offer)": {"mode": "create_offer", "amount_to_sell": 300, "price": 9, "resource_type": 2,
                                        "sell_market_capacity": 14400, "city": {"id": "111", "name": "Alpha", "position": []}},
    "trainArmy": {"city_id": "111", "type": "troops", "rounds": [{"phalanx": 10}, {"phalanx": 5}], "repeat": 2, "replicate_to": None},
    "trainArmy (replicated)": {"city_id": "111", "type": "troops", "rounds": [{"phalanx": 10}], "repeat": 0, "replicate_to": ["222"]},
    # trainArmy started from an older menu, which saved the city and the building's units with their costs
    "trainArmy (old menu)": {"city": {"id": "111", "name": "Alpha", "pos": "4", "position": []}, "trainTroops": True,
                             "tranings": [[dict(PHALANX, cantidad=10)]], "replicate": "n", "countRepeat": 1, "cityTrainings": [],
                             "units": [dict(PHALANX, cantidad=10)]},
    "trainSpies": {"run_hours": 4, "cities_ids": ["111"],
                   "settings": {"target": 10, "goldFloor": 50000, "crystalFloor": 1000, "maxPerPass": 50},
                   "notification_mode": 2, "check_now": False},
    "trainSpies (all cities)": {"run_hours": 6, "cities_ids": None,
                                "settings": {"target": 0, "goldFloor": 0, "crystalFloor": 0, "maxPerPass": 100},
                                "notification_mode": 3, "check_now": False},
    "attackBarbarians": {"island_id": "4415", "city_id": "111", "plan": [
        {"units": {"303": 50}, "loot": False, "round": 1, "ships": 2}, {"units": {"307": 2}, "loot": True, "round": 2}]},
    # attackBarbarians started from an older menu, which saved the island, the city and the barbarians
    "attackBarbarians (old menu)": {"island": dict(BARBARIANS_ISLAND, cities=[]), "city": {"id": "111", "position": []},
                                    "babarians_info": {"ships": 3, "resources": [1] * 5}, "ship_capacity": 500,
                                    "plan": [{"units": {"303": 50}, "loot": False, "round": 1, "ships": 2}]},
    "autoBarbarians": {"island_id": "4415", "city_id": "111", "float_city_id": None, "schematic": "default", "send_notifications": True},
    # autoBarbarians started from an older menu, which saved the island, the city, the scheme and the units' data
    "autoBarbarians (old menu)": {"island": dict(BARBARIANS_ISLAND, cities=[]), "city": {"id": "111", "position": []},
                                  "float_city": None, "schematic": DEFAULT_SCHEMATICS["WITHOUT_HEPHAESTUS"],
                                  "units_data": {"302": {"speed": 60, "weight": 1}}, "ship_capacity": 500, "send_notifications": False},
    "constructionList": {"city_id": "111", "buildings": [
        {"position": 1, "upgradeTo": 9, "transport": {"origins": {"wood": ["222"]}, "useFreighters": False, "useRounding": True}},
        {"position": 0, "upgradeTo": 12}], "transport": None, "expand": True},
    # constructionList started from an older menu, which saved the buildings, the shipments and the times
    "constructionList (old menu)": {"city_id": "111", "city_name": "Alpha",
                                    "buildings": [dict(BUILDINGS_CITY["position"][1], upgradeTo=9, constructionTimes=[60, 60])],
                                    "shipments": [{"origins": {"0": [{"id": "222"}]}, "missing": [5, 0, 0, 0, 0],
                                                   "useFreighters": False, "useRounding": True}],
                                    "expand_overall": False, "wait_resources": True, "construction_queue": [60, 60], "total_time": 120},
    "loginDaily (old menu)": {"wine_city": {"id": 111, "name": "Alpha", "position": []}, "wood_city": None, "luxury_city": None,
                              "favour_tasks": ["Collect resource favour", "Look at hightscore/shop/inventory"], "collect_ambrosia": False},
}


class TestRelaunchFromExportedConfig(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        for mod in ["alertAttacks", "alertLowWine", "searchForIslandSpaces"]:
            stack.enter_context(patch(f"ikabot.function.{mod}.requireNotifications"))
        stack.enter_context(patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN))
        stack.enter_context(patch("ikabot.function.donationBot.getIdsOfCities", return_value=OWN))
        stack.enter_context(patch("ikabot.function.activateShrine.findShrine", return_value=("111", 3)))
        stack.enter_context(patch("ikabot.function.autoPirate.getPiracyCities", return_value=FORTRESS))
        stack.enter_context(patch("ikabot.function.autoPirate.updateProcessList", return_value=[]))
        stack.enter_context(patch("ikabot.function.searchForIslandSpaces.islandIdFromCoords", return_value=50))
        stack.enter_context(patch("ikabot.function.webServer.is_port_in_use", return_value=False))
        # the CI runs without flask, which only the web server needs to start
        find_spec = ikabot.function.webServer.importlib.util.find_spec
        stack.enter_context(patch.object(
            ikabot.function.webServer.importlib.util, "find_spec",
            side_effect=lambda name, *args: object() if name == "flask" else find_spec(name, *args),
        ))
        academy_city = {"id": "111", "name": "Alpha", "position": [{"building": "academy", "position": 7}],
                        "availableResources": [0, 0, 0, 900000, 0]}
        stack.enter_context(patch("ikabot.function.research.getCityById", return_value=academy_city))
        stack.enter_context(patch("ikabot.function.sendResources.getIdsOfCities", return_value=OWN))
        stocked_city = {"id": "111", "name": "Alpha", "islandId": "77", "availableResources": [5000, 5000, 0, 0, 0]}
        stack.enter_context(patch("ikabot.function.sendResources.getCityById", return_value=stocked_city))
        island = {"id": "4415", "x": 50, "y": 60, "cities": [{"type": "city", "id": 9000, "name": "Foreign"}]}
        stack.enter_context(patch("ikabot.function.sendResources.getIsland", return_value=island))
        stack.enter_context(patch("ikabot.function.activateMiracle.obtainMiraclesAvailable", return_value=[HERMES]))
        workshop_city = {"id": "111", "name": "Alpha", "position": [{"building": "workshop", "position": 5, "level": 10}]}
        stack.enter_context(patch("ikabot.function.UpgradeUnits.getCityById", return_value=workshop_city))
        hoplite = {"completeData": {"303": {"offensive": {"currentLevel": {"upgradeLevel": 5}}}}, "unitDetails": {}}
        stack.enter_context(patch("ikabot.function.UpgradeUnits.workshop_tab_data", return_value=hoplite))
        stack.enter_context(patch("ikabot.function.distributeResources.getIdsOfCities", return_value=OWN))
        stack.enter_context(patch("ikabot.function.resourceTransportManager.getIdsOfCities", return_value=OWN))
        stack.enter_context(patch("ikabot.function.distributeResources.plan_routes", return_value=[("a route",)]))
        market = {"id": "111", "name": "Alpha", "freeSpaceForResources": [9000] * 5}
        stack.enter_context(patch("ikabot.function.buyResources.market_city", return_value=market))
        stack.enter_context(patch("ikabot.function.buyResources.live_offers", return_value=[dict(MARKET_OFFER)]))
        stack.enter_context(patch("ikabot.function.buyResources.getGold", return_value=(10 ** 7, 0)))
        stack.enter_context(patch("ikabot.function.sellResources.market_city", return_value=dict(market, availableResources=[9000] * 5)))
        stack.enter_context(patch("ikabot.function.sellResources.getOffers", return_value=[("Shop", "Buyer", 5000, 12, 2, 9000)]))
        stack.enter_context(patch("ikabot.function.sellResources.getMarketInfo", return_value=""))
        stack.enter_context(patch("ikabot.function.sellResources.price_limits", return_value=(4, 21)))
        for mod in ("attackBarbarians", "autoBarbarians"):
            stack.enter_context(patch("ikabot.function.{}.get_island".format(mod), return_value=BARBARIANS_ISLAND))
            stack.enter_context(patch("ikabot.function.{}.getCityById".format(mod), return_value={"id": "111", "islandId": "77"}))
            stack.enter_context(patch("ikabot.function.{}.get_units".format(mod), return_value=CITY_UNITS))
        stack.enter_context(patch("ikabot.function.attackBarbarians.getTotalShips", return_value=10))
        stack.enter_context(patch("ikabot.function.constructionList.getCityById", return_value=BUILDINGS_CITY))
        stack.enter_context(patch("ikabot.function.constructionList.getResourcesNeeded", side_effect=all_levels))
        stack.enter_context(patch("ikabot.function.trainArmy.city_with_building", return_value={"id": "111", "name": "Alpha", "pos": "4"}))
        stack.enter_context(patch("ikabot.function.trainArmy.building_units", return_value=[PHALANX]))
        stack.enter_context(patch("ikabot.function.sellResources.own_offers", return_value=[{"type": "444", "amount": 0, "price": 7}] * 5))

    def test_every_task_relaunches_from_its_exported_config(self):
        session = MagicMock()
        for label, menu_result in MENU.items():
            name = label.split(" ")[0]
            func = _TASK_REGISTRY[name]
            with self.subTest(label):
                # started from the menu: the process list holds the configurator's result
                exported = json.loads(json.dumps(menu_result, default=list))
                first = _validate_task_config(name, func, func.prepare(session, **_validate_task_config(name, func, exported)))
                # started from the CLI: the process list holds the prepare result
                again = _validate_task_config(name, func, func.prepare(session, **json.loads(json.dumps(first))))
                self.assertEqual(again, first)

    def test_covers_every_task_with_a_prepare(self):
        with_prepare = {
            name
            for name, func in _TASK_REGISTRY.items()
            if getattr(func, "prepare", None) and func.__module__.startswith("ikabot.function.")  # not the tests' own tasks
        }
        self.assertLessEqual(with_prepare, {label.split(" ")[0] for label in MENU})


if __name__ == "__main__":
    unittest.main()
