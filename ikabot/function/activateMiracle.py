#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import traceback

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *


def obtainMiraclesAvailable(session):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session

    Returns
    -------
    islands: list[dict]
    """
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


def activateMiracleHttpCall(session, island):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    island : dict

    Returns
    -------
    json : dict
    """
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


def chooseIsland(islands):
    """
    Parameters
    ----------
    islands : list[dict]

    Returns
    -------
    island : dict
    """
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


def activateMiracle(session, event, stdin_fd, predetermined_input):
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

        islands = obtainMiraclesAvailable(session)
        if islands == []:
            print("There are no miracles available.")
            enter()
            event.set()
            return

        island = chooseIsland(islands)
        if island is None:
            event.set()
            return

        if island['available']:
            print(_('\nThe miracle {} will be activated.\nAfter cooldown, it will be reactivated.').format(island['wonderName']))
            print(_('Proceed? [Y/n]'))
            activate_miracle_input = read(values=['y', 'Y', 'n', 'N', ''])
            if activate_miracle_input.lower() == 'n':
                event.set()
                return

            miracle_activation_result = activateMiracleHttpCall(session, island)

            if miracle_activation_result[1][1][0] == "error":
                print(
                    "The miracle {} could not be activated.".format(
                        island["wonderName"]
                    )
                )
                enter()
                event.set()
                return

            data = miracle_activation_result[2][1]
            for elem in data:
                if "countdown" in data[elem]:
                    enddate = data[elem]["countdown"]["enddate"]
                    currentdate = data[elem]["countdown"]["currentdate"]
                    break
            wait_time = enddate - currentdate

            print(_('The miracle {} was activated.').format(island['wonderName']))
            #enter()
            banner()
            iterations = 1000
        else:
            print(_('\nThe miracle {} will be activated in {}.\nAfter cooldown, it will be reactivated.').format(island['wonderName'], daysHoursMinutes(island['available_in'])))
            print(_('Proceed? [Y/n]'))
            user_confirm = read(values=['y', 'Y', 'n', 'N', ''])
            if user_confirm.lower() == 'n':
                event.set()
                return
            wait_time = island['available_in']
            iterations = 1000

            print(_('\nThe miracle will be activated.'))
            #enter()
            banner()
    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()

    info = "\nI activate the miracle {} {:d} times\n".format(
        island["wonderName"], iterations
    )
    setInfoSignal(session, info)
    try:
        do_it(session, island, iterations)
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def wait_for_miracle(session, island):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    island : dict
    """
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


def do_it(session, island, iterations):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    island : dict
    iterations : int
    """
    iterations_left = iterations
    for i in range(iterations):

        wait_for_miracle(session, island)

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
