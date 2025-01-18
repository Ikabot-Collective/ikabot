#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import traceback

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.varios import *

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ikabot.web.session import Session


ActivateMiracleConfig = TypedDict("ActivateMiracleConfig", {"island": dict, "iterations": int})
def activateMiracle(session: Session) -> ActivateMiracleConfig:
    
    banner()
    islands = obtainMiraclesAvailable(session)
    if islands == []:
        print("There are no miracles available.")
        enter()
        return

    island = chooseIsland(islands)
    if island is None:
        return

    if island["available"]:
        print("\nThe miracle {} will be activated".format(island["wonderName"]))
        print("Proceed? [Y/n]")
        activate_miracle_input = read(values=["y", "Y", "n", "N", ""])
        if activate_miracle_input.lower() == "n":
            return

        miracle_activation_result = activateMiracleHttpCall(session, island)

        if miracle_activation_result[1][1][0] == "error":
            print(
                "The miracle {} could not be activated.".format(
                    island["wonderName"]
                )
            )
            enter()
            return

        data = miracle_activation_result[2][1]
        for elem in data:
            if "countdown" in data[elem]:
                enddate = data[elem]["countdown"]["enddate"]
                currentdate = data[elem]["countdown"]["currentdate"]
                break
        wait_time = enddate - currentdate

        print("The miracle {} was activated.".format(island["wonderName"]))
        enter()
        banner()

        while True:
            print("Do you wish to activate it again when it is finished? [y/N]")

            reactivate_again_input = read(values=["y", "Y", "n", "N", ""])
            if reactivate_again_input.lower() != "y":
                return

            iterations = read(msg="How many times?: ", digit=True, min=0)

            if iterations == 0:
                return

            duration = wait_time * iterations

            print("It will finish in:{}".format(daysHoursMinutes(duration)))

            print("Proceed? [Y/n]")
            reactivate_again_input = read(values=["y", "Y", "n", "N", ""])
            if reactivate_again_input.lower() == "n":
                banner()
                continue
            break
    else:
        print(
            "\nThe miracle {} will be activated in {}".format(
                island["wonderName"], daysHoursMinutes(island["available_in"])
            )
        )
        print("Proceed? [Y/n]")
        user_confirm = read(values=["y", "Y", "n", "N", ""])
        if user_confirm.lower() == "n":
            return
        wait_time = island["available_in"]
        iterations = 1

        print("\nThe miracle will be activated.")
        enter()
        banner()

        while True:
            print("Do you wish to activate it again when it is finished? [y/N]")

            reactivate_again_input = read(values=["y", "Y", "n", "N", ""])
            again = reactivate_again_input.lower() == "y"
            if again is True:
                try:
                    iterations = read(msg="How many times?: ", digit=True, min=0)
                except KeyboardInterrupt:
                    iterations = 1
                    break

                if iterations == 0:
                    iterations = 1
                    break

                iterations += 1
                duration = wait_time * iterations
                print("It is not possible to calculate the time of finalization. (at least: {})".format(daysHoursMinutes(duration)))
                print("Proceed? [Y/n]")

                try:
                    activate_input = read(values=["y", "Y", "n", "N", ""])
                except KeyboardInterrupt:
                    iterations = 1
                    break

                if activate_input.lower() == "n":
                    iterations = 1
                    banner()
                    continue
            break
    
    return {'island': island, 'iterations': iterations}

def do_it(session: Session, island: dict, iterations: int):
    
    iterations_left = iterations
    for i in range(iterations):

        waitForMiracle(session, island)

        response = activateMiracleHttpCall(session, island)

        if response[1][1][0] == "error":
            msg = "The miracle {} could not be activated.".format(
                island["wonderName"]
            )
            sendToBot(session, msg)
            return
        iterations_left -= 1
        session.setStatus(
            f"Activated {island['wonderName']} @{getDateTime()}, iterations left: {iterations_left}"
        )
        msg = "Miracle {} successfully activated".format(island["wonderName"])
        sendToBotDebug(session, msg, debugON_activateMiracle)

