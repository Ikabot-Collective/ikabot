#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import math
import re
import traceback
from decimal import *

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import banner, enter
from ikabot.helpers.market import *
from ikabot.helpers.naval import getTotalShips
from ikabot.helpers.pedirInfo import getIdsOfCities, read
from ikabot.helpers.planRoutes import waitForArrival
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.resources import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import addThousandSeparator, getDateTime
from ikabot.helpers.pedirInfo import getShipCapacity



def chooseResource(session, city):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    """
    print("Which resource do you want to buy?")
    for index, material_name in enumerate(materials_names):
        print("({:d}) {}".format(index + 1, material_name))
    choise = read(min=1, max=5)
    resource = choise - 1
    if resource == 0:
        resource = "resource"
    data = {
        "cityId": city["id"],
        "position": city["pos"],
        "view": "branchOffice",
        "activeTab": "bargain",
        "type": 444,
        "searchResource": resource,
        "range": city["rango"],
        "backgroundView": "city",
        "currentCityId": city["id"],
        "templateView": "branchOffice",
        "currentTab": "bargain",
        "actionRequest": actionRequest,
        "ajax": 1,
    }
    # this will set the chosen resource in the store
    session.post(params=data)
    resource = choise - 1
    # return the chosen resource
    return resource


def getOffers(session, city):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    Returns
    -------
    offers : list[dict]
    """
    html = getMarketHtml(session, city)
    hits = re.findall(
        r'short_text80">(.*?) <br/>\((.*?)\)\s*</td>\s*<td>(\d+)</td>\s*<td>([\d,\s]+)(?:<div class="tooltip">.*?)?</td>\s*<td><img src="([^"]+\.png)"[\s\S]*?white-space:nowrap;">(\d+)\s*[\s\S]*?href="\?view=takeOffer&destinationCityId=(\d+)&oldView=branchOffice&activeTab=bargain&cityId=(\d+)&position=(\d+)&type=(\d+)&resource=(\w+)"',
        html,
        re.DOTALL
    )

    # Clean up the hits by stripping whitespace from each captured string
    cleaned_hits = []
    for hit in hits:
        cleaned_hit = tuple(item.strip() for item in hit)  # Strip whitespace from each item
        cleaned_hits.append(cleaned_hit)
    hits = cleaned_hits
        
    offers = []
    for hit in hits:
        offer = {
            "ciudadDestino": hit[0],
            "jugadorAComprar": hit[1],
            "bienesXminuto": int(hit[2]),
            "amountAvailable": int(
                hit[3].replace(",", "").replace(".", "").replace("<", "").replace(" ", "")
            ),
            "tipo": hit[4],
            "precio": int(hit[5]),
            "destinationCityId": hit[6],
            "cityId": hit[7],
            "position": hit[8],
            "type": hit[9],
            "resource": hit[10],
        }

        # Parse CDN Images to material type
        if offer["tipo"] == "//gf2.geo.gfsrv.net/cdn19/c3527b2f694fb882563c04df6d8972.png":
            offer["tipo"] = "wood"
        elif (
            offer["tipo"] == "//gf1.geo.gfsrv.net/cdnc6/94ddfda045a8f5ced3397d791fd064.png"
        ):
            offer["tipo"] = "wine"
        elif (
            offer["tipo"] == "//gf3.geo.gfsrv.net/cdnbf/fc258b990c1a2a36c5aeb9872fc08a.png"
        ):
            offer["tipo"] = "marble"
        elif (
            offer["tipo"] == "//gf2.geo.gfsrv.net/cdn1e/417b4059940b2ae2680c070a197d8c.png"
        ):
            offer["tipo"] = "glass"
        elif (
            offer["tipo"] == "//gf1.geo.gfsrv.net/cdn9b/5578a7dfa3e98124439cca4a387a61.png"
        ):
            offer["tipo"] = "sulfur"
        else:
            continue

        offers.append(offer)
    return offers


def calculateCost(offers, total_amount_to_buy):
    """
    Parameters
    ----------
    offers : list[dict]
    total_amount_to_buy : int
    Returns
    -------
    total_cost : int
    """
    total_cost = 0
    for offer in offers:
        if total_amount_to_buy == 0:
            break
        buy_amount = min(offer["amountAvailable"], total_amount_to_buy)
        total_amount_to_buy -= buy_amount
        total_cost += buy_amount * offer["precio"]
    return total_cost


def chooseCommertialCity(commercial_cities):
    """
    Parameters
    ----------
    commercial_cities : list[dict]

    Returns
    -------
    commercial_city : dict
    """
    print("From which city do you want to buy resources?\n")
    for i, city in enumerate(commercial_cities):
        print("({:d}) {}".format(i + 1, city["name"]))
    selected_city_index = read(min=1, max=len(commercial_cities))
    return commercial_cities[selected_city_index - 1]


