#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import sys
from decimal import Decimal

import ikabot.config as config
from ikabot.config import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import banner, bcolors, enter
from ikabot.helpers.naval import (
    getAvailableFreighters,
    getAvailableShips,
    getTotalFreighters,
    getTotalShips,
)
from ikabot.helpers.pedirInfo import getIdsOfCities, read
from ikabot.helpers.varios import getDateTime
from ikabot.function.stationArmy import getCityMilitaryData


def _parse_amount(text):
    cleaned = re.sub(r"[^\d]", "", text)
    return int(cleaned) if cleaned else 0


def _parse_military_section(html, section_class):
    pattern = r'<div class="{} (.*?)">\s*<div class="tooltip">(.*?)</div>'.format(
        section_class
    )
    unit_id_names = re.findall(pattern, html)
    unit_amounts = re.findall(r"<td>\s*([^<]+)\s*</td>", html)

    entries = []
    for i in range(min(len(unit_id_names), len(unit_amounts))):
        unit_id = unit_id_names[i][0]
        if unit_id.startswith("s"):
            unit_id = unit_id[1:]
        entries.append(
            {
                "id": unit_id,
                "name": unit_id_names[i][1],
                "amount": _parse_amount(unit_amounts[i]),
            }
        )
    return entries


def _get_city_global_header(session):
    data = session.get("view=updateGlobalData&ajax=1", noIndex=True)
    json_data = json.loads(data, strict=False)
    return json_data[0][1]["headerData"]


def exportCityInfo(session, event, stdin_fd, predetermined_input):
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
        print(
            "{}WARNING:{} This export contains account-identifying information.".format(
                bcolors.WARNING, bcolors.ENDC
            )
        )
        print("")

        home = "USERPROFILE" if isWindows else "HOME"
        default_dir = os.path.join(os.getenv(home), "ikabot_exports")
        default_name = "cities_export_{}.json".format(getDateTime())
        output_dir = read(
            msg="Output directory (default: {}): ".format(default_dir),
            default=default_dir,
        )
        output_dir = output_dir.strip() if output_dir else default_dir
        filename = read(
            msg="Output filename (default: {}): ".format(default_name),
            default=default_name,
        )
        filename = filename.strip() if filename else default_name
        if not filename.lower().endswith(".json"):
            filename += ".json"

        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, filename)

        ids, _ = getIdsOfCities(session)
        export_data = {
            "exported_at": getDateTime(),
            "server": session.servidor,
            "world": session.mundo,
            "player": session.username,
            "merchant_ships": {
                "available": getAvailableShips(session),
                "total": getTotalShips(session),
            },
            "freighters": {
                "available": getAvailableFreighters(session),
                "total": getTotalFreighters(session),
            },
            "cities": [],
        }

        for index, city_id in enumerate(ids, start=1):
            print("Collecting city {}/{}...".format(index, len(ids)))
            html = session.get(city_url + city_id, noIndex=True)
            city = getCity(html)

            header = _get_city_global_header(session)
            resources = city["availableResources"]
            resources_listed = city["resourcesListedForSale"]
            free_space = city["freeSpaceForResources"]

            wood_per_hour = int(Decimal(header["resourceProduction"]) * 3600)
            luxury_type = int(header["producedTradegood"])
            luxury_per_hour = int(Decimal(header["tradegoodProduction"]) * 3600)
            production = {
                materials_names[0]: wood_per_hour,
                materials_names[luxury_type]: luxury_per_hour,
            }

            military_html = getCityMilitaryData(session, city_id)
            army_section = military_html.split('<div class="fleet')[0]
            fleet_section_parts = military_html.split('<div class="fleet', 1)
            fleet_section = ""
            if len(fleet_section_parts) > 1:
                fleet_section = '<div class="fleet' + fleet_section_parts[1]

            army_units = _parse_military_section(army_section, "army")
            fleet_units = (
                _parse_military_section(fleet_section, "fleet") if fleet_section else []
            )

            buildings = []
            for building in city["position"]:
                if building["name"] == "empty":
                    continue
                buildings.append(
                    {
                        "position": building.get("position"),
                        "name": building.get("name"),
                        "building": building.get("building"),
                        "level": building.get("level"),
                        "isBusy": building.get("isBusy"),
                        "canUpgrade": building.get("canUpgrade"),
                        "isMaxLevel": building.get("isMaxLevel"),
                    }
                )

            export_data["cities"].append(
                {
                    "id": city["id"],
                    "name": city["cityName"],
                    "island": {
                        "id": city["islandId"],
                        "name": city["islandName"],
                        "x": city["islandXCoord"],
                        "y": city["islandYCoord"],
                    },
                    "resources": dict(zip(materials_names, resources)),
                    "resources_listed_for_sale": dict(
                        zip(materials_names, resources_listed)
                    ),
                    "free_space_for_resources": dict(zip(materials_names, free_space)),
                    "storage_capacity": city["storageCapacity"],
                    "population": header["currentResources"]["population"],
                    "citizens": header["currentResources"]["citizens"],
                    "free_citizens": city["freeCitizens"],
                    "wine_consumption_per_hour": city["wineConsumptionPerHour"],
                    "production_per_hour": production,
                    "buildings": buildings,
                    "army_units": army_units,
                    "fleet_units": fleet_units,
                }
            )

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=True)

        banner()
        print(
            "{}SUCCESS!{} Exported city details to {}".format(
                bcolors.GREEN, bcolors.ENDC, out_path
            )
        )
        enter()
        event.set()
    except KeyboardInterrupt:
        event.set()
        return
