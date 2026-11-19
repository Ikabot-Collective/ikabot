#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import html as html_lib
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
from ikabot.helpers.decorators import configurator, task
from ikabot.helpers.resources import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import addThousandSeparator, getDateTime
from ikabot.helpers.pedirInfo import getShipCapacity
from ikabot.helpers.taskConfig import asInt, getCityById, requireOwnCity
from ikabot.function.sendResources import RESOURCE_KEYS


BUY_FROM_ANYONE = 1
BUY_FROM_PLAYER = 2
BUY_FROM_CITY = 3


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
    search_offers(session, city, resource)
    # return the chosen resource
    return resource


def search_offers(session, city, resource):
    """Sets the resource the trading post of ``city`` lists offers of
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
        with the trading post's position (``pos``) and range (``rango``)
    resource : int
        0 (wood) to 4 (sulfur)
    """
    data = {
        "cityId": city["id"],
        "position": city["pos"],
        "view": "branchOffice",
        "activeTab": "bargain",
        "type": 444,
        "searchResource": "resource" if resource == 0 else resource,
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

    resource_names = {
        "resource": "wood",
        "1": "wine",
        "2": "marble",
        "3": "glass",
        "4": "sulfur",
    }

    offers = []
    for row in re.findall(r'<tr[^>]*>([\s\S]*?)</tr>', html):
        city_match   = re.search(r'<td class="short_text80">(.*?)<br/>\((.*?)\)', row)
        amount_match = re.search(r'<div class="tooltip"[^>]*>(\d[^<]*)</div>', row)
        price_match  = re.search(r'<td style="white-space:nowrap;">(\d+)', row)
        href_match   = re.search(
            r'href="\?view=takeOffer&destinationCityId=(\d+)&oldView=branchOffice&activeTab=bargain&cityId=(\d+)&position=(\d+)&type=(\d+)&resource=(\w+)"',
            row,
        )

        if not all([city_match, amount_match, price_match, href_match]):
            continue

        resource_key = href_match.group(5)
        raw_amount = re.sub(r'\D', '', amount_match.group(1))
        offer = {
            "ciudadDestino": city_match.group(1).strip(),
            "jugadorAComprar": city_match.group(2).strip(),
            "amountAvailable": int(raw_amount),
            "tipo": resource_names.get(resource_key, resource_key),
            "precio": int(price_match.group(1)),
            "destinationCityId": href_match.group(1),
            "cityId": href_match.group(2),
            "position": href_match.group(3),
            "type": href_match.group(4),
            "resource": resource_key,
        }
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


def filterOffers(offers):
    """Lets the user buy from one specific player or one specific city instead of always
    taking the cheapest offers. The lowest price is not always the desired one, the user
    might need to trade with someone in particular
    Parameters
    ----------
    offers : list[dict]

    Returns
    -------
    (offers, key, seller) : tuple
        the offers that belong to the chosen seller, the offer key the seller was chosen
        by ("jugadorAComprar" or "ciudadDestino") and its name (None if the user did not
        choose one)
    """
    print("Buy from:")
    print("({:d}) Anyone in range".format(BUY_FROM_ANYONE))
    print("({:d}) A specific player".format(BUY_FROM_PLAYER))
    print("({:d}) A specific city".format(BUY_FROM_CITY))
    choice = read(min=BUY_FROM_ANYONE, max=BUY_FROM_CITY, default=BUY_FROM_ANYONE)
    if choice == BUY_FROM_ANYONE:
        return offers, None, None

    if choice == BUY_FROM_PLAYER:
        key = "jugadorAComprar"
        print("\nWhich player do you want to buy from?\n")
    else:
        key = "ciudadDestino"
        print("\nWhich city do you want to buy from?\n")

    # dict.fromkeys removes the duplicates without losing the order of the offers
    sellers = list(dict.fromkeys([offer[key] for offer in offers]))
    for i, seller in enumerate(sellers):
        print("({:d}) {}".format(i + 1, seller))
    seller = sellers[read(min=1, max=len(sellers)) - 1]

    return [offer for offer in offers if offer[key] == seller], key, seller


def buy(session, city, offer, amount_to_buy, ships_available, ship_capacity, max_price=None):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    offer : dict
    amount_to_buy : int
    max_price : int
        the seller may have raised the price since the offers were read: nothing is
        bought when the price of the offer is now above it

    Returns
    -------
    (price, problem) : tuple
        the price paid per unit, and None; or None and why nothing was bought
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
    price_key = "resourcePrice" if resource == "resource" else "tradegood{}Price".format(resource)
    price = data_dict.get(price_key)
    if max_price is not None and (price is None or price > max_price):
        if price is None:
            return None, "could not read the price of the offer of {}".format(offer["ciudadDestino"])
        return None, "the offer of {} now costs {} gold, above max_price {}".format(offer["ciudadDestino"], price, max_price)
    if resource == "resource":
        data_dict["cargo_resource"] = amount_to_buy
    else:
        data_dict["cargo_tradegood{}".format(resource)] = amount_to_buy
    problem = rejection(session.post(params=data_dict))
    if problem is not None:
        return None, "the game did not take the purchase: {}".format(problem)
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
    return (price if price is not None else offer["precio"]), None


def rejection(response):
    """The text of the game's rejection (feedback type 11) in a response, or None
    Parameters
    ----------
    response : str

    Returns
    -------
    text : str or None
    """
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


def resource_index(value, name="resource"):
    """0 (wood) to 4 (sulfur), from a number or a name"""
    text = "" if value is None or isinstance(value, bool) else str(value).strip().lower()
    if text.isdigit() and int(text) < len(RESOURCE_KEYS):
        return int(text)
    if text in RESOURCE_KEYS:
        return RESOURCE_KEYS.index(text)
    # how the trading post names wood and crystal
    if text in ("resource", "glass"):
        return {"resource": 0, "glass": 3}[text]
    raise ValueError("{} must be {} (or 0 to 4), got {!r}".format(name, ", ".join(RESOURCE_KEYS), value))


def market_city(session, city_id):
    """One of the user's cities with its trading post: position (``pos``) and range (``rango``)
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : str

    Returns
    -------
    city : dict
    """
    city = getCityById(session, city_id)
    for pos, building in enumerate(city["position"]):
        if building["building"] == "branchOffice":
            city["pos"] = pos
            positions = re.findall(r"<option.*?>(\d+)</option>", getMarketHtml(session, city))
            city["rango"] = int(positions[-1])
            return city
    raise ValueError("{} has no trading post".format(city.get("name", city_id)))


def live_offers(session, city, resource):
    """The offers of ``resource`` in range of the trading post of ``city``, cheapest first"""
    search_offers(session, city, resource)
    offers = getOffers(session, city)
    offers.sort(key=lambda o: o["precio"])
    return offers


def matching_offers(offers, max_price=None, seller_player=None, seller_city=None):
    """The offers that can be bought from, cheapest first
    Parameters
    ----------
    offers : list[dict]
    max_price : int or None
    seller_player, seller_city : str or None
        only that player's offers, or only that city's

    Returns
    -------
    offers : list[dict]
    """
    def same(a, b):
        return html_lib.unescape(str(a)).strip().lower() == html_lib.unescape(str(b)).strip().lower()

    return sorted(
        (
            offer for offer in offers
            if offer["amountAvailable"] > 0
            and (max_price is None or offer["precio"] <= max_price)
            and (seller_player is None or same(offer["jugadorAComprar"], seller_player))
            and (seller_city is None or same(offer["ciudadDestino"], seller_city))
        ),
        key=lambda o: o["precio"],
    )


def next_purchase(offers, remaining, ship_space, gold, max_price=None, seller_player=None, seller_city=None):
    """The offer to buy from next and how much: the cheapest one that matches, as much as
    the ships carry and the gold pays for
    Parameters
    ----------
    offers : list[dict]
        the offers on the market now
    remaining : int
        what is left to buy
    ship_space : int
        what the available ships carry
    gold : int

    Returns
    -------
    (offer, amount) : tuple
        (None, 0) when no offer matches; amount is 0 when the gold does not pay for one unit
    """
    candidates = matching_offers(offers, max_price, seller_player, seller_city)
    if not candidates:
        return None, 0
    offer = candidates[0]
    return offer, max(0, min(remaining, offer["amountAvailable"], ship_space, gold // offer["precio"]))


def price_cap(offers, amount):
    """The highest price among the cheapest offers that cover ``amount``"""
    cap = None
    for offer in sorted(offers, key=lambda o: o["precio"]):
        if amount <= 0:
            break
        if offer["amountAvailable"] > 0:
            cap = offer["precio"]
            amount -= offer["amountAvailable"]
    return cap


def config_from_saved(city, offers, amount_to_buy):
    """An older menu saved the trading post's city and the offers it showed: buy the same
    amount, never above the highest price it showed for that amount"""
    config = {"city_id": city["id"], "amount": amount_to_buy, "max_price": price_cap(offers or [], amount_to_buy)}
    if offers:
        config["resource"] = resource_index(offers[0]["resource"])
    return config


def offers_text(resource, max_price, seller_player, seller_city):
    text = "{} offers".format(RESOURCE_KEYS[resource])
    if max_price is not None:
        text += " at or below {} gold".format(max_price)
    if seller_player is not None:
        text += " from {}".format(seller_player)
    if seller_city is not None:
        text += " from the city {}".format(seller_city)
    return text


def prepare_buyResources(session, city_id=None, resource=None, amount=None, max_price=None, seller_player=None,
                         seller_city=None, city=None, offers=None, amount_to_buy=None):
    """Checks the config of a buyResources task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int or str
        one of your cities with a trading post; it receives what is bought
    resource : str or int
        wood, wine, marble, crystal or sulfur (or 0 to 4)
    amount : int
    max_price : int
        highest price per unit to pay; null pays what the offers ask
    seller_player, seller_city : str
        buy only from that player, or only from that city (names as the trading post shows them)
    city, offers, amount_to_buy :
        saved by older menus

    Returns
    -------
    config : dict
    """
    if city is not None:
        saved = config_from_saved(city, offers, amount_to_buy)
        city_id = saved["city_id"]
        amount = saved["amount"]
        resource = saved.get("resource", resource)
        if max_price is None:
            max_price = saved["max_price"]
    if city_id is None:
        raise ValueError("city_id is needed: one of your cities with a trading post")
    if resource is None:
        raise ValueError("resource is needed: {}".format(", ".join(RESOURCE_KEYS)))
    if amount is None:
        raise ValueError("amount is needed")
    city_id = requireOwnCity(session, city_id, "city_id")
    resource = resource_index(resource)
    amount = asInt(amount, "amount", minimum=1)
    if max_price is not None:
        max_price = asInt(max_price, "max_price", minimum=1)
    sellers = {}
    for key, value in (("seller_player", seller_player), ("seller_city", seller_city)):
        if value is not None and not str(value).strip():
            raise ValueError("{} must be a name or null, got {!r}".format(key, value))
        sellers[key] = str(value).strip() if value is not None else None

    market = market_city(session, city_id)
    name = market["name"]
    free = market["freeSpaceForResources"][resource]
    if amount > free:
        raise ValueError("{} has room for {} {}, asked to buy {}".format(
            name, addThousandSeparator(free), RESOURCE_KEYS[resource], addThousandSeparator(amount)))
    matching = matching_offers(live_offers(session, market, resource), max_price, **sellers)
    on_offer = sum(o["amountAvailable"] for o in matching)
    what = offers_text(resource, max_price, sellers["seller_player"], sellers["seller_city"])
    if on_offer == 0:
        raise ValueError("there are no {} in range of {}".format(what, name))
    if amount > on_offer:
        raise ValueError("the {} in range of {} add up to {}, asked to buy {}".format(
            what, name, addThousandSeparator(on_offer), addThousandSeparator(amount)))
    cost = calculateCost(matching, amount)
    gold, _ = getGold(session, market)
    if cost > gold:
        raise ValueError("buying {} {} costs {} gold and you have {}".format(
            addThousandSeparator(amount), RESOURCE_KEYS[resource], addThousandSeparator(cost), addThousandSeparator(gold)))
    return {"city_id": city_id, "resource": RESOURCE_KEYS[resource], "amount": amount, "max_price": max_price, **sellers}


@task("buyResources", prepare=prepare_buyResources)
def do_it(session, city_id=None, resource=None, amount=None, max_price=None, seller_player=None, seller_city=None,
          city=None, offers=None, amount_to_buy=None):
    """Buys from the cheapest offers that match, reading them again before each purchase.
    Ends when it bought ``amount``, or when no offer matches any more
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : str
    resource : str
    amount : int
    max_price : int or None
    seller_player, seller_city : str or None
    city, offers, amount_to_buy :
        saved by older menus
    """
    if city is not None:
        saved = config_from_saved(city, offers, amount_to_buy)
        city_id, amount = saved["city_id"], saved["amount"]
        resource = saved.get("resource", resource)
        max_price = saved["max_price"] if max_price is None else max_price
    resource = resource_index(resource)
    name = RESOURCE_KEYS[resource]
    try:
        market = market_city(session, city_id)
    except ValueError as e:
        msg = "Nothing was bought: {}".format(e)
        session.setStatus(msg)
        sendToBot(session, msg)
        return

    setInfoSignal(session, "\nI will buy {} {} to {}\n".format(addThousandSeparator(amount), name, market["name"]))
    # what is bought travels to the city: only what fits in its warehouse now
    total = min(amount, market["freeSpaceForResources"][resource])
    ship_capacity, _ = getShipCapacity(session)
    bought = 0
    spent = 0
    problem = None
    if total < amount:
        problem = "{} has room for {} {}".format(market["name"], addThousandSeparator(total), name)
    while bought < total:
        session.setStatus("Buying {} {} for {}: waiting for free ships".format(
            addThousandSeparator(total - bought), name, market["name"]))
        ships_available = waitForArrival(session)
        # read after the wait: the offers may have changed meanwhile
        offers_now = live_offers(session, market, resource)
        gold, _ = getGold(session, market)
        offer, buy_amount = next_purchase(
            offers_now, total - bought, ships_available * ship_capacity, gold, max_price, seller_player, seller_city
        )
        if offer is None:
            problem = "there are no more {}".format(offers_text(resource, max_price, seller_player, seller_city))
            break
        if buy_amount == 0:
            problem = "not enough gold: {} gold, the cheapest offer asks {} per unit".format(
                addThousandSeparator(gold), offer["precio"])
            break
        price, problem = buy(session, market, offer, buy_amount, ships_available, ship_capacity, max_price)
        if problem is not None:
            break
        bought += buy_amount
        spent += buy_amount * price

    msg = "Bought {} of {} {} for {} gold @{}".format(
        addThousandSeparator(bought), addThousandSeparator(amount), name, addThousandSeparator(spent), getDateTime())
    if problem is not None:
        msg += ": {}".format(problem)
        sendToBot(session, msg)
    session.setStatus(msg)


@configurator
def buyResources(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    banner()

    # get all the cities with a store
    commercial_cities = getCommercialCities(session)
    if len(commercial_cities) == 0:
        print("There is no store build")
        enter()
        return None

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
    offers.sort(key=lambda o: o["precio"])
    if len(offers) == 0:
        print("There are no offers available.")
        enter()
        return None

    # let the user buy from one seller only
    (offers, seller_key, seller) = filterOffers(offers)
    banner()

    # display offers to the user
    total_price = 0
    total_amount = 0
    for offer in offers:
        amount = offer["amountAvailable"]
        price = offer["precio"]
        cost = amount * price
        print(
            "seller:{} ({})".format(
                offer["jugadorAComprar"], offer["ciudadDestino"]
            )
        )
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
        return None

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
        return None

    print("It will be purchased {}".format(addThousandSeparator(amount_to_buy)))
    enter()
    # the task reads the offers again before each purchase: the config keeps what the user
    # decided, and never more than the highest price shown for this amount
    return {
        "session": session,
        "city_id": str(city["id"]),
        "resource": RESOURCE_KEYS[resource],
        "amount": amount_to_buy,
        "max_price": price_cap(offers, amount_to_buy),
        "seller_player": seller if seller_key == "jugadorAComprar" else None,
        "seller_city": seller if seller_key == "ciudadDestino" else None,
    }

