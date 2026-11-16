import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.UpgradeUnits import execute_sequential_upgrades, prepare_UpgradeUnits, run_city_upgrades
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN = (["111", "222"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}})


def city(city_id, workshop_level=10):
    position = [{"building": "townHall", "position": 0, "level": 12}]
    if workshop_level:
        position.append({"building": "workshop", "position": 5, "level": workshop_level})
    return {"id": city_id, "name": {"111": "Alpha", "222": "Beta"}[city_id], "position": position}


class Workshop:
    """The workshop of every city, with levels that go up when an upgrade is sent"""

    def __init__(self):
        self.levels = {("303", "offensive"): 5, ("303", "defensive"): 4, ("210", "offensive"): 2}

    def tab(self, session, city_id, position, tab):
        units = {"tabUnits": {"303": "Hoplite"}, "tabShips": {"210": "Ram ship"}}[tab]
        return {
            "completeData": {
                unit_id: {
                    upgrade_type: {"upgradeTypeDesc": upgrade_type.title(), "currentLevel": {"upgradeLevel": level}}
                    for (uid, upgrade_type), level in self.levels.items()
                    if uid == unit_id
                }
                for unit_id in units
            },
            "unitDetails": {unit_id: {"unitName": name} for unit_id, name in units.items()},
        }

    def upgrade(self, session, city_id, position, unit_id, upgrade_type, action_request, tab):
        self.levels[(unit_id, upgrade_type)] += 1
        return True, None


@patch("ikabot.function.UpgradeUnits.getCityById", side_effect=lambda session, city_id: city(city_id))
@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN)
class TestPrepareUpgradeUnits(unittest.TestCase):
    def setUp(self):
        self.workshop = Workshop()
        patcher = patch("ikabot.function.UpgradeUnits.workshop_tab_data", side_effect=self.workshop.tab)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_is_registered_for_the_cli(self, *_mocks):
        self.assertIs(_TASK_REGISTRY["UpgradeUnits"].prepare, prepare_UpgradeUnits)

    def test_keeps_the_target_levels(self, *_mocks):
        config = prepare_UpgradeUnits(
            MagicMock(),
            jobs=[{"city_id": 111, "upgrades": [{"unitId": 303, "upgradeType": "Offensive", "target": "8"},
                                                {"unitId": "210", "upgradeType": "offensive", "target": 3}]}],
        )
        self.assertEqual(config, {"jobs": [{"city_id": "111", "upgrades": [
            {"unitId": "303", "upgradeType": "offensive", "target": 8},
            {"unitId": "210", "upgradeType": "offensive", "target": 3},
        ]}]})

    def test_accepts_a_config_saved_by_an_older_menu(self, *_mocks):
        steps = [
            {"unit": "Hoplite", "type": "Damage", "from": "5", "to": "6", "unitId": "303", "upgradeType": "offensive"},
            {"unit": "Hoplite", "type": "Damage", "from": "6", "to": "7", "unitId": "303", "upgradeType": "offensive"},
            {"unit": "Hoplite", "type": "Armour", "from": "4", "to": "5", "unitId": "303", "upgradeType": "defensive"},
        ]
        config = prepare_UpgradeUnits(
            MagicMock(), jobs=[{"city_id": "111", "city_name": "Alpha", "position": 5, "tab": "tabUnits", "tasks": steps}]
        )
        self.assertEqual(config["jobs"][0]["upgrades"], [
            {"unitId": "303", "upgradeType": "offensive", "target": 7},
            {"unitId": "303", "upgradeType": "defensive", "target": 5},
        ])

    def test_rejects_bad_jobs(self, mock_ids, mock_city):
        upgrade = {"unitId": "303", "upgradeType": "offensive", "target": 8}
        bad = [
            ([], "jobs must be a list"),
            ([{"city_id": "999", "upgrades": [upgrade]}], "jobs\\[0\\].city_id 999 is not one of your cities"),
            ([{"city_id": "111", "upgrades": []}], "jobs\\[0\\].upgrades must be a list"),
            ([{"city_id": "111", "upgrades": [upgrade]}, {"city_id": "111", "upgrades": [upgrade]}],
             "jobs\\[1\\].city_id 111 is already in jobs\\[0\\]"),
            ([{"city_id": "111", "upgrades": [dict(upgrade, unitId=305)]}],
             "unitId 305 cannot be upgraded in the workshop of Alpha. Units: 303 = Hoplite, 210 = Ram ship"),
            ([{"city_id": "111", "upgrades": [dict(upgrade, upgradeType="speed")]}],
             "upgradeType must be offensive or defensive, got 'speed'"),
            ([{"city_id": "111", "upgrades": [dict(upgrade, target=11)]}],
             "target 11 is above what the workshop of Alpha allows: 10"),
            ([{"city_id": "111", "upgrades": [dict(upgrade, target=5)]}], "every upgrade is already at its target level"),
        ]
        for jobs, error in bad:
            with self.subTest(error):
                with self.assertRaisesRegex(ValueError, error):
                    prepare_UpgradeUnits(MagicMock(), jobs=jobs)

    def test_the_city_needs_a_workshop(self, mock_ids, mock_city):
        mock_city.side_effect = lambda session, city_id: city(city_id, workshop_level=0)
        with self.assertRaisesRegex(ValueError, "Alpha has no workshop"):
            prepare_UpgradeUnits(MagicMock(), jobs=[{"city_id": "111", "upgrades": [{"unitId": "303", "upgradeType": "offensive", "target": 8}]}])


