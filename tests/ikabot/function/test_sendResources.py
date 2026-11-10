import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.sendResources import do_it, prepare_sendResources
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN_CITIES = (["111", "222"], {"111": {"name": "Alpha"}, "222": {"name": "Nu00e9stor"}})
ISLAND = {
    "id": "4415",
    "x": 50,
    "y": 60,
    "cities": [{"type": "city", "id": 9000, "name": "Foreign"}, {"type": "empty"}],
}


def game_city(session, city_id):
    return {"id": city_id, "name": {"111": "Alpha", "222": "Néstor"}[city_id], "islandId": "77",
            "availableResources": [10000, 5000, 0, 0, 0]}


@patch("ikabot.function.sendResources.getIsland", return_value=ISLAND)
@patch("ikabot.function.sendResources.getCityById", side_effect=game_city)
@patch("ikabot.function.sendResources.getIdsOfCities", return_value=OWN_CITIES)
@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN_CITIES)
class TestPrepareSendResources(unittest.TestCase):
    def test_is_registered_for_the_cli(self, *_mocks):
        self.assertIs(_TASK_REGISTRY["sendResources"].prepare, prepare_sendResources)

    def test_between_own_cities(self, *_mocks):
        config = prepare_sendResources(
            MagicMock(),
            routes=[
                {"from": 111, "to": "222", "resources": [5000, 0, 0, 0, 0]},
                {"from": "111", "to": 222, "resources": {"wine": 2000}},
            ],
        )
        self.assertEqual(
            config,
            {
                "routes": [
                    {"from": "111", "to": "222", "resources": [5000, 0, 0, 0, 0]},
                    {"from": "111", "to": "222", "resources": [0, 2000, 0, 0, 0]},
                ],
                "useFreighters": False,
            },
        )

    def test_to_another_players_city_needs_its_island(self, *_mocks):
        route = {"from": "111", "to": 9000, "resources": [1000, 0, 0, 0, 0]}
        with self.assertRaisesRegex(ValueError, 'routes\\[0\\].island is needed when "to" is not your city'):
            prepare_sendResources(MagicMock(), routes=[route])
        config = prepare_sendResources(MagicMock(), routes=[dict(route, island="50:60")], useFreighters="y")
        self.assertEqual(config["routes"][0]["island"], "4415")
        self.assertIs(config["useFreighters"], True)
        with self.assertRaisesRegex(ValueError, "routes\\[0\\].to 9001 is not on island 50:60"):
            prepare_sendResources(MagicMock(), routes=[dict(route, to=9001, island="4415")])

    def test_accepts_a_config_saved_by_an_older_menu(self, *_mocks):
        alpha = {"id": "111", "name": "Alpha", "position": ["lots", "of", "data"]}
        foreign = {"id": "9000", "name": "Foreign", "isOwnCity": False}
        config = prepare_sendResources(MagicMock(), routes=[[alpha, foreign, "4415", 1000, 0, 0, 0, 0]], useFreighters=False)
        self.assertEqual(config["routes"], [{"from": "111", "to": "9000", "resources": [1000, 0, 0, 0, 0], "island": "4415"}])

    def test_rejects_bad_routes(self, *_mocks):
        bad = [
            ([], "routes must be a list"),
            ([{"from": "111", "to": "111", "resources": [1, 0, 0, 0, 0]}], "routes\\[0\\] sends from city 111 to itself"),
            ([{"from": "111", "to": "222", "resources": [0, 0, 0, 0, 0]}], "routes\\[0\\].resources sends nothing"),
            ([{"from": "111", "to": "222", "resources": [1, 2]}], "routes\\[0\\].resources must be 5 amounts"),
            ([{"from": "111", "to": "222", "resources": {"gold": 5}}], "unknown resources \\['gold'\\]"),
            ([{"from": "999", "to": "222", "resources": [1, 0, 0, 0, 0]}], "routes\\[0\\].from 999 is not one of your cities"),
        ]
        for routes, error in bad:
            with self.subTest(error):
                with self.assertRaisesRegex(ValueError, error):
                    prepare_sendResources(MagicMock(), routes=routes)

    def test_the_origin_must_have_what_all_its_routes_send(self, *_mocks):
        with self.assertRaisesRegex(ValueError, "Alpha has 10.000 wood, the routes send 12.000"):
            prepare_sendResources(
                MagicMock(),
                routes=[
                    {"from": "111", "to": "222", "resources": [6000, 0, 0, 0, 0]},
                    {"from": "111", "to": 9000, "island": "4415", "resources": [6000, 0, 0, 0, 0]},
                ],
            )


@patch("ikabot.function.sendResources.setInfoSignal")
@patch("ikabot.function.sendResources.executeRoutes")
@patch("ikabot.function.sendResources.getIsland", return_value=ISLAND)
@patch("ikabot.function.sendResources.getCityById", side_effect=game_city)
@patch("ikabot.function.sendResources.getIdsOfCities", return_value=OWN_CITIES)
class TestSendResourcesTask(unittest.TestCase):
    def test_finds_the_names_and_islands_for_the_shipments(self, _ids, _city, _island, mock_execute, _info):
        session = MagicMock()
        do_it.__wrapped__(
            session,
            routes=[
                {"from": "111", "to": "222", "resources": [5000, 0, 0, 0, 0]},
                {"from": "222", "to": "9000", "island": "4415", "resources": [0, 100, 0, 0, 0]},
            ],
            useFreighters=True,
        )
        shipments, use_freighters = mock_execute.call_args.args[1], mock_execute.call_args.args[2]
        self.assertEqual(
            shipments,
            [
                ({"id": "111", "name": "Alpha"}, {"id": "222", "name": "Néstor"}, "77", 5000, 0, 0, 0, 0),
                ({"id": "222", "name": "Néstor"}, {"id": "9000", "name": "Foreign"}, "4415", 0, 100, 0, 0, 0),
            ],
        )
        self.assertIs(use_freighters, True)


if __name__ == "__main__":
    unittest.main()
