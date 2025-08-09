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


def getProductionPerHour(session, city_id):
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
    luxury_type_match = re.search(r'tradegood&type=(\d+)', prod)
    if not luxury_type_match:
        raise ValueError(f"Could not determine luxury resource type for city {city_id}")
    luxury_type = int(luxury_type_match.group(1))

    # The group ([\d,\s]+) now matches digits, commas, AND spaces.
    production_pattern = r'<td id="{}"[^>]*>\s*([\d,\s]+)\s*</td>'

    # Get wood production
    wood_match = re.search(production_pattern.format("js_GlobalMenu_resourceProduction"), prod)
    # Get luxury production
    luxury_match = re.search(production_pattern.format(resource_search_pool[luxury_type]), prod)

    if not wood_match or not luxury_match:
        raise AttributeError("Could not find production values. The game's HTML may have changed.")
    
    # helper function to strip all non-digit characters.
    def clean_number(num_str):
        return re.sub(r'[^\d]', '', num_str)

    # Use the helper to clean the strings before converting to int.
    wood_prod = int(clean_number(wood_match.group(1)))
    luxury_prod = int(clean_number(luxury_match.group(1)))

    wood_production = Decimal(wood_prod)
    luxury_production = Decimal(luxury_prod)
    luxury_resource_type = int(luxury_type)

    return wood_production, luxury_production, luxury_resource_type