@patch("ikabot.function.UpgradeUnits.sendToBot")
@patch("ikabot.function.UpgradeUnits.time.sleep")
@patch("ikabot.function.UpgradeUnits.wait_for_upgrade_start")
@patch("ikabot.function.UpgradeUnits.wait_for_upgrade_completion")
@patch("ikabot.function.UpgradeUnits.getCityById", side_effect=lambda session, city_id: city(city_id))
class TestUpgradeTask(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.session.get.return_value = '<input name="actionRequest" value="abc123">'
        self.workshop = Workshop()
        for name, side_effect in [("workshop_tab_data", self.workshop.tab), ("send_upgrade_request", self.workshop.upgrade)]:
            patcher = patch("ikabot.function.UpgradeUnits." + name, side_effect=side_effect)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def test_goes_up_one_level_at_a_time_until_each_target(self, *_mocks):
        session = self.session
        run_city_upgrades(session, "111", [{"unitId": "303", "upgradeType": "offensive", "target": 7},
                                           {"unitId": "303", "upgradeType": "defensive", "target": 5}])
        self.assertEqual(self.send_upgrade_request.call_count, 3)
        self.assertEqual(self.workshop.levels[("303", "offensive")], 7)
        self.assertEqual(self.workshop.levels[("303", "defensive")], 5)
        self.assertRegex(session.setStatus.call_args.args[0], r"^Alpha: all workshop upgrades completed @")

    def test_a_relaunched_task_goes_on_from_the_current_level(self, *_mocks):
        self.workshop.levels[("303", "offensive")] = 7
        run_city_upgrades(self.session, "111", [{"unitId": "303", "upgradeType": "offensive", "target": 7}])
        self.send_upgrade_request.assert_not_called()

    def test_stops_when_resources_run_out(self, _city, _wait, _start, _sleep, mock_bot):
        self.send_upgrade_request.side_effect = lambda *args: (False, "insufficient_resources")
        session = self.session
        run_city_upgrades(session, "111", [{"unitId": "303", "upgradeType": "offensive", "target": 7}])
        self.assertEqual(self.send_upgrade_request.call_count, 1)
        self.assertEqual(session.setStatus.call_args.args[0], "Alpha: upgrade aborted: insufficient_resources")
        self.assertIn("Upgrade aborted in city Alpha: insufficient_resources for Hoplite (Offensive)", mock_bot.call_args.args[1])

    @patch("ikabot.function.UpgradeUnits.setInfoSignal")
    def test_runs_every_city(self, *_mocks):
        execute_sequential_upgrades.__wrapped__(
            self.session,
            jobs=[{"city_id": "111", "upgrades": [{"unitId": "303", "upgradeType": "offensive", "target": 6}]},
                  {"city_id": "222", "upgrades": [{"unitId": "210", "upgradeType": "offensive", "target": 3}]}],
        )
        self.assertEqual(self.send_upgrade_request.call_count, 2)
        self.assertEqual({call.args[1] for call in self.send_upgrade_request.call_args_list}, {"111", "222"})


if __name__ == "__main__":
    unittest.main()
