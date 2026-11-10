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
import ikabot.function.webServer, ikabot.function.loginDaily  # noqa
from ikabot.helpers.decorators import _TASK_REGISTRY
from ikabot.helpers.ipc import _validate_task_config

OWN = (["111", "222"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}})
FORTRESS = [{"id": "111", "name": "Alpha", "position": [{"building": "pirateFortress"}]}]

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
    # a loginDaily started from the menu before this change: full cities and the long names
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
