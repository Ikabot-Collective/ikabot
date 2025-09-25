#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import datetime
import traceback
from decimal import *
import json

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import getIdsOfCities
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.resources import getWineConsumptionPerHour, getAvailableResources, getProductionPerHour
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import daysHoursMinutes
from ikabot.helpers.planRoutes import *

getcontext().prec = 30

def alertLowWine(session, event, stdin_fd, predetermined_input):
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
        if checkTelegramData(session) is False:
            event.set()
            return
        banner()
        hours = read(
            msg=(
                "How many hours should be left until the wine runs out in a city so that it's alerted? : "
            ),
            min=1,
        )
        auto_transfer = read(msg=("Would you like to automatically transfer wine if necessary? (y/n) : ")).strip().lower()
        
        if auto_transfer in ["y", "yes"]:
            auto_transfer = True
            transfer_amount = read(msg=("How much wine should be sent automatically? : "), min=1)
        else:
            auto_transfer = False
            transfer_amount = 0
        print("It will be alerted when the wine runs out in less than {:d} hours in any city, and {:,d} wine will be transferred if necessary.".format(hours, transfer_amount))

        enter()
    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()

    info = ("\nI alert if the wine runs out in less than {:d} hours\n".format(hours))
    setInfoSignal(session, info)
    try:
        do_it(session, hours, auto_transfer, transfer_amount)
    except Exception as e:
        msg = (f"Error in:\n{info}\nCause:\n{traceback.format_exc()}")
        sendToBot(session, msg)
    finally:
        session.logout()

def getMovementsFromHtml(session):
    """
    Extract fleet movements using the same approach as See movements.
    Parameters
    ----------
    session : ikabot.web.session.Session
    Returns
    -------
    list
        A list of movements.
    """
    html = session.get()
    cityId = re.search(r"currentCityId:\s*(\d+),", html).group(1)
    url = "view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1".format(
        cityId, actionRequest
    )
    resp = session.post(url)
    resp = json.loads(resp, strict=False)
    movements = resp[1][1][2]["viewScriptParams"]["militaryAndFleetMovements"]
    return movements

def isWineTransportInProgress(session, destinationCityId):
    """
    Check if there is an ongoing wine transport to the specified city.
    Parameters
    ----------
    session : ikabot.web.session.Session
    destinationCityId : str
    Returns
    -------
    bool
    """
    movements = getMovementsFromHtml(session)
    for movement in movements:
        target = movement.get("target", {})
        resources = movement.get("resources", [])

        # Convert both IDs to the same type for comparison
        target_city_id = str(target.get("cityId"))
        destination_city_id_str = str(destinationCityId)

        # Check if the target city matches and the transport includes wine
        if target_city_id == destination_city_id_str:
            wine_resource = next((res for res in resources if res["cssClass"] == "resource_icon wine"), None)
            if wine_resource:
                origin = movement.get("origin", {}).get("name", "Unknown")
                amount = wine_resource.get("amount", "Unknown")
                destination_name = movement.get("target", {}).get("name", "Unknown")
                return f"Active wine transport: {amount} wine from {origin} to {destination_name}."

    return None

def do_it(session, hours, auto_transfer, transfer_amount):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    hours : int
    auto_transfer : bool
    transfer_amount : int
    """
    was_alerted = {}
    message_log = []
    routes = []  # Store all routes for batch execution
    last_reset_time = datetime.datetime.now()
    
    while True:
        current_time = datetime.datetime.now()
        time_elapsed = (current_time - last_reset_time).total_seconds()
        if time_elapsed >= 12 * 60 * 60:  # 12 h to reset the alerted list
            was_alerted.clear()  # Reset all alerts
            last_reset_time = current_time  # Update the last time reseted the list
            
        ids, cities = getIdsOfCities(session)

        for cityId in cities:
            if cityId not in was_alerted:
                was_alerted[cityId] = False

        for cityId in cities:
            html = session.get(city_url + cityId)
            city = getCity(html)

            if "tavern" not in [building["building"] for building in city["position"]]:
                continue

            consumption_per_hour = getWineConsumptionPerHour(html)

            # Determine Wine Press reduction
            wine_press_level = 0
            for building in city["position"]:
                if building.get("building") == "vineyard":
                    wine_press_level = building.get("level", 0)
                    break

            # Apply reduction to wine consumption
            reduction_factor = Decimal(1 - (wine_press_level / 100))
            consumption_per_hour *= reduction_factor

            wine_available = Decimal(city["availableResources"][1])

            consumption_net = Decimal(consumption_per_hour)

            if consumption_net == 0:
                was_alerted[cityId] = False
                continue

            consumption_per_seg = consumption_net / Decimal(3600)
            seconds_left = wine_available / consumption_per_seg

            if seconds_left < hours * 60 * 60:
                if was_alerted[cityId] is False:
                    time_left = daysHoursMinutes(seconds_left)
                    message_log.append(f"In {city['name']} you have: {city['availableResources'][1]:,.0f} wine. Consumption: {consumption_per_hour:.2f} per hour.\nThe wine will run out in {time_left}")

                    if auto_transfer:
                        transport_status = isWineTransportInProgress(session, cityId)
                        if transport_status:
                            message_log.append(transport_status)
                            message_log.append(f"A wine transport is already in progress to {city['name']}. No additional transport initiated.")
                            was_alerted[cityId] = True
                            continue

                        donor_city_id = None
                        donor_city = None

                        # Find the donor city among wine-producing cities with the most wine available
                        max_wine_available = 0
                        for donor_id, donor in cities.items():
                            wood_prod, luxury_prod, tradegood = getProductionPerHour(session, donor_id)
                                
                            if tradegood != 1:  # Skip if not wine-producing
                                continue

                            donor_html = session.get(city_url + donor_id)
                            donor_info = getCity(donor_html)

                            if donor_id == cityId:
                                continue

                            # Check if the city has enough wine to send
                            wine_available = donor_info.get("availableResources", [0, 0, 0, 0, 0])[1]
                            if wine_available >= transfer_amount and wine_available > max_wine_available:
                                donor_city_id = donor_id
                                donor_city = donor
                                max_wine_available = wine_available

                        if donor_city_id:
                            routes.append((
                                donor_city,  # Origin
                                city,  # Destination
                                city["islandId"],  # Island ID
                                0,  # Wood
                                transfer_amount,  # Wine
                                0,  # Marble
                                0,  # Crystal
                                0,  # Sulfur
                            ))
                            
                            message_log.append(f"Will transfer {transfer_amount:,d} from {donor_city['name']}.")

                        else:
                            message_log.append(f"No city has sufficient wine to transfer to {city['name']}.")

                    was_alerted[cityId] = True
            else:
                was_alerted[cityId] = False

        if message_log:
            
            sendToBot(session, "\n".join(message_log))
            message_log.clear()

        if routes:
            executeRoutes(session, routes, useFreighters=False)
            routes.clear()
        time.sleep(60 * 60)
