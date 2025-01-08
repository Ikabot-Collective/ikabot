#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import copy
import json
import re
import traceback

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.resources import getAvailableResources
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *
from ikabot.helpers.varios import addThousandSeparator


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
    """
    buildingPos = city["pos"]

    # trainings might be divided in multriple rounds
    while True:

        # total number of units to create
        total = sum([unit["cantidad"] for training in trainings for unit in training])
        if total == 0:
            return

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
                msg = "It was not possible to finish the training due to lack of resources."
                
                sendToBot(session, msg)
                return

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


def trainArmy(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input
    try:
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
            event.set()
            return

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
                event.set()
                return

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
        if replicate.lower() == "y":
            cityTrainings = []
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
                event.set()
                return
            elif selected in [1, 2, 3, 4]:
                cityTrainings = filterCitiesByResource(
                    cities, resourceMapping[selected], cityTrainings
                )
            elif selected == 5:
                city = []
                while True:
                    city = chooseCity(session)
                    if city["id"] in cityTrainings:
                        print("\nYou have already selected this city!")
                        continue
                    cityTrainings.append(city["id"])
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
                event.set()
                return

        if trainTroops:
            print("\nThe selected troops will be trained.")
        else:
            print("\nThe selected fleet will be trained.")
        enter()

        if replicate == "y":
            countRepeat = countRepeat + 1
            while countRepeat > 0:
                for cityId in cityTrainings:
                    html = session.get(city_url + str(cityId))
                    city = getCity(html)

                    lookfor = "barracks" if trainTroops else "shipyard"
                    try:
                        for i in range(len(city["position"])):
                            if city["position"][i]["building"] == lookfor:
                                city["pos"] = str(i)
                                tranings_copy = []
                                units_copy = copy.deepcopy(units)
                                tranings_copy.append(units_copy)
                                loop = asyncio.get_event_loop()
                                loop.run_until_complete(
                                    planTrainings(
                                        session, city, tranings_copy, trainTroops
                                    )
                                )
                                break
                    except Exception as e:
                        if trainTroops:
                            info = "\nI train troops in {}\n".format(
                                city["cityName"]
                            )
                        else:
                            info = "\nI train fleets in {}\n".format(
                                city["cityName"]
                            )
                        msg = "Error in:\n{}\nCause:\n{}".format(
                            info, traceback.format_exc()
                        )
                        sendToBot(session, msg)
                countRepeat = countRepeat - 1

        else:
            if trainTroops:
                info = "\nI train troops in {}\n".format(city["cityName"])
            else:
                info = "\nI train fleets in {}\n".format(city["cityName"])
            setInfoSignal(session, info)
            try:
                planTrainings(session, city, tranings, trainTroops)
            except Exception as e:
                msg = "Error in:\n{}\nCause:\n{}".format(
                    info, traceback.format_exc()
                )
                sendToBot(session, msg)
            finally:
                session.logout()
    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()


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
