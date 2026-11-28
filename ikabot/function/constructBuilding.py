from ikabot.helpers.decorators import configurator, task
#! /usr/bin/env python3
# -*- coding: utf-8 -*-


import json
import re

from ikabot.config import *
from ikabot.helpers.botComm import sendToBot
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.taskConfig import asInt, getCityById, requireOwnCity
from ikabot.helpers.varios import addThousandSeparator, getDateTime


def parseBuildingCosts(html_block):
    costs = [0] * len(materials_names)
    resource_map = {
        "wood": 0,
        "wine": 1,
        "marble": 2,
        "crystal": 3,
        "glass": 3,
        "sulfur": 4,
    }
    matches = re.findall(
        r'<li\s+class="(\w+)[^"]*"[^>]*\s+title="[^"]*?:\s*([\d\s\xa0\.]+)"', html_block
    )
    for res_type, amount_str in matches:
        if res_type not in resource_map:
            continue
        idx = resource_map[res_type]
        amount_str = amount_str.replace("\xa0", "").replace(" ", "").replace(".", "")
        try:
            costs[idx] = int(amount_str)
        except ValueError:
            pass
    return costs


def splitBuildingBlocks(html):
    blocks = []
    pattern = r'<li class="building (\w+)[^"]*">((?:(?!<li class="building ).)+)</li>'
    for match in re.finditer(pattern, html, re.DOTALL):
        blocks.append({"type": match.group(1), "html": match.group(2)})
    return blocks


def buildable_buildings(session, city):
    """The buildings that can be built in the free places of the city
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict

    Returns
    -------
    (buildings, action_request) : tuple
        buildings: {"building" (technical name), "name", "buildingId", "type" (the kind of
        place), "costs", "canAfford"}; action_request: the one the game sent last
    """
    # list of free spaces in the selected city
    free_spaces = [
        buildings
        for buildings in city["position"]
        if buildings["building"] == "empty"
    ]

    # get a list of all the posible buildings that can be built
    buildings = []
    seen_ids = set()
    # different buildings can be built in different areas
    current_action_request = actionRequest
    type_spaces = ["sea", "land", "shore", "wall", "dockyard"]
    for type_space in type_spaces:
        free_spaces_of_type = [
            free_space
            for free_space in free_spaces
            if free_space["type"] == type_space
        ]
        # Iterate through available slots for this surface type until an active/unlocked slot is found.
        # Slots like position 13 require specific research (e.g., Bureaucracy) and will return empty HTML if locked.
        for free_space_of_type in free_spaces_of_type:
            params = {
                "view": "buildingGround",
                "cityId": city["id"],
                "position": free_space_of_type["position"],
                "backgroundView": "city",
                "currentCityId": city["id"],
                "actionRequest": actionRequest,
                "ajax": "1",
            }
            buildings_response = session.post(params=params, noIndex=True)
            parsed_response = json.loads(buildings_response, strict=False)

            # Extract fresh actionRequest from the response
            try:
                update_global = [item for item in parsed_response if item[0] == 'updateGlobalData']
                if update_global:
                    current_action_request = update_global[0][1].get('actionRequest', actionRequest)
                else:
                    current_action_request = actionRequest
            except Exception:
                current_action_request = actionRequest

            buildings_response = parsed_response[1][1]
            if buildings_response == "":
                continue

            html = buildings_response[1]
            blocks = splitBuildingBlocks(html)
            # Skip slot if the server returned empty content (e.g., locked slot or special restriction)
            if len(blocks) == 0:
                continue

            for block in blocks:
                btype = block["type"]
                block_html = block["html"]
                info_match = re.search(
                    r'<div title="(.+?)"\s*class="buildingimg .+?"\s*onclick="ajaxHandlerCall\(\'.*?buildingId=(\d+)&',
                    block_html,
                )
                if not info_match:
                    continue

                building_id = info_match.group(2)
                building_name = info_match.group(1)

                if building_id in seen_ids:
                    continue

                seen_ids.add(building_id)
                costs = parseBuildingCosts(block_html)
                can_afford = all(
                    costs[i] <= city["availableResources"][i]
                    for i in range(len(materials_names))
                )

                buildings.append(
                    {
                        "building": btype,
                        "name": building_name,
                        "buildingId": building_id,
                        "type": type_space,
                        "costs": costs,
                        "canAfford": can_afford,
                    }
                )
            # Stop checking remaining slots of this surface type once build options are retrieved
            if len(blocks) > 0:
                break
    return buildings, current_action_request


def free_places(city, building):
    """The free places of the city where ``building`` can go"""
    return [
        position_id
        for position_id in city["position"]
        if position_id["building"] == "empty"
        and position_id["type"] == building["type"]
    ]


def missing_text(city, building):
    """What the city lacks to build it, e.g. "1.200 Marble (has 300)\""""
    return ", ".join(
        "{} {} (has {})".format(addThousandSeparator(cost - city["availableResources"][i]), materials_names[i],
                                addThousandSeparator(city["availableResources"][i]))
        for i, cost in enumerate(building["costs"])
        if cost > city["availableResources"][i]
    )


