#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *
from ikabot.helpers.varios import addThousandSeparator
from ikabot.helpers.taskConfig import asInt, getCityById, findBuildingPosition, requireOwnCity


def getBuildingInfo(session, city, trainTroops):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    trainTroops : bool

    Returns
    -------
    response : dict
    """
    view = "barracks" if trainTroops else "shipyard"
    params = {
        "view": view,
        "cityId": city["id"],
        "position": city["pos"],
        "backgroundView": "city",
        "currentCityId": city["id"],
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    data = session.post(params=params)
    return json.loads(data, strict=False)


def train(session, city, trainings, trainTroops):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    trainings : list[dict]
    trainTroops : bool
    """
    templateView = "barracks" if trainTroops else "shipyard"
    function = "buildUnits" if trainTroops else "buildShips"
    payload = {
        "action": "CityScreen",
        "function": function,
        "actionRequest": "REQUESTID",
        "cityId": city["id"],
        "position": city["pos"],
        "backgroundView": "city",
        "currentCityId": city["id"],
        "templateView": templateView,
        "ajax": "1",
    }
    for training in trainings:
        payload[training["unit_type_id"]] = training["train"]
    session.post(params=payload)


def waitForTraining(session, city, trainTroops):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    trainTroops : bool
    """
    data = getBuildingInfo(session, city, trainTroops)
    html = data[1][1][1]
    seconds = re.search(r"\'buildProgress\', (\d+),", html)
    if seconds:
        seconds = seconds.group(1)
        seconds = int(seconds) - data[0][1]["time"]
        wait(seconds + 5)


def planTrainings(session, city, trainings, trainTroops):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    trainings : list[list[dict]]
    trainTroops : bool

    Returns
    -------
    finished : bool
        False when it stopped for lack of resources
    """
    buildingPos = city["pos"]

    # trainings might be divided in multriple rounds
    while True:

        # total number of units to create
        total = sum([unit["cantidad"] for training in trainings for unit in training])
        if total == 0:
            return True

        for training in trainings:
            waitForTraining(session, city, trainTroops)
            html = session.get(city_url + city["id"])
            city = getCity(html)
            city["pos"] = buildingPos

            resourcesAvailable = city["availableResources"].copy()
            resourcesAvailable.append(city["freeCitizens"])

            # for each unit type in training
            for unit in training:

                # calculate how many units can actually be trained based on the resources available
                unit["train"] = unit["cantidad"]

                for i in range(len(materials_names_english)):
                    material_name = materials_names_english[i].lower()
                    if material_name in unit["costs"]:
                        limiting = resourcesAvailable[i] // unit["costs"][material_name]
                        unit["train"] = min(unit["train"], limiting)

                if "citizens" in unit["costs"]:
                    limiting = (
                        resourcesAvailable[len(materials_names_english)]
                        // unit["costs"]["citizens"]
                    )
                    unit["train"] = min(unit["train"], limiting)

                # calculate the resources that will be left
                for i in range(len(materials_names_english)):
                    material_name = materials_names_english[i].lower()
                    if material_name in unit["costs"]:
                        resourcesAvailable[i] -= (
                            unit["costs"][material_name] * unit["train"]
                        )

                if "citizens" in unit["costs"]:
                    resourcesAvailable[len(materials_names_english)] -= (
                        unit["costs"]["citizens"] * unit["train"]
                    )

                unit["cantidad"] -= unit["train"]

            # amount of units that will be trained
            total = sum([unit["train"] for unit in training])
            if total == 0:
                msg = "It was not possible to finish the training in {} due to lack of resources.".format(city["name"])
                sendToBot(session, msg)
                return False

            train(session, city, training, trainTroops)


def generateArmyData(units_info):
    """
    Parameters
    ----------
    units_info : dict

    Returns
    -------
    units : list[dict]
    """
    i = 1
    units = []
    while "js_barracksSlider{:d}".format(i) in units_info:
        # {'identifier':'phalanx','unit_type_id':303,'costs':{'citizens':1,'wood':27,'sulfur':30,'upkeep':3,'completiontime':71.169695412658},'local_name':'Hoplita'}
        info = units_info["js_barracksSlider{:d}".format(i)]["slider"]["control_data"]
        info = json.loads(info, strict=False)
        units.append(info)
        i += 1
    return units

from ikabot.helpers.decorators import configurator, task

TYPES = {"troops": "barracks", "ships": "shipyard"}


def building_units(session, city, troops):
    """The units the barracks (or shipyard) of ``city`` trains, with their costs
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
        with the building's position in ``pos``
    troops : bool

    Returns
    -------
    units : list[dict]
    """
    return generateArmyData(getBuildingInfo(session, city, troops)[2][1])


