#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import sys
from decimal import *

from ikabot import config
from ikabot.config import *
from ikabot.helpers.getJson import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import decodeUnicodeEscape

getcontext().prec = 30


def read(
    min=None,
    max=None,
    digit=False,
    msg=prompt,
    values=None,
    empty=False,
    additionalValues=None,
    default=None,
    _retries=0,
    _max_retries=20
):
    """Reads input from user
    Parameters
    ----------
    min : int
        smallest number acceptable as input
    max : int
        greatest number acceptable as input
    digit : bool
        boolean indicating whether or not the input MUST be an int
    msg : str
        string printed before the user is asked for input
    values : list
        list of strings which are acceptable as input
    empty : bool
        a boolean indicating whether or not an empty string is acceptable as input
    additionalValues : list
        list of strings which are additional valid inputs. Can be used with digit = True to validate a string as an input among all digits
    Returns
    -------
    result : int | str
        int representing the user's choice
    """
    if _retries >= _max_retries:
        print('Error: Max recursion depth reached for read function. Returning None!')
        return None
        
    if min is not None and max is not None and min > max:
        print('Error: minimum input value is greater than maximum input value!')
        return None
        
    try:
        if len(config.predetermined_input) != 0:
            return config.predetermined_input.pop(0)
    except Exception:
        pass
    
    def _invalid():
        print("\033[1A\033[K", end="")  # remove line
        return read(min=min, max=max, digit=digit, msg=msg, values=values, empty=empty, additionalValues=additionalValues, default=default, _retries=_retries+1, _max_retries=_max_retries)
    
    try:
        read_input = input(msg)
    except EOFError:
        return _invalid()
    
    if additionalValues is not None and read_input in additionalValues:
        return read_input
    if read_input == "" and default is not None:
        return default
    if read_input == "" and empty is True:
        return read_input
    
    if digit is True or min is not None or max is not None:
        if not read_input.isdigit():
            return _invalid()
        else:
            try:
                read_input = int(read_input)
            except ValueError:
                return _invalid()
    
    if min is not None and read_input < min:
        return _invalid()
    if max is not None and read_input > max:
        return _invalid()
    if values is not None and read_input not in values:
        return _invalid()
    return read_input


def chooseCity(session, foreign=False):
    """Prompts the user to chose a city
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    foreign : bool
        lets the user choose a foreign city

    Returns
    -------
    city : City
        a city object representing the chosen city
    """
    global menu_cities
    (ids, cities) = getIdsOfCities(session)
    if menu_cities == "":
        longest_city_name_length = 0
        for city_id in ids:
            length = len(cities[city_id]["name"])
            if length > longest_city_name_length:
                longest_city_name_length = length

        def pad(city_name):
            return " " * (longest_city_name_length - len(city_name) + 2)

        resources_abbreviations = {
            "1": "(W)",
            "2": "(M)",
            "3": "(C)",
            "4": "(S)",
        }

        i = 0
        if foreign:
            print(" 0: foreign city")
        else:
            print("")
        for city_id in ids:
            i += 1
            resource_index = str(cities[city_id]["tradegood"])
            resource_abb = resources_abbreviations[resource_index]
            city_name = decodeUnicodeEscape(cities[city_id]["name"])
            menu_cities += "{: >2}: {}{}{}\n".format(
                i, city_name, pad(city_name), resource_abb
            )
        menu_cities = menu_cities[:-1]
    if foreign:
        print(" 0: foreign city")
    print(menu_cities)

    if foreign:
        selected_city_index = read(min=0, max=len(ids))
    else:
        selected_city_index = read(min=1, max=len(ids))
    if selected_city_index == 0:
        return chooseForeignCity(session)
    else:
        html = session.get(city_url + ids[selected_city_index - 1])
        return getCity(html)


def chooseForeignCity(session):
    """Prompts the user to select an island, and a city on that island (is only used in chooseCity)
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    city : City
        a city object representing the city the user chose
    """
    banner()
    x = read(msg="coordinate x:", digit=True)
    y = read(msg="coordinate y:", digit=True)
    print("")
    url = "view=worldmap_iso&islandX={}&islandY={}&oldBackgroundView=island&islandWorldviewScale=1".format(
        x, y
    )
    html = session.get(url)
    try:
        islands_json = re.search(r"jsonData = \'(.*?)\';", html).group(1)
        islands_json = json.loads(islands_json, strict=False)
        island_id = islands_json["data"][str(x)][str(y)][0]
    except Exception:
        print("Incorrect coordinates")
        enter()
        banner()
        return chooseCity(session, foreign=True)
    html = session.get(island_url + island_id)
    island = getIsland(html)

    i = 0
    city_options = []
    for city in island["cities"]:
        if (
            city["type"] == "city"
            and city["state"] == ""
            and city["Name"] != session.username
        ):
            i += 1
            num = " " + str(i) if i < 10 else str(i)
            print(
                "{: >2}: {: >{max_city_name_length}} ({})".format(
                    num,
                    decodeUnicodeEscape(city["name"]),
                    decodeUnicodeEscape(city["Name"]),
                    max_city_name_length=MAXIMUM_CITY_NAME_LENGTH,
                )
            )
            city_options.append(city)
    if i == 0:
        print("There are no cities where to send resources on this island")
        enter()
        return chooseCity(session, foreign=True)
    selected_city_index = read(min=1, max=i)
    city = city_options[selected_city_index - 1]
    city["islandId"] = island["id"]
    city["cityName"] = decodeUnicodeEscape(city["name"])
    city["isOwnCity"] = False
    return city


