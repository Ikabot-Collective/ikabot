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
from ikabot.helpers.decorators import configurator, task
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import addThousandSeparator, wait, getDateTime
from ikabot.helpers.pedirInfo import getShipCapacity
from ikabot.helpers.taskConfig import asId, asInt, getCityById, requireOwnCity
from ikabot.function.sendResources import RESOURCE_KEYS
from ikabot.function.buyResources import market_city, rejection, resource_index

MODES = ("sell_to_offers", "create_offer")
# the trade type of each good in the trading post's own offers
SELL = "444"
BUY = "333"
OFFER_KEYS = ("resource", "tradegood1", "tradegood2", "tradegood3", "tradegood4")


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
    """The offers to buy ``resource_type`` in range of the trading post
    Parameters
    ----------
    session : ikabot.web.session.Session
    my_market_city : dict
    resource_type : int

    Returns
    -------
    offers : list
        (city name, player name, amount, price, distance, city id) for each offer
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

    processed_offers = []
    for row in re.findall(r'<tr[^>]*>([\s\S]*?)</tr>', html):
        city_match   = re.search(r'<td class="short_text80">(.*?)<br/>\((.*?)\)', row)
        amount_match = re.search(r'<div class="tooltip">([\d,.]+)</div>', row)
        price_match  = re.search(r'<td style="white-space:nowrap;">(\d+)', row)
        dist_match   = re.search(r'<td>(\d+)</td>', row)
        dest_match   = re.search(r'href="\?view=takeOffer&destinationCityId=(\d+)', row)

        if not all([city_match, amount_match, price_match, dist_match, dest_match]):
            continue

        raw_amount = amount_match.group(1).replace('.', '').replace(',', '')
        processed_offers.append((
            city_match.group(1).strip(),
            city_match.group(2).strip(),
            int(raw_amount),
            int(price_match.group(1)),
            int(dist_match.group(1)),
            int(dest_match.group(1)),
        ))

    return processed_offers


def sellToOffers(session, city_to_buy_from, resource_type):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_to_buy_from : dict
    resource_type : int
    """
    banner()

    offers = getOffers(session, city_to_buy_from, resource_type)

    if len(offers) == 0:
        print("No offers available.")
        enter()
        return None

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
        return None

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
        return None

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
        return None

    # the task reads the offers again before each sale: the config keeps the offers the
    # user chose (their cities) and never less than the lowest price among them
    return {
        "session": session,
        "mode": "sell_to_offers",
        "city_id": str(city_to_buy_from["id"]),
        "resource": RESOURCE_KEYS[resource_type],
        "amount": amount_to_sell,
        "min_price": min(int(offer[3]) for offer in chosen_offers),
        "buyers": [str(offer[5]) for offer in chosen_offers],
    }


