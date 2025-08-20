#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import time
from math import ceil, floor
from ikabot.helpers.resources import *
from ikabot.helpers.varios import decodeUnicodeEscape
from ikabot.config import *
from typing import Dict, TypedDict, Optional, Any
# TODO replace Optional with NotRequried when we drop support for python 3.9 and 3.10. NotRequired is more precise here than Optional
LinkDict = TypedDict("LinkDict", {"onclick": str, "href": str, "tooltip": str})

FlyingTraderDict = TypedDict("FlyingTraderDict", {"link": LinkDict, "banner": str})

VisibilityDict = TypedDict(
    "VisibilityDict",
    {
        "military": int,
        "espionage": int,
        "resourceShop": int,
        "slot1": int,
        "slot2": int,
        "slot3": int,
        "slot4": int,
    },
)

CityLeftMenuDict = TypedDict("CityLeftMenuDict", {"visibility": VisibilityDict, "ownCity": int})

PositionDict = TypedDict(
    "PositionDict",
    {
        "name": str,
        "level": Optional[int],
        "isBusy": bool,
        "canUpgrade": Optional[bool],
        "isMaxLevel": Optional[bool],
        "building": str,
        "shipIsAtDockyard": Optional[int],

        # Added for compatibility
        "position": int,
        "type": Optional[str],
    },
)

FullCityDict = TypedDict(
    "FullCityDict",
    {
        "name": str,
        "id": str,
        "phase": int,
        "isCapital": bool,
        "ownerId": str,
        "ownerName": str,
        "islandId": str,
        "islandName": str,
        "islandXCoord": str,
        "islandYCoord": str,
        "buildingSpeedupActive": int,
        "showPirateFortressBackground": int,
        "showPirateFortressShip": int,
        "underConstruction": int,
        "endUpgradeTime": int,
        "startUpgradeTime": int,
        "position": list[PositionDict],
        "beachboys": str,
        "spiesInside": None,
        "cityLeftMenu": CityLeftMenuDict,
        "walkers": list[Any],
        "displayStaticPlague": bool,
        "dailyTasks": str,
        "cityCinema": str,
        "flyingTrader": FlyingTraderDict,

        # Added for compatibility
        "x": str,
        "y": str,
        "cityName": str,
        "isOwnCity": bool,
        "availableResources": list[int],
        "storageCapacity": int,
        "freeCitizens": int,
        "wineConsumptionPerHour": int,
        "resourcesListedForSale": list[int],
        "freeSpaceForResources": list[int],
    },
)


AvatarScoreDict = TypedDict(
    "AvatarScoreDict",
    {
        "avatar_id": str,
        "place": str,
        "building_score_main": str,
        "research_score_main": str,
        "army_score_main": str,
        "trader_score_secondary": str,
    },
)

AvatarScoresDict = Dict[str, AvatarScoreDict]

BarbariansDict = TypedDict(
    "BarbariansDict",
    {
        "invisible": int,
        "actionTitle": str,
        "actionClass": str,
        "actionLink": str,
        "count": int,
        "wallLevel": int,
        "level": int,
        "underAttack": int,
        "isTradegoodSiege": int,
        "city": str,
        "destroyed": int,
    },
)

CityDict = TypedDict(
    "CityDict",
    {
        "type": str,
        "name": str,
        "id": int,
        "level": int,
        "ownerId": Optional[str],
        "ownerName": Optional[str],
        "ownerAllyId": Optional[int],
        "ownerAllyTag": Optional[str],
        "hasTreaties": Optional[int],
        "actions": Optional[list[Any]],
        "state": Optional[str],
        "viewAble": int,
        "infestedByPlague": Optional[bool],
        "buildplace_type": Optional[str],

        # Added for compatibility

        "Id": Optional[str],
        "Name": Optional[str],
        "AllyId": Optional[int],
        "AllyTag": Optional[str],
        "_type": Optional[str],
    },
)