def askForValue(text, max_val):
    """Displays text and asks the user to enter a value between 0 and max

    Parameters
    ----------
    text : str
        text to be displayed when asking the user for input
    max_val : int
        integer representing the number of input options

    Returns
    -------
    var : int
        integer representing the user's input
        if the user has inputed nothing, 0 will be returned instead
    """
    var = read(
        msg=text, min=0, max=max_val, default=0, additionalValues=["all", "half"]
    )
    if var == "all":
        var = max_val
    elif var == "half":
        var = max_val // 2
    return var


def getIdsOfCities(session, all=False):
    """Gets the user's cities
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    all : bool
        boolean indicating whether all cities should be returned, or only those that belong to the current user

    Returns
    -------
    (ids, cities) : tuple
        a tuple containing the a list of city IDs and a list of city objects
    """
    global cities_cache
    global ids_cache
    if ids_cache is None or cities_cache is None or session.padre is False:
        html = session.get()
        cities_cache = (
            re.search(
                r'relatedCityData:\sJSON\.parse\(\'(.+?),\\"additionalInfo', html
            ).group(1)
            + "}"
        )
        cities_cache = cities_cache.replace("\\", "")
        cities_cache = cities_cache.replace("city_", "")
        cities_cache = json.loads(cities_cache, strict=False)

        ids_cache = [city_id for city_id in cities_cache]
        ids_cache = sorted(ids_cache)

    # {'coords': '[x:y] ', 'id': idCiudad, 'tradegood': '..', 'name': 'nomberCiudad', 'relationship': 'ownCity'|'occupiedCities'|..}
    if all is False:
        ids_own = [
            city_id
            for city_id in cities_cache
            if cities_cache[city_id]["relationship"] == "ownCity"
        ]
        ids_other = [
            city_id
            for city_id in cities_cache
            if cities_cache[city_id]["relationship"] != "ownCity"
        ]
        own_cities = cities_cache.copy()
        for id in ids_other:
            del own_cities[id]
        return ids_own, own_cities
    else:
        return ids_cache, cities_cache


def getIslandsIds(session):
    """Gets the IDs of islands the user has cities on
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    islands_ids : list
        a list containing the IDs of the users islands
    """
    (cities_ids, cities) = getIdsOfCities(session)
    islands_ids = set()
    for city_id in cities_ids:
        html = session.get(city_url + city_id)
        city = getCity(html)
        island_id = city["islandId"]
        islands_ids.add(island_id)
    return list(islands_ids)


def getShipCapacity(session):
    """Gets the ship capacity
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    capacity : int
        an integer representing the ship capacity of the user's current city
    """
    html = session.post('view=merchantNavy')
    ship_capacity = html.split('singleTransporterCapacity":')[1].split(',"singleFreighterCapacity')[0]
    freighter_capacity = html.split('singleFreighterCapacity":')[1].split(',"draftEffect')[0]

    return int(ship_capacity), int(freighter_capacity)


def ignoreCities(session, msg=None):
    """Prompts the user to select cities which should be ignored
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    (cities_ids) : list
        a list containing IDs of cities that were not ignored
    """
    (cities_ids, cities) = getIdsOfCities(session)
    choice = None
    ignored_cities = []
    while True:
        banner()
        if msg is not None: print(f"{msg}")
        displayed_string = (
            f'(currently ignoring: {", ".join(ignored_cities)})'
            if ignored_cities
            else ""
        )
        print(f"Select cities to ignore. {displayed_string}")
        print("0) Continue")
        choice_to_cityid_map = []
        for i, city in enumerate(cities.values()):
            choice_to_cityid_map.append(city["id"])
            print(f'{i + 1}) {city["name"]} - {materials_names[city["tradegood"]]}')
        choice = read(min=0, max=len(cities_ids))
        if choice == 0:
            break
        city_id = choice_to_cityid_map[choice - 1]
        cities_ids = list(filter(lambda x: x != str(city_id), cities_ids))
        ignored_cities.append(cities[str(city_id)]["name"])
        del cities[str(city_id)]
        
    return cities_ids, cities