def createOffer(session, my_offering_market_city, resource_type):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    my_offering_market_city : dict
    resource_type : int
    """
    banner()

    html = getMarketInfo(session, my_offering_market_city)
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
        return None

    price_min, price_max = price_limits(html, resource_type)
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
        return None

    # the task reads the trading post's capacity when it adds to the offer
    return {
        "session": session,
        "mode": "create_offer",
        "city_id": str(my_offering_market_city["id"]),
        "resource": RESOURCE_KEYS[resource_type],
        "amount": amount_to_sell,
        "price": price,
    }


def price_limits(html, resource):
    """The lowest and highest price the trading post accepts for ``resource``"""
    price_max, price_min = re.findall(r"\'upper\': (\d+),\s*\'lower\': (\d+)", html)[resource]
    return int(price_min), int(price_max)


def own_offers(html):
    """The trading post's own offers, one per good, as the game shows them
    Parameters
    ----------
    html : str
        the trading post's own offers page (getMarketInfo)

    Returns
    -------
    offers : list[dict]
        {"type": SELL or BUY, "amount": int, "price": int} for wood, wine, marble, crystal and sulfur
    """
    offers = []
    for key in OFFER_KEYS:
        select = re.search(r'<select[^>]*name="{}TradeType"[\s\S]*?</select>'.format(key), html)
        trade_type = re.search(r'<option\s+value="(\d+)"[^>]*\bselected', select.group(0)) if select else None
        amount = re.search(r'name="{0}"\s*id="{0}"\s*value="(\d+)"'.format(key), html)
        price = re.search(r'name="{0}Price"\s*id="{0}Price"[^>]*?value="(\d+)"'.format(key), html)
        if not (trade_type and amount and price):
            raise ValueError("could not read the offers of the trading post")
        offers.append({"type": trade_type.group(1), "amount": int(amount.group(1)), "price": int(price.group(1))})
    return offers


def offers_payload(city, offers, resource, amount, price):
    """The request that sets the trading post's offers: the current ones, with ``resource``
    offered for sale (``amount`` at ``price``). The game sets the five goods at once, so
    the others must be sent as they are or they would be removed
    Parameters
    ----------
    city : dict
    offers : list[dict]
        as returned by own_offers
    resource : int
    amount : int
    price : int

    Returns
    -------
    payload : dict
    """
    payload = {
        "cityId": city["id"],
        "position": city["pos"],
        "action": "CityScreen",
        "function": "updateOffers",
        "backgroundView": "city",
        "currentCityId": city["id"],
        "templateView": "branchOfficeOwnOffers",
        "currentTab": "tab_branchOfficeOwnOffers",
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    for i, key in enumerate(OFFER_KEYS):
        offer = {"type": SELL, "amount": amount, "price": price} if i == resource else offers[i]
        payload[key + "TradeType"] = offer["type"]
        payload[key] = offer["amount"]
        payload[key + "Price"] = offer["price"]
    return payload


def matching_buy_offers(offers, min_price=None, buyers=None):
    """The offers that can be sold to, the best paid first
    Parameters
    ----------
    offers : list[tuple]
        as returned by getOffers
    min_price : int or None
    buyers : list[str] or None
        only the offers of these cities

    Returns
    -------
    offers : list[tuple]
    """
    return sorted(
        (
            offer for offer in offers
            if offer[2] > 0
            and (min_price is None or offer[3] >= min_price)
            and (buyers is None or str(offer[5]) in buyers)
        ),
        key=lambda o: -o[3],
    )


def next_sale(offers, remaining, ship_space, available, min_price=None, buyers=None):
    """The offer to sell to next and how much: the best paid one that matches, as much as
    the ships carry and the city has
    Parameters
    ----------
    offers : list[tuple]
        the offers on the market now
    remaining : int
        what is left to sell
    ship_space : int
        what the available ships carry
    available : int
        what the city has of the resource

    Returns
    -------
    (offer, amount) : tuple
        (None, 0) when no offer matches; amount is 0 when the city has none left
    """
    candidates = matching_buy_offers(offers, min_price, buyers)
    if not candidates:
        return None, 0
    offer = candidates[0]
    return offer, max(0, min(remaining, offer[2], ship_space, available))


def config_from_saved(mode, amount_to_sell, offers, resource_type, city_to_buy_from, city):
    """An older menu saved the trading post's city, and the offers it showed"""
    if mode == "sell_to_offers" and city_to_buy_from is not None:
        return {
            "city_id": city_to_buy_from["id"], "resource": resource_type, "amount": amount_to_sell,
            "min_price": min(int(o[3]) for o in offers) if offers else None,
            "buyers": [str(o[5]) for o in offers] if offers else None,
        }
    if mode == "create_offer" and city is not None:
        return {"city_id": city["id"], "resource": resource_type, "amount": amount_to_sell}
    return {}


def offers_text(resource, min_price, buyers):
    text = "offers to buy {}".format(RESOURCE_KEYS[resource])
    if min_price is not None:
        text += " at {} gold or more".format(min_price)
    if buyers is not None:
        text += " from the cities {}".format(", ".join(buyers))
    return text