IslandDict = TypedDict(
    "IslandDict",
    {
        "id": str,
        "type": int,
        "name": str,
        "xCoord": str,
        "yCoord": str,
        "tradegood": int,
        "tradegoodTarget": str,
        "resourceLevel": str,
        "tradegoodLevel": str,
        "wonder": str,
        "wonderLevel": str,
        "wonderName": str,
        "showResourceWorkers": int,
        "showTradegoodWorkers": int,
        "showAgora": int,
        "canEnterResource": int,
        "canEnterTradegood": int,
        "tradegoodEndUpgradeTime": int,
        "resourceEndUpgradeTime": int,
        "wonderEndUpgradeTime": int,
        "isOwnCityOnIsland": bool,
        "cities": list[CityDict],
        "barbarians": BarbariansDict,
        "avatarScores": AvatarScoresDict,
        "specialServerBadges": list[Any],
        "selectedCityParameters": list[Any],
        "island": int,
        "isHeliosTowerBuilt": bool,
        "heliosTop": int,
        "heliosMid": int,
        "heliosBase": int,
        "heliosName": str,
        "heliosTooltip": str,
        "heliosActive": int,
        "showResourceBonusIcon": int,
        "showTradegoodBonusIcon": int,
        "walkers": list[Any],

        # Added for compatibility

        "x": int,
        "y": int,
        "tipo": str,
    },
)

WorldMapIslandDict = TypedDict(
    "WorldMapIslandDict",
    {
        "x": int,
        "y": int,
        "id": int,
        "name": str,
        "resourceType": int,
        "miracleType": int,
        "unknownValue1": int,
        "unknownValue2": int,
        "woodLvl": int,
        "cityCount": int,
        "piracyInRange": bool,
        "heliosTower": bool,
        "red": bool,
        "blue": bool,
        
        # Added for ease of use
        "resourceName": str,
        "miracleName": str,
    },
)


def getFreeCitizens(html: str) -> int:
    """This function is used in the ``getCity`` function to determine the amount of free (idle) citizens in the given city.
    Parameters
    ----------
    html : str
        a string representing html which is returned when sending a get request to view a city.

    Returns
    -------
    freeCitizens : int
        an integer representing the amount of free citizens in the given city.
    """
    freeCitizens = re.search(r'js_GlobalMenu_citizens">(.*?)</span>', html).group(1)
    freeCitizens = re.sub(r'\D', '', freeCitizens)
    return int(freeCitizens)


def getResourcesListedForSale(html: str) -> list[int]:
    """This function is used in the ``getCity`` function to determine the amount of each resource which is listed for sale in the branch office
    Parameters
    ----------
    html : str
        a string representing html which is returned when sending a get request to view a city.

    Returns
    -------
    onSale : list[int]
        a list containing 5 integers each of which representing the amount of that particular resource which is on sale in the given city. For more information about the order of the resources, refer to ``config.py``
    """
    rta = re.search(
        r'branchOfficeResources: JSON\.parse\(\'{\\"resource\\":\\"(\d+)\\",\\"1\\":\\"(\d+)\\",\\"2\\":\\"(\d+)\\",\\"3\\":\\"(\d+)\\",\\"4\\":\\"(\d+)\\"}\'\)',
        html,
    )
    if rta:
        return [
            int(rta.group(1)),
            int(rta.group(2)),
            int(rta.group(3)),
            int(rta.group(4)),
            int(rta.group(5)),
        ]
    else:
        return [0, 0, 0, 0, 0]

def getWorldMapIslands(html: str) -> list[WorldMapIslandDict]:
    """This function uses the html passed to it as a string to extract, parse and return a list of WorldMapIsland objects
    Parameters
    ----------
    html : str
        the html or json returned when a get request is made to the `view=worldmap_iso` or `action=WorldMap&function=getJSONArea` endpoints respectively. 

    Returns
    -------
    islands : list[WorldMapIsland]
        this function returns a json parsed list of WorldMapIsland objects.
    """

    isla = re.search(r"jsonData = '([\S\s]*?)'", html).group(1) if '!DOCTYPE html' in html else html

    worldMapIslands = []

    data = json.loads(isla)['data']
    for x in data:
        for y in data[x]:
            worldMapIslands.append({
                'x': int(x),
                'y': int(y),
                'id': int(data[x][y][0]),
                'name': data[x][y][1],
                'resourceType': int(data[x][y][2]),
                'miracleType': int(data[x][y][3]),
                'unknownValue1': int(data[x][y][4]),
                'unknownValue2': int(data[x][y][5]),
                'woodLvl': int(data[x][y][6]),
                'cityCount': int(data[x][y][7]),
                'piracyInRange': bool(data[x][y][8]),
                'heliosTower': bool(int(data[x][y][9])),
                'red': bool(int(data[x][y][10])),
                'blue': bool(int(data[x][y][11])),
                'resourceName': materials_names_english[int(data[x][y][2])],
                'miracleName': miracle_names_english[int(data[x][y][3])]
            })

    return worldMapIslands
