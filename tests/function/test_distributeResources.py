from collections import namedtuple
import pytest

import ikabot.config
import ikabot.function.distributeResources
from ikabot.config import materials_names_tec
from ikabot.function.distributeResources import distribute_evenly


def test_distribute_evenly(monkeypatch, session, cities):
    monkeypatch.setattr(ikabot.function.distributeResources, "getIdsOfCities", lambda s: ([city["id"] for city in cities], cities))
    monkeypatch.setattr(ikabot.function.distributeResources, "getCity", lambda city: city)

    # test
    routes = distribute_evenly(session, materials_names_tec.index("wine"))

    sorted_routes = sorted(routes, key=lambda route: route[1]["id"])

    assert sorted_routes == [
        (cities[0], cities[1], cities[1]["islandId"], 0, 200, 0, 0, 0),
        (cities[0], cities[2], cities[2]["islandId"], 0, 200, 0, 0, 0),
    ]


@pytest.fixture()
def cities():
    city_1 = {
        "Id": "111",
        "Name": "City111",
        "x": "1",
        "y": "1",
        "cityName": "City with wine",
        "id": "1",
        "isOwnCity": True,
        "availableResources": [100, 800, 300, 400, 500],
        "storageCapacity": 1000,
        "freeCitizens": 10,
        "wineConsumptionPerHour": 10,
        "resourcesListedForSale": [0, 0, 0, 0, 0],
        "freeSpaceForResources": [],
        "islandId": "100",
    }
    city_2 = {
        "Id": "222",
        "Name": "City222",
        "x": "2",
        "y": "2",
        "cityName": "City #2",
        "id": "2",
        "isOwnCity": True,
        "availableResources": [100, 200, 300, 400, 500],
        "storageCapacity": 1000,
        "freeCitizens": 10,
        "wineConsumptionPerHour": 10,
        "resourcesListedForSale": [0, 0, 0, 0, 0],
        "freeSpaceForResources": [],
        "islandId": "200",
    }
    city_3 = {
        "Id": "333",
        "Name": "City333",
        "x": "3",
        "y": "3",
        "cityName": "City #3",
        "id": "3",
        "isOwnCity": True,
        "availableResources": [100, 200, 300, 400, 500],
        "storageCapacity": 1000,
        "freeCitizens": 10,
        "wineConsumptionPerHour": 10,
        "resourcesListedForSale": [0, 0, 0, 0, 0],
        "freeSpaceForResources": [],
        "islandId": "300",
    }

    cities = [
        city_1,
        city_2,
        city_3,
    ]
    for city in cities:
        for i in range(5):
            city['freeSpaceForResources'].append(city['storageCapacity'] - city['availableResources'][i] - city['resourcesListedForSale'][i]),

    return cities


@pytest.fixture()
def session(cities):
    data = {}
    for city in cities:
        data[ikabot.config.city_url + city["id"]] = city

    def get(url):
        return data[url]

    Session = namedtuple("Session", "get")

    return Session(get)
