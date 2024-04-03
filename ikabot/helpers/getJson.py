#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import time
from math import ceil, floor
from ikabot.helpers.resources import *
from ikabot.helpers.varios import decodeUnicodeEscape


def getFreeCitizens(html):
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
    return int(freeCitizens.replace(",", "").replace(".", ""))


def getResourcesListedForSale(html):
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


def getIsland(html):
    """This function uses the html passed to it as a string to extract, parse and return an Island object
    Parameters
    ----------
    html : str
        the html returned when a get request to view the island is made. This request can be made with the following statement: ``s.get(urlIsla + islandId)``, where ``urlIsla`` is a string defined in ``config.py`` and ``islandId`` is the id of the island.

    Returns
    -------
    island : Island
        this function returns a json parsed Island object. For more information about this object refer to the github wiki page of Ikabot.
    """
    isla = (
        re.search(
            r'\[\["updateBackgroundData",([\s\S]*?),"specialServerBadges', html
        ).group(1)
        + "}"
    )

    isla = isla.replace("buildplace", "empty")
    isla = isla.replace("xCoord", "x")
    isla = isla.replace("yCoord", "y")
    isla = isla.replace(',"owner', ',"')

    # {"id":idIsla,"name":nombreIsla,"x":,"y":,"good":numeroBien,"woodLv":,"goodLv":,"wonder":numeroWonder, "wonderName": "nombreDelMilagro","wonderLv":"5","cities":[{"type":"city","name":cityName,"id":cityId,"level":lvIntendencia,"Id":playerId,"Name":playerName,"AllyId":,"AllyTag":,"state":"vacation"},...}}
    isla = json.loads(isla, strict=False)
    isla["tipo"] = re.search(r'"tradegood":(\d)', html).group(1)
    isla["x"] = int(isla["x"])
    isla["y"] = int(isla["y"])

    return isla


def getCity(html):
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
    city["ownerName"] = decodeUnicodeEscape(city.pop("ownerName"))
    city["x"] = int(city.pop("islandXCoord"))
    city["y"] = int(city.pop("islandYCoord"))
    city["cityName"] = decodeUnicodeEscape(city["name"])

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

def getTransportLoadingAndTravelTime(html, totalResources = 0, useFreighters = False, capacityPerTransportPercent = 100, tritonBoostPercent = 0):
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