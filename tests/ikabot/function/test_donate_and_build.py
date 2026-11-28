import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.constructBuilding import choose_building, prepare_constructBuilding
from ikabot.function.donate import donation_amount, prepare_donate
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN = (["111", "222"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}})


def info(resource_upgrading=False, tradegood_upgrading=False):
    return {
        "islandId": "77", "woodOnInventory": 0,
        "resource": {"name": "Saw mill", "upgrading": resource_upgrading, "endUpgradeTime": 3600 if resource_upgrading else 0},
        "tradegood": {"name": "Quarry", "upgrading": tradegood_upgrading, "endUpgradeTime": 7200 if tradegood_upgrading else 0},
    }


@patch("ikabot.function.donate.donation_info", return_value=info())
@patch("ikabot.function.donate.getCityById", return_value={"id": "111", "name": "Alpha", "availableResources": [5000, 0, 0, 0, 0]})
@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN)
class TestPrepareDonate(unittest.TestCase):
    def test_registered_for_the_cli(self, *_):
        self.assertIs(_TASK_REGISTRY["donate"].prepare, prepare_donate)

    def test_a_number_or_all_or_half_of_the_wood(self, *_):
        self.assertEqual(prepare_donate(MagicMock(), city_id=111, type="wood", amount="1000"),
                         {"city_id": "111", "type": "resource", "amount": 1000})
        self.assertEqual(prepare_donate(MagicMock(), city_id=111, type="tradegood", amount="All")["amount"], "all")
        self.assertEqual((donation_amount("all", 5001), donation_amount("half", 5001), donation_amount(300, 5001)), (5001, 2500, 300))

    def test_rejects_what_cannot_be_donated(self, _ids, _city, mock_info):
        bad = [
            (dict(type="gold", amount=10), 'type must be "resource"'),
            (dict(type="resource"), 'amount is needed'),
            (dict(type="resource", amount=0), "amount must be at least 1"),
            (dict(type="resource", amount=6000), "Alpha has 5.000 wood, asked to donate 6.000"),
            (dict(type="resource", amount=10, city_id=999), "999 is not one of your cities"),
        ]
        for config, error in bad:
            with self.subTest(error):
                with self.assertRaisesRegex(ValueError, error):
                    prepare_donate(MagicMock(), **dict(dict(city_id=111), **config))
        mock_info.return_value = info(tradegood_upgrading=True)
        with self.assertRaisesRegex(ValueError, "the Quarry of Alpha is being upgraded"):
            prepare_donate(MagicMock(), city_id=111, type="tradegood", amount=10)


BUILDINGS = [
    {"building": "museum", "name": "Museum", "buildingId": "10", "type": "land", "costs": [500, 0, 0, 0, 0], "canAfford": True},
    {"building": "palace", "name": "Palace", "buildingId": "11", "type": "land", "costs": [9000, 0, 2000, 0, 0], "canAfford": False},
    {"building": "port", "name": "Trading Port", "buildingId": "3", "type": "shore", "costs": [60, 0, 0, 0, 0], "canAfford": True},
]
CITY = {"id": "111", "name": "Alpha", "availableResources": [1000, 0, 300, 0, 0], "position": [
    {"position": 0, "building": "townHall", "type": "land"},
    {"position": 4, "building": "empty", "type": "land"},
    {"position": 7, "building": "empty", "type": "land"},
    {"position": 1, "building": "port", "type": "shore"},
]}


@patch("ikabot.function.constructBuilding.buildable_buildings", return_value=(BUILDINGS, "REQ"))
class TestChooseBuilding(unittest.TestCase):
    def test_by_technical_name_name_or_id_and_the_first_free_place(self, _):
        building, place, _ = choose_building(MagicMock(), CITY, "MUSEUM")
        self.assertEqual((building["buildingId"], place["position"]), ("10", 4))
        self.assertEqual(choose_building(MagicMock(), CITY, "Museum", position=7)[1]["position"], 7)
        self.assertEqual(choose_building(MagicMock(), CITY, 10)[0]["building"], "museum")

    def test_what_cannot_be_built(self, _):
        bad = [
            (("theatre",), "building 'theatre' cannot be built in Alpha. Buildings: museum = Museum, palace = Palace, port = Trading Port"),
            (("palace",), "Alpha lacks resources to build Palace: 8.000 Wood \\(has 1.000\\), 1.700 Marble \\(has 300\\)"),
            (("port",), "Alpha has no free place for Trading Port"),
            (("museum", 0), "position 0 is not a free place for Museum in Alpha. Free places for it: 4, 7"),
        ]
        for args, error in bad:
            with self.subTest(error):
                with self.assertRaisesRegex(ValueError, error):
                    choose_building(MagicMock(), CITY, *args)

    @patch("ikabot.function.constructBuilding.getCityById", return_value=CITY)
    @patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN)
    def test_prepare(self, *_):
        self.assertIs(_TASK_REGISTRY["constructBuilding"].prepare, prepare_constructBuilding)
        self.assertEqual(prepare_constructBuilding(MagicMock(), city_id=111, building="Museum"),
                         {"city_id": "111", "building": "museum", "position": None})
        self.assertEqual(prepare_constructBuilding(MagicMock(), city_id=111, building="museum", position="7")["position"], 7)
        with self.assertRaisesRegex(ValueError, "building is needed"):
            prepare_constructBuilding(MagicMock(), city_id=111)


if __name__ == "__main__":
    unittest.main()