def obtainMiraclesAvailable(session: Session) -> list[dict]:
    """Returns a list of islands with available miracles"""
    
    idsIslands = getIslandsIds(session)
    islands = []
    for idIsland in idsIslands:
        html = session.get(island_url + idIsland)
        island = getIsland(html)
        island["activable"] = False
        islands.append(island)

    ids, cities = getIdsOfCities(session)
    for city_id in cities:
        city = cities[city_id]
        # get the wonder for this city
        wonder = [
            island["wonder"]
            for island in islands
            if city["coords"] == "[{}:{}] ".format(island["x"], island["y"])
        ][0]
        # if the wonder is not new, continue
        if wonder in [island["wonder"] for island in islands if island["activable"]]:
            continue

        html = session.get(city_url + str(city["id"]))
        city = getCity(html)

        # make sure that the city has a temple
        for i in range(len(city["position"])):
            if city["position"][i]["building"] == "temple":
                city["pos"] = str(i)
                break
        else:
            continue

        # get wonder information
        params = {
            "view": "temple",
            "cityId": city["id"],
            "position": city["pos"],
            "backgroundView": "city",
            "currentCityId": city["id"],
            "actionRequest": actionRequest,
            "ajax": "1",
        }
        data = session.post(params=params)
        data = json.loads(data, strict=False)
        html = data[1][1][1]
        match = re.search(r'<div id="wonderLevelDisplay"[^>]*>\\n\s*(\d+)\s*</div>', html)
        level = 0
        if match:
            level = int(match.group(1))

        data = data[2][1]
        available = data["js_WonderViewButton"]["buttonState"] == "enabled"
        if available is False:
            for elem in data:
                if "countdown" in data[elem]:
                    enddate = data[elem]["countdown"]["enddate"]
                    currentdate = data[elem]["countdown"]["currentdate"]
                    break

        # set the information on the island which wonder we can activate
        for island in islands:
            if island["id"] == city["islandId"]:
                island["activable"] = True
                island["ciudad"] = city
                island["wonderActivationLevel"] = level
                island["available"] = available
                if available is False:
                    island["available_in"] = enddate - currentdate
                break

    # only return island which wonder we can activate
    return [island for island in islands if island["activable"]]


def activateMiracleHttpCall(session: Session, island: dict) -> dict:
    """Makes an http call to activate a miracle on some island."""
    params = {
        "action": "CityScreen",
        "cityId": island["ciudad"]["id"],
        "function": "activateWonder",
        "position": island["ciudad"]["pos"],
        "backgroundView": "city",
        "currentCityId": island["ciudad"]["id"],
        "templateView": "temple",
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    response = session.post(params=params)
    return json.loads(response, strict=False)


def chooseIsland(islands: list[dict]) -> dict:
    print("Which miracle do you want to activate?")
    # Sort islands by name
    sorted_islands = sorted(islands, key=lambda x: x["wonderName"])
    i = 0
    print("(0) Exit")
    for island in sorted_islands:
        i += 1
        if island["available"]:
            print("({:d}) {}".format(i, island["wonderName"]))
        else:
            print(
                "({:d}) {} (available in: {})".format(
                    i, island["wonderName"], daysHoursMinutes(island["available_in"])
                )
            )

    index = read(min=0, max=i)
    if index == 0:
        return None
    island = sorted_islands[index - 1]
    return island

def waitForMiracle(session: Session, island: dict):
    while True:
        params = {
            "view": "temple",
            "cityId": island["ciudad"]["id"],
            "position": island["ciudad"]["pos"],
            "backgroundView": "city",
            "currentCityId": island["ciudad"]["id"],
            "actionRequest": actionRequest,
            "ajax": "1",
        }
        temple_response = session.post(params=params)
        temple_response = json.loads(temple_response, strict=False)
        temple_response = temple_response[2][1]

        for elem in temple_response:
            if "countdown" in temple_response[elem]:
                enddate = temple_response[elem]["countdown"]["enddate"]
                currentdate = temple_response[elem]["countdown"]["currentdate"]
                wait_time = enddate - currentdate
                break
        else:
            available = (
                temple_response["js_WonderViewButton"]["buttonState"] == "enabled"
            )
            if available:
                return
            else:
                wait_time = 60

        msg = "I wait {:d} seconds to activate the miracle {}".format(
            wait_time, island["wonderName"]
        )
        sendToBotDebug(session, msg, debugON_activateMiracle)
        wait(wait_time + 5)



