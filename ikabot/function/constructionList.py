#! /usr/bin/env python3
# -*- coding: utf-8 -*-


import hashlib
import html
import json
import math
import random
import re
import threading
import time
import traceback
from decimal import *
from urllib.parse import parse_qs, urlparse

import requests
from functools import cache

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planRoutes import *
from ikabot.helpers.resources import getAvailableResources
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *
from ikabot.web.session import normal_get
from ikabot.helpers.decorators import configurator, task
from ikabot.helpers.taskConfig import asBool, asInt, getCityById, requireOwnCity
from ikabot.function.sendResources import RESOURCE_KEYS


def _parseConstructionTime(row):
    cells = re.findall(r'<td class="costs">(.*?)</td>', row, re.DOTALL)
    if not cells:
        return None

    cell = cells[-1]
    match = re.search(r'data-(?:seconds|duration|time)=["\'](\d+)', cell)
    if match:
        return int(match.group(1))

    values = re.findall(r'title=["\']([^"\']+)', cell)
    values.append(re.sub(r"<[^>]+>", " ", html.unescape(cell)))
    # case matters: "25m 34s" are minutes but "1M 7D" is one month and "1A 3M" one year (A, Spanish "anio").
    # The game rounds long times to two units, so months and years are approximate anyway.
    units = {
        "A": 365 * 86400, "Y": 365 * 86400, "y": 365 * 86400,
        "M": 30 * 86400,
        "D": 86400, "d": 86400,
        "H": 3600, "h": 3600,
        "m": 60,
        "S": 1, "s": 1,
    }
    for value in values:
        parts = re.findall(r"(\d+)\s*([AYyMDdHhmSs])", value)
        if parts:
            return sum(int(amount) * units[unit] for amount, unit in parts)
    return None


def _formatEndTime(timestamp):
    # an absolute date stays correct while the task sleeps until the construction ends
    return time.strftime("%b %d %H:%M", time.localtime(timestamp))


def _findHtml(value, element_id):
    if isinstance(value, str):
        return value if element_id in value and "ambrosiaIcon" in value else None
    if isinstance(value, list):
        for item in value:
            result = _findHtml(item, element_id)
            if result is not None:
                return result
    if isinstance(value, dict):
        for item in value.values():
            result = _findHtml(item, element_id)
            if result is not None:
                return result
    return None


def _getFreeSpeedupParams(response, city_id, position):
    try:
        popup = _findHtml(json.loads(response, strict=False), "js_buildingSpeedupActivateBtn")
    except (TypeError, ValueError):
        popup = response if isinstance(response, str) else None
    if popup is None:
        return None

    buttons = re.findall(
        r'<a\b(?=[^>]*\bid=["\']js_buildingSpeedupActivateBtn["\'])[^>]*>.*?</a>',
        popup,
        re.DOTALL,
    )
    if len(buttons) != 1:
        return None
    button = buttons[0]

    span_pattern = r'<span\b(?=[^>]*\bclass=["\'][^"\']*\bambrosiaIcon\b[^"\']*["\'])[^>]*>'
    ambrosia_spans = re.findall(span_pattern, button)
    costs = re.findall(span_pattern + r'\s*(\d+)\s*</span>', button)
    if len(ambrosia_spans) != 1 or len(costs) != 1 or costs[0] != "0":
        return None

    href = re.search(r'href=["\']([^"\']+)', button)
    if href is None:
        return None

    query = parse_qs(urlparse(html.unescape(href.group(1))).query)
    required = {
        "action": "Premium",
        "function": "buildingSpeedup",
        "cityId": str(city_id),
        "position": str(position),
    }
    if any(query.get(key) != [value] for key, value in required.items()):
        return None
    if query.get("currentCityId", [str(city_id)]) != [str(city_id)]:
        return None
    if len(query.get("level", [])) != 1 or not query["level"][0].isdigit():
        return None

    return {
        **required,
        "level": query["level"][0],
        "backgroundView": "city",
        "currentCityId": str(city_id),
        "actionRequest": actionRequest,
        "ajax": "1",
    }


