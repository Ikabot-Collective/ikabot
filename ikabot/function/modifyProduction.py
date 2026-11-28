from ikabot.helpers.decorators import configurator, task
#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from ikabot.config import *
from ikabot.helpers.botComm import sendToBot
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.taskConfig import asBool, asInt, findBuildingPosition, getCityById, requireOwnCity
from ikabot.helpers.varios import getDateTime, wait

RESOURCES = {"wood": ["resource"], "tradegood": ["tradegood"], "both": ["resource", "tradegood"]}
RESOURCE_CHOICES = {1: "wood", 2: "tradegood", 3: "both"}


def workers_for(max_normal, overcharge, percentage, use_overcharge=False):
    """The workers to set: a percentage of the normal maximum, or with 100% and overcharge,
    the normal maximum plus the overcharge
    Parameters
    ----------
    max_normal : int
    overcharge : int
        the workers the overcharge adds
    percentage : int
        0 to 100
    use_overcharge : bool

    Returns
    -------
    workers : int
    """
    if percentage == 100:
        return max_normal + overcharge if use_overcharge else max_normal
    return int(max_normal / 100 * percentage)


def cities_config(session, cities_ids, name="cities_ids"):
    """null, or the list of the player's own city ids without repetitions"""
    if cities_ids is None:
        return None
    if not isinstance(cities_ids, (list, tuple)) or not cities_ids:
        raise ValueError("{} must be a non-empty list of your city ids or null for all of them, got {!r}".format(name, cities_ids))
    return list(dict.fromkeys(requireOwnCity(session, city_id, "{}[{}]".format(name, i)) for i, city_id in enumerate(cities_ids)))


def selected_or_all(session, cities_ids):
    """null in the config: every city of the player"""
    if cities_ids is not None:
        return [str(city_id) for city_id in cities_ids]
    return getIdsOfCities(session)[0]


def cities_from_menu(session, city_ids):
    """The menu lists every city and lets the user leave some out: null when none was left out"""
    return None if len(city_ids) == len(getIdsOfCities(session)[0]) else [str(city_id) for city_id in city_ids]


def report(session, show_results, message):
    if show_results:
        print(message)


def finish(session, show_results, done, skipped, what, menu_text):
    msg = "{} set in {} @{}".format(what, ", ".join(done) if done else "no city", getDateTime())
    if skipped:
        msg += ", skipped: {}".format("; ".join(skipped))
    session.setStatus(msg)
    if show_results:
        print(menu_text)
        enter()
    elif skipped:
        sendToBot(session, msg)


def prepare_modifyProduction(session, cities_ids=None, resources="both", percentage=100, overcharge=False, show_results=False):
    """Checks the config of a modifyProduction task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    cities_ids : list
        your city ids; null for all of them
    resources : str
        "wood" (saw mill), "tradegood" (luxury good mine) or "both"
    percentage : int
        0 to 100 of the workers the mine takes
    overcharge : bool
        only with 100: also fill the overcharge
    show_results : bool
        the menu shows each city and waits for Enter; never from the CLI

    Returns
    -------
    config : dict
    """
    text = str(resources).strip().lower()
    text = {"resource": "wood", "1": "wood", "2": "tradegood", "3": "both", "luxury": "tradegood"}.get(text, text)
    if text not in RESOURCES:
        raise ValueError('resources must be "wood", "tradegood" or "both", got {!r}'.format(resources))
    percentage = asInt(percentage, "percentage", minimum=0, maximum=100)
    overcharge = asBool(overcharge, "overcharge")
    if overcharge and percentage != 100:
        raise ValueError("overcharge needs percentage 100, got {}".format(percentage))
    return {"cities_ids": cities_config(session, cities_ids), "resources": text, "percentage": percentage, "overcharge": overcharge}


