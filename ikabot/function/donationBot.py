#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import traceback

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.decorators import configurator, task
from ikabot.helpers.resources import getAvailableResources, getProductionPerHour
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.taskConfig import asId, asInt, requireOwnCity
from ikabot.helpers.varios import wait, getDateTime


def _get_donation_config(cities, donate_method, cityId):
    """
    Get donation configuration for a city.

    Parameters
    ----------
    cities : dict
    donate_method : int
    cityId : int

    Returns
    -------
    tuple[str|None, int|None]
        (donation_type, percentage)
    """
    initials = [material_name[0] for material_name in materials_names]
    tradegood = cities[cityId]["tradegood"]
    initial = initials[int(tradegood)]

    print(
        "In {} ({}), Do you wish to donate to the forest, to the trading good, to both or none? [f/t/b/n]".format(
            cities[cityId]["name"], initial
        )
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
        return donation_type, percentage

    if donate_method == 1:
        print(
            "What is the maximum percentage of your storage capacity that you wish to keep occupied? (the resources that exceed it, will be donated) (default: 80%)"
        )
        percentage = read(min=0, max=100, empty=True)
        if percentage == "":
            percentage = 80
        elif percentage == 100:
            # if the user is ok with the storage being totally full, don't donate at all
            donation_type = None
    elif donate_method == 2:
        print(
            "What is the percentage of your production that you wish to donate? (enter 0 to disable donation for the town) (default: 50%)"
        )
        percentage = read(min=0, max=100, empty=True)
        if percentage == "":
            percentage = 50
        elif percentage == 0:
            donation_type = None
    elif donate_method == 3:
        print(
            "What is the amount would you like to donate? (enter 0 to disable donation for the town) (default: 10000)"
        )
        percentage = read(min=0, empty=True)
        if percentage == "":
            percentage = 10000
        elif percentage == 0:
            donation_type = None

    return donation_type, percentage


DONATION_TYPES = {
    "resource": "resource", "forest": "resource", "wood": "resource", "f": "resource",
    "tradegood": "tradegood", "luxury": "tradegood", "t": "tradegood",
    "both": "both", "b": "both",
    "none": None, "n": None,
}
# default value per donate_method, and the value that disables the donation, as in the menu
DEFAULT_PERCENTAGE = {1: 80, 2: 50, 3: 10000}
NO_DONATION_PERCENTAGE = {1: 100, 2: 0, 3: 0}


def prepare_donationBot(session, cities_dict, waiting_time=24 * 60, donate_method=1, cities_ids=None):
    """Checks the config of a donationBot task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    cities_dict : dict
        {city id: {"donation_type": ..., "percentage": ...}}; the key "all" applies to every own city
    waiting_time : int
        minutes between donations
    donate_method : int
        1 = storage percentage to keep, 2 = percentage of production, 3 = fixed amount
    cities_ids : list
        built from cities_dict

    Returns
    -------
    config : dict
    """
    donate_method = asInt(donate_method, "donate_method", minimum=1, maximum=3)
    if not isinstance(cities_dict, dict) or not cities_dict:
        raise ValueError(
            'cities_dict must map city ids (or "all") to {{"donation_type": ..., "percentage": ...}}, got {!r}'.format(cities_dict)
        )
    own_ids = getIdsOfCities(session)[0]
    settings = {}
    if "all" in cities_dict:
        for city_id in own_ids:
            settings[city_id] = cities_dict["all"]
    for key, value in cities_dict.items():
        if key == "all":
            continue
        city_id = asId(key, "cities_dict")
        if city_id not in own_ids:
            requireOwnCity(session, city_id, "cities_dict")  # raises, listing the own cities
        settings[city_id] = value

    normalized = {}
    for city_id, value in settings.items():
        name = "cities_dict[{}]".format(city_id)
        if not isinstance(value, dict):
            raise ValueError('{} must be {{"donation_type": ..., "percentage": ...}}, got {!r}'.format(name, value))
        donation_type = value.get("donation_type")
        key = "none" if donation_type is None else str(donation_type).strip().lower()
        if key not in DONATION_TYPES:
            raise ValueError(
                "{}.donation_type must be resource, tradegood, both or none, got {!r}".format(name, donation_type)
            )
        donation_type = DONATION_TYPES[key]
        percentage = value.get("percentage")
        if percentage is None:
            percentage = DEFAULT_PERCENTAGE[donate_method]
        percentage = asInt(
            percentage, name + ".percentage", minimum=0, maximum=None if donate_method == 3 else 100
        )
        if donation_type is None or percentage == NO_DONATION_PERCENTAGE[donate_method]:
            donation_type, percentage = None, None
        normalized[city_id] = {"donation_type": donation_type, "percentage": percentage}

    return {
        "cities_ids": list(normalized),
        "cities_dict": normalized,
        "waiting_time": asInt(waiting_time, "waiting_time", minimum=1),
        "donate_method": donate_method,
    }


@task("donationBot", prepare=prepare_donationBot)
def do_it(
    session,
    cities_dict,
    waiting_time=24 * 60,
    donate_method=1,
    cities_ids=None,
):
    if cities_ids is None:
        cities_ids = list(cities_dict)
    info = "\nI donate every {} minutes\n".format(waiting_time)
    setInfoSignal(session, info)
    for cityId in cities_ids:
        try:
            html = session.get(city_url + cityId)
            city = getCity(html)
            cities_dict[cityId]["island"] = city["islandId"]
        except Exception:
            continue

    total_general_donated = 0

    while True:
        session.setStatus(f"Checking cities... | Total Donated: {total_general_donated}")
        
        for cityId in cities_ids:
            donation_type = cities_dict[cityId]["donation_type"]
            if donation_type is None:
                continue

            try:
                html_init = session.get(city_url + cityId)
                city_init = getCity(html_init)
                wood_init = int(city_init["availableResources"][0])
                storage = int(city_init["storageCapacity"])
                
                inv_init = getInventoryItem(session, 2201)
                amount_inv_init = 0
                if inv_init is not None:
                    raw_count = str(inv_init.get("count", "0"))
                    amount_inv_init = int(re.sub(r'[^0-9]', '', raw_count))
                
                current_total_init = wood_init + amount_inv_init

                to_donate = 0
                if donate_method == 1:
                    max_keep = int(storage * (float(cities_dict[cityId]["percentage"]) / 100))
                    to_donate = current_total_init - max_keep
                elif donate_method == 2:
                    (wood_prod, _, _) = getProductionPerHour(session, cityId)
                    to_donate = int((float(wood_prod) * float(cities_dict[cityId]["percentage"]) / 100) * (waiting_time / 60))
                elif donate_method == 3:
                    to_donate = int(cities_dict[cityId]["percentage"])

                if to_donate <= 0:
                    continue

                islandId = cities_dict[cityId]["island"]
                
                def execute_donation(d_type, d_amount):
                    if d_amount <= 0:
                        return 0
                    
                    # Baseline before this specific donation
                    inv_ref = getInventoryItem(session, 2201)
                    amount_ref = int(re.sub(r'[^0-9]', '', str(inv_ref.get("count", "0")))) if inv_ref else 0
                    
                    resp = session.post(params={
                        "islandId": islandId,
                        "type": d_type,
                        "action": "IslandScreen",
                        "function": "donate",
                        "donation": int(d_amount),
                        "backgroundView": "island",
                        "templateView": "resource",
                        "actionRequest": actionRequest,
                        "ajax": "1",
                    })
                    
                    # 1. Check for rejection feedback (e.g., building expanding)
                    json_resp = json.loads(resp, strict=False)
                    for r in json_resp:
                        if r[0] == "provideFeedback":
                            for fb in r[1]:
                                if fb.get("type") == 11: # Rejected
                                    return 0
                    
                    # 2. Verify wood reduction in inventory
                    # We wait a brief moment for the server to update the inventory count
                    wait(1)
                    inv_post = getInventoryItem(session, 2201)
                    amount_post = int(re.sub(r'[^0-9]', '', str(inv_post.get("count", "0")))) if inv_post else 0
                    
                    # Actual spent wood is the difference
                    spent = amount_ref - amount_post
                    
                    # If difference is 0 but no error was shown, it might be a small donation
                    # from city wood instead of inventory. We return d_amount as fallback.
                    if spent <= 0:
                        # Scan city wood to be sure
                        html_city = session.get(city_url + cityId)
                        wood_city_post = int(getCity(html_city)["availableResources"][0])
                        spent = wood_init - wood_city_post
                    
                    return max(0, spent) if spent > 0 else int(d_amount)

                city_total = 0
                if donation_type == "both":
                    half = to_donate // 2
                    city_total += execute_donation("resource", half + (to_donate % 2))
                    wait(2, maxrandom=4)
                    city_total += execute_donation("tradegood", half)
                else:
                    city_total += execute_donation(donation_type, to_donate)

                if city_total > 0:
                    total_general_donated += city_total
                    session.setStatus(f"Donated: {city_total} | Total: {total_general_donated} @{getDateTime()}")
                
                wait(2, maxrandom=5)
            except Exception:
                continue

        session.setStatus(checked_status(waiting_time, total_general_donated))
        wait(waiting_time * 60)


def checked_status(waiting_time, total_donated):
    return "Every {} min, last check {} | Total donated: {}".format(
        waiting_time, time.strftime("%H:%M"), total_donated
    )


@configurator
def donationBot(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    banner()
    (cities_ids, cities) = getIdsOfCities(session)
    cities_dict = {}
    initials = [material_name[0] for material_name in materials_names]
    print(
        "Enter how often you want to donate in minutes. (min = 1, default = 1 day)"
    )
    waiting_time = read(min=1, digit=True, default=1 * 24 * 60)
    print(
        """Which donation method would you like to use to donate automatically? (default = 1)
(1) Donate exceeding percentage of your storage capacity
(2) Donate a percentage of production
(3) Donate specific amount
    """
    )
    donate_method = read(min=1, max=3, digit=True, default=1)

    print(
        """Do you wish to apply the same donation configuration to all cities? (default = 1)
(1) Apply same configuration to all cities
(2) Define configuration separately for each city
    """
    )
    apply_to_all = read(min=1, max=2, digit=True, default=1) == 1

    # Get donation configuration
    if apply_to_all:
        # Ask for configuration once
        donation_type, percentage = _get_donation_config(cities, donate_method, cities_ids[0])
        # Apply to all cities
        for cityId in cities_ids:
            cities_dict[cityId] = {
                "donation_type": donation_type,
                "percentage": percentage,
            }
    else:
        # Ask for each city separately
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
                )
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
    return {"session": session, "cities_ids": cities_ids, "cities_dict": cities_dict, "waiting_time": waiting_time, "donate_method": donate_method}