def city_with_building(session, city_id, troops):
    """The city, with its barracks' (or shipyard's) position in ``pos``
    Raises ValueError when it does not have one"""
    city = getCityById(session, city_id)
    pos = findBuildingPosition(city, TYPES["troops" if troops else "ships"])
    if pos is None:
        raise ValueError("{} has no {}".format(city["name"], TYPES["troops" if troops else "ships"]))
    city["pos"] = str(pos)
    return city


def unit_key(units, value, name):
    """The identifier of one of ``units``, given its identifier, id or name"""
    text = str(value).strip().lower()
    for unit in units:
        if text in (str(unit["identifier"]).lower(), str(unit["unit_type_id"]), str(unit["local_name"]).lower()):
            return unit["identifier"]
    raise ValueError("{} {!r} is not trained there. Units: {}".format(
        name, value, ", ".join("{} = {} ({})".format(u["identifier"], u["local_name"], u["unit_type_id"]) for u in units)))


def rounds_from_saved(tranings):
    """An older menu saved each round as the building's units with their amounts"""
    rounds = [
        {unit["identifier"]: unit["cantidad"] for unit in training if unit.get("cantidad")}
        for training in tranings
    ]
    # a round where nothing was asked for trains nothing
    return [training for training in rounds if training]


def trainings_for(units, rounds):
    """What planTrainings takes: one list of units with their amounts for each round"""
    return [
        [dict(unit, cantidad=training[unit["identifier"]]) for unit in units if training.get(unit["identifier"])]
        for training in rounds
    ]


def prepare_trainArmy(session, city_id=None, type=None, rounds=None, repeat=0, replicate_to=None, city=None, tranings=None,
                      trainTroops=None, replicate=None, countRepeat=None, cityTrainings=None, units=None):
    """Checks the config of a trainArmy task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int or str
        one of your cities with barracks (troops) or a shipyard (ships)
    type : str
        "troops" or "ships"
    rounds : list[dict]
        trained one after another, each one when the previous has finished, e.g.
        [{"phalanx": 20, "archer": 10}]; units by identifier, id or name
    repeat : int
        how many more times to train all the rounds
    replicate_to : list
        other city ids that train the same rounds; null trains only in city_id
    city, tranings, trainTroops, replicate, countRepeat, cityTrainings, units :
        saved by older menus

    Returns
    -------
    config : dict
    """
    if city is not None:
        city_id = city["id"]
        type = "troops" if trainTroops else "ships"
        rounds = rounds_from_saved(tranings or [])
        repeat = countRepeat or 0
        replicate_to = cityTrainings if str(replicate).lower() == "y" else None
    type = str(type).strip().lower() if type is not None else None
    if type not in TYPES:
        raise ValueError('type must be "troops" (barracks) or "ships" (shipyard), got {!r}'.format(type))
    troops = type == "troops"
    if city_id is None:
        raise ValueError("city_id is needed: one of your cities with {}".format(TYPES[type]))
    city_id = requireOwnCity(session, city_id, "city_id")
    repeat = asInt(repeat if repeat is not None else 0, "repeat", minimum=0)
    main = city_with_building(session, city_id, troops)
    known = building_units(session, main, troops)
    if not isinstance(rounds, (list, tuple)) or not rounds:
        raise ValueError('rounds must be a list like [{{"{}": 10}}], got {!r}'.format(known[0]["identifier"] if known else "phalanx", rounds))
    checked = []
    for i, training in enumerate(rounds):
        if not isinstance(training, dict):
            raise ValueError("rounds[{}] must be an object with units and amounts, got {!r}".format(i, training))
        amounts = {}
        for unit, amount in training.items():
            key = unit_key(known, unit, "rounds[{}]".format(i))
            amounts[key] = amounts.get(key, 0) + asInt(amount, "rounds[{}].{}".format(i, unit), minimum=0)
        amounts = {key: amount for key, amount in amounts.items() if amount > 0}
        if not amounts:
            raise ValueError("rounds[{}] trains nothing".format(i))
        checked.append(amounts)
    others = []
    if replicate_to is not None:
        if not isinstance(replicate_to, (list, tuple)):
            raise ValueError("replicate_to must be a list of your city ids or null, got {!r}".format(replicate_to))
        for i, other in enumerate(replicate_to):
            other = requireOwnCity(session, other, "replicate_to[{}]".format(i))
            # the menu's "all cities" also lists the city itself
            if other != city_id and other not in others:
                city_with_building(session, other, troops)
                others.append(other)
    return {"city_id": city_id, "type": type, "rounds": checked, "repeat": repeat, "replicate_to": others or None}


