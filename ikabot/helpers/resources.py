#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
from decimal import *

from ikabot.config import *

getcontext().prec = 30


def getAvailableResources(html, num=False):
    """
    Parameters
    ----------
    html : string

    Returns
    -------
    resources_available : list[int] | list[str]
    """
    resources = re.search(
        r'\\"resource\\":(\d+),\\"2\\":(\d+),\\"1\\":(\d+),\\"4\\":(\d+),\\"3\\":(\d+)}',
        html,
    )
    if num:
        return [
            int(resources.group(1)),
            int(resources.group(3)),
            int(resources.group(2)),
            int(resources.group(5)),
            int(resources.group(4)),
        ]
    else:
        return [
            resources.group(1),
            resources.group(3),
            resources.group(2),
            resources.group(5),
            resources.group(4),
        ]


def getWarehouseCapacity(html):
    """
    Parameters
    ----------
    html : string
    Returns
    -------
    capacity : int
    """
    capacity = re.search(
        r'maxResources:\s*JSON\.parse\(\'{\\"resource\\":(\d+),', html
    ).group(1)
    return int(capacity)


def getWineConsumptionPerHour(html):
    """
    Parameters
    ----------
    html : string
    Returns
    -------
    capacity : int
    """
    result = re.search(r"wineSpendings:\s(\d+)", html)
    if result:
        return int(result.group(1))
    return 0


def getProductionPerSecond(session, city_id):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int

    Returns
    -------
    production: tuple[Decimal, Decimal, int]
    """
    resource_search_pool = {
        1: "js_GlobalMenu_production_wine",
        2: "js_GlobalMenu_production_marble",
        3: "js_GlobalMenu_production_crystal",
        4: "js_GlobalMenu_production_sulfur",
    }

    prod = session.get('?view=city&cityId=' + city_id)
    luxury_type = re.search(r'tradegood&type=(\d+)', prod)
    luxury_type = int(luxury_type.group(1))
    
    #get wood production
    match = re.search(r'<td id="js_GlobalMenu_resourceProduction"[^>]*>\s*(\d+)\s*</td>', prod)
    wood_prod = int(match.group(1))

    #get luxury production
    match = re.search(fr'<td id="{resource_search_pool[int(luxury_type)]}"[^>]*>\s*(\d+)\s*</td>', prod)
    luxury_prod = int(match.group(1))

    #get luxury production
    wood_production = Decimal(wood_prod)
    luxury_production = Decimal(luxury_prod)
    luxury_resource_type = int(luxury_type)

    return wood_production, luxury_production, luxury_resource_type
