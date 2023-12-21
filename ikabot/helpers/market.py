#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
from ikabot.config import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.pedirInfo import getIdsOfCities
from bs4 import BeautifulSoup


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
        for pos, building in enumerate(city['position']):
            if building['building'] == 'branchOffice':
                city['pos'] = pos
                html = getMarketHtml(session, city)
                positions = re.findall(r'<option.*?>(\d+)</option>', html)
                city['rango'] = int(positions[-1])
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
    url = 'view=branchOffice&cityId={}&position={:d}&currentCityId={}&backgroundView=city&actionRequest={}&ajax=1'.format(city['id'], city['pos'], city['id'], actionRequest)
    data = session.post(url)
    json_data = json.loads(data, strict=False)
    return json_data[1][1][1]


def storageCapacityOfMarket(html):
    match = re.search(r'var\s*storageCapacity\s*=\s*(\d+);', html)
    if match:
        return int(match.group(1))
    else:
        return 0


def onSellInMarket(html):
    mad, vin, mar, cri, azu = re.findall(r'<input type="text" class="textfield"\s*size="\d+"\s*name=".*?"\s*id=".*?"\s*value="(\d+)"', html)
    return [int(mad), int(vin), int(mar), int(cri), int(azu)]

def getFinances(session, city_id):
    """
    Get json of finances screen

    :param session : ikabot.web.session.Session
    :param city_id : int
    :return json
    """
    url = 'view=finances&backgroundView=city&currentCityId={}&templateView=finances&actionRequest={}&ajax=1'.format(city_id, actionRequest)
    data = session.post(url)
    return json.loads(data, strict=False)

def getGold(session, city_id):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int
    Returns
    -------
    gold : int
    """
    json_data = getFinances(session, city_id)
    gold = json_data[0][1]['headerData']['gold']
    gold = gold.split('.')[0]
    gold = int(gold)
    gold_production = json_data[0][1]['headerData']['scientistsUpkeep'] + json_data[0][1]['headerData']['income'] + json_data[0][1]['headerData']['upkeep']
    return gold, int(gold_production)


def print_table(html_table):
    for row in html_table.find_all('tr'):
        fmt = "{: >30}"
        cells = []
        for cell in row.find_all(['th', 'td']):
            cells.append(fmt.format(cell.get_text(strip=True)))
            fmt = "{: >15}"
        print(" | ".join(cells))

def printGoldForAllCities(session, city_id):
    """
    Prints all the tables from finances for all cities

    :param session : ikabot.web.session.Session
    :param city_id : int
    """
    json_data = getFinances(session, city_id)
    html_code = json_data[1][1][1] # changeView -> finances
    soup = BeautifulSoup(html_code, 'html.parser')
    html_tables = soup.find_all('table')


    # Print each table in a readable format
    for html_table in html_tables:
        print_table(html_table)
        print('-' * 85)  # Add a separator between tables
