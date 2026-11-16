import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.distributeResources import do_it, plan_routes, prepare_distributeResources
from ikabot.helpers.decorators import _TASK_REGISTRY

# Alpha and Gamma produce wine, Beta crystal
OWN = (["111", "222", "333"], {"111": {"name": "Alpha", "tradegood": 1}, "222": {"name": "Beta", "tradegood": 3},
                               "333": {"name": "Gamma", "tradegood": 1}})
ROUTES = [({"id": "111", "name": "Alpha"}, {"id": "222", "name": "Beta"}, "77", 0, 500, 0, 0, 0)]


@patch("ikabot.function.distributeResources.plan_routes", return_value=ROUTES)
@patch("ikabot.function.distributeResources.getIdsOfCities", return_value=OWN)
@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN)
class TestPrepareDistributeResources(unittest.TestCase):
    def test_is_registered_for_the_cli(self, *_mocks):
        self.assertIs(_TASK_REGISTRY["distributeResources"].prepare, prepare_distributeResources)

    def test_evenly_among_all_the_cities_by_default(self, _ids, _own, mock_plan):
        config = prepare_distributeResources(MagicMock(), resource="Wine")
        self.assertEqual(config, {"resource": "wine", "mode": "even", "cities_ids": None, "useFreighters": False})
        self.assertEqual(mock_plan.call_args.args[1:], (1, "even", ["111", "222", "333"]))

    def test_some_cities_from_the_producers(self, _ids, _own, mock_plan):
        config = prepare_distributeResources(MagicMock(), resource="wine", mode="producers", cities_ids=[111, "222", 111],
                                             useFreighters="y")
        self.assertEqual(config, {"resource": "wine", "mode": "producers", "cities_ids": ["111", "222"], "useFreighters": True})

    def test_rejects_bad_values(self, *_mocks):
        bad = [
            ({"resource": "gold"}, "resource must be one of wood, wine, marble, crystal, sulfur, got 'gold'"),
            ({"resource": "wine", "mode": "random"}, 'mode must be "even"'),
            ({"resource": "wood", "mode": "producers"}, 'every city produces wood: use mode "even"'),
            ({"resource": "wine", "cities_ids": [111]}, "cities_ids needs at least 2 cities, got 1"),
            ({"resource": "wine", "cities_ids": "111"}, "cities_ids must be a list"),
            ({"resource": "wine", "cities_ids": [111, 999]}, "cities_ids\\[1\\] 999 is not one of your cities"),
            ({"resource": "marble", "mode": "producers"}, "none of the cities produces marble"),
            ({"resource": "wine", "mode": "producers", "cities_ids": [111, 333]}, "every city produces wine: there is nowhere to send it"),
        ]
        for config, error in bad:
            with self.subTest(error):
                with self.assertRaisesRegex(ValueError, error):
                    prepare_distributeResources(MagicMock(), **config)

    def test_needs_something_to_send(self, _ids, _own, mock_plan):
        mock_plan.side_effect = ValueError("there is nothing to distribute")
        with self.assertRaisesRegex(ValueError, "there is nothing to distribute"):
            prepare_distributeResources(MagicMock(), resource="wine")

    def test_a_config_saved_by_an_older_menu_holds_old_shipments(self, *_mocks):
        with self.assertRaisesRegex(ValueError, 'saved by an older menu .* "resource", "mode" and "cities_ids"'):
            prepare_distributeResources(MagicMock(), resource=1, routes=ROUTES, useFreighters=False)


@patch("ikabot.function.distributeResources.getIdsOfCities", return_value=OWN)
class TestPlanRoutes(unittest.TestCase):
    @patch("ikabot.function.distributeResources.distribute_unevenly", return_value=ROUTES)
    @patch("ikabot.function.distributeResources.distribute_evenly", return_value=[])
    def test_uses_the_mode_and_reports_when_there_is_nothing_to_send(self, mock_even, mock_uneven, _ids):
        self.assertEqual(plan_routes(MagicMock(), 1, "producers", ["111", "222"]), ROUTES)
        with self.assertRaisesRegex(ValueError, "there is nothing to distribute: the cities already have about the same wine"):
            plan_routes(MagicMock(), 1, "even", ["111", "222"])

    @patch("ikabot.function.distributeResources.getCity")
    def test_producers_without_anything_to_send(self, mock_city, _ids):
        mock_city.return_value = {"availableResources": [0, 10, 0, 0, 0], "wineConsumptionPerHour": 20,
                                  "freeSpaceForResources": [0, 1000, 0, 0, 0], "islandId": "77"}
        with self.assertRaisesRegex(ValueError, "the cities that produce wine have none to send"):
            plan_routes(MagicMock(), 1, "producers", ["111", "222"])


@patch("ikabot.function.distributeResources.setInfoSignal")
@patch("ikabot.function.distributeResources.sendToBot")
@patch("ikabot.function.distributeResources.executeRoutes")
@patch("ikabot.function.distributeResources.plan_routes", return_value=ROUTES)
@patch("ikabot.function.distributeResources.getIdsOfCities", return_value=OWN)
class TestDistributeResourcesTask(unittest.TestCase):
    def test_works_out_the_shipments_when_it_starts(self, _ids, mock_plan, mock_execute, _bot, _info):
        session = MagicMock()
        do_it.__wrapped__(session, resource="wine", mode="producers", cities_ids=["111", "222"], useFreighters=True)
        self.assertEqual(mock_plan.call_args.args[1:], (1, "producers", ["111", "222"]))
        self.assertEqual(mock_execute.call_args.args[1:], (ROUTES, True))
        self.assertRegex(session.setStatus.call_args.args[0], r"^Distributed wine in 1 shipments @")

    def test_all_the_cities(self, _ids, mock_plan, *_mocks):
        do_it.__wrapped__(MagicMock(), resource="crystal")
        self.assertEqual(mock_plan.call_args.args[1:], (3, "even", ["111", "222", "333"]))

    def test_reports_when_there_is_nothing_to_send(self, _ids, mock_plan, mock_execute, mock_bot, _info):
        mock_plan.side_effect = ValueError("there is nothing to distribute")
        session = MagicMock()
        do_it.__wrapped__(session, resource="wine")
        mock_execute.assert_not_called()
        self.assertEqual(session.setStatus.call_args.args[0], "Distribute wine: there is nothing to distribute")
        self.assertEqual(mock_bot.call_args.args[1], "Distribute wine: there is nothing to distribute")

    def test_a_task_started_by_an_older_menu_sends_its_shipments(self, _ids, mock_plan, mock_execute, *_mocks):
        do_it.__wrapped__(MagicMock(), resource=1, routes=ROUTES, useFreighters=False)
        mock_plan.assert_not_called()
        self.assertEqual(mock_execute.call_args.args[1:], (ROUTES, False))


if __name__ == "__main__":
    unittest.main()