@task("modifyProduction", prepare=prepare_modifyProduction)
def do_modifyProduction(session, cities_ids=None, resources="both", percentage=100, overcharge=False, show_results=False):
    """Sets the workers of the saw mill and/or the luxury good mine of each city
    Parameters
    ----------
    session : ikabot.web.session.Session
    cities_ids : list or None
    resources : str
    percentage : int
    overcharge : bool
    show_results : bool
    """
    resource_types_to_modify = RESOURCES[resources]
    cities_to_process = {}
    for city_id in selected_or_all(session, cities_ids):
        city = getCityById(session, city_id)
        if city['islandId'] not in cities_to_process:
            cities_to_process[city['islandId']] = {'island': getIsland(session.get(island_url + city['islandId'])), 'cities': []}
        cities_to_process[city['islandId']]['cities'].append(city)

    if show_results:
        banner()
    done = []
    # loop through each selected city
    current_city_id_for_request = getCity(session.get())['id']
    # Loop through islands first
    for islandId, island_data in cities_to_process.items():
        island = island_data['island']
        resource_name = tradegoods_names[0]
        tradegood_name = tradegoods_names[int(island["tipo"])]

        # Then loop through cities on that island
        for city in island_data['cities']:
            session.setStatus("Setting the production of {}".format(city['name']))
            # Change the session context to the current city
            session.post(params={
                'action': 'header', 'function': 'changeCurrentCity',
                'actionRequest': actionRequest, 'cityId': city['id'],
                'oldView': 'city', 'backgroundView': 'city',
                'currentCityId': current_city_id_for_request, 'ajax': '1'
            })
            # Update the current city ID for the next request
            current_city_id_for_request = city['id']

            # Loop through only the resource types the user chose to modify
            for resource_type in resource_types_to_modify:
                # Fetch data for the current resource type
                url = f"view={resource_type}&type={resource_type}&islandId={islandId}&cityId={city['id']}&backgroundView=island&currentIslandId={islandId}&actionRequest={actionRequest}&ajax=1"
                resp = session.post(url)
                resp_json = json.loads(resp, strict=False)

                slider_data = resp_json[2][1]['js_ResourceSlider']['slider']
                finalWorkers = workers_for(slider_data['max_value'], slider_data['overcharge'], percentage, overcharge)

                # Set the workers
                worker_key = "rw" if resource_type == "resource" else "tw"
                session.post(params={
                    "islandId": islandId, "cityId": city["id"],
                    "type": resource_type, "screen": resource_type,
                    "action": "IslandScreen", "function": "workerPlan",
                     worker_key: finalWorkers, "templateView": resource_type,
                    "actionRequest": actionRequest, "ajax": "1"
                })

                selected_good_name = resource_name if resource_type == "resource" else tradegood_name
                report(session, show_results, f"{finalWorkers} workers set for {selected_good_name} in {city['name']}.")

                # Ikariam silently ignores a workerPlan request that arrives too soon
                # after another one on the same island, so space out resource/tradegood.
                if resource_type != resource_types_to_modify[-1]:
                    wait(2, 2)

            done.append(city['name'])
            wait(3, 4)

    finish(session, show_results, done, [], "Production", "\nAll productions have been set!")