@task("trainArmy", prepare=prepare_trainArmy)
def do_trainArmy(session, city_id=None, type=None, rounds=None, repeat=0, replicate_to=None, city=None, tranings=None,
                 trainTroops=None, replicate=None, countRepeat=None, cityTrainings=None, units=None):
    """Trains the rounds one after another in city_id and in each city of replicate_to, and
    all of it ``repeat`` more times. Costs and units are read from the building each time
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : str
    type : str
        "troops" or "ships"
    rounds : list[dict]
        identifier -> amount, one dict per round
    repeat : int
    replicate_to : list[str] or None
    city, tranings, trainTroops, replicate, countRepeat, cityTrainings, units :
        saved by older menus
    """
    if city is not None:
        city_id = city["id"]
        type = "troops" if trainTroops else "ships"
        rounds = rounds_from_saved(tranings or [])
        repeat = countRepeat or 0
        replicate_to = cityTrainings if str(replicate).lower() == "y" else None
    troops = type == "troops"
    cities = [str(city_id)] + [str(c) for c in (replicate_to or []) if str(c) != str(city_id)]
    passes = (repeat or 0) + 1
    setInfoSignal(session, "\nI train {} in {} cities, {} round(s), {} time(s)\n".format(type, len(cities), len(rounds), passes))
    problems = []
    for done in range(passes):
        for cid in cities:
            try:
                city_now = city_with_building(session, cid, troops)
            except ValueError as e:
                problems.append(str(e))
                continue
            session.setStatus("Training {} in {} ({}/{})".format(type, city_now["name"], done + 1, passes))
            trainings = trainings_for(building_units(session, city_now, troops), rounds)
            if not planTrainings(session, city_now, trainings, troops):
                problems.append("{}: not enough resources".format(city_now["name"]))
    msg = "Trained {} in {} @{}".format(type, ", ".join(cities), getDateTime())
    if problems:
        msg = "Trained {} @{}, with problems: {}".format(type, getDateTime(), "; ".join(dict.fromkeys(problems)))
        sendToBot(session, msg)
    session.setStatus(msg)


