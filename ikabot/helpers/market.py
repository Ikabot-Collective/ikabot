#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re

from ikabot.config import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.pedirInfo import getIdsOfCities


def getCommercialCities(session):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session

    Returns
    -------
    commercial_cities : list[dict]
    """
    cities_ids = getIdsOfCities(session)[0]
    commercial_cities = []
    for city_id in cities_ids:
        html = session.get(city_url + city_id)
        city = getCity(html)
        for pos, building in enumerate(city["position"]):
            if building["building"] == "branchOffice":
                city["pos"] = pos
                html = getMarketHtml(session, city)
                positions = re.findall(r"<option.*?>(\d+)</option>", html)
                city["rango"] = int(positions[-1])
                commercial_cities.append(city)
                break
    return commercial_cities


def getMarketHtml(session, city):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    """
    url = "view=branchOffice&cityId={}&position={:d}&currentCityId={}&backgroundView=city&actionRequest={}&ajax=1".format(
        city["id"], city["pos"], city["id"], actionRequest
    )
    data = session.post(url)
    json_data = json.loads(data, strict=False)
    return json_data[1][1][1]


def storageCapacityOfMarket(html):
    match = re.search(r"var\s*storageCapacity\s*=\s*(\d+);", html)
    if match:
        return int(match.group(1))
    else:
        return 0


def onSellInMarket(html):
    mad, vin, mar, cri, azu = re.findall(
        r'<input type="text" class="textfield"\s*size="\d+"\s*name=".*?"\s*id=".*?"\s*value="(\d+)"',
        html,
    )
    return [int(mad), int(vin), int(mar), int(cri), int(azu)]


def getOwnOfferPrices(html):
    """Parse current prices from own offers form inputs.
    Parameters
    ----------
    html : str
        HTML from getMarketInfo() (branchOfficeOwnOffers view)
    Returns
    -------
    prices : list[int]
        [wood_price, wine_price, marble_price, crystal_price, sulfur_price]
    """
    prices = re.findall(
        r'<input type="text" class="textfield"\s*size="\d+"\s*name=".*?Price"\s*id=".*?"\s*maxlength="\d+"\s*value="(\d+)"',
        html,
    )
    return [int(p) for p in prices]


def getOwnOfferTradeTypes(html):
    """Parse current trade types (Buy/Sell) from own offers dropdowns.
    Parameters
    ----------
    html : str
        HTML from getMarketInfo() (branchOfficeOwnOffers view)
    Returns
    -------
    types : list[str]
        List of 5 strings, each "333" (Buy) or "444" (Sell)
    """
    types = re.findall(
        r'<option value="(\d+)" selected="">',
        html,
    )
    return types


def getPriceLimits(html):
    """Parse min/max price boundaries per resource from marketplace JS.
    Parameters
    ----------
    html : str
        HTML from getMarketInfo() (branchOfficeOwnOffers view)
    Returns
    -------
    limits : list[tuple[int, int]]
        List of 5 (min_price, max_price) tuples
    """
    raw = re.findall(r"'upper':\s*(\d+),\s*'lower':\s*(\d+)", html)
    return [(int(lo), int(hi)) for hi, lo in raw]


def scanMarketPrices(session, city, resource_index, scan_type="444"):
    """Browse marketplace offers to find the current lowest sell or highest buy price.
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    resource_index : int
        0=Wood, 1=Wine, 2=Marble, 3=Crystal, 4=Sulfur
    scan_type : str
        "444" to browse sell offers (find lowest sell price for undercutting),
        "333" to browse buy offers (find highest buy price for outbidding)
    Returns
    -------
    best_price : int or None
        The best price found (lowest for sell, highest for buy), or None if no offers
    """
    search_resource = "resource" if resource_index == 0 else str(resource_index)
    data = {
        "cityId": city["id"],
        "position": city["pos"],
        "view": "branchOffice",
        "activeTab": "bargain",
        "type": scan_type,
        "searchResource": search_resource,
        "range": city["rango"],
        "backgroundView": "city",
        "currentCityId": city["id"],
        "templateView": "branchOffice",
        "currentTab": "bargain",
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    resp = session.post(params=data)
    html = json.loads(resp, strict=False)[1][1][1]
    prices = re.findall(r'white-space:nowrap;">(\d+)\s', html)
    if not prices:
        return None
    prices = [int(p) for p in prices]
    if scan_type == "444":
        return min(prices)  # lowest sell price to undercut
    else:
        return max(prices)  # highest buy price to outbid


def getGold(session, city):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    Returns
    -------
    gold : int
    """
    url = "view=finances&backgroundView=city&currentCityId={}&templateView=finances&actionRequest={}&ajax=1".format(
        city["id"], actionRequest
    )
    data = session.post(url)
    json_data = json.loads(data, strict=False)
    gold = json_data[0][1]["headerData"]["gold"]
    gold = gold.split(".")[0]
    gold = int(gold)
    gold_production = (
        json_data[0][1]["headerData"]["scientistsUpkeep"]
        + json_data[0][1]["headerData"]["income"]
        + json_data[0][1]["headerData"]["upkeep"]
    )
    return gold, int(gold_production)