# [
# "58",         //id 0
# "Phytios",    //name 1
# "1",          //resource type 2
# "2",          //type of miracle 3
# "5",          // ?? 4
# "4",          // ?? 5
# "9",          // lumber level  6
# "12",         // number of people 7
# 0,            // piracy in range 8
# "0",          // helios tower 9
# "0",          // red 10
# "0"           // blue 11
# ]

def getIsland(html: str) -> IslandDict:
    """This function uses the html passed to it as a string to extract, parse and return an Island object
    Parameters
    ----------
    html : str
        the html returned when a get request to view the island is made. This request can be made with the following statement: ``s.get(urlIsla + islandId)``, where ``urlIsla`` is a string defined in ``config.py`` and ``islandId`` is the id of the island.

    Returns
    -------
    island : Island
        this function returns a json parsed Island object.
    """
    isla = re.search(r'ajax.Responder, (\[\[[\S\s]*?\]\])\)\;', html).group(1)

    island: IslandDict = json.loads(isla)[0][1]

    # Must add aliases for different properties to maintain backwards compatibility with old code

    island["x"] = int(island["xCoord"])
    island["y"] = int(island["yCoord"])
    island["tipo"] = str(island["tradegood"])

    for city in island["cities"]:
        for key in ["Id", "Name", "AllyId", "AllyTag"]:
            if ('owner'+key) in city:
                city[key] = city['owner'+key]
        
        if "buildplace_type" in city:
            city["_type"] = city["buildplace_type"]
        
        if city["type"] == 'buildplace':
            city["type"] = 'empty'

    return island



    # isla = isla.replace("buildplace", "empty")
    # isla = isla.replace("xCoord", "x")
    # isla = isla.replace("yCoord", "y")
    # isla = isla.replace(',"owner', ',"')

    # # {"id":idIsla,"name":nombreIsla,"x":,"y":,"good":numeroBien,"woodLv":,"goodLv":,"wonder":numeroWonder, "wonderName": "nombreDelMilagro","wonderLv":"5","cities":[{"type":"city","name":cityName,"id":cityId,"level":lvIntendencia,"Id":playerId,"Name":playerName,"AllyId":,"AllyTag":,"state":"vacation"},...}}
    # isla = json.loads(isla, strict=False)
    # isla["tipo"] = re.search(r'"tradegood":(\d)', html).group(1)
    # isla["x"] = int(isla["x"])
    # isla["y"] = int(isla["y"])

    # return isla


def getCity(html: str) -> FullCityDict:
    """This function uses the ``html`` passed to it as a string to extract, parse and return a City object
    Parameters
    ----------
    html : str
        the html returned when a get request to view the city is made. This request can be made with the following statement: ``s.get(urlCiudad + id)``, where urlCiudad is a string defined in ``config.py`` and id is the id of the city.

    Returns
    -------
    city : dict
        this function returns a json parsed City object. For more information about this object refer to the github wiki page of Ikabot.
    """

    city = re.search(
        r'"updateBackgroundData",\s?([\s\S]*?)\],\["updateTemplateData"', html
    ).group(1)
    city = json.loads(city, strict=False)

    city["ownerId"] = city.pop("ownerId")
    city["ownerName"] = decodeUnicodeEscape(city["ownerName"])
    city["x"] = int(city["islandXCoord"])
    city["y"] = int(city["islandYCoord"])
    city["cityName"] = decodeUnicodeEscape(city["name"])
    city["name"] = decodeUnicodeEscape(city["name"])

    i = 0
    for position in city["position"]:
        position["position"] = i
        i += 1
        if "level" in position:
            position["level"] = int(position["level"])
        position["isBusy"] = False
        if "constructionSite" in position["building"]:
            position["isBusy"] = True
            position["building"] = position["building"][:-17]
        elif "buildingGround " in position["building"]:
            position["name"] = "empty"
            position["type"] = position["building"].split(" ")[-1]
            position["building"] = "empty"

    city["id"] = str(city["id"])
    city["isOwnCity"] = True
    city["availableResources"] = getAvailableResources(html, num=True)
    city["storageCapacity"] = getWarehouseCapacity(html)
    city["freeCitizens"] = getFreeCitizens(html)
    city["wineConsumptionPerHour"] = getWineConsumptionPerHour(html)
    city["resourcesListedForSale"] = getResourcesListedForSale(html)
    city["freeSpaceForResources"] = []
    for i in range(5):
        city["freeSpaceForResources"].append(
            city["storageCapacity"]
            - city["availableResources"][i]
            - city["resourcesListedForSale"][i]
        )

    return city

