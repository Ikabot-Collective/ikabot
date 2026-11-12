#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import traceback

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.decorators import configurator, task
from ikabot.helpers.getJson import getCity, getIsland
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planRoutes import executeRoutes
from ikabot.helpers.resources import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.taskConfig import asBool, asId, asInt, getCityById, requireOwnCity
from ikabot.helpers.varios import addThousandSeparator, decodeUnicodeEscape


RESOURCE_KEYS = ("wood", "wine", "marble", "crystal", "sulfur")


def route_from_saved(route):
    """A route as {"from", "to", "resources"[, "island"]}; an older menu saved
    (origin city, destination city, island id, wood, wine, marble, crystal, sulfur)"""
    if isinstance(route, (list, tuple)) and len(route) == 3 + len(RESOURCE_KEYS):
        origin, destination, island_id = route[0], route[1], route[2]
        return {
            "from": origin["id"] if isinstance(origin, dict) else origin,
            "to": destination["id"] if isinstance(destination, dict) else destination,
            "island": island_id,
            "resources": list(route[3:]),
        }
    return route


def get_island(session, value, name):
    """The island with this id or "X:Y" coordinates, as returned by getIsland"""
    text = str(value).strip()
    if re.fullmatch(r"\d+\s*:\s*\d+", text):
        x, y = text.replace(" ", "").split(":")
        return getIsland(session.get("view=island&xcoord={}&ycoord={}".format(x, y)))
    return getIsland(session.get(island_url + asId(value, name)))


def resource_amounts(value, name):
    if isinstance(value, dict):
        unknown = [key for key in value if key not in RESOURCE_KEYS]
        if unknown:
            raise ValueError("{} has unknown resources {}, use {}".format(name, unknown, ", ".join(RESOURCE_KEYS)))
        value = [value.get(key, 0) for key in RESOURCE_KEYS]
    if not isinstance(value, (list, tuple)) or len(value) != len(RESOURCE_KEYS):
        raise ValueError(
            "{} must be 5 amounts (wood, wine, marble, crystal, sulfur) or an object like {{\"wood\": 5000}}, got {!r}".format(name, value)
        )
    amounts = [asInt(amount, name, minimum=0) for amount in value]
    if sum(amounts) == 0:
        raise ValueError("{} sends nothing".format(name))
    return amounts


def prepare_sendResources(session, routes, useFreighters=False):
    """Checks the config of a sendResources task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    routes : list
        [{"from": city id, "to": city id, "resources": [wood, wine, marble, crystal, sulfur]}, ...];
        "island" (id or "X:Y") is needed when "to" is another player's city
    useFreighters : bool

    Returns
    -------
    config : dict
    """
    if not isinstance(routes, (list, tuple)) or not routes:
        raise ValueError('routes must be a list of {{"from": ..., "to": ..., "resources": [...]}}, got {!r}'.format(routes))
    own_ids, _ = getIdsOfCities(session)
    checked = []
    asked = {}  # origin id -> amounts asked by all its routes
    for i, route in enumerate(routes):
        name = "routes[{}]".format(i)
        route = route_from_saved(route)
        if not isinstance(route, dict):
            raise ValueError('{} must be {{"from": ..., "to": ..., "resources": [...]}}, got {!r}'.format(name, route))
        origin = requireOwnCity(session, route.get("from"), name + ".from")
        destination = asId(route.get("to"), name + ".to")
        if destination == origin:
            raise ValueError("{} sends from city {} to itself".format(name, origin))
        amounts = resource_amounts(route.get("resources"), name + ".resources")
        checked_route = {"from": origin, "to": destination, "resources": amounts}

        if destination not in own_ids:
            if route.get("island") is None:
                raise ValueError(
                    '{}.island is needed when "to" is not your city: the id of its island or its "X:Y" coordinates'.format(name)
                )
            island = get_island(session, route["island"], name + ".island")
            if not any(str(city.get("id")) == destination for city in island["cities"] if city.get("type") == "city"):
                raise ValueError(
                    "{}.to {} is not on island {}:{}".format(name, destination, island["x"], island["y"])
                )
            checked_route["island"] = str(island["id"])
        checked.append(checked_route)
        asked[origin] = [a + b for a, b in zip(asked.get(origin, [0] * len(RESOURCE_KEYS)), amounts)]

    # like the menu, which only lets you send what the origin has
    for origin, amounts in asked.items():
        city = getCityById(session, origin)
        for key, amount, available in zip(RESOURCE_KEYS, amounts, city["availableResources"]):
            if amount > int(available):
                raise ValueError(
                    "{} has {} {}, the routes send {}".format(
                        city["name"], addThousandSeparator(int(available)), key, addThousandSeparator(amount)
                    )
                )

    return {"routes": checked, "useFreighters": asBool(useFreighters, "useFreighters")}


