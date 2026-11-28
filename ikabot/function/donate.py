from ikabot.helpers.decorators import configurator, task
#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re

from ikabot.config import *
from ikabot.helpers.botComm import sendToBot
from ikabot.helpers.getJson import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.resources import *
from ikabot.helpers.taskConfig import asInt, getCityById, requireOwnCity
from ikabot.helpers.varios import *

TYPES = {"resource": "resource", "wood": "resource", "sawmill": "resource", "saw mill": "resource",
         "tradegood": "tradegood", "luxury": "tradegood", "mine": "tradegood"}


def _wood_counts(html):
    """(needed, donated, on_inventory) of a mine's donation page"""
    matches = re.findall(r'<li class="wood">(.*?)</li>', html)
    # if there are 3 matches, the third one is the wood on inventory
    if len(matches) == 3:
        needed, donated, on_inventory = matches
    else:
        needed, donated = matches[:2]
        on_inventory = "0"
    # remove all characters that are not numbers
    return tuple(int(re.sub(r'[^0-9]', '', value) or 0) for value in (needed, donated, on_inventory))


def donation_info(session, city):
    """The levels, the upgrades and the donations of the saw mill and the luxury good mine of
    the city's island
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict

    Returns
    -------
    info : dict
        "resource" and "tradegood", each {"name", "level", "upgrading", "endUpgradeTime",
        "needed", "donated"}, plus "islandId" and "woodOnInventory"
    """
    islandId = city["islandId"]
    island = getIsland(session.get(island_url + islandId))
    island_type = island["tipo"]

    # get resource information
    url = "view=resource&type=resource&islandId={0}&backgroundView=island&currentIslandId={0}&actionRequest={1}&ajax=1".format(
        islandId, actionRequest
    )
    resp = json.loads(session.post(url), strict=False)
    background = resp[0][1]["backgroundData"]
    needed, donated, _ = _wood_counts(resp[1][1][1])
    info = {
        "islandId": islandId,
        "resource": {
            "name": tradegoods_names[0],
            "level": background["resourceLevel"],
            "endUpgradeTime": int(background["resourceEndUpgradeTime"]),
            "needed": needed,
            "donated": donated,
        },
    }

    # get tradegood information
    url = "view=tradegood&type={0}&islandId={1}&backgroundView=island&currentIslandId={1}&actionRequest={2}&ajax=1".format(
        island_type, islandId, actionRequest
    )
    resp = json.loads(session.post(url), strict=False)
    needed, donated, on_inventory = _wood_counts(resp[1][1][1])
    info["tradegood"] = {
        "name": tradegoods_names[int(island_type)],
        "level": background["tradegoodLevel"],
        "endUpgradeTime": int(background["tradegoodEndUpgradeTime"]),
        "needed": needed,
        "donated": donated,
    }
    info["woodOnInventory"] = on_inventory
    for kind in ("resource", "tradegood"):
        info[kind]["upgrading"] = info[kind]["endUpgradeTime"] > 0
    return info


def donation_amount(amount, wood_available):
    """A number, or "all" / "half" of the wood the city has"""
    if isinstance(amount, str) and amount.strip().lower() in ("all", "half"):
        return wood_available if amount.strip().lower() == "all" else wood_available // 2
    return amount


def rejection(response):
    """The text of the game's rejection (feedback type 11) in a response, or None"""
    try:
        data = json.loads(response, strict=False)
    except (TypeError, ValueError):
        return None
    for entry in data if isinstance(data, list) else []:
        if isinstance(entry, list) and len(entry) >= 2 and entry[0] == "provideFeedback":
            for item in entry[1] if isinstance(entry[1], list) else []:
                if isinstance(item, dict) and item.get("type") == 11:
                    return re.sub(r"<[^>]+>", " ", str(item.get("text", ""))).strip() or "rejected"
    return None


def prepare_donate(session, city_id=None, type=None, amount=None, show_results=False):
    """Checks the config of a donate task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int or str
        one of your cities; it donates to its island
    type : str
        "resource" (the saw mill) or "tradegood" (the luxury good mine)
    amount : int or str
        wood to donate, or "all" / "half" of what the city has when it donates
    show_results : bool
        the menu shows the result and waits for Enter; never from the CLI

    Returns
    -------
    config : dict
    """
    if city_id is None:
        raise ValueError("city_id is needed")
    city_id = requireOwnCity(session, city_id, "city_id")
    kind = TYPES.get(str(type).strip().lower()) if type is not None else None
    if kind is None:
        raise ValueError('type must be "resource" (the saw mill) or "tradegood" (the luxury good mine), got {!r}'.format(type))
    if amount is None:
        raise ValueError('amount is needed: a number, "all" or "half"')
    city = getCityById(session, city_id)
    wood = city["availableResources"][0]
    if isinstance(amount, str) and amount.strip().lower() in ("all", "half"):
        amount = amount.strip().lower()
        if donation_amount(amount, wood) < 1:
            raise ValueError("{} has no wood to donate".format(city["name"]))
    else:
        amount = asInt(amount, "amount", minimum=1)
        if amount > wood:
            raise ValueError("{} has {} wood, asked to donate {}".format(
                city["name"], addThousandSeparator(wood), addThousandSeparator(amount)))
    info = donation_info(session, city)
    if info[kind]["upgrading"]:
        raise ValueError("the {} of {} is being upgraded (ends in {}): donations are not possible now".format(
            info[kind]["name"], city["name"], daysHoursMinutes(info[kind]["endUpgradeTime"])))
    return {"city_id": city_id, "type": kind, "amount": amount}


