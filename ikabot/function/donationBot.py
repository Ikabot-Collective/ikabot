#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import traceback

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.resources import getAvailableResources, getProductionPerHour
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import wait, getDateTime


def donationBot(session, event, stdin_fd, predetermined_input):
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
        (cities_ids, cities) = getIdsOfCities(session)
        cities_dict = {}
        initials = [material_name[0] for material_name in materials_names]
        print(
            "Enter how often you want to donate in minutes. (min = 1, default = 1 day)"
        )
        waiting_time = read(min=1, digit=True, default=1 * 24 * 60)
        print(
            "Enter a maximum additional random waiting time between donations in minutes. (min = 0, default = 1 hour)"
        )
        max_random_waiting_time = read(min=0, digit=True, default=1 * 60)
        print(
            """Which donation method would you like to use to donate automatically? (default = 1)
(1) Donate exceeding percentage of your storage capacity
(2) Donate a percentage of production
(3) Donate specific amount
        """
        )
        donate_method = read(min=1, max=3, digit=True, default=1)
        for cityId in cities_ids:
            tradegood = cities[cityId]["tradegood"]
            initial = initials[int(tradegood)]
            print(
                
                "In {} ({}), Do you wish to donate to the forest, to the trading good, to both or none? [f/t/b/n]".format(cities[cityId]["name"], initial)
            )
            f = "f"
            t = "t"
            b = "b"
            n = "n"

            rta = read(values=[f, f.upper(), t, t.upper(), b, b.upper(), n, n.upper()])
            if rta.lower() == f:
                donation_type = "resource"
            elif rta.lower() == t:
                donation_type = "tradegood"
            elif rta.lower() == b:
                donation_type = "both"
            else:
                donation_type = None
                percentage = None

            if donation_type is not None and donate_method == 1:
                print(
                    
                    "What is the maximum percentage of your storage capacity that you wish to keep occupied? (the resources that exceed it, will be donated) (default: 80%)"
                    
                )
                percentage = read(min=0, max=100, empty=True)
                if percentage == "":
                    percentage = 80
                elif (
                    percentage == 100
                ):  # if the user is ok with the storage beeing totally full, don't donate at all
                    donation_type = None
            elif donation_type is not None and donate_method == 2:
                print(
                    
                    "What is the percentage of your production that you wish to donate? (enter 0 to disable donation for the town) (default: 50%)"
                    
                )
                percentage = read(
                    min=0, max=100, empty=True
                )  # max_random_waiting_time increases inaccuracy
                if percentage == "":
                    percentage = 50
                elif percentage == 0:
                    donation_type = None
            elif donation_type is not None and donate_method == 3:
                print(
                    
                    "What is the amount would you like to donate? (enter 0 to disable donation for the town) (default: 10000)"
                    
                )
                percentage = read(
                    min=0, empty=True
                )  # no point changing the variable's name everywhere just for this
                if percentage == "":
                    percentage = 10000
                elif percentage == 0:
                    donation_type = None

            cities_dict[cityId] = {
                "donation_type": donation_type,
                "percentage": percentage,
            }

        print("I will donate every {} minutes.".format(waiting_time))
        enter()
    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()

    info = "\nI donate every {} minutes\n".format(waiting_time)
    setInfoSignal(session, info)
    try:
        do_it(
            session,
            cities_ids,
            cities_dict,
            waiting_time,
            max_random_waiting_time,
            donate_method,
        )
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def do_it(
    session,
    cities_ids,
    cities_dict,
    waiting_time,
    max_random_waiting_time,
    donate_method,
):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    cities_ids : list[int]
    cities_dict : dict[int, dict]
    waiting_time: int
    max_random_waiting_time: int
    """
    for cityId in cities_ids:
        html = session.get(city_url + cityId)
        city = getCity(html)
        cities_dict[cityId]["island"] = city["islandId"]

    while True:
        total_donated = 0
        for cityId in cities_ids:
            donation_type = cities_dict[cityId]["donation_type"]
            if donation_type is None:
                continue

            # get the storageCapacity and the wood this city has
            html = session.get(city_url + cityId)
            city = getCity(html)
            wood = city["availableResources"][0]
            storageCapacity = city["storageCapacity"]

            # get the percentage
            if donate_method == 1:
                percentage = cities_dict[cityId]["percentage"]
                percentage /= 100

                # calculate what is the amount of wood that should be preserved
                max_wood = storageCapacity * percentage
                max_wood = int(max_wood)

                # calculate the wood that is exceeding the percentage
                to_donate = wood - max_wood
                if to_donate <= 0:
                    continue

            elif donate_method == 2:
                # get current production rate if changed since starting the bot
                (wood_prod, good_prod, typeGood) = getProductionPerHour(
                    session, cityId
                )
                percentage = cities_dict[cityId]["percentage"]

                # calculate the amount of wood to be donated from production, based on the given donation frequency
                to_donate = int((float(wood_prod) * percentage / 100) * (waiting_time / 60))
                # Note: Connection delay can/will cause "inaccurate" donations especially with low waiting_time
                if to_donate <= 0:
                    continue

            elif donate_method == 3:
                percentage = cities_dict[cityId]["percentage"]
                # make sure the donation amount is never lower than resources available
                max_wood = wood - percentage
                max_wood = int(max_wood)

                to_donate = percentage
                if max_wood <= 0:
                    continue

            islandId = cities_dict[cityId]["island"]
            
            # donate
            if donation_type == "both":
                forrest = int(to_donate / 2)
                trade = int(to_donate / 2)
                session.post(
                    params={
                        "islandId": islandId,
                        "type": "resource",
                        "action": "IslandScreen",
                        "function": "donate",
                        "donation": forrest,
                        "backgroundView": "island",
                        "templateView": donation_type,
                        "actionRequest": actionRequest,
                        "ajax": "1",
                    }
                )
                wait(1, maxrandom=5)  # just to simulate user interaction
                session.post(
                    params={
                        "islandId": islandId,
                        "type": "tradegood",
                        "action": "IslandScreen",
                        "function": "donate",
                        "donation": trade,
                        "backgroundView": "island",
                        "templateView": donation_type,
                        "actionRequest": actionRequest,
                        "ajax": "1",
                    }
                )
            else:
                session.post(
                    params={
                        "islandId": islandId,
                        "type": donation_type,
                        "action": "IslandScreen",
                        "function": "donate",
                        "donation": to_donate,
                        "backgroundView": "island",
                        "templateView": donation_type,
                        "actionRequest": actionRequest,
                        "ajax": "1",
                    }
                )
            total_donated += to_donate
        session.setStatus(
            f"Donated {total_donated} wood @{getDateTime()}"
        )
        msg = "I donated automatically."
        sendToBotDebug(session, msg, debugON_donationBot)

        # sleep a day
        wait(waiting_time * 60, maxrandom=max_random_waiting_time * 60)