def prepare_sellResources(session, mode=None, city_id=None, resource=None, amount=None, min_price=None, buyers=None,
                          price=None, amount_to_sell=None, offers=None, resource_type=None, city_to_buy_from=None,
                          sell_market_capacity=None, city=None):
    """Checks the config of a sellResources task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    mode : str
        "sell_to_offers": sell to other players' offers to buy; "create_offer": offer it for
        sale in your trading post
    city_id : int or str
        one of your cities with a trading post; the resource leaves from it
    resource : str or int
        wood, wine, marble, crystal or sulfur (or 0 to 4)
    amount : int
    min_price : int
        sell_to_offers: lowest price per unit to accept; null accepts any
    buyers : list
        sell_to_offers: only the offers of these city ids; null sells to anyone in range
    price : int
        create_offer: price per unit, within what the trading post accepts
    amount_to_sell, offers, resource_type, city_to_buy_from, sell_market_capacity, city :
        saved by older menus

    Returns
    -------
    config : dict
    """
    mode = str(mode).strip().lower() if mode is not None else None
    if mode not in MODES:
        raise ValueError('mode must be "sell_to_offers" (sell to offers to buy) or "create_offer" (offer it in your '
                         'trading post), got {!r}'.format(mode))
    saved = config_from_saved(mode, amount_to_sell, offers, resource_type, city_to_buy_from, city)
    if saved:
        city_id, resource, amount = saved["city_id"], saved["resource"], saved["amount"]
        if mode == "sell_to_offers":
            min_price = saved["min_price"] if min_price is None else min_price
            buyers = saved["buyers"] if buyers is None else buyers
    for key, value in (("city_id", city_id), ("resource", resource), ("amount", amount)):
        if value is None:
            raise ValueError("{} is needed".format(key))
    city_id = requireOwnCity(session, city_id, "city_id")
    resource = resource_index(resource)
    amount = asInt(amount, "amount", minimum=1)
    name = RESOURCE_KEYS[resource]
    market = market_city(session, city_id)
    have = market["availableResources"][resource]
    if amount > have:
        raise ValueError("{} has {} {}, asked to sell {}".format(
            market["name"], addThousandSeparator(have), name, addThousandSeparator(amount)))
    config = {"mode": mode, "city_id": city_id, "resource": name, "amount": amount}

    if mode == "sell_to_offers":
        if min_price is not None:
            min_price = asInt(min_price, "min_price", minimum=1)
        if buyers is not None:
            if not isinstance(buyers, (list, tuple)) or not buyers:
                raise ValueError("buyers must be a list of city ids or null, got {!r}".format(buyers))
            buyers = list(dict.fromkeys(asId(b, "buyers[{}]".format(i)) for i, b in enumerate(buyers)))
        matching = matching_buy_offers(getOffers(session, market, resource), min_price, buyers)
        on_offer = sum(o[2] for o in matching)
        if on_offer == 0:
            raise ValueError("there are no {} in range of {}".format(offers_text(resource, min_price, buyers), market["name"]))
        if amount > on_offer:
            raise ValueError("the {} in range of {} add up to {}, asked to sell {}".format(
                offers_text(resource, min_price, buyers), market["name"], addThousandSeparator(on_offer), addThousandSeparator(amount)))
        config.update({"min_price": min_price, "buyers": buyers})
        return config

    if price is None:
        raise ValueError("price is needed for create_offer")
    html = getMarketInfo(session, market)
    lowest, highest = price_limits(html, resource)
    price = asInt(price, "price", minimum=lowest, maximum=highest)
    current = own_offers(html)[resource]
    if current["type"] == BUY and current["amount"] > 0:
        raise ValueError("{} has an offer to buy {} {}: remove it first, the trading post has one offer per resource".format(
            market["name"], addThousandSeparator(current["amount"]), name))
    config["price"] = price
    return config