@task("donate", prepare=prepare_donate)
def do_donate(session, city_id=None, type=None, amount=None, show_results=False):
    """Donates wood once to the saw mill or the luxury good mine of the city's island
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : str
    type : str
        "resource" or "tradegood"
    amount : int or str
        a number, "all" or "half"
    show_results : bool
    """
    city = getCityById(session, city_id)
    info = donation_info(session, city)
    name = info[type]["name"]
    wood = donation_amount(amount, city["availableResources"][0])
    problem = None
    if info[type]["upgrading"]:
        problem = "the {} is being upgraded".format(name)
    elif wood < 1:
        problem = "{} has no wood to donate".format(city["name"])
    else:
        wood = min(wood, city["availableResources"][0])
        # do the donation
        resp = session.post(
            params={
                "islandId": info["islandId"],
                "type": type,
                "action": "IslandScreen",
                "function": "donate",
                "donation": wood,
                "backgroundView": "island",
                "templateView": "resource",
                "actionRequest": actionRequest,
                "ajax": "1",
            }
        )
        problem = rejection(resp)

    if problem is None:
        msg = "Donated {} wood to the {} from {} @{}".format(addThousandSeparator(wood), name, city["name"], getDateTime())
    else:
        msg = "Nothing was donated to the {} from {}: {}".format(name, city["name"], problem)
        if not show_results:
            sendToBot(session, msg)
    session.setStatus(msg)
    if show_results:
        print("\nDonation successful." if problem is None else "\n" + msg)
        enter()


@configurator(blocking=True)
def donate(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    banner()

    city = chooseCity(session)
    banner()

    woodAvailable = city["availableResources"][0]
    info = donation_info(session, city)
    resource, tradegood = info["resource"], info["tradegood"]
    resource_name, tradegood_name = resource["name"], tradegood["name"]
    resourceUpgrading, tradegoodUpgrading = resource["upgrading"], tradegood["upgrading"]

    resourceUpgradeMsg = "(upgrading, ends in:{})".format(daysHoursMinutes(resource["endUpgradeTime"])) if resourceUpgrading else ""
    tradegoodUpgradeMsg = "(upgrading, ends in:{})".format(daysHoursMinutes(tradegood["endUpgradeTime"])) if tradegoodUpgrading else ""

    if resourceUpgrading and tradegoodUpgrading:
        print(
            "Both the {} (ends in:{}) and the {} (ends in:{}) are being upgraded rigth now.\n".format(
                resource_name,
                daysHoursMinutes(resource["endUpgradeTime"]),
                tradegood_name,
                daysHoursMinutes(tradegood["endUpgradeTime"]),
            )
        )
        enter()
        return None

    print("{} lv:{} {}".format(resource_name, resource["level"], resourceUpgradeMsg))
    print(
        "{} / {} ({}%)\n".format(
            addThousandSeparator(resource["donated"]),
            addThousandSeparator(resource["needed"]),
            addThousandSeparator(int((100 * resource["donated"]) / resource["needed"])) if resource["needed"] else 0,
        )
    )

    print("{} lv:{} {}".format(tradegood_name, tradegood["level"], tradegoodUpgradeMsg))
    print(
        "{} / {} ({}%)\n".format(
            addThousandSeparator(tradegood["donated"]),
            addThousandSeparator(tradegood["needed"]),
            addThousandSeparator(int((100 * tradegood["donated"]) / tradegood["needed"])) if tradegood["needed"] else 0,
        )
    )

    wood_on_inventory = info["woodOnInventory"]
    print("Wood available:{}\n".format(addThousandSeparator(woodAvailable)))
    print("Wood on inventory available:{}\n".format(addThousandSeparator(wood_on_inventory)))
    print("Total wood available for donation:{}\n".format(addThousandSeparator(woodAvailable + wood_on_inventory)))

    if resourceUpgrading is False and tradegoodUpgrading is False:
        msg = "Donate to {} (1) or {} (2)?:".format(
            resource_name, tradegood_name
        )
        donation_type = read(msg=msg, min=1, max=2)
        name = resource_name if donation_type == 1 else tradegood_name
        print("")
    else:
        if resourceUpgrading is False and tradegoodUpgrading is True:
            donation_type = 1
            name = resource_name
        else:
            donation_type = 2
            name = tradegood_name
        print("Donate to:{}\n".format(name))

    donation_type = "resource" if donation_type == 1 else "tradegood"

    amount = read(
        min=0,
        max=woodAvailable,
        default=0,
        additionalValues=["all", "half"],
        msg="Amount (number, all, half):",
    )
    if amount == "all":
        amount = woodAvailable
    elif amount == "half":
        amount = woodAvailable // 2
    elif amount == 0:
        return None
    print("Will donate {} to the {}?".format(addThousandSeparator(amount), name))
    print("\nProceed? [Y/n]")
    rta = read(values=["y", "Y", "n", "N", ""])
    if rta.lower() == "n":
        return None

    # the task donates while the menu waits and shows the result
    return {
        "session": session,
        "city_id": str(city["id"]),
        "type": donation_type,
        "amount": amount,
        "show_results": True,
    }
