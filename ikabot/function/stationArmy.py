import re

from ikabot.config import *
from ikabot.helpers.naval import getAvailableShips
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.varios import addThousandSeparator
from ikabot.helpers.pedirInfo import getShipCapacity

def getCityMilitaryData(session, city_id):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int

    returns
    -------
    data : dict
    """
    params = {
        "view": "cityMilitary",
        "activeTab": "tabUnits",
        "cityId": city_id,
        "currentTab": "tabUnits",
        "currentCityId": city_id,
        "templateView": "cityMilitary",
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    data = session.post(params=params)
    data = json.loads(data, strict=False)
    return data[1][1][1]


def extractTooltipsAndValues(data):
    tooltips = re.findall(r'<div class="tooltip">(.*?)</div>', data)
    values = re.findall(r"<td>\s*([\d.,-]+)\s*</td>", data)
    return tooltips, values


def calculateTotals(tooltips, values):
    total_units = 0
    total_ships = 0

    desc_value_dict = {}

    for i, (tooltip, value) in enumerate(zip(tooltips, values)):
        value = value.replace(",", "")
        is_digit = value.isdigit()
        int_value = int(value) if is_digit else 0

        if value.isdigit() and int_value > 0:
            desc_value_dict.setdefault(tooltip, []).append(int_value)

            if i <= 14:
                total_units += int_value
            else:
                total_ships += int_value

    return desc_value_dict, total_units, total_ships


def getArmyAvailable(session, type_army, destination_city_id, origin_city_id, event):
    params = {
        "view": "deployment",
        "deploymentType": "army" if type_army else "fleet",
        "destinationCityId": destination_city_id,
        "backgroundView": "city",
        "currentCityId": origin_city_id,
        "actionRequest": actionRequest,
        "ajax": 1,
    }
    ship_capacity, freighter_capacity = getShipCapacity(session)

    data = session.post(params=params)
    amount_results = re.findall(r'<div class=\\"amount\\">(.*?)<\\/div>', data)

    if type_army:
        army_results = re.findall(
            r'name=\\"cargo_army_([^\\]+)_upkeep\\"\\n\s+value=\\"([^\\"]+)\\"', data
        )
        weight_total_ships = int(getAvailableShips(session)) * ship_capacity if type_army else 0
        weight_results = re.findall(r'<div class=\\"weight\\">(.*?)<\\/div>', data)
    else:
        army_results = re.findall(
            r'name=\\"cargo_fleet_([^\\]+)_upkeep\\"\\n\s+value=\\"([^\\"]+)\\"', data
        )

    army_available = {}
    weight_total_army = 0

    if army_results:
        for i, result in enumerate(army_results):
            army_code = result[0]
            army = "cargo_{}_{}_upkeep".format(
                "army" if type_army else "fleet", army_code
            )
            army_only = "cargo_{}_{}".format(
                "army" if type_army else "fleet", army_code
            )
            upkeep = result[1]
            quantity = amount_results[i]
            army_available[army] = upkeep
            army_available[army_only] = quantity
            if type_army and weight_results and int(weight_results[i]) > 0:
                weight_total_army += int(quantity) * int(weight_results[i])

        if type_army and weight_total_army > weight_total_ships:
            banner()
            print("Not enough ships to transport all the units!")
            enter()
            return None
        return army_available
    return None


def sendArmy(session, origin_city, destination_city, type_army, army_available):
    params = {
        "action": "transportOperations",
        "function": "deployArmy" if type_army else "deployFleet",
        "actionRequest": actionRequest,
        "islandId": destination_city["islandId"],
        "destinationCityId": destination_city["id"],
        "deploymentType": "army" if type_army else "fleet",
        "backgroundView": "city",
        "currentCityId": origin_city["id"],
        "templateView": "deployment",
        "ajax": 1,
    }

    for army in army_available:
        params[army] = army_available[army]

    session.post(params=params)


def stationArmy(session, event, stdin_fd, predetermined_input):
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input
    type_army = True
    try:
        banner()

        ids, cities = getIdsOfCities(session)
        army = {}
        print("Total:")
        print("{:>19}|{:>19}|{:>19}|".format("", "Units", "Ships"))

        for city_id in cities:
            city = cities[city_id]
            data = getCityMilitaryData(session, city["id"])
            desc, values = extractTooltipsAndValues(data)
            army, total_units, total_ships = calculateTotals(desc, values)

            print(
                "{:>19}|{:>19}|{:>19}|".format(
                    city["name"],
                    addThousandSeparator(total_units),
                    addThousandSeparator(total_ships),
                )
            )

        print()
        print("(0) Back")
        print("(1) Move troops")
        print("(2) Move ships")
        print("(3) Move all ground units to a city.")
        print("(4) Move all maritime units to a city.")
        print("(5) Move all units to a city.")

        selected = read(min=0, max=5, digit=True)
        if selected == 0:
            event.set()
            return
        elif selected in (1, 2):
            print("Origin city:")
            origin_city = chooseCity(session)
            print()
            print("Destination city:")
            destination_city = chooseCity(session)
            if origin_city["id"] == destination_city["id"]:
                banner()
                print("The city of origin and the destination city cannot be the same!")
                enter()
                event.set()
            else:
                type_army = selected == 1
                army_available = getArmyAvailable(
                    session, type_army, destination_city["id"], origin_city["id"], event
                )
                if army_available != None:
                    sendArmy(
                        session,
                        origin_city,
                        destination_city,
                        type_army,
                        army_available,
                    )
                    print("Army sent!")
                    enter()
                    event.set()
                else:
                    print()
                    print(
                        "No {} units available in {}.".format(
                            "ground" if type_army else "maritime", origin_city["name"]
                        )
                    )
                    enter()
                    event.set()
        elif selected in (3, 4, 5):
            print("Destination city:")
            destination_city = chooseCity(session)
            ids, cities = getIdsOfCities(session)

            if selected in (3, 5):
                type_army = True
                for city_id in cities:
                    if city_id != destination_city["id"]:
                        city = cities[city_id]
                        army_available = getArmyAvailable(
                            session,
                            type_army,
                            destination_city["id"],
                            city["id"],
                            event,
                        )
                        if army_available != None:
                            sendArmy(
                                session,
                                city,
                                destination_city,
                                type_army,
                                army_available,
                            )
                        else:
                            print(
                                "No ground units available in {}.".format(city["name"])
                            )
            if selected in (4, 5):
                type_army = False
                for city_id in cities:
                    if city_id != destination_city["id"]:
                        city = cities[city_id]
                        army_available = getArmyAvailable(
                            session,
                            type_army,
                            destination_city["id"],
                            city["id"],
                            event,
                        )
                        if army_available != None:
                            sendArmy(
                                session,
                                city,
                                destination_city,
                                type_army,
                                army_available,
                            )
                        else:
                            print(
                                "No maritime units available in {}.".format(
                                    city["name"]
                                )
                            )
            enter()
            event.set()
    except KeyboardInterrupt:
        event.set()
        return