def choose_building(session, city, value, position=None):
    """The building to build and the place for it
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    value : str or int
        the building's technical name (museum), its name in the game or its id
    position : int or None
        a free place of the city for it; None takes the first one

    Returns
    -------
    (building, place, action_request) : tuple
    """
    buildings, action_request = buildable_buildings(session, city)
    if not buildings:
        raise ValueError("no building can be built in {}".format(city["name"]))
    text = str(value).strip().lower()
    building = next((b for b in buildings if text in (b["building"].lower(), b["name"].lower(), str(b["buildingId"]))), None)
    if building is None:
        raise ValueError("building {!r} cannot be built in {}. Buildings: {}".format(
            value, city["name"], ", ".join("{} = {}".format(b["building"], b["name"]) for b in buildings)))
    if not building["canAfford"]:
        raise ValueError("{} lacks resources to build {}: {}".format(city["name"], building["name"], missing_text(city, building)))
    places = free_places(city, building)
    if not places:
        raise ValueError("{} has no free place for {}".format(city["name"], building["name"]))
    if position is None:
        return building, places[0], action_request
    place = next((p for p in places if int(p["position"]) == int(position)), None)
    if place is None:
        raise ValueError("position {} is not a free place for {} in {}. Free places for it: {}".format(
            position, building["name"], city["name"], ", ".join(str(p["position"]) for p in places)))
    return building, place, action_request


def prepare_constructBuilding(session, city_id=None, building=None, position=None, show_results=False):
    """Checks the config of a constructBuilding task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int or str
        one of your cities
    building : str
        the building's technical name (museum), its name in the game or its id
    position : int
        a free place of the city for it; null takes the first one
    show_results : bool
        the menu shows the game's answer and waits for Enter; never from the CLI

    Returns
    -------
    config : dict
    """
    if city_id is None:
        raise ValueError("city_id is needed")
    if building is None or not str(building).strip():
        raise ValueError("building is needed: its technical name (museum), its name in the game or its id")
    city_id = requireOwnCity(session, city_id, "city_id")
    if position is not None:
        position = asInt(position, "position", minimum=0)
    chosen, place, _ = choose_building(session, getCityById(session, city_id), building, position)
    return {"city_id": city_id, "building": chosen["building"], "position": position}


@task("constructBuilding", prepare=prepare_constructBuilding)
def do_constructBuilding(session, city_id=None, building=None, position=None, show_results=False):
    """Builds a building once in a free place of the city
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : str
    building : str
    position : int or None
    show_results : bool
    """
    city = getCityById(session, city_id)
    try:
        chosen, place, current_action_request = choose_building(session, city, building, position)
    except ValueError as e:
        msg = "Nothing was built: {}".format(e)
        session.setStatus(msg)
        if show_results:
            print(msg)
            enter()
        else:
            sendToBot(session, msg)
        return

    # build it
    params = {
        "action": "BuildNewBuilding",
        "cityId": city["id"],
        "position": place["position"],
        "building": chosen["buildingId"],
        "backgroundView": "city",
        "currentCityId": city["id"],
        "templateView": "buildingGround",
        "actionRequest": current_action_request,
        "ajax": "1",
    }
    buildings_response = session.post(params=params, noIndex=True)
    response_data = json.loads(buildings_response, strict=False)
    msg = None
    rejected = False
    for item in response_data:
        if item[0] == 'provideFeedback':
            for feedback in item[1]:
                if feedback.get('text'):
                    msg = feedback['text']
                    rejected = feedback.get("type") == 11
                    break
            if msg:
                break
    if not msg:
        msg = "Building process completed."
    status = "{}: {} at position {}: {} @{}".format(city["name"], chosen["name"], place["position"], msg, getDateTime())
    session.setStatus(status)
    if show_results:
        print(msg)
        enter()
    elif rejected:
        sendToBot(session, status)


@configurator(blocking=True)
def constructBuilding(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    banner()

    print("City where to build:")
    city = chooseCity(session)
    banner()

    buildings, _ = buildable_buildings(session, city)

    if len(buildings) == 0:
        print("No building can be built.")
        enter()
        return None

    # show list of buildings to the user with color coding
    while True:
        banner()
        print("What building do you want to build?\n")
        i = 0
        for building in buildings:
            i += 1
            color = bcolors.GREEN if building["canAfford"] else bcolors.RED
            print(
                "({:d}) {}{}{}".format(
                    i, color, building["name"], bcolors.ENDC
                )
            )
        print(
            "\n{}Green{} = can afford | {}Red{} = insufficient resources | (0) Exit".format(
                bcolors.GREEN, bcolors.ENDC, bcolors.RED, bcolors.ENDC
            )
        )
        selected_building_index = read(min=0, max=i)
        if selected_building_index == 0:
            return None
        selected_building = buildings[selected_building_index - 1]

        if not selected_building["canAfford"]:
            banner()
            print("{}Insufficient resources to build: {}{}".format(bcolors.RED, selected_building["name"], bcolors.ENDC))
            print("\nMissing resources:")
            any_missing = False
            for idx, cost in enumerate(selected_building["costs"]):
                if cost == 0:
                    continue
                have = city["availableResources"][idx]
                if have >= cost:
                    continue
                missing = cost - have
                any_missing = True
                print(
                    "- {}{}: {} {}(have: {}){}".format(
                        materials_names[idx],
                        bcolors.RED,
                        addThousandSeparator(missing),
                        bcolors.STONE,
                        addThousandSeparator(have),
                        bcolors.ENDC,
                    )
                )
            if not any_missing:
                print("You have enough resources for this building.")
            print("\nPress Enter to return to the menu...")
            enter()
            continue
        else:
            break
    building = selected_building
    banner()
    print("{}\n".format(building["name"]))
    options = free_places(city, building)
    if len(options) == 1:
        option = options[0]
    else:
        print("In which position do you want to build?\n")
        i = 0
        for option in options:
            i += 1
            print("({:d}) {}".format(i, option["position"]))
        selected_building_index = read(min=1, max=i)
        option = options[selected_building_index - 1]
        banner()

    # the task builds it while the menu waits and shows the game's answer
    return {
        "session": session,
        "city_id": str(city["id"]),
        "building": building["building"],
        "position": int(option["position"]),
        "show_results": True,
    }