@task("sendResources", prepare=prepare_sendResources)
def do_it(session, routes, useFreighters=False):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    routes : list
        [{"from": city id, "to": city id, "resources": [...]}, ...], with "island" when "to"
        is another player's city
    useFreighters : bool
    """
    info = "\nSend resources\n"
    setInfoSignal(session, info)
    own_ids, own_cities = getIdsOfCities(session)
    shipments = []
    for route in map(route_from_saved, routes):
        origin = str(route["from"])
        destination = str(route["to"])
        if destination in own_ids:
            island_id = getCityById(session, destination)["islandId"]
            destination_name = decodeUnicodeEscape(own_cities[destination]["name"])
        else:
            island = getIsland(session.get(island_url + str(route["island"])))
            island_id = island["id"]
            destination_name = next(
                (city["name"] for city in island["cities"] if str(city.get("id")) == destination), destination
            )
        shipments.append(
            (
                {"id": origin, "name": decodeUnicodeEscape(own_cities[origin]["name"])},
                {"id": destination, "name": destination_name},
                island_id,
                *route["resources"],
            )
        )
    executeRoutes(session, shipments, useFreighters)


@configurator
def sendResources(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    try:
        print("What type of ships do you want to use? (Default: Trade ships)")
        print("(1) Trade ships")
        print("(2) Freighters")
        shiptype = read(min=1, max=2, digit=True, empty=True)
        if shiptype == '':
            shiptype = 1
        if shiptype == 1:
            useFreighters = False
        elif shiptype == 2:
            useFreighters = True
        routes = []
        while True:

            banner()
            print("Origin city:")
            try:
                cityO = chooseCity(session)
            except KeyboardInterrupt:
                if routes:
                    print("Send shipment? [Y/n]")
                    rta = read(values=["y", "Y", "n", "N", ""])
                    if rta.lower() != "n":
                        break
                return None

            banner()
            print("Destination city")
            cityD = chooseCity(session, foreign=True)
            idIsland = cityD["islandId"]

            if cityO["id"] == cityD["id"]:
                continue

            resources_left = cityO["availableResources"]
            for route in routes:
                (origin_city, destination_city, __, *toSend) = route
                if origin_city["id"] == cityO["id"]:
                    for i in range(len(materials_names)):
                        resources_left[i] -= toSend[i]

                # the destination city might be from another player
                if cityD["isOwnCity"] and destination_city["id"] == cityD["id"]:
                    for i in range(len(materials_names)):
                        cityD["freeSpaceForResources"][i] -= toSend[i]

            banner()
            # the destination city might be from another player
            if cityD["isOwnCity"]:
                msg = ""
                for i in range(len(materials_names)):
                    if resources_left[i] > cityD["freeSpaceForResources"][i]:
                        msg += "{} more {}\n".format(
                            addThousandSeparator(cityD["freeSpaceForResources"][i]),
                            materials_names[i].lower(),
                        )

                if len(msg) > 0:
                    print("You can store just:\n{}".format(msg))

            print("Available:")
            for i in range(len(materials_names)):
                print(
                    "{}:{} ".format(
                        materials_names[i], addThousandSeparator(resources_left[i])
                    ),
                    end="",
                )
            print("")

            print("Send:")
            try:
                max_name = max([len(material) for material in materials_names])
                send = []
                for i in range(len(materials_names)):
                    material_name = materials_names[i]
                    pad = " " * (max_name - len(material_name))
                    val = askForValue(
                        "{}{}:".format(pad, material_name), resources_left[i]
                    )
                    send.append(val)
            except KeyboardInterrupt:
                continue
            if sum(send) == 0:
                continue

            banner()
            print(
                "About to send from {} to {}".format(
                    cityO["cityName"], cityD["cityName"]
                )
            )
            for i in range(len(materials_names)):
                if send[i] > 0:
                    print(
                        "{}:{} ".format(
                            materials_names[i], addThousandSeparator(send[i])
                        ),
                        end="",
                    )
            print("")

            print("Proceed? [Y/n]")
            rta = read(values=["y", "Y", "n", "N", ""])
            if rta.lower() != "n":
                route = (cityO, cityD, idIsland, *send)
                routes.append(route)
                print("Create another shipment? [y/N]")
                rta = read(values=["y", "Y", "n", "N", ""])
                if rta.lower() != "y":
                    break
    except KeyboardInterrupt:
        return None

    if not routes:
        return None

    # the task fetches the cities again: the saved config only holds their ids
    saved_routes = []
    for (origin_city, destination_city, island_id, *send) in routes:
        route = {"from": origin_city["id"], "to": destination_city["id"], "resources": send}
        if not destination_city["isOwnCity"]:
            route["island"] = island_id
        saved_routes.append(route)
    return {
        "session": session,
        "routes": saved_routes,
        "useFreighters": useFreighters,
    }