@task("sellResources", prepare=prepare_sellResources)
def do_it(session, mode, city_id=None, resource=None, amount=None, min_price=None, buyers=None, price=None,
          amount_to_sell=None, offers=None, resource_type=None, city_to_buy_from=None, sell_market_capacity=None, city=None):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    mode : str
        "sell_to_offers" or "create_offer"
    city_id : str
    resource : str
    amount : int
    min_price : int or None
    buyers : list[str] or None
    price : int
    amount_to_sell, offers, resource_type, city_to_buy_from, sell_market_capacity, city :
        saved by older menus
    """
    saved = config_from_saved(mode, amount_to_sell, offers, resource_type, city_to_buy_from, city)
    if saved:
        city_id, resource, amount = saved["city_id"], saved["resource"], saved["amount"]
        if mode == "sell_to_offers":
            min_price = saved["min_price"] if min_price is None else min_price
            buyers = saved["buyers"] if buyers is None else buyers
    resource = resource_index(resource)
    try:
        market = market_city(session, city_id)
    except ValueError as e:
        msg = "Nothing was sold: {}".format(e)
        session.setStatus(msg)
        sendToBot(session, msg)
        return
    setInfoSignal(session, "\nI sell {} of {} in {}\n".format(
        addThousandSeparator(amount), materials_names[resource], market["name"]))
    if mode == "sell_to_offers":
        sell_to_offers(session, market, resource, amount, min_price, buyers)
    elif mode == "create_offer":
        create_offer(session, market, resource, amount, price)


@configurator
def sellResources(session, event, stdin_fd, predetermined_input):
    banner()

    commercial_cities = getCommercialCities(session)
    if len(commercial_cities) == 0:
        print("There is no store built")
        enter()
        return None

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

    print("Do you want to sell to existing offers (1) or do you want to make your own offer (2)?")
    selected = read(min=1, max=2)
    if selected == 1:
        return sellToOffers(session, city, resource)
    else:
        return createOffer(session, city, resource)


def sell(session, city, offer, amount, resource_type, ships_available, ship_capacity):
    """Sells ``amount`` to one offer to buy
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    offer : tuple
        as returned by getOffers
    amount : int
    resource_type : int

    Returns
    -------
    problem : str or None
        why nothing was sold
    """
    cityname, username, _, precio, _, destination_city_id = offer
    ships_used = min(ships_available, math.ceil(Decimal(amount) / Decimal(ship_capacity)))
    data = {
        "action": "transportOperations",
        "function": "sellGoodsAtAnotherBranchOffice",
        "cityId": city["id"],
        "destinationCityId": destination_city_id,
        "oldView": "branchOffice",
        "position": city["pos"],
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
        "currentCityId": city["id"],
        "templateView": "takeOffer",
        "currentTab": "bargain",
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    if resource_type == 0:
        data["cargo_resource"] = amount
        data["resourcePrice"] = precio
    else:
        data["tradegood{:d}Price".format(resource_type)] = precio
        data["cargo_tradegood{:d}".format(resource_type)] = amount

    session.get(city_url + str(city["id"]), noIndex=True)
    problem = rejection(session.post(params=data))
    if problem is not None:
        return "the game did not take the sale: {}".format(problem)
    session.setStatus(
        f"Sold {addThousandSeparator(amount)} {materials_names[resource_type]} for {precio} gold to {cityname} ({username}) <--- {city['name']} | {getDateTime()}"
    )
    return None


def sell_to_offers(session, city, resource, amount, min_price=None, buyers=None):
    """Sells to the best paid offers that match, reading them again before each sale.
    Ends when it sold ``amount``, or when no offer matches any more
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
        the trading post's city (market_city)
    resource : int
    amount : int
    min_price : int or None
    buyers : list[str] or None
    """
    name = RESOURCE_KEYS[resource]
    ship_capacity, _ = getShipCapacity(session)
    sold = 0
    earned = 0
    problem = None
    while sold < amount:
        session.setStatus("Selling {} {} from {}: waiting for free ships".format(
            addThousandSeparator(amount - sold), name, city["name"]))
        ships_available = waitForArrival(session)
        available = getCityById(session, city["id"])["availableResources"][resource]
        offer, sell_amount = next_sale(
            getOffers(session, city, resource), amount - sold, ships_available * ship_capacity, available, min_price, buyers
        )
        if offer is None:
            problem = "there are no more {}".format(offers_text(resource, min_price, buyers))
            break
        if sell_amount == 0:
            problem = "{} has no {} left".format(city["name"], name)
            break
        problem = sell(session, city, offer, sell_amount, resource, ships_available, ship_capacity)
        if problem is not None:
            break
        sold += sell_amount
        earned += sell_amount * offer[3]

    msg = "Sold {} of {} {} for {} gold @{}".format(
        addThousandSeparator(sold), addThousandSeparator(amount), name, addThousandSeparator(earned), getDateTime())
    if problem is not None:
        msg += ": {}".format(problem)
        sendToBot(session, msg)
    session.setStatus(msg)


def create_offer(session, city, resource, amount, price):
    """Offers ``amount`` for sale in the trading post at ``price``, adding it as the
    trading post makes room, and tells the user when it is sold
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
        the trading post's city (market_city)
    resource : int
    amount : int
    price : int
    """
    name = RESOURCE_KEYS[resource]

    def stop(problem):
        msg = "Offered {} of {} {} at {} in {}: {}".format(
            addThousandSeparator(amount - left), addThousandSeparator(amount), name, price, city["name"], problem)
        session.setStatus(msg)
        sendToBot(session, msg)

    left = amount
    current = own_offers(getMarketInfo(session, city))[resource]
    if current["type"] == BUY and current["amount"] > 0:
        return stop("there is an offer to buy {} {}".format(addThousandSeparator(current["amount"]), name))
    previous_on_sell = current["amount"]
    while True:
        html = getMarketInfo(session, city)
        offers_now = own_offers(html)
        on_sale = offers_now[resource]["amount"]
        room = max(0, storageCapacityOfMarket(html) - on_sale)
        available = getCityById(session, city["id"])["availableResources"][resource]
        add = min(left, room, available)
        if add > 0:
            problem = rejection(session.post(params=offers_payload(city, offers_now, resource, on_sale + add, price)))
            if problem is not None:
                return stop("the game did not take the offer: {}".format(problem))
            left -= add
        if left == 0:
            break
        if room > 0 and available == 0:
            return stop("{} has no {} left".format(city["name"], name))
        session.setStatus("Offered {} of {} {} at {} in {}: the rest when the trading post has room (checks every 2 hours)".format(
            addThousandSeparator(amount - left), addThousandSeparator(amount), name, price, city["name"]))
        wait(60 * 60 * 2)

    # wait until the last of our offer is actually bought, and let the user know
    session.setStatus("Offered {} {} at {} in {}: waiting until it is sold".format(
        addThousandSeparator(amount), name, price, city["name"]))
    while own_offers(getMarketInfo(session, city))[resource]["amount"] > previous_on_sell:
        wait(60 * 60 * 2)
    msg = "{} of {} was sold at {:d}".format(addThousandSeparator(amount), materials_names[resource], price)
    sendToBot(session, msg)
    session.setStatus("{} @{}".format(msg, getDateTime()))