@configurator(blocking=True)
def modifyProduction(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    banner()
    mod_msg = "In which cities do you want to modify production?"
    city_ids, _ = ignoreCities(session, msg=mod_msg)

    print("You want to modify the number of workers in Wood (1), Tradegood (2) or Both (3)?")
    res_choice = read(min=1, max=3)

    print("What % of production do you want to use? (Default 100%)")
    percentageWorkers = read(min=0, max=100, default=100)
    if percentageWorkers == 100:
        print("Would you like to use overcharge? (y/N)")
        overcharge = read(values=["y", "Y", "n", "N", ""])
        use_overcharge = overcharge.lower() == "y"
    else:
        use_overcharge = False

    if not city_ids:
        return None
    # the task sets the workers while the menu waits and shows each city
    return {
        "session": session,
        "cities_ids": cities_from_menu(session, city_ids),
        "resources": RESOURCE_CHOICES[res_choice],
        "percentage": percentageWorkers,
        "overcharge": use_overcharge,
        "show_results": True,
    }


def building_workers(session, cities_ids, building, show_results):
    """(cities, skipped): the cities to set with the position of ``building``, and the
    ones that do not have it"""
    found, skipped = [], []
    for city_id in selected_or_all(session, cities_ids):
        city = getCityById(session, city_id)
        position = findBuildingPosition(city, building)
        if position is None:
            report(session, show_results, f"No {building} in {city['name']}, skipping.")
            skipped.append("{} has no {}".format(city["name"], building))
            continue
        found.append((city, position))
    return found, skipped


def require_building(session, cities_ids, building):
    """The cities listed must have the building; with null, at least one of the player's"""
    with_building = 0
    for city_id in selected_or_all(session, cities_ids):
        city = getCityById(session, city_id)
        if findBuildingPosition(city, building) is not None:
            with_building += 1
        elif cities_ids is not None:
            raise ValueError("{} ({}) has no {}".format(city["name"], city_id, building))
    if with_building == 0:
        raise ValueError("none of your cities has {} {}".format("an" if building[0] in "aeiou" else "a", building))


def prepare_modifyAcademyWorkers(session, cities_ids=None, percentage=100, show_results=False):
    """Checks the config of a modifyAcademyWorkers task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    cities_ids : list
        your city ids, each with an academy; null for all the cities that have one
    percentage : int
        0 to 100 of the scientists the academy takes
    show_results : bool
        the menu shows each city and waits for Enter; never from the CLI

    Returns
    -------
    config : dict
    """
    cities_ids = cities_config(session, cities_ids)
    percentage = asInt(percentage, "percentage", minimum=0, maximum=100)
    require_building(session, cities_ids, "academy")
    return {"cities_ids": cities_ids, "percentage": percentage}


@task("modifyAcademyWorkers", prepare=prepare_modifyAcademyWorkers)
def do_modifyAcademyWorkers(session, cities_ids=None, percentage=100, show_results=False):
    """Sets the scientists of the academy of each city
    Parameters
    ----------
    session : ikabot.web.session.Session
    cities_ids : list or None
    percentage : int
    show_results : bool
    """
    if show_results:
        banner()
    found, skipped = building_workers(session, cities_ids, "academy", show_results)
    done = []
    for city, position in found:
        session.setStatus("Setting the scientists of {}".format(city['name']))
        url = f"view=academy&cityId={city['id']}&position={position}&backgroundView=city&currentCityId={city['id']}&actionRequest={actionRequest}&ajax=1"
        resp = session.post(url)
        resp_json = json.loads(resp, strict=False)
        max_scientists = resp_json[2][1]['js_AcademySlider']['slider']['max_value']
        finalScientists = workers_for(max_scientists, 0, percentage)

        session.post(params={
            "action": "IslandScreen", "function": "workerPlan",
            "screen": "academy", "position": position,
            "cityId": city["id"], "s": finalScientists,
            "backgroundView": "city", "currentCityId": city["id"],
            "templateView": "academy", "actionRequest": actionRequest, "ajax": "1"
        })
        report(session, show_results, f"{finalScientists} scientists set for Academy in {city['name']}.")
        done.append(city['name'])

        wait(3, 4)

    finish(session, show_results, done, skipped, "Scientists", "\nAll academies have been set!")


@configurator(blocking=True)
def modifyAcademyWorkers(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    banner()
    city_ids, _ = ignoreCities(session, msg="In which cities do you want to set academy workers?")

    print("What % of scientists do you want to use? (Default 100%)")
    percentageWorkers = read(min=0, max=100, default=100)

    if not city_ids:
        return None
    # the task sets the scientists while the menu waits and shows each city
    return {
        "session": session,
        "cities_ids": cities_from_menu(session, city_ids),
        "percentage": percentageWorkers,
        "show_results": True,
    }


def prepare_modifyTempleWorkers(session, cities_ids=None, percentage=100, show_results=False):
    """Checks the config of a modifyTempleWorkers task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    cities_ids : list
        your city ids, each with a temple; null for all the cities that have one
    percentage : int
        0 to 100 of the priests the temple takes
    show_results : bool
        the menu shows each city and waits for Enter; never from the CLI

    Returns
    -------
    config : dict
    """
    cities_ids = cities_config(session, cities_ids)
    percentage = asInt(percentage, "percentage", minimum=0, maximum=100)
    require_building(session, cities_ids, "temple")
    return {"cities_ids": cities_ids, "percentage": percentage}


@task("modifyTempleWorkers", prepare=prepare_modifyTempleWorkers)
def do_modifyTempleWorkers(session, cities_ids=None, percentage=100, show_results=False):
    """Sets the priests of the temple of each city
    Parameters
    ----------
    session : ikabot.web.session.Session
    cities_ids : list or None
    percentage : int
    show_results : bool
    """
    if show_results:
        banner()
    found, skipped = building_workers(session, cities_ids, "temple", show_results)
    done = []
    for city, position in found:
        session.setStatus("Setting the priests of {}".format(city['name']))
        url = f"view=temple&cityId={city['id']}&position={position}&backgroundView=city&currentCityId={city['id']}&actionRequest={actionRequest}&ajax=1"
        resp = session.post(url)
        resp_json = json.loads(resp, strict=False)
        max_priests = resp_json[2][1]['js_TempleSlider']['slider']['max_value']
        finalPriests = workers_for(max_priests, 0, percentage)

        session.post(params={
            "action": "CityScreen", "function": "assignPriests",
            "cityId": city["id"], "position": position,
            "priests": finalPriests,
            "backgroundView": "city", "currentCityId": city["id"],
            "templateView": "temple", "actionRequest": actionRequest, "ajax": "1"
        })
        report(session, show_results, f"{finalPriests} priests set for Temple in {city['name']}.")
        done.append(city['name'])

        wait(3, 4)

    finish(session, show_results, done, skipped, "Priests", "\nAll temples have been set!")


@configurator(blocking=True)
def modifyTempleWorkers(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    banner()
    city_ids, _ = ignoreCities(session, msg="In which cities do you want to set priests?")

    print("What % of priests do you want to use? (Default 100%)")
    percentageWorkers = read(min=0, max=100, default=100)

    if not city_ids:
        return None
    # the task sets the priests while the menu waits and shows each city
    return {
        "session": session,
        "cities_ids": cities_from_menu(session, city_ids),
        "percentage": percentageWorkers,
        "show_results": True,
    }