@configurator
def trainArmy(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    banner()

    print("Do you want to train troops (1) or ships (2)?")
    rta = read(min=1, max=2)
    trainTroops = rta == 1
    banner()

    if trainTroops:
        print("In what city do you want to train the troops?")
    else:
        print("In what city do you want to train the fleet?")
    city = chooseCity(session)
    banner()

    lookfor = "barracks" if trainTroops else "shipyard"
    for i in range(len(city["position"])):
        if city["position"][i]["building"] == lookfor:
            city["pos"] = str(i)
            break
    else:
        if trainTroops:
            print("Barracks not built.")
        else:
            print("Shipyard not built.")
        enter()
        return None

    data = getBuildingInfo(session, city, trainTroops)

    units_info = data[2][1]
    units = generateArmyData(units_info)

    maxSize = max([len(unit["local_name"]) for unit in units])

    tranings = []
    while True:
        units = generateArmyData(units_info)
        print("Train:")
        for unit in units:
            pad = " " * (maxSize - len(unit["local_name"]))
            amount = read(
                msg="{}{}:".format(pad, unit["local_name"]), min=0, empty=True
            )
            if amount == "":
                amount = 0
            unit["cantidad"] = amount

        # calculate costs
        cost = [0] * (len(materials_names_english) + 3)
        for unit in units:
            for i in range(len(materials_names_english)):
                material_name = materials_names_english[i].lower()
                if material_name in unit["costs"]:
                    cost[i] += unit["costs"][material_name] * unit["cantidad"]

            if "citizens" in unit["costs"]:
                cost[len(materials_names_english) + 0] += (
                    unit["costs"]["citizens"] * unit["cantidad"]
                )
            if "upkeep" in unit["costs"]:
                cost[len(materials_names_english) + 1] += (
                    unit["costs"]["upkeep"] * unit["cantidad"]
                )
            if "completiontime" in unit["costs"]:
                cost[len(materials_names_english) + 2] += (
                    unit["costs"]["completiontime"] * unit["cantidad"]
                )

        print("\nTotal cost:")
        for i in range(len(materials_names_english)):
            if cost[i] > 0:
                print(
                    "{}: {}".format(
                        materials_names_english[i], addThousandSeparator(cost[i])
                    )
                )
        if cost[len(materials_names_english) + 0] > 0:
            print(
                "Citizens: {}".format(
                    addThousandSeparator(cost[len(materials_names_english) + 0])
                )
            )
        if cost[len(materials_names_english) + 1] > 0:
            print(
                "Maintenance: {}".format(
                    addThousandSeparator(cost[len(materials_names_english) + 1])
                )
            )
        if cost[len(materials_names_english) + 2] > 0:
            print(
                "Duration: {}".format(
                    daysHoursMinutes(int(cost[len(materials_names_english) + 2]))
                )
            )

        print("\nProceed? [Y/n]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            return None

        tranings.append(units)

        if trainTroops:
            print("\nDo you want to train more troops when you finish? [y/N]")
        else:
            print("\nDo you want to train more fleets when you finish? [y/N]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "y":
            banner()
            if trainTroops:
                print("Train new troops (1) or repeat (2)?")
            else:
                print("Train new fleets (1) or repeat (2)?")
            rta = read(min=1, max=2)
            if rta == 1:
                continue
            else:
                print("\nRepeat how many times?")
                countRepeat = read(min=1, default=0)
                break
        else:
            countRepeat = 0
            break

    print("Do you want to replicate the training to other cities? (y/N)")
    replicate = read(values=["y", "Y", "n", "N", ""])
    cityTrainings = []
    if replicate.lower() == "y":
        ids, cities = getIdsOfCities(session)

        print("(0) Back")
        print("(1) All the wine cities")
        print("(2) All the marble cities")
        print("(3) All the cristal cities")
        print("(4) All the sulfur cities")
        print("(5) Choose City")
        print("(6) All City")

        selected = read(min=0, max=6, digit=True)
        if selected == 0:
            return None
        elif selected in [1, 2, 3, 4]:
            cityTrainings = filterCitiesByResource(
                cities, resourceMapping[selected], cityTrainings
            )
        elif selected == 5:
            loop_city = []
            while True:
                loop_city = chooseCity(session)
                if loop_city["id"] in cityTrainings:
                    print("\nYou have already selected this city!")
                    continue
                cityTrainings.append(loop_city["id"])
                print("\nDo you want to add another city? [y/N]")
                rta = read(values=["y", "Y", "n", "N", ""])
                if rta.lower() == "y":
                    continue
                else:
                    break
        elif selected == 6:
            ids, cities = getIdsOfCities(session)
            for cityId in ids:
                cityTrainings.append(cityId)

    # calculate if the city has enough resources
    resourcesAvailable = city["availableResources"].copy()
    resourcesAvailable.append(city["freeCitizens"])

    for training in tranings:
        for unit in training:
            if unit["cantidad"] != 0:
                for i in range(len(materials_names_english)):
                    material_name = materials_names_english[i].lower()
                    if material_name in unit["costs"]:
                        resourcesAvailable[i] -= (
                            unit["costs"][material_name] * unit["cantidad"]
                        )

                if "citizens" in unit["costs"]:
                    resourcesAvailable[len(materials_names_english)] -= (
                        unit["costs"]["citizens"] * unit["cantidad"]
                    )

    not_enough = [elem for elem in resourcesAvailable if elem < 0] != []

    if not_enough:
        print("\nThere are not enough resources:")
        for i in range(len(materials_names_english)):
            if resourcesAvailable[i] < 0:
                print(
                    "{}:{}".format(
                        materials_names[i],
                        addThousandSeparator(resourcesAvailable[i] * -1),
                    )
                )

        if resourcesAvailable[len(materials_names_english)] < 0:
            print(
                "Citizens:{}".format(
                    addThousandSeparator(
                        resourcesAvailable[len(materials_names_english)] * -1
                    )
                )
            )

        print("\nProceed anyway? [Y/n]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            return None

    if trainTroops:
        print("\nThe selected troops will be trained.")
    else:
        print("\nThe selected fleet will be trained.")
    enter()

    # the task reads the units and their costs from the building: the config keeps the
    # amounts the user chose
    return {
        "session": session,
        "city_id": str(city["id"]),
        "type": "troops" if trainTroops else "ships",
        "rounds": rounds_from_saved(tranings),
        "repeat": countRepeat,
        "replicate_to": [str(c) for c in cityTrainings if str(c) != str(city["id"])] or None,
    }


def filterCitiesByResource(cities, resource_id, cityTrainings):
    for cityId, cityData in cities.items():
        if cityData["tradegood"] == resource_id:
            cityTrainings.append(cityData["id"])
    return cityTrainings


resourceMapping = {
    1: "1",  # Wine
    2: "2",  # Marble
    3: "3",  # Cristal
    4: "4",  # Sulfur
}
