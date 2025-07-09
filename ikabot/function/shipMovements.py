#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import math
import re
import sys
from decimal import *

from ikabot import config
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.naval import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.varios import *
from ikabot.helpers.pedirInfo import getShipCapacity


def isHostile(movement):
    """
    Parameters
    ----------
    movement : dict

    Returns
    -------
    is hostile : bool
    """
    if movement["army"]["amount"]:
        return True
    for mov in movement["fleet"]["ships"]:
        if mov["cssClass"] != "ship_transport":
            return True
    return False


def shipMovements(session, event, stdin_fd, predetermined_input):
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

        print(
            "Ships {:d}/{:d}\n".format(
                getAvailableShips(session), getTotalShips(session)
            )
        )

        cityId = getCurrentCityId(session)
        url = "view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1".format(
            cityId, actionRequest
        )
        resp = session.post(url)
        resp = json.loads(resp, strict=False)
        movements = resp[1][1][2]["viewScriptParams"]["militaryAndFleetMovements"]
        time_now = int(resp[0][1]["time"])

        if len(movements) == 0:
            print("There are no movements")
            enter()
            event.set()
            return

        for movement in movements:

            color = ""
            if movement["isHostile"]:
                color = bcolors.RED + bcolors.BOLD
            elif movement["isOwnArmyOrFleet"]:
                color = bcolors.BLUE + bcolors.BOLD
            elif movement["isSameAlliance"]:
                color = bcolors.GREEN + bcolors.BOLD

            origin = "{} ({})".format(
                movement["origin"]["name"], movement["origin"]["avatarName"]
            )
            destination = "{} ({})".format(
                movement["target"]["name"], movement["target"]["avatarName"]
            )
            arrow = "<-" if movement["event"]["isFleetReturning"] else "->"
            time_left = int(movement["eventTime"]) - time_now
            print(
                "{}{} {} {}: {} ({}) {}".format(
                    color,
                    origin,
                    arrow,
                    destination,
                    movement["event"]["missionText"],
                    daysHoursMinutes(time_left),
                    bcolors.ENDC,
                )
            )

            if movement["isHostile"]:
                troops = movement["army"]["amount"]
                fleets = movement["fleet"]["amount"]
                print(
                    "Troops:{}\nFleets:{}".format(
                        addThousandSeparator(troops), addThousandSeparator(fleets)
                    )
                )
            elif isHostile(movement):
                troops = movement["army"]["amount"]
                ships = 0
                fleets = 0
                for mov in movement["fleet"]["ships"]:
                    if mov["cssClass"] == "ship_transport":
                        ships += int(mov["amount"])
                    else:
                        fleets += int(mov["amount"])
                print(
                    "Troops:{}\nFleets:{}\n Ships:{}".format(
                        addThousandSeparator(troops),
                        addThousandSeparator(fleets),
                        addThousandSeparator(ships),
                    )
                )
            else:
                assert len(materials_names) == 5
                total_load = 0
                for resource in movement["resources"]:
                    amount = resource["amount"]
                    tradegood = resource["cssClass"].split()[1]
                    # gold won't be translated
                    if tradegood != "gold":
                        index = materials_names_tec.index(tradegood)
                        tradegood = materials_names[index]
                    total_load += int(amount.replace(",", "").replace(".", ""))
                    print("{} of {}".format(amount, tradegood))
                ship_capacity, freighter_capacity = getShipCapacity(session)
                ships = int(math.ceil((Decimal(total_load) / Decimal(ship_capacity))))
                print("{:d} Ships".format(ships))
        enter()
        event.set()
    except KeyboardInterrupt:
        event.set()
        return