def buyResources(session, event, stdin_fd, predetermined_input):
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

        # get all the cities with a store
        commercial_cities = getCommercialCities(session)
        if len(commercial_cities) == 0:
            print("There is no store build")
            enter()
            event.set()
            return

        # choose which city to buy from
        if len(commercial_cities) == 1:
            city = commercial_cities[0]
        else:
            city = chooseCommertialCity(commercial_cities)
            banner()

        # choose resource to buy
        resource = chooseResource(session, city)
        banner()

        # get all the offers of the chosen resource from the chosen city
        offers = getOffers(session, city)
        if len(offers) == 0:
            print("There are no offers available.")
            enter()
            event.set()
            return

        # display offers to the user
        total_price = 0
        total_amount = 0
        for offer in offers:
            amount = offer["amountAvailable"]
            price = offer["precio"]
            cost = amount * price
            print("amount:{}".format(addThousandSeparator(amount)))
            print("price :{:d}".format(price))
            print("cost  :{}".format(addThousandSeparator(cost)))
            print("")
            total_price += cost
            total_amount += amount

        # ask how much to buy
        print(
            "Total amount available to purchase: {}, for {}".format(
                addThousandSeparator(total_amount), addThousandSeparator(total_price)
            )
        )
        available = city["freeSpaceForResources"][resource]
        if available < total_amount:
            print(
                "You just can buy {} due to storing capacity".format(
                    addThousandSeparator(available)
                )
            )
            total_amount = available
        print("")
        amount_to_buy = read(
            msg="How much do you want to buy?: ", min=0, max=total_amount
        )
        if amount_to_buy == 0:
            event.set()
            return

        # calculate the total cost
        (gold, __) = getGold(session, city)
        total_cost = calculateCost(offers, amount_to_buy)

        print(
            "\nCurrent gold: {}.\nTotal cost  : {}.\nFinal gold  : {}.".format(
                addThousandSeparator(gold),
                addThousandSeparator(total_cost),
                addThousandSeparator(gold - total_cost),
            )
        )
        print("Proceed? [Y/n]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            event.set()
            return

        print("It will be purchased {}".format(addThousandSeparator(amount_to_buy)))
        enter()
    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()

    info = "\nI will buy {} from {} to {}\n".format(
        addThousandSeparator(amount_to_buy), materials_names[resource], city["cityName"]
    )
    setInfoSignal(session, info)
    try:
        do_it(session, city, offers, amount_to_buy)
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def buy(session, city, offer, amount_to_buy, ships_available, ship_capacity):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    offer : dict
    amount_to_buy : int
    """
    ships = int(math.ceil((Decimal(amount_to_buy) / Decimal(ship_capacity))))
    data_dict = {
        "action": "transportOperations",
        "function": "buyGoodsAtAnotherBranchOffice",
        "cityId": offer["cityId"],
        "destinationCityId": offer["destinationCityId"],
        "oldView": "branchOffice",
        "position": city["pos"],
        "avatar2Name": offer["jugadorAComprar"],
        "city2Name": offer["ciudadDestino"],
        "type": int(offer["type"]),
        "activeTab": "bargain",
        "transportDisplayPrice": 0,
        "premiumTransporter": 0,
        "normalTransportersMax": ships_available,
        "capacity": 5,
        "max_capacity": 5,
        "jetPropulsion": 0,
        "transporters": ships,
        "backgroundView": "city",
        "currentCityId": offer["cityId"],
        "templateView": "takeOffer",
        "currentTab": "bargain",
        "actionRequest": actionRequest,
        "ajax": 1,
    }
    url = "view=takeOffer&destinationCityId={}&oldView=branchOffice&activeTab=bargain&cityId={}&position={}&type={}&resource={}&backgroundView=city&currentCityId={}&templateView=branchOffice&actionRequest={}&ajax=1".format(
        offer["destinationCityId"],
        offer["cityId"],
        offer["position"],
        offer["type"],
        offer["resource"],
        offer["cityId"],
        actionRequest,
    )
    data = session.post(url)
    html = json.loads(data, strict=False)[1][1][1]
    hits = re.findall(r'"tradegood(\d)Price"\s*value="(\d+)', html)
    for hit in hits:
        data_dict["tradegood{}Price".format(hit[0])] = int(hit[1])
        data_dict["cargo_tradegood{}".format(hit[0])] = 0
    hit = re.search(r'"resourcePrice"\s*value="(\d+)', html)
    if hit:
        data_dict["resourcePrice"] = int(hit.group(1))
        data_dict["cargo_resource"] = 0
    resource = offer["resource"]
    if resource == "resource":
        data_dict["cargo_resource"] = amount_to_buy
    else:
        data_dict["cargo_tradegood{}".format(resource)] = amount_to_buy
    session.post(params=data_dict)
    msg = "I buy {} to {} from {}".format(
        addThousandSeparator(amount_to_buy),
        offer["ciudadDestino"],
        offer["jugadorAComprar"],
    )
    sendToBotDebug(session, msg, debugON_buyResources)
    resource_name = offer['tipo']
    session.setStatus(
        f"Bought {addThousandSeparator(amount_to_buy)} {resource_name} for {offer['precio']} gold from {offer['ciudadDestino']} ({offer['jugadorAComprar']}) ---> {city['name']} | {getDateTime()}"
    )


def do_it(session, city, offers, amount_to_buy):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    offers : list[dict]
    amount_to_buy : int
    """
    ship_capacity, freighter_capacity = getShipCapacity(session)
    while True:
        for offer in offers:
            if amount_to_buy == 0:
                return
            if offer["amountAvailable"] == 0:
                continue
            ships_available = waitForArrival(session)
            storageCapacity = ships_available * ship_capacity
            buy_amount = min(amount_to_buy, storageCapacity, offer["amountAvailable"])

            amount_to_buy -= buy_amount
            offer["amountAvailable"] -= buy_amount
            buy(session, city, offer, buy_amount, ships_available, ship_capacity)
            # start from the beginning again, so that we always buy from the cheapest offers fisrt
            break
