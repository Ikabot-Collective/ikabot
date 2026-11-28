import unittest
from unittest.mock import MagicMock

from ikabot.helpers import pedirInfo

# how the game embeds the cities in the page: a JSON string inside JavaScript, with escaped quotes
HTML = (
    "relatedCityData: JSON.parse('{"
    '\\"city_7668\\":{\\"id\\":7668,\\"name\\":\\"N\\\\u00e9stor en Bloqe\\",\\"relationship\\":\\"ownCity\\",\\"tradegood\\":2},'
    '\\"city_7665\\":{\\"id\\":7665,\\"name\\":\\"Winery\\",\\"relationship\\":\\"ownCity\\",\\"tradegood\\":1},'
    '\\"city_99\\":{\\"id\\":99,\\"name\\":\\"Occupied\\",\\"relationship\\":\\"occupiedCities\\",\\"tradegood\\":3},'
    "\\\"additionalInfo\\\":{}}')"
)


class TestGetIdsOfCities(unittest.TestCase):
    def setUp(self):
        pedirInfo.ids_cache = None
        pedirInfo.cities_cache = None
        self.addCleanup(setattr, pedirInfo, "ids_cache", None)
        self.addCleanup(setattr, pedirInfo, "cities_cache", None)

    def test_names_keep_their_accents(self):
        session = MagicMock(padre=False)
        session.get.return_value = HTML
        ids, cities = pedirInfo.getIdsOfCities(session)
        self.assertEqual(sorted(ids), ["7665", "7668"])
        self.assertEqual(cities["7668"]["name"], "Néstor en Bloqe")
        self.assertEqual(cities["7665"]["name"], "Winery")
        _, every_city = pedirInfo.getIdsOfCities(session, all=True)
        self.assertEqual(every_city["99"]["name"], "Occupied")


if __name__ == "__main__":
    unittest.main()
