#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
import hashlib
import json
import math
import random
import re
import threading
import time
import traceback
from decimal import *

import requests
from functools import cache

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planRoutes import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.resources import getAvailableResources
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *
from ikabot.web.session import normal_get

t = gettext.translation(
    "constructionList", localedir, languages=languages, fallback=True
)
_ = t.gettext

sendResources = True
expand = True
thread = None


def waitForConstruction(session, city_id, final_lvl):
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

        msg = _("{}: I wait {:d} seconds so that {} gets to the level {:d}").format(
            city["cityName"],
            seconds_to_wait,
            construction_building["name"],
            construction_building["level"] + 1,
        )
        sendToBotDebug(session, msg, debugON_constructionList)
        session.setStatus(
            f"Waiting until {getDateTime(time.time()+seconds_to_wait+10)[8:]}, {construction_building['name']} {construction_building['level']} -> {construction_building['level']+1} in {city['name']}, final lvl: {final_lvl}"
        )
        wait(seconds_to_wait + 10)

    html = session.get(city_url + city_id)
    city = getCity(html)
    return city


def expandBuilding(session, cityId, building, waitForResources):
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
        city = waitForConstruction(session, cityId, upgradeTo)
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
            msg = _("City:{}\n").format(city["cityName"])
            msg += _("Building:{}\n").format(building["name"])
            msg += _("The building could not be completed due to lack of resources.\n")
            msg += _("Missed {:d} levels").format(levels_to_upgrade - lv)
            sendToBot(session, msg)
            return

        url = "action=CityScreen&function=upgradeBuilding&actionRequest={}&cityId={}&position={:d}&level={}&activeTab=tabSendTransporter&backgroundView=city&currentCityId={}&templateView={}&ajax=1".format(
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
            msg = _("{}: The building {} was not extended").format(
                city["cityName"], building["name"]
            )
            sendToBot(session, msg)
            sendToBot(session, resp)
            return

        msg = _("{}: The building {} is being extended to level {:d}.").format(
            city["cityName"], building["name"], building["level"] + 1
        )
        sendToBotDebug(session, msg, debugON_constructionList)

    msg = _("{}: The building {} finished extending to level: {:d}.").format(
        city["cityName"], building["name"], building["level"] + 1
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


def getResourcesNeeded(session, city, building, current_level, final_level):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    building : dict
    current_level : int
    final_level : int

    Returns
    -------
    costs_per_material : dict[int, int]
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
        + re.escape(building["building"])
        + r'"\s*onmouseover="\$\(this\)\.addClass\(\'hover\'\);" onmouseout="\$\(this\)\.removeClass\(\'hover\'\);"\s*onclick="ajaxHandlerCall\(\'\?(.*?)\'\);'
    )
    match = re.search(regex_building_detail, building_html)
    building_costs_url = match.group(1)
    building_costs_url += "backgroundView=city&currentCityId={}&templateView=buildingDetail&actionRequest={}&ajax=1".format(
        city["id"], actionRequest
    )
    building_costs_response = session.post(building_costs_url)
    building_costs = json.loads(building_costs_response, strict=False)
    html_costs = building_costs[1][1][1]

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
    costs_reductions = getCostsReducers(city)

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
    levels_to_upgrade = 0
    for match in matches:
        lv = re.search(r'"level">(\d+)</td>', match).group(1)
        lv = int(lv)

        if lv <= current_level:
            continue
        if lv > final_level:
            break

        levels_to_upgrade += 1
        # get the costs for the current level
        costs = re.findall(r'<td class="costs">([\d,\.]*)</td>', match)

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
            real_cost = Decimal(cost)
            # investigation reduction
            original_cost = Decimal(real_cost) / Decimal(costs_reduction)
            # special building reduction
            real_cost -= Decimal(original_cost) * (
                Decimal(costs_reductions[resource_index]) / Decimal(100)
            )

            final_costs[resource_index] += math.ceil(real_cost)

    if levels_to_upgrade < final_level - current_level:
        print(
            _("This building only allows you to expand {:d} more levels").format(
                levels_to_upgrade
            )
        )
        msg = _("Expand {:d} levels? [Y/n]:").format(levels_to_upgrade)
        rta = read(msg=msg, values=["Y", "y", "N", "n", ""])
        if rta.lower() == "n":
            return [-1, -1, -1, -1, -1]

    return final_costs


def sendResourcesNeeded(session, destination_city_id, city_origins, missing_resources, useFreighters=False):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    destination_city_id : int
    city_origins : dict
    missing_resources : dict[int, int]
    """

    info = _("\nTransport resources to upload building\n")

    try:
        routes = []
        html = session.get(city_url + destination_city_id)
        cityD = getCity(html)
        for i in range(len(materials_names)):
            missing = missing_resources[i]
            if missing <= 0:
                continue

            # send the resources from each origin city
            for cityOrigin in city_origins[i]:
                if missing == 0:
                    break

                available = cityOrigin["availableResources"][i]
                send = min(available, missing)
                missing -= send
                toSend = [0] * len(materials_names)
                toSend[i] = send
                route = (cityOrigin, cityD, cityD["islandId"], *toSend)
                routes.append(route)
        executeRoutes(session, routes, useFreighters)
    except Exception as e:
        msg = _("Error in:\n{}\nCause:\n{}").format(info, traceback.format_exc())
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
    global sendResources
    sendResources = True
    global expand
    expand = True

    banner()
    print(_("From what cities obtain {}?").format(materials_names[resource].lower()))

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
            return origin_cities

    # if we reach this part, there are not enough resources to expand the building
    print(_("\nThere are not enough resources."))

    if len(origin_cities) > 0:
        print(_("\nSend the resources anyway? [Y/n]"))
        choice = read(values=["y", "Y", "n", "N", ""])
        if choice.lower() == "n":
            sendResources = False

    print(_("\nTry to expand the building anyway? [y/N]"))
    choice = read(values=["y", "Y", "n", "N", ""])
    if choice.lower() == "n" or choice == "":
        expand = False

    return origin_cities


def sendResourcesMenu(session, city_id, missing, useFreighters=False):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int
    missing : list[int, int]
    """
    global thread
    cities_ids, cities = getIdsOfCities(session)
    origins = {}
    # for each missing resource, choose providers
    for resource in range(len(missing)):
        if missing[resource] <= 0:
            continue

        origin_cities = chooseResourceProviders(
            session, cities_ids, cities, city_id, resource, missing[resource]
        )
        if sendResources is False and expand:
            print(_("\nThe building will be expanded if possible."))
            enter()
            return
        elif sendResources is False:
            return
        origins[resource] = origin_cities

    if expand:
        print(
            _(
                "\nThe resources will be sent and the building will be expanded if possible."
            )
        )
    else:
        print(_("\nThe resources will be sent."))

    enter()

    # create a new thread to send the resources
    thread = threading.Thread(
        target=sendResourcesNeeded,
        args=(
            session,
            city_id,
            origins,
            missing,
            useFreighters,
        ),
    )
    thread.start()


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
    print(_("Which buildings do you want to expand? Separate numbers with commas (7, 1, 3, 5, ...)\n"))
    print(_("(0)\t\texit"))
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
        print(_("({:d})\tlv:{}\t{}{}{}").format(i + 1, level, color, building["name"], bcolors.ENDC))

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
        print(_("building:{}").format(building["name"]))
        print(_("current level:{}").format(current_level))

        final_level = read(min=current_level, msg=_("increase to level:"))
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


def constructionList(session, event, stdin_fd, predetermined_input):
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
        global expand
        global sendResources
        expand = True
        sendResources = True

        banner()
        wait_resources = False
        print(_("In which city do you want to expand buildings?"))
        city = chooseCity(session)
        cityId = city["id"]
        buildings = getBuildingsToExpand(session, cityId)
        if buildings is None or len(buildings) == 0:
            event.set()
            return

        # Sequentially upgrade each building
        for building in buildings:
            current_level = building["level"]
            if building["isBusy"]:
                current_level += 1
            final_level = building["upgradeTo"]

            # calculate the resources that are needed
            resourcesNeeded = getResourcesNeeded(
                session, city, building, current_level, final_level
            )
            if -1 in resourcesNeeded:
                event.set()
                return

            print("\nMaterials needed for {}:".format(building["name"]))
            for i, name in enumerate(materials_names):
                amount = resourcesNeeded[i]
                if amount == 0:
                    continue
                print("- {}: {}".format(name, addThousandSeparator(amount)))
            print("")

            # calculate the resources that are missing
            missing = [0] * len(materials_names)
            for i in range(len(materials_names)):
                if city["availableResources"][i] < resourcesNeeded[i]:
                    missing[i] = resourcesNeeded[i] - city["availableResources"][i]

            # show missing resources to the user
            if sum(missing) > 0:
                print(_("\nMissing:"))
                for i in range(len(materials_names)):
                    if missing[i] == 0:
                        continue
                    name = materials_names[i].lower()
                    print(_("{} of {}").format(addThousandSeparator(missing[i]), name))
                print("")

                # if the user wants, send the resources from the selected cities
                print(_("Automatically transport resources? [Y/n]"))
                rta = read(values=["y", "Y", "n", "N", ""])
                if rta.lower() == "n":
                    print(_("Proceed anyway? [Y/n]"))
                    rta = read(values=["y", "Y", "n", "N", ""])
                    if rta.lower() == "n":
                        event.set()
                        return
                else:
                    print(_("What type of ships do you want to use? (Default: Trade ships)"))
                    print(_("(1) Trade ships"))
                    print(_("(2) Freighters"))
                    shiptype = read(min=1, max=2, digit=True, empty=True)
                    if shiptype == '':
                        shiptype = 1
                    if shiptype == 1:
                        useFreighters = False
                    elif shiptype == 2:
                        useFreighters = True
                    wait_resources = True
                    sendResourcesMenu(session, cityId, missing, useFreighters)
            else:
                print(_("\nYou have enough materials"))
                print(_("Proceed? [Y/n]"))
                rta = read(values=["y", "Y", "n", "N", ""])
                if rta.lower() == "n":
                    event.set()
                    return
    except KeyboardInterrupt:
        event.set()
        return
    
    set_child_mode(session)
    event.set()

    info = _("\nUpgrade building\n")
    info = info + _("City: {}\nBuilding: {}. From {:d}, to {:d}").format(
        city["cityName"], building["name"], current_level, final_level
    )

    setInfoSignal(session, info)
    try:
        if expand:
            for building in buildings:
                expandBuilding(session, cityId, building, wait_resources)
        elif thread:
            thread.join()
    except Exception as e:
        msg = _("Error in:\n{}\nCause:\n{}").format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()