def getTransportLoadingAndTravelTime(html: str, totalResources = 0, useFreighters = False, capacityPerTransportPercent = 100, tritonBoostPercent = 0) -> tuple[int, int, int, int]:
    """Gets total loading and travel time for a shipment.
    Parameters
    ----------
    html : str
        text of the response obtained when requesting the `transport` view from the trading port
    totalResources : int
        total amount of resources that are being sent
    useFreighters : bool
        whether or not freighters will be used for this shipment (increases travel time by 20x)
    capacityPerTransportPercent : int
        percentage of the total capacity for each transport. Lowering this decreases travel time but also decreases the number of resources that can be sent. 
        Possible values are 100, 80, 60, 40, 20. These correspond to a 0, 16.7, 33.3, 50, and 66.7 % speed boost respectively
    tritonBoostPercent : int
        percentage speed boost gained from triton engines. Possible values are 0, 100, 200 and 300

    Returns
    -------
    totalTime : int
        loading time + travel time + queueTime
    loadingTime : int
        seconds it takes to load resources. This only depends on the number of resources and trading port level.
    travelTime : int
        seconds it takes to travel to the destination. Depends on distance, transporter type and world, government, triton, poseidon, sea chart archive bonuses
    queueTime : int
        seconds it takes for port to load OTHER shipments. 0 if port is not busy currently
    """
    assert capacityPerTransportPercent in [100, 80, 60, 40, 20], 'Please enter valid capacityPerTransportPercent, available values are 100, 80, 60, 40, 20'
    assert tritonBoostPercent in [0, 100, 200, 300], 'Please enter valid tritonBoostPercent, available values are 0, 100, 200, 300'
    
    # get relevant bonuses and parmeters from response
    transporterSpeed = float(re.search(r"'transporterSpeed': ([\d\.]+),", html).group(1))
    worldBonus = float(re.search(r"'worldBonus': ([\d\.]+),", html).group(1))
    governmentBonus = float(re.search(r"'governmentBonus': ([\d\.]+),", html).group(1))
    poseidonEffect = float(re.search(r"'poseidonEffect': ([\d\.]+),", html).group(1))
    marineChartArchiveBonus = float(re.search(r"'marineChartArchiveBonus': ([\d\.]+),", html).group(1))
    minimumJourneyDuration = int(re.search(r"'minimumJourneyDuration': (\d+),", html).group(1))
    distance = float(re.search(r"'distance': ([\d\.]+),", html).group(1))
    fleetJourneyTime = int(re.search(r"'fleetJourneyTime': (\d+),", html).group(1))
    queueTime = int(re.search(r"'queueTime': (\d+),", html).group(1))
    loadingSpeed = float(re.search(r"'loadingSpeed': ([\d\.]+),", html).group(1))
    
    # make sure queue time is not in the past
    queueTime = 0 if queueTime - time.time() <= 0 else int(queueTime - time.time())
    
    # calculate loading time
    loadingTime = int(totalResources / loadingSpeed)

    # calculate travel time            # lower capacity actually speeds up the transporter speed instead of lowering total travel time, this is stupid
    fleetSpeed = floor(transporterSpeed *  (1.0 + (-0.835 * capacityPerTransportPercent + 83.5) / 100 ) ) * worldBonus * governmentBonus * (1.0 + poseidonEffect + tritonBoostPercent / 100)
    uncappedDuration = int(ceil(((distance * fleetJourneyTime) / fleetSpeed) * marineChartArchiveBonus))
    uncappedDuration *= 20 if useFreighters else 1

    travelTime = uncappedDuration if uncappedDuration > minimumJourneyDuration else minimumJourneyDuration

    return  travelTime + loadingTime + queueTime, loadingTime, travelTime, queueTime
