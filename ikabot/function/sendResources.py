#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planRoutes import executeRoutes, Route
from ikabot.helpers.resources import *
from ikabot.helpers.varios import addThousandSeparator

from typing import TYPE_CHECKING, TypedDict, Union
if TYPE_CHECKING:
    from ikabot.web.session import Session

SendResourcesConfig = TypedDict("SendResourcesConfig", {"use_freighters": bool, "routes": list[Route]})
def sendResources(session: Session) -> SendResourcesConfig:
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
            return

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
    
    return {
        "routes": routes,
        "useFreighters": useFreighters
        }

def do_it(session: Session, routes: list[Route], useFreighters: bool):
    executeRoutes(session, routes, useFreighters)
    