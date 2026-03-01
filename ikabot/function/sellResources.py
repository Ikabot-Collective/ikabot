#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import math
import time
import traceback
from decimal import *

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import *
from ikabot.helpers.market import *
from ikabot.helpers.naval import getTotalShips
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.planRoutes import waitForArrival
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import addThousandSeparator, wait, getDateTime
from ikabot.helpers.pedirInfo import getShipCapacity


def chooseCommercialCity(commercial_cities):
    """
    Parameters
    ----------
    commercial_cities : list[dict]

    Returns
    -------
    commercial_city : dict
    """
    print("In which city do you want to sell resources?\n")
    for i, city in enumerate(commercial_cities):
        print("({:d}) {}".format(i + 1, city["name"]))
    ind = read(min=1, max=len(commercial_cities))
    return commercial_cities[ind - 1]


def getMarketInfo(session, city):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict

    Returns
    -------
    response : dict
    """
    params = {
        "view": "branchOfficeOwnOffers",
        "activeTab": "tab_branchOfficeOwnOffers",
        "cityId": city["id"],
        "position": city["pos"],
        "backgroundView": "city",
        "currentCityId": city["id"],
        "templateView": "branchOfficeOwnOffers",
        "currentTab": "tab_branchOfficeOwnOffers",
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    resp = session.post(params=params, noIndex=True)
    return json.loads(resp, strict=False)[1][1][1]


def getOffers(session, my_market_city, resource_type):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    my_market_city : dict
    resource_type : int

    Returns
    -------
    offers : list
    """
    if resource_type == 0:
        resource_type = "resource"
    else:
        resource_type = str(resource_type)
    data = {
        "cityId": my_market_city["id"],
        "position": my_market_city["pos"],
        "view": "branchOffice",
        "activeTab": "bargain",
        "type": "333",
        "searchResource": resource_type,
        "range": my_market_city["rango"],
        "backgroundView": "city",
        "currentCityId": my_market_city["id"],
        "templateView": "branchOffice",
        "currentTab": "bargain",
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    resp = session.post(params=data)
    html = json.loads(resp, strict=False)[1][1][1]

    offers_found = re.findall(
        r'<td class="short_text80">(.*?)<br/>\((.*?)\)[\s\S]*?<div class="tooltip">([\d,]+)</div>[\s\S]*?<td style="white-space:nowrap;">(\d+)[\s\S]*?<td>(\d+)</td>[\s\S]*?href="\?view=takeOffer&destinationCityId=(\d+)',
        html
    )
    # Process the found offers, removing commas and converting to integers
    processed_offers = []
    for city_name, user_name, amount, price, dist, dest_id in offers_found:
        clean_amount = int(amount.replace(',', ''))
        processed_offers.append((city_name.strip(), user_name.strip(), clean_amount, int(price), int(dist), int(dest_id)))
    
    return processed_offers


def sellToOffers(session, city_to_buy_from, resource_type, event):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_to_buy_from : dict
    resource_type : int
    event : multiprocessing.Event
    """
    banner()

    offers = getOffers(session, city_to_buy_from, resource_type)

    if len(offers) == 0:
        print("No offers available.")
        enter()
        event.set()
        return

    print("Which offers do you want to sell to?\n")

    chosen_offers = []
    total_amount = 0
    profit = 0
    for offer in offers:
        cityname, username, amount, price, dist, destination_city_id = offer
        cityname = cityname.strip()
        amount = int(amount)
        price = int(price)
        msg = "{} ({}): {} at {:d} each ({} in total) [Y/n]".format(
            cityname,
            username,
            addThousandSeparator(amount),
            price,
            addThousandSeparator(price * amount),
        )
        rta = read(msg=msg, values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            continue
        chosen_offers.append(offer)
        total_amount += amount
        profit += amount * price

    if len(chosen_offers) == 0:
        event.set()
        return

    available = city_to_buy_from["availableResources"][resource_type]
    amount_to_sell = min(available, total_amount)

    banner()
    print(
        "\nHow much do you want to sell? [max = {}]".format(
            addThousandSeparator(amount_to_sell)
        )
    )
    amount_to_sell = read(min=0, max=amount_to_sell)
    if amount_to_sell == 0:
        event.set()
        return

    left_to_sell = amount_to_sell
    profit = 0
    for offer in chosen_offers:
        cityname, username, amount, price, dist, destination_city_id = offer
        cityname = cityname.strip()
        amount = int(amount)
        price = int(price)
        sell = min(amount, left_to_sell)
        left_to_sell -= sell
        profit += sell * price
    print(
        "\nSell {} of {} for a total of {}? [Y/n]".format(
            addThousandSeparator(amount_to_sell),
            materials_names[resource_type],
            addThousandSeparator(profit),
        )
    )
    rta = read(values=["y", "Y", "n", "N", ""])
    if rta.lower() == "n":
        event.set()
        return

    set_child_mode(session)
    event.set()

    info = "\nI sell {} of {} in {}\n".format(
        addThousandSeparator(amount_to_sell),
        materials_names[resource_type],
        city_to_buy_from["name"],
    )
    setInfoSignal(session, info)
    try:
        do_it1(session, amount_to_sell, chosen_offers, resource_type, city_to_buy_from)
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def createOffer(session, my_offering_market_city, resource_type, event):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    my_offering_market_city : dict
    resource_type : int
    event : multiprocessing.Event
    """
    banner()

    html = getMarketInfo(session, my_offering_market_city)
    sell_market_capacity = storageCapacityOfMarket(html)
    total_available_amount_of_resource = my_offering_market_city["availableResources"][
        resource_type
    ]

    print(
        "How much do you want to sell? [max = {}]".format(
            addThousandSeparator(total_available_amount_of_resource)
        )
    )
    amount_to_sell = read(min=0, max=total_available_amount_of_resource)
    if amount_to_sell == 0:
        event.set()
        return

    price_max, price_min = re.findall(r"\'upper\': (\d+),\s*\'lower\': (\d+)", html)[
        resource_type
    ]
    price_max = int(price_max)
    price_min = int(price_min)
    print("\nAt what price? [min = {:d}, max = {:d}]".format(price_min, price_max))
    price = read(min=price_min, max=price_max)

    print(
        "\nI will sell {} of {} at {}: {}".format(
            addThousandSeparator(amount_to_sell),
            materials_names[resource_type],
            addThousandSeparator(price),
            addThousandSeparator(price * amount_to_sell),
        )
    )
    print("\nProceed? [Y/n]")
    rta = read(values=["y", "Y", "n", "N", ""])
    if rta.lower() == "n":
        event.set()
        return

    set_child_mode(session)
    event.set()

    info = "\nI sell {} of {} in {}\n".format(
        addThousandSeparator(amount_to_sell),
        materials_names[resource_type],
        my_offering_market_city["name"],
    )
    setInfoSignal(session, info)
    try:
        do_it2(
            session,
            amount_to_sell,
            price,
            resource_type,
            sell_market_capacity,
            my_offering_market_city,
        )
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def sellResources(session, event, stdin_fd, predetermined_input):
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

        commercial_cities = getCommercialCities(session)
        if len(commercial_cities) == 0:
            print("There is no store built")
            enter()
            event.set()
            return

        if len(commercial_cities) == 1:
            city = commercial_cities[0]
        else:
            city = chooseCommercialCity(commercial_cities)
            banner()

        print("What resource do you want to sell?")
        for index, material_name in enumerate(materials_names):
            print("({:d}) {}".format(index + 1, material_name))
        selected_material = read(min=1, max=len(materials_names))
        resource = selected_material - 1
        banner()

        print(
            
            "Do you want to sell to existing offers (1) or do you want to make your own offer (2)?"
            
        )
        selected = read(min=1, max=2)
        [sellToOffers, createOffer][selected - 1](session, city, resource, event)
    except KeyboardInterrupt:
        event.set()
        return


def do_it1(session, left_to_sell, offers, resource_type, city_to_buy_from):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    left_to_sell : int
    offers : list[dict]
    resource_type : int
    city_to_buy_from : dict
    """
    ship_capacity, freighter_capacity = getShipCapacity(session)
    for offer in offers:
        cityname, username, amount, precio, dist, destination_city_id = offer
        cityname = cityname.strip()
        amount_to_buy = int(amount)
        while True:
            amount_to_sell = min(amount_to_buy, left_to_sell)
            ships_available = waitForArrival(session)
            ships_needed = math.ceil((Decimal(amount_to_sell) / Decimal(ship_capacity)))
            ships_used = min(ships_available, ships_needed)
            if ships_needed > ships_used:
                amount_to_sell = ships_used * ship_capacity
            left_to_sell -= amount_to_sell
            amount_to_buy -= amount_to_sell

            data = {
                "action": "transportOperations",
                "function": "sellGoodsAtAnotherBranchOffice",
                "cityId": city_to_buy_from["id"],
                "destinationCityId": destination_city_id,
                "oldView": "branchOffice",
                "position": city_to_buy_from["pos"],
                "avatar2Name": username,
                "city2Name": cityname,
                "type": "333",
                "activeTab": "bargain",
                "transportDisplayPrice": "0",
                "premiumTransporter": "0",
                "normalTransportersMax": ships_available,
                "capacity": "5",
                "max_capacity": "5",
                "jetPropulsion": "0",
                "transporters": str(ships_used),
                "backgroundView": "city",
                "currentCityId": city_to_buy_from["id"],
                "templateView": "takeOffer",
                "currentTab": "bargain",
                "actionRequest": actionRequest,
                "ajax": "1",
            }
            if resource_type == 0:
                data["cargo_resource"] = amount_to_sell
                data["resourcePrice"] = precio
            else:
                data["tradegood{:d}Price".format(resource_type)] = precio
                data["cargo_tradegood{:d}".format(resource_type)] = amount_to_sell

            session.get(city_url + city_to_buy_from["id"], noIndex=True)
            session.post(params=data)
            
            resource_name = materials_names[resource_type]
            session.setStatus(
                f"Sold {addThousandSeparator(amount_to_sell)} {resource_name} for {precio} gold to {cityname} ({username}) <--- {city_to_buy_from['name']} | {getDateTime()}"
            )

            if left_to_sell == 0:
                return
            if amount_to_buy == 0:
                break


def do_it2(session, amount_to_sell, price, resource_type, sell_market_capacity, city):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    amount_to_sell : int
    price : int
    resource_type : int
    sell_market_capacity : int
    city : dict
    """
    initial_amount_to_sell = amount_to_sell
    html = getMarketInfo(session, city)
    previous_on_sell = onSellInMarket(html)[resource_type]
    while True:
        html = getMarketInfo(session, city)
        currently_on_sell = onSellInMarket(html)[resource_type]
        # if there is space in the store
        if currently_on_sell < storageCapacityOfMarket(html):
            # add our new offer to the free space
            free_space = sell_market_capacity - currently_on_sell
            offer = min(amount_to_sell, free_space)
            amount_to_sell -= offer
            new_offer = currently_on_sell + offer

            payloadPost = {
                "cityId": city["id"],
                "position": city["pos"],
                "action": "CityScreen",
                "function": "updateOffers",
                "resourceTradeType": "444",
                "resource": "0",
                "resourcePrice": "10",
                "tradegood1TradeType": "444",
                "tradegood1": "0",
                "tradegood1Price": "11",
                "tradegood2TradeType": "444",
                "tradegood2": "0",
                "tradegood2Price": "12",
                "tradegood3TradeType": "444",
                "tradegood3": "0",
                "tradegood3Price": "17",
                "tradegood4TradeType": "444",
                "tradegood4": "0",
                "tradegood4Price": "5",
                "backgroundView": "city",
                "currentCityId": city["id"],
                "templateView": "branchOfficeOwnOffers",
                "currentTab": "tab_branchOfficeOwnOffers",
                "actionRequest": actionRequest,
                "ajax": "1",
            }
            if resource_type == 0:
                payloadPost["resource"] = new_offer
                payloadPost["resourcePrice"] = price
            else:
                payloadPost["tradegood{:d}".format(resource_type)] = new_offer
                payloadPost["tradegood{:d}Price".format(resource_type)] = price
            session.post(params=payloadPost)

            # if we don't have any more to add to the offer, leave the loop
            if amount_to_sell == 0:
                break

        # sleep for 2 hours
        wait(60 * 60 * 2)

    # wait until the last of our offer is actualy bought, and let the user know
    while True:
        html = getMarketInfo(session, city)
        currently_on_sell = onSellInMarket(html)[resource_type]
        if currently_on_sell <= previous_on_sell:
            msg = "{} of {} was sold at {:d}".format(
                addThousandSeparator(initial_amount_to_sell),
                materials_names[resource_type],
                price,
            )
            sendToBot(session, msg)
            return

        # sleep for 2 hours
        wait(60 * 60 * 2)