def tryFreeBuildingSpeedup(session, city_id, building):
    popup_params = {
        "view": "buildingSpeedup",
        "cityId": city_id,
        "position": building["position"],
        "backgroundView": "city",
        "currentCityId": city_id,
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    response = session.post(params=popup_params)
    speedup_params = _getFreeSpeedupParams(response, city_id, building["position"])
    if speedup_params is None:
        return False

    wait(random.randint(1, SPEEDUP_RANDOMWAIT)) # random wait
    # Recheck the current price and target after the delay before activating.
    response = session.post(params=popup_params)
    speedup_params = _getFreeSpeedupParams(response, city_id, building["position"])
    if speedup_params is None:
        return False

    session.post(params=speedup_params)
    return True


def waitForConstruction(session, city_id, final_lvl, construction_queue=None):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int
    final_lvl : int

    Returns
    -------
    city : dict
    """
    while True:

        html = session.get(city_url + city_id)
        city = getCity(html)

        construction_buildings = [
            building for building in city["position"] if "completed" in building
        ]
        if len(construction_buildings) == 0:
            break

        construction_building = construction_buildings[0]
        construction_time = construction_building["completed"]

        current_time = int(time.time())
        final_time = int(construction_time)
        seconds_to_wait = final_time - current_time
        current_end = max(final_time, current_time)
        total_end = current_end + sum(construction_queue or [])
        status = "{}: {} -> level {} , ends {} , all done {}".format(
            city["cityName"],
            construction_building["name"],
            construction_building["level"] + 1,
            _formatEndTime(current_end),
            _formatEndTime(total_end),
        )
        session.setStatus(status)

        if CONSTRUCTION_FREE_SPEEDUP and 0 < seconds_to_wait <= 300:
            if tryFreeBuildingSpeedup(session, city_id, construction_building):
                session.setStatus(status + " , free speedup sent")
                msg = "{}: Finished {} for 0 Ambrosia".format(
                    city["cityName"], construction_building["name"]
                )
                sendToBotDebug(session, msg, debugON_constructionList)
            else:
                session.setStatus(status + " , waiting for zero-cost speedup")
            wait(5)
            continue

        msg = "{}: I wait {:d} seconds so that {} gets to the level {:d}".format(
            city["cityName"],
            seconds_to_wait,
            construction_building["name"],
            construction_building["level"] + 1,
        )
        sendToBotDebug(session, msg, debugON_constructionList)
        if CONSTRUCTION_FREE_SPEEDUP:
            wait(max(5, seconds_to_wait - 300))
        else:
            wait(max(5, seconds_to_wait + 10))

    html = session.get(city_url + city_id)
    city = getCity(html)
    return city


def expandBuilding(session, cityId, building, waitForResources, construction_queue=None):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    cityId : int
    building : dict
    waitForResources : bool
    """
    current_level = building["level"]
    if building["isBusy"]:
        current_level += 1
    levels_to_upgrade = building["upgradeTo"] - current_level
    position = building["position"]
    upgradeTo = building["upgradeTo"]
    time.sleep(
        random.randint(5, 15)
    )  # to avoid race conditions with sendResourcesNeeded

    for lv in range(levels_to_upgrade):
        city = waitForConstruction(session, cityId, upgradeTo, construction_queue)
        building = city["position"][position]

        if building["canUpgrade"] is False and waitForResources is True:
            while building["canUpgrade"] is False:
                time.sleep(60)
                seconds = getMinimumWaitingTime(session)
                html = session.get(city_url + cityId)
                city = getCity(html)
                building = city["position"][position]
                # if no ships are comming, exit no matter if the building can or can't upgrade
                if seconds == 0:
                    break
                wait(seconds + 5)

        if building["canUpgrade"] is False:
            msg = "City:{}\n".format(city["cityName"])
            msg += "Building:{}\n".format(building["name"])
            msg += "The building could not be completed due to lack of resources.\n"
            msg += "Missed {:d} levels".format(levels_to_upgrade - lv)
            sendToBot(session, msg)
            return

        url = "action=UpgradeExistingBuilding&actionRequest={}&cityId={}&position={:d}&level={}&activeTab=tabSendTransporter&backgroundView=city&currentCityId={}&templateView={}&ajax=1".format(
            actionRequest,
            cityId,
            position,
            building["level"],
            cityId,
            building["building"],
        )
        resp = session.post(url)
        html = session.get(city_url + cityId)
        city = getCity(html)
        building = city["position"][position]
        if building["isBusy"] is False:
            msg = "{}: The building {} was not extended".format(
                city["cityName"], building["name"]
            )
            sendToBot(session, msg)
            sendToBot(session, resp)
            return
        if construction_queue:
            construction_queue.pop(0)

        msg = "{}: The building {} is being extended to level {:d}.".format(
            city["cityName"], building["name"], building["level"] + 1
        )
        sendToBotDebug(session, msg, debugON_constructionList)

    city = waitForConstruction(session, cityId, upgradeTo, construction_queue)
    building = city["position"][position]
    msg = "{}: The building {} finished extending to level: {:d}.".format(
        city["cityName"], building["name"], building["level"]
    )
    sendToBotDebug(session, msg, debugON_constructionList)


def getCostsReducers(city):
    """
    Parameters
    ----------
    city : dict

    Returns
    -------
    reducers_per_material_level : dict[int, int]
    """
    reducers_per_material = [0] * len(materials_names)
    assert len(reducers_per_material) == 5

    for building in city["position"]:
        if building["name"] == "empty":
            continue
        lv = building["level"]
        if building["building"] == "carpentering":
            reducers_per_material[0] = lv
        elif building["building"] == "vineyard":
            reducers_per_material[1] = lv
        elif building["building"] == "architect":
            reducers_per_material[2] = lv
        elif building["building"] == "optician":
            reducers_per_material[3] = lv
        elif building["building"] == "fireworker":
            reducers_per_material[4] = lv
    return reducers_per_material


def _getBuildingHelpTable(session, city, building_type):
    """Returns the html of the help (Ikipedia) page of a building, the one with the table of costs per level
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    building_type : str
        technical name of the building, eg. townHall or chronosForge
    """
    # get html with information about buildings
    building_detail_url = "view=buildingDetail&buildingId=0&helpId=1&backgroundView=city&currentCityId={}&templateView=ikipedia&actionRequest={}&ajax=1".format(
        city["id"], actionRequest
    )
    building_detail_response = session.post(building_detail_url)
    building_detail = json.loads(building_detail_response, strict=False)
    building_html = building_detail[1][1][1]

    # get html with information about buildings costs
    regex_building_detail = (
        r'<div class="(?:selected)? button_building '
        + re.escape(building_type)
        + r'"\s*onmouseover="\$\(this\)\.addClass\(\'hover\'\);" onmouseout="\$\(this\)\.removeClass\(\'hover\'\);"\s*onclick="ajaxHandlerCall\(\'\?(.*?)\'\);'
    )
    match = re.search(regex_building_detail, building_html)
    building_costs_url = match.group(1)
    building_costs_url += "backgroundView=city&currentCityId={}&templateView=buildingDetail&actionRequest={}&ajax=1".format(
        city["id"], actionRequest
    )
    building_costs_response = session.post(building_costs_url)
    building_costs = json.loads(building_costs_response, strict=False)
    return building_costs[1][1][1]


def _parseChronosForgeReductions(html_table):
    """Reads the construction time reduction of every Chronoforge level from its help table
    Parameters
    ----------
    html_table : str

    Returns
    -------
    reductions : dict[int, float]
        level -> fraction of the construction time that is removed (eg. 6 -> 0.73786)
    """
    reductions = {}
    rows = re.findall(
        r'<td class="level">(\d+)</td>(.*?)(?=<td class="level">|</table>|$)',
        html_table,
        re.DOTALL,
    )
    for level, row in rows:
        # the reduction is the only percentage of the row, eg. "-73,786%" or "-73.786%"
        percentages = re.findall(r"(\d+(?:[.,]\d+)?)\s*%", re.sub(r"<[^>]+>", " ", row))
        if percentages:
            reductions[int(level)] = round(float(percentages[-1].replace(",", ".")) / 100, 6)
    return reductions


_chronos_forge_reductions = {}


def getChronosForgeReduction(session, city):
    """Returns the construction time reduction given by the Chronoforge of the city
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict

    Returns
    -------
    (level, reduction) : (int, float or None)
        Chronoforge level (0 if the city has none) and the fraction of the construction
        time that is removed. reduction is None if the help table could not be read.
    """
    levels = [
        int(b["level"]) for b in city["position"] if b.get("building") == "chronosForge"
    ]
    level = max(levels) if levels else 0
    if level == 0:
        return 0, 0.0
    if not _chronos_forge_reductions:
        try:
            html_table = _getBuildingHelpTable(session, city, "chronosForge")
            _chronos_forge_reductions.update(_parseChronosForgeReductions(html_table))
        except Exception:
            session.logger.warning("Could not read the Chronoforge help table", exc_info=True)
    return level, _chronos_forge_reductions.get(level)


def getResourcesNeeded(session, city, building, current_level, final_level, simulated_reducers=None, time_reduction=0.0):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    building : dict
    current_level : int
    final_level : int
    simulated_reducers : list[int]
    time_reduction : float
        fraction of the construction time removed by the Chronoforge

    Returns
    -------
    costs_per_material : dict[int, int]
    """
    html_costs = _getBuildingHelpTable(session, city, building["building"])

    # if the user has all the resource saving studies, we save that in the session data (one less request)
    sessionData = session.getSessionData()
    if "reduccion_inv_max" in sessionData:
        costs_reduction = 14
    else:
        # get the studies
        url = "view=noViewChange&researchType=economy&backgroundView=city&currentCityId={}&templateView=researchAdvisor&actionRequest={}&ajax=1".format(
            city["id"], actionRequest
        )
        rta = session.post(url)
        rta = json.loads(rta, strict=False)
        studies = rta[2][1]["new_js_params"]
        studies = json.loads(studies, strict=False)
        studies = studies["currResearchType"]

        # look for resource saving studies
        costs_reduction = 0
        for study in studies:
            if studies[study]["liClass"] != "explored":
                continue
            link = studies[study]["aHref"]
            if "2020" in link:
                costs_reduction += 2
            elif "2060" in link:
                costs_reduction += 4
            elif "2100" in link:
                costs_reduction += 8

        # if the user has all the resource saving studies, save that in the session data
        if costs_reduction == 14:
            sessionData["reduccion_inv_max"] = True
            session.setSessionData(sessionData)

    # calculate cost reductions
    costs_reduction /= 100
    costs_reduction = 1 - costs_reduction

    # get buildings that reduce the cost of upgrades
    if simulated_reducers is None:
        costs_reductions = getCostsReducers(city)
    else:
        costs_reductions = simulated_reducers

    # get the type of resources that this upgrade will cost (wood, marble, etc)
    resources_types = re.findall(
        r'<th class="costs"><img src="(.*?)\.png"/></th>', html_costs
    )[:-1]

    # get the actual cost of each upgrade
    matches = re.findall(
        r'<td class="level">\d+</td>(?:\s+<td class="costs">.*?</td>)+', html_costs
    )

    # calculate the cost of the entire upgrade, taking into account all the possible reductions
    final_costs = [0] * len(materials_names)
    construction_time = 0
    construction_times = []
    levels_to_upgrade = 0
    for match in matches:
        lv = re.search(r'"level">(\d+)</td>', match).group(1)
        lv = int(lv)

        if lv <= current_level:
            continue
        if lv > final_level:
            break

        levels_to_upgrade += 1
        level_time = _parseConstructionTime(match)
        if level_time is not None:
            # The help table shows base times, apply the Chronoforge of the city.
            # Keep full durations otherwise: optional speedups may be unavailable or rejected.
            level_time = int(round(level_time * (1 - time_reduction)))
            construction_time += level_time
            construction_times.append(level_time)
        # get the costs for the current level
        costs = re.findall(r'<td class="costs"><div.*>([\d,\.\s\xa0]*)</div></div></td>', match)
        # delete blank spaces (\xa0) in costs
        costs = [value.replace('\xa0', '').replace(' ', '') for value in costs]

        for i in range(len(costs)):
            # get hash from CDN images to identify the resource type
            resource_type = checkhash("https:" + resources_types[i] + ".png")

            for j in range(len(materials_names_tec)):
                name = materials_names_tec[j]
                if resource_type == name:
                    resource_index = j
                    break

            # get the cost of the current resource type
            cost = costs[i]
            cost = cost.replace(",", "").replace(".", "")
            cost = 0 if cost == "" else int(cost)

            # calculate all the reductions
            investigation_multiplier = Decimal(str(costs_reduction))
            building_reduction = Decimal(costs_reductions[resource_index]) / Decimal(100)

            # Calculate the final multiplier
            final_multiplier = investigation_multiplier - building_reduction

            # Apply the direct proportion without trying to guess the hidden base cost
            real_cost = Decimal(cost) * (final_multiplier / investigation_multiplier)

            # Always round up to ensure we never fall short by 1 unit (prevents wasted transports or failed upgrades)
            final_costs[resource_index] += math.ceil(real_cost)


        if building["building"] == "carpentering":
            costs_reductions[0] = min(50, costs_reductions[0] + 1)
        elif building["building"] == "vineyard":
            costs_reductions[1] = min(50, costs_reductions[1] + 1)
        elif building["building"] == "architect":
            costs_reductions[2] = min(50, costs_reductions[2] + 1)
        elif building["building"] == "optician":
            costs_reductions[3] = min(50, costs_reductions[3] + 1)
        elif building["building"] == "fireworker":
            costs_reductions[4] = min(50, costs_reductions[4] + 1)

    # the help table ends at the building's last level: the caller decides what to do when
    # fewer levels than asked are left
    building["levelsAvailable"] = levels_to_upgrade
    building["constructionTime"] = construction_time
    building["constructionTimes"] = construction_times
    return final_costs


def _round_up_resources(amount):
    if amount < 1000:
        return math.ceil(amount / 100) * 100
    elif amount < 10000:
        return math.ceil(amount / 500) * 500
    else:
        return math.ceil(amount / 1000) * 1000


def sendResourcesNeeded(session, destination_city_id, city_origins, missing_resources, useFreighters=False, useRounding=False):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    destination_city_id : int
    city_origins : dict
    missing_resources : dict[int, int]
    useFreighters : bool
    useRounding : bool
    """

    info = "\nTransport resources to upload building\n"

    try:
        html = session.get(city_url + destination_city_id)
        cityD = getCity(html)

        # build combined routes per origin city so multiple resources
        # from the same city are sent in a single shipment
        combined = {}  # origin_city_id -> (cityOrigin, toSend_list)

        for i in range(len(materials_names)):
            missing = missing_resources[i]
            if missing <= 0:
                continue

            target = _round_up_resources(missing) if useRounding else missing
            remaining = target

            for cityOrigin in (city_origins.get(i) or city_origins.get(str(i), [])):
                if remaining == 0:
                    break

                available = cityOrigin["availableResources"][i]
                send = min(available, remaining)
                remaining -= send

                city_id = cityOrigin["id"]
                if city_id not in combined:
                    combined[city_id] = (cityOrigin, [0] * len(materials_names))
                combined[city_id][1][i] += send

        routes = []
        for city_id, (cityOrigin, toSend) in combined.items():
            route = (cityOrigin, cityD, cityD["islandId"], *toSend)
            routes.append(route)

        executeRoutes(session, routes, useFreighters)
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
        # no s.logout() because this is a thread, not a process


def chooseResourceProviders(session, cities_ids, cities, city_id, resource, missing):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    cities_ids : list[int]
    cities : dict[int, dict]
    city_id : int
    resource : int
    missing : int
    """
    send_resources_flag = True
    expand_flag = True

    banner()
    print("From what cities obtain {}?".format(materials_names[resource].lower()))

    tradegood_initials = [material_name[0] for material_name in materials_names]
    maxName = max(
        [len(cities[city]["name"]) for city in cities if cities[city]["id"] != city_id]
    )

    origin_cities = []
    total_available = 0
    for cityId in cities_ids:
        if cityId == city_id:
            continue

        html = session.get(city_url + cityId)
        city = getCity(html)

        available = city["availableResources"][resource]
        if available == 0:
            continue

        # ask the user it this city should provide resources
        tradegood_initial = tradegood_initials[int(cities[cityId]["tradegood"])]
        pad = " " * (maxName - len(cities[cityId]["name"]))
        is_producer = (int(cities[cityId]["tradegood"]) == int(resource))
        msg = "{}{} ({}): {} [{}]:".format(
            pad,
            cities[cityId]["name"],
            tradegood_initial,
            addThousandSeparator(available),
            ("y/N", "Y/n")[is_producer == True]
        )
        choice = read(msg=msg, values=["Y", "y", "N", "n", ""], default=("N", "Y")[is_producer == True])
        if choice.lower() == "n":
            continue

        # if so, save the city and calculate the total amount resources to send
        total_available += available
        origin_cities.append(city)
        # if we have enough resources, return
        if total_available >= missing:
            return origin_cities, send_resources_flag, expand_flag

    # if we reach this part, there are not enough resources to expand the building
    print("\nThere are not enough resources.")

    if len(origin_cities) > 0:
        print("\nSend the resources anyway? [Y/n]")
        choice = read(values=["y", "Y", "n", "N", ""])
        if choice.lower() == "n":
            send_resources_flag = False

    print("\nTry to expand the building anyway? [y/N]")
    choice = read(values=["y", "Y", "n", "N", ""])
    if choice.lower() == "n" or choice == "":
        expand_flag = False

    return origin_cities, send_resources_flag, expand_flag


def sendResourcesMenu(session, city_id, missing):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int
    missing : list[int, int]
    """
    cities_ids, cities = getIdsOfCities(session)
    origins = {}
    
    send_resources_flag = True
    expand_flag = True
    
    # for each missing resource, choose providers
    for resource in range(len(missing)):
        if missing[resource] <= 0:
            continue

        origin_cities, current_send_resources, current_expand = chooseResourceProviders(
            session, cities_ids, cities, city_id, resource, missing[resource]
        )
        send_resources_flag = current_send_resources
        expand_flag = current_expand
        if send_resources_flag is False and expand_flag:
            print("\nThe building will be expanded if possible.")
            enter()
            return None, expand_flag
        elif send_resources_flag is False:
            return None, expand_flag
        origins[resource] = origin_cities

    if expand_flag:
        print("\nThe resources will be sent and the building will be expanded if possible.")
    else:
        print("\nThe resources will be sent.")

    enter()

    return origins, expand_flag


def getBuildingsToExpand(session, cityId):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    cityId : int

    Returns
    -------
    buildings : list of dict
    """
    html = session.get(city_url + cityId)
    city = getCity(html)

    banner()
    # show the buildings available to expand (ignore empty spaces)
    print("Which buildings do you want to expand? Separate numbers with commas (7, 1, 3, 5, ...)\n")
    print("(0)\t\texit")
    buildings = [
        building for building in city["position"] if building["name"] != "empty"
    ]
    for i in range(len(buildings)):
        building = buildings[i]

        level = building["level"]

        if building["isMaxLevel"] is True:
            color = bcolors.BLACK
        elif building["canUpgrade"] is True:
            color = bcolors.GREEN
        else:
            color = bcolors.RED
        if level < 10:
            level = " " + str(level)
        else:
            level = str(level)
        if building["isBusy"]:
            level = level + "+"
        print("({:d})\tlv:{}\t{}{}{}".format(i + 1, level, color, building["name"], bcolors.ENDC))

    selected_building_ids = read().split(",")
    selected_building_ids = [int(id.strip()) for id in selected_building_ids if id.strip().isdigit()]

    if len(selected_building_ids) == 0 or 0 in selected_building_ids:
        return None

    selected_buildings = []
    for building_id in selected_building_ids:
        building = buildings[building_id - 1]

        current_level = int(building["level"])
        # if the building is being expanded, add 1 level
        if building["isBusy"]:
            current_level += 1

        banner()
        print("building:{}".format(building["name"]))
        print("current level:{}".format(current_level))

        final_level = read(min=current_level, msg="increase to level:")
        building["upgradeTo"] = final_level
        selected_buildings.append(building)

    return selected_buildings

@cache
def checkhash(url):
    m = hashlib.md5()
    r = requests.get(url)
    for data in r.iter_content(8192):
        m.update(data)
        if m.hexdigest() == config.material_img_hash[0]:
            material = "wood"
        elif m.hexdigest() == config.material_img_hash[1]:
            material = "wine"
        elif m.hexdigest() == config.material_img_hash[2]:
            material = "marble"
        elif m.hexdigest() == config.material_img_hash[3]:
            material = "glass"
        elif m.hexdigest() == config.material_img_hash[4]:
            material = "sulfur"
        else:
            continue
    return material


REDUCERS = ("carpentering", "vineyard", "architect", "optician", "fireworker")


def busy_reducers(city):
    """The cost reducers of the city, counting a level more for those being expanded"""
    reducers = getCostsReducers(city)
    for building in city["position"]:
        if building["name"] != "empty" and building.get("isBusy", False) and building["building"] in REDUCERS:
            i = REDUCERS.index(building["building"])
            reducers[i] = min(50, reducers[i] + 1)
    return reducers


def plan_construction(session, city, buildings, time_reduction=0.0):
    """Works out, in order, what each upgrade costs, what the city lacks for it and how long
    it takes, as the menu does: each upgrade spends from what the previous ones left, and a
    cost reducer that is expanded lowers the costs of the next ones
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    buildings : list[dict]
        {"position", "upgradeTo"}
    time_reduction : float
        fraction of the construction time removed by the Chronoforge

    Returns
    -------
    plans : list[dict]
        {"building" (the city's building with upgradeTo, capped at its last level),
        "requested", "costs", "missing", "times"}
    """
    resources = list(city["availableResources"])
    reducers = busy_reducers(city)
    plans = []
    for wanted in buildings:
        building = dict(city["position"][int(wanted["position"])], upgradeTo=int(wanted["upgradeTo"]))
        current_level = building["level"] + (1 if building["isBusy"] else 0)
        current_reducers = list(reducers)
        costs = getResourcesNeeded(
            session, city, building, current_level, building["upgradeTo"], current_reducers, time_reduction
        )
        requested = building["upgradeTo"]
        building["upgradeTo"] = min(requested, current_level + building["levelsAvailable"])
        missing = [max(0, costs[i] - resources[i]) for i in range(len(resources))]
        resources = [max(0, resources[i] - costs[i]) for i in range(len(resources))]
        reducers = current_reducers
        plans.append({
            "building": building,
            "requested": requested,
            "costs": costs,
            "missing": missing,
            "times": list(building.get("constructionTimes", [])),
        })
    return plans


def buildings_list(city):
    return ", ".join(
        "{} = {} ({}, level {})".format(b["position"], b["name"], b["building"], b["level"])
        for b in city["position"] if b["name"] != "empty"
    )


def building_position(city, value, name):
    """The position of a building of the city, given its position, its technical name
    (townHall) or its name in the game; the first one when there are several"""
    text = str(value).strip().lower()
    for building in city["position"]:
        if building["name"] == "empty":
            continue
        if text in (str(building["position"]), str(building["building"]).lower(), str(building["name"]).lower()):
            return int(building["position"])
    raise ValueError("{} {!r} is not a building of {}. Buildings: {}".format(name, value, city["name"], buildings_list(city)))


def transport_config(session, value, city_id, name):
    """{"origins": {resource: [city ids]}, "useFreighters", "useRounding"}"""
    if value is None:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("origins"), dict) or not value["origins"]:
        raise ValueError('{} must be an object like {{"origins": {{"marble": [1111, 2222]}}}} or null, got {!r}'.format(name, value))
    origins = {}
    for resource, cities in value["origins"].items():
        text = str(resource).strip().lower()
        if text.isdigit() and int(text) < len(RESOURCE_KEYS):
            text = RESOURCE_KEYS[int(text)]
        if text == "glass":
            text = "crystal"
        if text not in RESOURCE_KEYS:
            raise ValueError("{}.origins: unknown resource {!r}, use {}".format(name, resource, ", ".join(RESOURCE_KEYS)))
        if not isinstance(cities, (list, tuple)) or not cities:
            raise ValueError("{}.origins.{} must be a list of your city ids".format(name, text))
        ids = []
        for i, city in enumerate(cities):
            origin = requireOwnCity(session, city, "{}.origins.{}[{}]".format(name, text, i))
            if origin == city_id:
                raise ValueError("{}.origins.{}: the city cannot send to itself".format(name, text))
            if origin not in ids:
                ids.append(origin)
        origins[text] = origins.get(text, []) + [i for i in ids if i not in origins.get(text, [])]
    return {
        "origins": origins,
        "useFreighters": asBool(value.get("useFreighters", False), name + ".useFreighters"),
        "useRounding": asBool(value.get("useRounding", True), name + ".useRounding"),
    }


def config_from_saved(buildings, shipments, expand_overall):
    """An older menu saved the city's buildings and the shipments it worked out"""
    transport = None
    for shipment in shipments or []:
        if not isinstance(shipment, dict):
            continue
        if transport is None:
            transport = {"origins": {}, "useFreighters": bool(shipment.get("useFreighters", False)),
                         "useRounding": bool(shipment.get("useRounding", True))}
        for resource, cities in (shipment.get("origins") or {}).items():
            key = RESOURCE_KEYS[int(resource)]
            for origin in cities or []:
                origin_id = str(origin.get("id")) if isinstance(origin, dict) else str(origin)
                if origin_id not in transport["origins"].setdefault(key, []):
                    transport["origins"][key].append(origin_id)
    return {
        "buildings": [
            {"position": b.get("position"), "upgradeTo": b.get("upgradeTo")} if isinstance(b, dict) else b
            for b in buildings or []
        ],
        "transport": transport,
        "expand": True if expand_overall is None else bool(expand_overall),
    }


def prepare_constructionList(session, city_id=None, buildings=None, transport=None, expand=True, city_name=None,
                             shipments=None, expand_overall=None, wait_resources=None, construction_queue=None,
                             total_time=None):
    """Checks the config of a constructionList task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int or str
    buildings : list[dict]
        expanded one after another: {"position": position, technical name or name in the game,
        "upgradeTo": level, "transport": optional, like the top one}
    transport : dict
        for every building without its own: {"origins": {"marble": [city ids], ...},
        "useFreighters": false, "useRounding": true}; null sends nothing
    expand : bool
        false only sends the resources
    city_name, shipments, expand_overall, wait_resources, construction_queue, total_time :
        saved by older menus

    Returns
    -------
    config : dict
    """
    if shipments is not None or construction_queue is not None or city_name is not None:
        saved = config_from_saved(buildings, shipments, expand_overall)
        buildings, transport, expand = saved["buildings"], saved["transport"], saved["expand"]
    if city_id is None:
        raise ValueError("city_id is needed")
    city_id = requireOwnCity(session, city_id, "city_id")
    expand = asBool(expand, "expand")
    transport = transport_config(session, transport, city_id, "transport")
    city = getCityById(session, city_id)
    if not isinstance(buildings, (list, tuple)) or not buildings:
        raise ValueError('buildings must be a list like [{{"position": 4, "upgradeTo": 20}}]. Buildings of {}: {}'.format(
            city["name"], buildings_list(city)))
    checked = []
    for i, wanted in enumerate(buildings):
        name = "buildings[{}]".format(i)
        if not isinstance(wanted, dict):
            raise ValueError("{} must be an object, got {!r}".format(name, wanted))
        position = building_position(city, wanted.get("position", wanted.get("building")), name)
        if any(b["position"] == position for b in checked):
            raise ValueError("{}: the building at position {} is already in the list".format(name, position))
        building = city["position"][position]
        current = building["level"] + (1 if building["isBusy"] else 0)
        target = asInt(wanted.get("upgradeTo"), name + ".upgradeTo", minimum=1)
        if target <= current:
            raise ValueError("{}: {} is already at level {}".format(name, building["name"], current))
        item = {"position": position, "upgradeTo": target}
        own_transport = transport_config(session, wanted.get("transport"), city_id, name + ".transport")
        if own_transport is not None:
            item["transport"] = own_transport
        checked.append(item)
    for plan in plan_construction(session, city, checked):
        if plan["building"]["upgradeTo"] < plan["requested"]:
            raise ValueError("{} can only be expanded up to level {}".format(plan["building"]["name"], plan["building"]["upgradeTo"]))
    return {"city_id": city_id, "buildings": checked, "transport": transport, "expand": expand}


@task("constructionList", prepare=prepare_constructionList)
def do_it(session, city_id=None, buildings=None, transport=None, expand=True, city_name=None, shipments=None,
          expand_overall=None, wait_resources=None, construction_queue=None, total_time=None):
    """Sends the resources the upgrades lack and expands the buildings one after another
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : str
    buildings : list[dict]
        {"position", "upgradeTo", "transport" (optional)}
    transport : dict or None
    expand : bool
    city_name, shipments, expand_overall, wait_resources, construction_queue, total_time :
        saved by older menus; the task works them out again
    """
    if shipments is not None or construction_queue is not None or city_name is not None:
        saved = config_from_saved(buildings, shipments, expand_overall)
        buildings, transport, expand = saved["buildings"], saved["transport"], saved["expand"]
    city = getCityById(session, city_id)
    chronos_level, time_reduction = getChronosForgeReduction(session, city)
    plans = plan_construction(session, city, buildings, time_reduction or 0.0)

    construction_queue = [duration for plan in plans for duration in plan["times"]]
    total_time = sum(construction_queue) + max(0, int(city.get("endUpgradeTime", 0)) - int(time.time()))
    session.setStatus(
        "{}: queued {} upgrades | all done {}".format(
            city["name"], len(construction_queue), _formatEndTime(time.time() + total_time)
        )
    )
    info = "\nUpgrade building\n"
    building_log_name = plans[0]["building"]["name"] if len(plans) == 1 else "Multiple buildings"
    info = info + "City: {}\nBuilding: {}".format(city["name"], building_log_name)
    setInfoSignal(session, info)
    for plan in plans:
        if plan["building"]["upgradeTo"] < plan["requested"]:
            sendToBot(session, "{}: {} can only be expanded up to level {}".format(
                city["name"], plan["building"]["name"], plan["building"]["upgradeTo"]))

    # the resources each upgrade lacks, from the cities chosen for it
    threads = []
    for wanted, plan in zip(buildings, plans):
        shipping = wanted.get("transport") or transport
        if not shipping or sum(plan["missing"]) == 0:
            continue
        origins = {}
        for i, key in enumerate(RESOURCE_KEYS):
            if plan["missing"][i] > 0 and shipping["origins"].get(key):
                origins[i] = [getCityById(session, origin) for origin in shipping["origins"][key]]
        if not origins:
            continue
        t = threading.Thread(
            target=sendResourcesNeeded,
            args=(session, str(city_id), origins, plan["missing"], shipping.get("useFreighters", False),
                  shipping.get("useRounding", True)),
        )
        t.start()
        threads.append(t)

    try:
        if expand:
            for plan in plans:
                expandBuilding(session, str(city_id), plan["building"], len(threads) > 0, construction_queue)
        else:
            for t in threads:
                t.join()
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)


def _printUpgradeSummary(building, current_level, final_level, resourcesNeeded):
    print("\nMaterials needed for {} (lv {:d} -> {:d}):".format(building["name"], current_level, final_level))
    for i, name in enumerate(materials_names):
        amount = resourcesNeeded[i]
        if amount == 0:
            continue
        print("- {}: {}".format(name, addThousandSeparator(max(0, amount))))
    if building.get("constructionTimes"):
        print("Construction time: {}".format(daysHoursMinutes(building["constructionTime"])))
    print("")


@configurator
def constructionList(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    banner()
    print("In which city do you want to expand buildings?")
    city = chooseCity(session)
    cityId = city["id"]
    buildings = getBuildingsToExpand(session, cityId)
    if buildings is None or len(buildings) == 0:
        return None

    chronos_level, time_reduction = getChronosForgeReduction(session, city)
    if time_reduction is None:
        print("\nCould not read the Chronoforge (lv {:d}) reduction, construction times are shown without it.".format(chronos_level))
        time_reduction = 0.0
    elif chronos_level > 0:
        print("\nChronoforge lv {:d}: construction times -{:.3f}%".format(chronos_level, time_reduction * 100))

    #simulated resources
    simulated_resources = list(city["availableResources"])
    simulated_reducers = getCostsReducers(city)

    for b in city["position"]:
        if b["name"] != "empty" and b.get("isBusy", False):
            if b["building"] == "carpentering":
                simulated_reducers[0] = min(50, simulated_reducers[0] + 1)
            elif b["building"] == "vineyard":
                simulated_reducers[1] = min(50, simulated_reducers[1] + 1)
            elif b["building"] == "architect":
                simulated_reducers[2] = min(50, simulated_reducers[2] + 1)
            elif b["building"] == "optician":
                simulated_reducers[3] = min(50, simulated_reducers[3] + 1)
            elif b["building"] == "fireworker":
                simulated_reducers[4] = min(50, simulated_reducers[4] + 1)

    # NewList - Only Accepted
    confirmed_buildings = []
    shipments = []
    expand_overall = True

    # Sequentially upgrade each building
    for building in buildings:
        current_level = building["level"]
        if building["isBusy"]:
            current_level += 1
        final_level = building["upgradeTo"]

        current_reducers = list(simulated_reducers)

        # calculate the resources that are needed
        resourcesNeeded = getResourcesNeeded(
            session, city, building, current_level, final_level, current_reducers, time_reduction
        )

        levels_available = building["levelsAvailable"]
        if levels_available < final_level - current_level:
            print(
                "This building only allows you to expand {:d} more levels".format(
                    levels_available
                )
            )
            msg = "Expand {:d} levels? [Y/n]:".format(levels_available)
            rta = read(msg=msg, values=["Y", "y", "N", "n", ""])
            if rta.lower() == "n":
                print(f"\nSkipping {building['name']}.\n")
                continue
            # the task would otherwise try the levels the building does not have
            final_level = current_level + levels_available
            building["upgradeTo"] = final_level

        if -1 in resourcesNeeded:
            return None

        missing = [0] * len(materials_names)
        for i in range(len(materials_names)):
            if simulated_resources[i] < resourcesNeeded[i]:
                missing[i] = resourcesNeeded[i] - simulated_resources[i]

        # show missing resources to the user
        if sum(missing) > 0:
            _printUpgradeSummary(building, current_level, final_level, resourcesNeeded)

            print("Missing:")
            for i in range(len(materials_names)):
                if missing[i] <= 0:
                    continue
                name = materials_names[i].lower()
                print("{} of {}".format(addThousandSeparator(missing[i]), name))
            print("")

            # if the user wants, send the resources from the selected cities
            print("Automatically transport resources? [Y/n]")
            rta = read(values=["y", "Y", "n", "N", ""])
            if rta.lower() == "n":
                print("Proceed anyway? [Y/n]")
                rta = read(values=["y", "Y", "n", "N", ""])
                if rta.lower() == "n":
                    print(f"\nSkipping {building['name']} due to user cancellation.\n")
                    continue  # If it cancels, we skip it and it is NOT added to confirm_buildings
            else:
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
                print("Round up transport amounts? [Y/n]")
                print("(amounts will be rounded up but capped at what each city can provide)")
                rta_round = read(values=["y", "Y", "n", "N", ""])
                useRounding = rta_round.lower() != "n"
                origins, current_expand = sendResourcesMenu(session, cityId, missing)
                
                if not current_expand:
                    expand_overall = False
                
                if origins:
                    shipments.append({
                        "origins": origins,
                        "missing": missing,
                        "useFreighters": useFreighters,
                        "useRounding": useRounding
                    })
                    building["transport"] = {
                        "origins": {
                            RESOURCE_KEYS[int(resource)]: [str(origin["id"]) for origin in cities]
                            for resource, cities in origins.items()
                        },
                        "useFreighters": useFreighters,
                        "useRounding": useRounding,
                    }
        else:
            _printUpgradeSummary(building, current_level, final_level, resourcesNeeded)

            print("You have enough materials")
            print("Proceed? [Y/n]")
            rta = read(values=["y", "Y", "n", "N", ""])
            if rta.lower() == "n":
                print(f"\nSkipping {building['name']} due to user cancellation.\n")
                continue  # If it cancels, we skip it and it is NOT added to confirm_buildings

        # Save the approved building and deduct it from the simulator
        confirmed_buildings.append(building)
        simulated_reducers = current_reducers

        for i in range(len(materials_names)):
            if simulated_resources[i] < resourcesNeeded[i]:
                simulated_resources[i] = 0
            else:
                simulated_resources[i] -= resourcesNeeded[i]

    # Replace list
    buildings = confirmed_buildings

    total_time = sum(building["constructionTime"] for building in buildings)
    active_time = int(city.get("endUpgradeTime", 0)) - int(time.time())
    total_time += max(0, active_time)
    if buildings:
        print("\nTotal construction time: {}".format(daysHoursMinutes(total_time)))

    # every shipment belongs to a confirmed building: without buildings there is nothing to do
    if not buildings:
        return None

    # the task works out the costs, what is missing and the times again when it starts: the
    # config keeps the buildings, their levels and where their resources come from
    return {
        "session": session,
        "city_id": str(cityId),
        "buildings": [
            dict({"position": building["position"], "upgradeTo": building["upgradeTo"]},
                 **({"transport": building["transport"]} if building.get("transport") else {}))
            for building in buildings
        ],
        "transport": None,
        "expand": expand_overall,
    }
