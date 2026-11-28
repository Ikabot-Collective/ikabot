#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import math
import time
import traceback
import re
from decimal import *
from collections import defaultdict

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.decorators import configurator, task
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.naval import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planRoutes import waitForArrival
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *
from ikabot.helpers.pedirInfo import getShipCapacity

from ikabot.helpers.taskConfig import asBool, asInt, getCityById, requireOwnCity
from ikabot.function.activateMiracle import obtainMiraclesAvailable
from ikabot.function.sendResources import get_island
from ikabot.function.attackBarbarians import (
    get_barbarians_info,
    get_current_attacks,
    filter_loading,
    filter_traveling,
    wait_until_attack_is_over,
    wait_for_round,
    wait_for_arrival,
    get_barbarians_lv,
    get_units,
    get_unit_data,
    load_troops,
    get_movements,
)


DEFAULT_SCHEMATICS = {
    "WITH_HEPHAESTUS": [
        # TODO Develop the preset here for when Hephaestus is available
    ],
    "WITHOUT_HEPHAESTUS": [
        {
            "level": (1, 9),
            "looting": {"from_float": False, "units": {"302": 1}},
            "needed_units": {"main": {"302": 90, "304": 21}},
            "waves": {
                "1": {
                    "send": [{"from_float": False, "units": {"302": 90, "304": 21}}],
                }
            },
        },
        {
            "level": (10, 19),
            "looting": {"from_float": False, "units": {"305": 12, "308": 50}},
            "needed_units": {"main": {"302": 60, "304": 35, "305": 12, "308": 50}},
            "waves": {
                "1": {
                    "send": [
                        {
                            "from_float": False,
                            "units": {"302": 60, "304": 35, "305": 12, "308": 50},
                        },
                    ],
                },
            },
        },
        {
            "level": (20, 29),
            "looting": {"from_float": False, "units": {"305": 12, "308": 100}},
            "needed_units": {
                "main": {
                    "302": 60,
                    "304": 70,
                    "305": 12,
                    "307": 12,
                    "308": 100,
                    "309": 30,
                    "310": 5,
                }
            },
            "waves": {
                "1": {
                    "send": [
                        {
                            "from_float": False,
                            "units": {
                                "302": 60,
                                "304": 70,
                                "305": 12,
                                "307": 12,
                                "308": 100,
                                "309": 30,
                                "310": 5,
                            },
                        },
                    ],
                },
            },
        },
        {
            "level": (30, 39),
            "looting": {"from_float": False, "units": {"305": 24, "308": 150}},
            "needed_units": {
                "main": {
                    "302": 300,
                    "304": 147,
                    "305": 24,
                    "307": 18,
                    "308": 300,
                    "310": 5,
                    "311": 10,
                }
            },
            "waves": {
                "1": {
                    "send": [
                        {
                            "from_float": False,
                            "units": {
                                "302": 300,
                                "304": 147,
                                "305": 24,
                                "307": 18,
                                "308": 300,
                                "310": 5,
                                "311": 10,
                            },
                        },
                    ],
                },
            },
        },
    ],
}


try:
    from ikabot.helpers.logging import getLogger

    _logger = getLogger(__name__)
except Exception:
    import logging

    _logger = logging.getLogger(__name__)

FIVE_MINUTES = 5 * 60
DEVELOPMENT = False





def choose_island(session):
    idsIslands = getIslandsIds(session)
    islands = []
    for idIsland in idsIslands:
        html = session.get(island_url + idIsland)
        island = getIsland(html)
        islands.append(island)

    if len(islands) == 1:
        return islands[0]

    islands.sort(key=lambda island: island["id"])

    longest_island_name_length = 0
    for island in islands:
        longest_island_name_length = max(
            len(island["name"]), longest_island_name_length
        )

    def pad(island_name):
        return " " * (longest_island_name_length - len(island_name)) + island_name

    print("In which island do you want to attack the barbarians?")
    print(" 0) Exit")
    for i, island in enumerate(islands):
        num = " " + str(i + 1) if i < 9 else str(i + 1)
        if island["barbarians"]["destroyed"] == 1:
            warn = "(currently destroyed)"
        else:
            warn = ""
        print(
            "{}) [{}:{}] {} ({}) : barbarians lv: {} ({}) {}".format(
                num,
                island["x"],
                island["y"],
                pad(island["name"]),
                materials_names[int(island["tradegood"])][0].upper(),
                island["barbarians"]["level"],
                island["barbarians"]["city"],
                warn,
            )
        )

    index = read(min=0, max=len(islands))
    if index == 0:
        return None
    else:
        return islands[index - 1]


def is_hephaestus_max(islands):
    for island in islands:
        if int(island["wonder"]) == 5 and island["wonderActivationLevel"] == 5:
            return True
    return False


def choose_schematic():
    print("Select what type of attack sequence you will do:")
    print("(0) Exit")
    print("(1) Default")
    print("(2) Custom")
    selected = read(min=0, max=2, digit=True)
    if selected == 0:
        return

    return selected


def check_need_float_city(schematic):
    return any(
        any(
            any(send.get("from_float", False) for send in wave_data.get("send", []))
            for wave_data in item.get("waves", {}).values()
        )
        or item.get("looting", {}).get("from_float", False)
        for item in schematic
    )


def choose_float_city(session, island):
    ids, cities = getIdsOfCities(session)
    inslands_cities = {}
    for city_id in cities:
        city = cities[city_id]

        html = session.get(city_url + str(city["id"]))
        city = getCity(html)

        if island["id"] == city["islandId"]:
            inslands_cities[city_id] = city

    if len(inslands_cities) == 1:
        return next(iter(inslands_cities.values()))

    print("Select the city where the float will be located:\n")
    menu_cities = ""
    longest_city_name_length = 0
    for city_id in inslands_cities:
        length = len(cities[city_id]["name"])
        if length > longest_city_name_length:
            longest_city_name_length = length

    def pad(city_name):
        return " " * (longest_city_name_length - len(city_name) + 2)

    i = 0
    cities_options = {}
    for city_id in ids:
        city = inslands_cities.get(city_id)
        if city is None:
            continue
        i += 1
        cities_options[i] = city_id
        city_name = decodeUnicodeEscape(cities[city_id]["name"])
        menu_cities += "{: >2}: {}{}\n".format(i, city_name, pad(city_name))
    menu_cities = menu_cities[:-1]
    print(menu_cities)
    cities_options_index = read(min=1, max=len(cities_options))
    return inslands_cities.get(cities_options[cities_options_index])


def get_max_schematics_units(schematic):
    max_units = {
        "main": defaultdict(int),
        "float": defaultdict(int),
        "total": defaultdict(int),
    }

    if isinstance(schematic, dict):
        schematic = [schematic]

    for item in schematic:
        needed_units = item.get("needed_units", {})

        for category in ("main", "float"):
            units = needed_units.get(category, {})
            for unit_id, unit_amount in units.items():
                max_units[category][unit_id] = max(
                    max_units[category][unit_id], unit_amount
                )

    for unit_id in set(max_units["main"].keys()).union(max_units["float"].keys()):
        max_units["total"][unit_id] = max_units["main"].get(unit_id, 0) + max_units[
            "float"
        ].get(unit_id, 0)

    return {key: dict(value) for key, value in max_units.items()}


def get_schematic_information(
    session, city, schematic, ship_capacity, float_city=None, is_in_island=False
):
    schematic_units = get_max_schematics_units(schematic)
    main_city_units = get_units(session, city)
    float_city_units = {}
    if float_city is not None:
        float_city_units = get_units(session, float_city)
        pass

    units_data = {}
    for unit_id in schematic_units["total"].keys():
        units_data[unit_id] = get_unit_data(session, city["id"], str(unit_id))

    schematic_ships = 2
    if is_in_island is False:
        schematic_ships += get_amount_ships_schematic(
            schematic_units["total"], units_data, ship_capacity
        )

    def get_success():
        return all(
            [
                all(
                    main_city_units.get(unit_id, {"amount": 0})["amount"] >= amount
                    for unit_id, amount in schematic_units["main"].items()
                ),
                (
                    all(
                        float_city_units.get(unit_id, {"amount": 0})["amount"] >= amount
                        for unit_id, amount in schematic_units["float"].items()
                    )
                    if float_city is not None
                    else True
                ),
            ]
        )

    return get_success(), {
        "units_data": units_data,
        "schematic_units": schematic_units,
        "main_city_units": main_city_units,
        "float_city_units": float_city_units,
        "schematic_ships": schematic_ships,
    }
    # return all(main_city_units.get(unit_id, {'amount': 0})['amount'] >= amount for unit_id, amount in schematic_units.items()),units_data,schematic_units,main_city_units,schematic_ships


def print_grid_units(schematic_units, city_units, schematic_ships, ships_available):
    header = ["Unit", "Required", "Available", "Missing"]
    table = []

    for unit_id, required in schematic_units.items():
        available = city_units.get(unit_id, 0)
        missing = max(0, required - available["amount"])
        table.append([available["name"], required, available["amount"], missing])

    col_widths = [
        max(len(str(row[i])) for row in table + [header]) for i in range(len(header))
    ]
    separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

    def format_row(row):
        return (
            "| "
            + " | ".join(
                f"{str(cell).ljust(col_widths[i])}" for i, cell in enumerate(row)
            )
            + " |"
        )

    print(separator)
    print(format_row(header))
    print(separator)
    for row in table:
        print(format_row(row))
    print(separator)
    footer = [
        "ships",
        str(schematic_ships),
        str(ships_available),
        max(0, int(schematic_ships) - int(ships_available)),
    ]
    print(format_row(footer))
    print(separator)


def get_barbarians_attack_plan(barbarians_info, schematic):
    barbarians_level = int(barbarians_info["level"])
    selected_scheme = None
    for scheme in schematic:
        if isinstance(scheme["level"], (tuple, list)):
            if barbarians_level in range(scheme["level"][0], (scheme["level"][1] + 1)):
                selected_scheme = scheme
                break
        elif isinstance(scheme["level"], int) and barbarians_level == scheme["level"]:
            selected_scheme = scheme
            break

    if selected_scheme is None:
        return

    return {
        "waves": selected_scheme["waves"],
        "looting": selected_scheme["looting"],
        "needed_units": get_max_schematics_units(selected_scheme),
    }


def get_amount_ships_schematic(schematic_units, units_data, ship_capacity):
    schematic_weight = 0.0
    schematic_ships = 2

    for unit_id, amount in schematic_units.items():
        schematic_weight += amount * units_data[str(unit_id)]["weight"]

    schematic_ships += math.ceil(Decimal(schematic_weight) / Decimal(ship_capacity))
    return schematic_ships


def has_units_in_city(session, city, units):
    if not isinstance(units, (dict)):
        raise TypeError(
            f"The type provided for units is invalid, a type (tuple | dict | list) is expected and its type is {type(units)}"
        )
    city_units = get_units(session, city)

    def has_unit(unit_id, unit_amount):
        unit = city_units.get(str(unit_id))
        if unit is None:
            return False
        return True if unit["amount"] >= unit_amount else False

    return all(
        [has_unit(unit_id, unit_amount) for unit_id, unit_amount in units.items()]
    )


SCHEMATIC_NAMES = {"default": "WITHOUT_HEPHAESTUS", "without_hephaestus": "WITHOUT_HEPHAESTUS"}


def schematic_units(value, name):
    """{"unit id": amount} with ids as text and amounts as whole numbers"""
    if not isinstance(value, dict) or not value:
        raise ValueError('{} must be an object like {{"302": 90}}, got {!r}'.format(name, value))
    units = {}
    for unit_id, amount in value.items():
        text = str(unit_id).strip()
        if not text.isdigit():
            raise ValueError("{}: {!r} is not a unit id".format(name, unit_id))
        units[text] = asInt(amount, "{}.{}".format(name, text), minimum=0)
    return units


def check_schematic(value):
    """The attack scheme: "default", or a list of levels like the default one
    Parameters
    ----------
    value : str or list[dict]
        each item: {"level": N or [from, to], "looting": {"from_float", "units"},
        "waves": {"1": {"send": [{"from_float", "units"}, ...]}, ...}, "needed_units" (optional)}

    Returns
    -------
    schematic : list[dict]
    """
    if isinstance(value, str):
        key = SCHEMATIC_NAMES.get(value.strip().lower())
        if key is None or not DEFAULT_SCHEMATICS.get(key):
            raise ValueError('schematic must be "default" or a list of levels, got {!r}'.format(value))
        return DEFAULT_SCHEMATICS[key]
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError('schematic must be "default" or a list of levels, got {!r}'.format(value))
    checked = []
    for i, item in enumerate(value):
        name = "schematic[{}]".format(i)
        if not isinstance(item, dict):
            raise ValueError("{} must be an object, got {!r}".format(name, item))
        level = item.get("level")
        if isinstance(level, (list, tuple)) and len(level) == 2:
            level = [asInt(level[0], name + ".level", minimum=1), asInt(level[1], name + ".level", minimum=1)]
            if level[0] > level[1]:
                raise ValueError("{}.level goes from {} down to {}".format(name, level[0], level[1]))
        else:
            level = asInt(level, name + ".level", minimum=1)
        looting = item.get("looting")
        if not isinstance(looting, dict):
            raise ValueError('{}.looting must be an object like {{"from_float": false, "units": {{"302": 1}}}}'.format(name))
        looting = {"from_float": asBool(looting.get("from_float", False), name + ".looting.from_float"),
                   "units": schematic_units(looting.get("units"), name + ".looting.units")}
        waves = item.get("waves")
        if not isinstance(waves, dict) or not waves:
            raise ValueError('{}.waves must be an object like {{"1": {{"send": [...]}}}}'.format(name))
        checked_waves = {}
        for wave_id, wave in waves.items():
            wave_name = "{}.waves.{}".format(name, wave_id)
            asInt(wave_id, wave_name, minimum=1)
            sends = wave.get("send") if isinstance(wave, dict) else None
            if not isinstance(sends, (list, tuple)) or not sends:
                raise ValueError("{}.send must be a list of groups of units".format(wave_name))
            checked_waves[str(int(wave_id))] = {"send": [
                {"from_float": asBool(send.get("from_float", False), "{}.send[{}].from_float".format(wave_name, j)),
                 "units": schematic_units(send.get("units"), "{}.send[{}].units".format(wave_name, j))}
                if isinstance(send, dict) else schematic_units(None, "{}.send[{}]".format(wave_name, j))
                for j, send in enumerate(sends)
            ]}
        needed = item.get("needed_units")
        if needed is None:
            # every unit the waves send, from each city
            needed = {"main": {}, "float": {}}
            for wave in checked_waves.values():
                for send in wave["send"]:
                    group = needed["float" if send["from_float"] else "main"]
                    for unit_id, amount in send["units"].items():
                        group[unit_id] = group.get(unit_id, 0) + amount
        elif not isinstance(needed, dict):
            raise ValueError("{}.needed_units must be an object with main and float units".format(name))
        else:
            needed = {group: schematic_units(needed[group], "{}.needed_units.{}".format(name, group))
                      for group in ("main", "float") if needed.get(group)}
        checked.append({"level": level, "looting": looting, "waves": checked_waves, "needed_units": needed})
    return checked


def schematic_levels(schematic):
    return ", ".join(
        "{}-{}".format(*item["level"]) if isinstance(item["level"], (list, tuple)) else str(item["level"])
        for item in schematic
    )


def schematic_from_saved(schematic):
    """An older menu saved the default scheme itself: keep its name"""
    default = json.loads(json.dumps(DEFAULT_SCHEMATICS["WITHOUT_HEPHAESTUS"]))
    if isinstance(schematic, (list, tuple)) and json.loads(json.dumps(schematic)) == default:
        return "default"
    return schematic


def auto_ids_from_saved(island_id, city_id, float_city_id, island, city, float_city):
    """An older menu saved the whole island and cities"""
    if isinstance(island, dict):
        island_id = island.get("id")
    if isinstance(city, dict):
        city_id = city.get("id")
    if isinstance(float_city, dict):
        float_city_id = float_city.get("id")
    return island_id, city_id, float_city_id


def prepare_autoBarbarians(session, island_id=None, city_id=None, float_city_id=None, schematic="default",
                           send_notifications=True, island=None, city=None, float_city=None, units_data=None,
                           ship_capacity=None):
    """Checks the config of an autoBarbarians task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    island_id : int or str
        the island of the barbarians, by id or "X:Y"
    city_id : int or str
        one of your cities, the troops leave from it
    float_city_id : int or str
        one of your cities on that island, only when the scheme sends units from it
    schematic : str or list
        "default", or the levels and waves of your own scheme
    send_notifications : bool
    island, city, float_city, units_data, ship_capacity :
        saved by older menus

    Returns
    -------
    config : dict
    """
    island_id, city_id, float_city_id = auto_ids_from_saved(island_id, city_id, float_city_id, island, city, float_city)
    if island is not None:
        schematic = schematic_from_saved(schematic)
    for key, value in (("island_id", island_id), ("city_id", city_id)):
        if value is None:
            raise ValueError("{} is needed".format(key))
    city_id = requireOwnCity(session, city_id, "city_id")
    found = get_island(session, island_id, "island_id")
    if not isinstance(found.get("barbarians"), dict):
        raise ValueError("island {}:{} has no barbarian village".format(found["x"], found["y"]))
    checked = check_schematic(schematic)
    known = get_units(session, getCityById(session, city_id))
    used = set(get_max_schematics_units(checked)["total"]) | {u for item in checked for u in item["looting"]["units"]}
    unknown = sorted(u for u in used if u not in known)
    if unknown:
        raise ValueError("the schematic uses units {} that are not units of the city. Units: {}".format(
            unknown, ", ".join("{} = {}".format(uid, unit["name"]) for uid, unit in known.items())))
    level = found["barbarians"].get("level")
    if get_barbarians_attack_plan({"level": level}, checked) is None:
        raise ValueError("the barbarians of {}:{} are level {}, the schematic covers levels {}".format(
            found["x"], found["y"], level, schematic_levels(checked)))
    config = {
        "island_id": str(found["id"]),
        "city_id": city_id,
        "float_city_id": None,
        "schematic": "default" if isinstance(schematic, str) else checked,
        "send_notifications": asBool(send_notifications, "send_notifications"),
    }
    if check_need_float_city(checked):
        if float_city_id is None:
            raise ValueError("float_city_id is needed: the schematic sends units from a city on the island {}:{}".format(found["x"], found["y"]))
        float_city_id = requireOwnCity(session, float_city_id, "float_city_id")
        if str(getCityById(session, float_city_id)["islandId"]) != str(found["id"]):
            raise ValueError("float_city_id {} is not on the island {}:{}".format(float_city_id, found["x"], found["y"]))
        config["float_city_id"] = float_city_id
    return config


@task("autoBarbarians", prepare=prepare_autoBarbarians)
def do_it(session, island_id=None, city_id=None, float_city_id=None, schematic="default", send_notifications=True,
          island=None, city=None, float_city=None, units_data=None, ship_capacity=None):
    """Attacks the barbarians of the island again and again, with the waves of the scheme for
    their level, until they reach a level the scheme does not cover
    Parameters
    ----------
    session : ikabot.web.session.Session
    island_id, city_id, float_city_id : str
    schematic : str or list
    send_notifications : bool
    island, city, float_city, units_data, ship_capacity :
        saved by older menus; the task reads them from the game
    """
    island_id, city_id, float_city_id = auto_ids_from_saved(island_id, city_id, float_city_id, island, city, float_city)
    schematic = check_schematic(schematic_from_saved(schematic))
    island = getIsland(session.get(island_url + str(island_id)))
    city = getCityById(session, city_id)
    float_city = getCityById(session, float_city_id) if float_city_id is not None else None
    ship_capacity, _ = getShipCapacity(session)
    # weight and speed of every unit the scheme sends; load_troops adds any other it meets
    units_data = {}
    for unit_id in get_max_schematics_units(schematic)["total"]:
        units_data[unit_id] = get_unit_data(session, city["id"], str(unit_id))
    info = "\nI grinding the barbarians in [{}:{}]\n".format(
        island["x"], island["y"]
    )
    setInfoSignal(session, info)
    attempts = {"ships": 0}
    first_loop = True
    while True:
        if first_loop is False:
            time.sleep(FIVE_MINUTES)
        else:
            first_loop = False
        html = session.get(island_url + island["id"])
        island = getIsland(html)
        babarians_info = get_barbarians_lv(session, island, ship_capacity)
        barbarians_plan = get_barbarians_attack_plan(babarians_info, schematic)
        if barbarians_plan is None:
            _logger.warning(
                "autoBarbarians stopped: barbarians level %s is outside the attack scheme",
                babarians_info["level"],
            )
            if send_notifications:
                sendToBot(
                    session,
                    "It was not possible to continue the attack on the barbarians because they reached a level that is outside the attack scheme.".format(
                        island["x"], island["y"]
                    ),
                )
            break
        if island["barbarians"]["destroyed"] == 1:
            loot(
                session,
                island,
                city,
                barbarians_plan,
                ship_capacity,
                float_city=float_city,
                units_data=units_data,
            )
            wait_for_looting(session, city, island)
            continue
        ships_available = waitForArrival(session)
        schematic_ships = (
            get_amount_ships_schematic(
                barbarians_plan["needed_units"]["total"], units_data, ship_capacity
            )
            + babarians_info["ships"]
        )
        if schematic_ships > ships_available:
            attempts["ships"] += 1
            session.setStatus(
                "waiting for availability of ({}) boats".format(schematic_ships)
            )
            if attempts["ships"] > 20:
                _logger.warning(
                    "autoBarbarians stopped: ships unavailable for too long (barbarians level %s, need %s, available %s)",
                    babarians_info["level"],
                    schematic_ships,
                    ships_available,
                )
                if send_notifications:
                    sendToBot(
                        session,
                        "It was not possible to continue the attack on the barbarians due to the long unavailability of ships.",
                    )
                break
            continue
        if (
            has_units_in_city(session, city, barbarians_plan["needed_units"]["total"])
            is False
        ):
            needed_units = barbarians_plan["needed_units"]["total"]
            city_units = get_units(session, city)
            missing = {
                unit_id: amount
                - city_units.get(str(unit_id), {"amount": 0})["amount"]
                for unit_id, amount in needed_units.items()
                if city_units.get(str(unit_id), {"amount": 0})["amount"] < amount
            }
            # names as the game shows them, with the id: nobody knows the ids by heart
            missing_text = ", ".join(
                "{} {} ({})".format(amount, city_units.get(str(unit_id), {}).get("name", "unit"), unit_id)
                for unit_id, amount in missing.items()
            )
            _logger.warning(
                "autoBarbarians stopped: not enough troops in city %s for barbarians level %s, missing: %s",
                city["id"],
                babarians_info["level"],
                missing_text,
            )
            session.setStatus("Stopped: {} lacks {} for barbarians level {}".format(
                city["name"], missing_text, babarians_info["level"]))
            if send_notifications:
                sendToBot(
                    session,
                    "It was not possible to continue the attack on the barbarians due to the lack of necessary troops in the city(ies).\n"
                    "{} lacks: {}".format(city["name"], missing_text),
                )
            break
        if send_notifications:
            sendToBot(
                session,
                "Starting attack on barbarians[{}:{}] level ({}).".format(
                    island["x"], island["y"], babarians_info["level"]
                ),
            )
        do_attack(
            session,
            island,
            city,
            barbarians_plan,
            ship_capacity,
            float_city=float_city,
            units_data=units_data,
        )
        wait_until_attack_is_over(session, city, island)
        for attempt_key in attempts.keys():
            attempts[attempt_key] = 0

    babarians_info = get_barbarians_lv(session, island, ship_capacity)
    if send_notifications:
        sendToBot(
            session,
            "Ended attack sequence on bariarians[{}:{}].".format(
                island["x"], island["y"], babarians_info["level"]
            ),
        )


def ordered_waves(waves):
    """The waves in battle order: by number, so wave 10 goes after wave 2"""
    return sorted(waves.items(), key=lambda wave: int(wave[0]))


def do_attack(session, island, city, schematic, ship_capacity, float_city=None, units_data={}):
    battle_start = None
    babarians_info = None

    i = 0
    for wave_id, wave_data in ordered_waves(schematic["waves"]):
        i += 1
        wave_id = int(wave_id)

        major_travel_time = None
        minor_travel_time, minor_travel_city = None, city
        sends_data = split_wave_sends_for_group(wave_id, wave_data)
        float_city_data = None
        if float_city is not None:
            float_city_data = []
            for float_attack_round in sends_data["float_city"]:
                float_attack_data, float_ships_needed, float_travel_time = (
                    get_send_attack_data(
                        session, island, float_city, float_attack_round, units_data, ship_capacity
                    )
                )
                float_city_data.append(
                    {
                        "attack_data": float_attack_data,
                        "travel_time": float_travel_time,
                        "ships_needed": float_ships_needed,
                    }
                )
                if major_travel_time is None or float_travel_time > major_travel_time:
                    major_travel_time = float_travel_time
                if minor_travel_time is None or float_travel_time < minor_travel_time:
                    minor_travel_city = float_city
                    minor_travel_time = float_travel_time

        main_city_data = []
        for main_attack_round in sends_data["main_city"]:
            main_attack_data, main_ships_needed, main_travel_time = (
                get_send_attack_data(
                    session, island, city, main_attack_round, units_data, ship_capacity
                )
            )
            main_city_data.append(
                {
                    "attack_data": main_attack_data,
                    "travel_time": main_travel_time,
                    "ships_needed": main_ships_needed,
                }
            )
            if major_travel_time is None or main_travel_time > major_travel_time:
                major_travel_time = main_travel_time
            if minor_travel_time is None or main_travel_time < minor_travel_time:
                minor_travel_city = city
                minor_travel_time = main_travel_time

        try:
            session.setStatus("Waiting for round (round: {})".format(wave_id))
            wait_for_round(
                session, city, island, major_travel_time, battle_start, wave_id
            )

        except AssertionError:
            # battle ended before expected
            return None

        if babarians_info is None:
            babarians_info = get_barbarians_lv(session, island, ship_capacity)
        if battle_start is None:
            battle_start = time.time() + major_travel_time

        ships_needed = sum([data["ships_needed"] for data in main_city_data])
        if float_city is not None:
            ships_needed += sum([data["ships_needed"] for data in float_city_data])

        assert getTotalShips(session) >= ships_needed, "Insufficient cargo ships!"
        ships_available = waitForArrival(session)
        ships_available -= ships_needed

        looting_wave = True if len(schematic["waves"]) == i else False

        if looting_wave:
            if len(main_city_data) > 0:
                main_city_data[0]["attack_data"]["transporter"] = max(
                    babarians_info["ships"], ships_available
                )
            elif float_city_data:
                float_city_data[0]["attack_data"]["transporter"] = max(
                    babarians_info["ships"], ships_available
                )

        if isinstance(main_city_data, list) and len(main_city_data) > 0:
            for data in main_city_data:
                session.post(params=data["attack_data"])

        if isinstance(float_city_data, list) and len(float_city_data) > 0:
            for data in float_city_data:
                session.post(params=data["attack_data"])

        if wave_id == 1:
            wait_for_arrival(session, minor_travel_city, island)


def split_wave_sends_for_group(wave_id, wave_data):
    send_groups = wave_data.get("send", [])

    float_city = []
    main_city = []

    for group_index, group in enumerate(send_groups, start=1):
        group_id = f"w{wave_id}_g{group_index}"

        group_with_id = group.copy()
        group_with_id["id"] = group_id

        if group["from_float"]:
            float_city.append(group_with_id)
        else:
            main_city.append(group_with_id)

    return {"float_city": float_city, "main_city": main_city}


def loot(session, island, city, schematic, ship_capacity, float_city=None, units_data={}):
    session.setStatus("Looting remaining resources")
    barbarian_countdown = None
    while True:
        babarians_info = get_barbarians_lv(session, island, ship_capacity)
        html = session.get(island_url + island["id"])
        island = getIsland(html)
        destroyed = island["barbarians"]["destroyed"] == 1
        resources = babarians_info["resources"]
        if destroyed is False or sum(resources) == 0:
            break

        attacks = get_current_attacks(session, city["id"], island["id"])
        attacks = filter_loading(attacks) + filter_traveling(attacks)
        if len(attacks) > 0:
            break

        ships_available = waitForArrival(session) - 2
        destin_city = (
            city if schematic["looting"]["from_float"] is False else float_city
        )
        # load_troops() expects a dict with a "units" key; schematic["looting"] has that shape
        attack_data, ships_needed, travel_time = get_send_attack_data(
            session, island, destin_city, schematic["looting"], units_data, ship_capacity
        )
        attack_data["transporter"] = min(ships_available, ships_needed)

        # make sure we have time to send the attack
        if barbarian_countdown is None:
            resp = get_barbarians_info(session, island["id"])
            if "barbarianCityCooldownTimer" in resp[2][1]:
                barbarian_countdown = resp[2][1]["barbarianCityCooldownTimer"][
                    "countdown"
                ]["enddate"]

        time_left = barbarian_countdown - time.time() if barbarian_countdown is not None else None
        send_scatter = False
        if time_left is not None and travel_time > (
            time_left - (travel_time + FIVE_MINUTES)
        ):
            send_scatter = True

        session.post(params=attack_data)

        if send_scatter:
            # same "units" key requirement as above
            ram_attack_data, _, ram_travel_time = get_send_attack_data(
                session, island, destin_city, {"from_float": False, "units": {"307": 1}}, units_data, ship_capacity
            )
            session.post(params=ram_attack_data)
            # wait_next_scatter takes the moment the ram arrives
            new_countdown = wait_next_scatter(session, time.time() + ram_travel_time)
            if new_countdown is not None:
                barbarian_countdown = new_countdown

        time_left = barbarian_countdown - time.time() if barbarian_countdown is not None else None
        if time_left is not None and travel_time > time_left:
            break
        wait_for_arrival(session, city, island)


def get_send_attack_data(session, island, city, attack_round, units_data, ship_capacity):
    attack_data = {
        "action": "transportOperations",
        "function": "attackBarbarianVillage",
        "actionRequest": actionRequest,
        "islandId": island["id"],
        "destinationCityId": 0,
        "cargo_army_304_upkeep": 3,
        "cargo_army_304": 0,
        "cargo_army_315_upkeep": 1,
        "cargo_army_315": 0,
        "cargo_army_302_upkeep": 4,
        "cargo_army_302": 0,
        "cargo_army_303_upkeep": 3,
        "cargo_army_303": 0,
        "cargo_army_312_upkeep": 15,
        "cargo_army_312": 0,
        "cargo_army_309_upkeep": 45,
        "cargo_army_309": 0,
        "cargo_army_307_upkeep": 15,
        "cargo_army_307": 0,
        "cargo_army_306_upkeep": 25,
        "cargo_army_306": 0,
        "cargo_army_305_upkeep": 30,
        "cargo_army_305": 0,
        "cargo_army_311_upkeep": 20,
        "cargo_army_311": 0,
        "cargo_army_310_upkeep": 10,
        "cargo_army_310": 0,
        "transporter": 0,
        "barbarianVillage": 1,
        "backgroundView": "island",
        "currentIslandId": island["id"],
        "templateView": "plunder",
        "ajax": 1,
    }
    return load_troops(session, city, island, attack_round, units_data, attack_data, ship_capacity)


def get_units_scattered(session, city_id=None):
    if city_id is None:
        city_id = getCurrentCityId(session)
    query = {
        "view": "militaryAdvisor",
        "oldView": "updateGlobalData",
        "cityId": city_id,
        "backgroundView": "city",
        "currentCityId": city_id,
        "templateView": "militaryAdvisor",
        "actionRequest": actionRequest,
        "ajax": 1,
    }

    resp = session.post(params=query)
    resp = json.loads(resp, strict=False)

    scattereds = extract_scattered_units(resp[1][1][1])

    return scattereds


def extract_scattered_units(html):
    scattered_units = []

    start_index = html.find('id="scatteredUnitsSidebar"')
    if start_index == -1:
        return scattered_units
    end_index = html.find("</div>", start_index) + len("</div>")
    html = html[start_index:end_index]

    start_index = html.find('<table class="breakdown_table">')
    if start_index == -1:
        return scattered_units
    end_index = html.find("</table>", start_index) + len("</table>")
    html = html[start_index:end_index]

    date_pattern = r"(\d{1,2}\.\d{1,2}\.\d{4}\s\d{1,2}:\d{1,2}:\d{1,2})"
    number_pattern = r"\b:\s(\d)</td>"

    dates = re.findall(date_pattern, html)
    numbers = re.findall(number_pattern, html)

    num_dates = len(dates)
    troop_counts = numbers[-num_dates:]

    for arrival, troop in zip(dates, troop_counts):
        try:
            timestamp = int(datetime.strptime(arrival, "%d.%m.%Y %H:%M:%S").timestamp())
            scattered_units.append({"arrival_time": timestamp, "amount": int(troop)})
        except ValueError:
            continue  # Ignore poorly formatted input

    return scattered_units


def wait_next_scatter(session, travel_time, city_id=None, old_scatter=None):
    if old_scatter is None:
        old_scatter = get_units_scattered(session, city_id)

        wait_time = travel_time
        wait_time -= time.time()
        wait(wait_time + 5)

        new_scatter = get_units_scattered(session, city_id)
        seen = {(entry["arrival_time"], entry["amount"]) for entry in old_scatter}
        new_entries = [
            entry
            for entry in new_scatter
            if (entry["arrival_time"], entry["amount"]) not in seen
        ]
        if len(new_entries) == 0:
            return None

        for entry in new_entries:
            if entry["amount"] == 1:
                return entry["arrival_time"]

    pass


def get_current_looting(session, city_id, island_id):
    movements = get_movements(session, city_id)
    curr_looting = []

    for movement in movements:
        if movement["event"]["mission"] != 13:
            continue
        if movement["target"]["islandId"] != int(island_id):
            continue
        if movement["event"]["isReturning"] != 2:
            continue
        if movement["origin"]["cityId"] == -1:
            continue

        curr_looting.append(movement)

    return curr_looting


def wait_for_looting(session, city, island):
    lootings = get_current_looting(session, city["id"], island["id"])
    lootings = filter_loading(lootings) + filter_traveling(lootings, onlyCanAbort=False)
    eventTimes = [looting["eventTime"] for looting in lootings]

    if len(eventTimes) == 0:
        return

    wait_time = max(eventTimes)
    wait_time -= time.time()
    wait(wait_time + 5)

    wait_for_looting(session, city, island)


@configurator
def autoBarbarians(session, event, stdin_fd, predetermined_input):
    ship_capacity, freighter_capacity = getShipCapacity(session)
    banner()
    print(
        
            "{}⚠️ BEWARE - THE BARBARIAN GRIND TO BE CARRIED OUT MORE EFFICIENTLY REQUIRES THE FOLLOWING RESOURCES ⚠️{}\n".format(
                bcolors.WARNING, bcolors.ENDC
            )
        
    )
    print(
        "- You need to leave at least 3 merchant ships available.",
        "- You leave 2 extra rams available in the city of origin.",
        "- It is not recommended that merchant ships be used during the grind, as maximizing their use increases the efficiency and effectiveness of attacks.",
        sep="\n",
    )
    print(
        
            "\nDo you agree that failure to comply with these rules will result in you losing out on resources? [y/N]"
        
    )
    if read(values=["y", "Y", "n", "N"], default="n") in ["n", "N"]:
        return None

    banner()
    island = choose_island(session)
    if island is None:
        return None

    banner()
    print("From which city do you want to attack?")
    city = chooseCity(session)
    if city is None:
        return None

    has_rams = has_units_in_city(session, city, {"307": 1})
    if has_rams is False:
        print(
            
                "\nYou do not have 2 or more battering rams in this city, the lack of them may prevent you from collecting all the resources present in the barbarian village, are you sure you want to continue anyway? [y/N]"
            
        )
        if read(values=["y", "Y", "n", "N"], default="n") in ["n", "N"]:
            return None

    banner()
    if DEVELOPMENT is True:
        islands = obtainMiraclesAvailable(session)
        hephaestus_max = is_hephaestus_max(islands)
        auto_activate_hephaestus = False
        if hephaestus_max:
            print(
                
                    "Do you want to keep activating your Hephaestus to maximize the grind? [Y/n]"
                
            )
            activate_miracle_input = read(values=["y", "Y", "n", "N", ""])
            auto_activate_hephaestus = (
                True if activate_miracle_input in ("y", "Y") else False
            )

    schematic = DEFAULT_SCHEMATICS["WITHOUT_HEPHAESTUS"]
    if DEVELOPMENT is True:
        banner()
        schematic_option = choose_schematic()
        if schematic_option is None:
            return None

        if schematic_option == 1:
            if auto_activate_hephaestus:
                schematic = DEFAULT_SCHEMATICS["WITH_HEPHAESTUS"]
            pass
        elif schematic_option == 2:
            # TODO do the part where the user can select a custom structure
            pass

    banner()
    success, schematic_informations = get_schematic_information(
        session,
        city,
        schematic,
        ship_capacity,
        is_in_island=True if city["islandId"] == island["id"] else False,
    )
    schematic_units = schematic_informations["schematic_units"]
    main_city_units = schematic_informations["main_city_units"]
    schematic_ships = schematic_informations["schematic_ships"]

    # just read the current count here; waitForArrival() would block the menu in
    # silence until a fleet returns, and do_it() already waits for real ships later
    ships_available = getAvailableShips(session)
    print(
        "For this sequence of attacks you need to have the following troops:\n"
    )
    print_grid_units(
        schematic_units["total"], main_city_units, schematic_ships, ships_available
    )
    if success is False:
        print(
            
                "\nYou do not have all the units needed to start this attack sequence, you want to continue executing the attack only as far as possible? [Y/n]"
            
        )
        if read(values=["y", "Y", "n", "N"], default="y") in ["n", "N"]:
            return None

    banner()
    need_float_city = check_need_float_city(schematic)
    float_city = None
    if need_float_city is True:
        float_city = choose_float_city(session, island)
        if float_city is None:
            return None

    banner()
    print("Do you want to receive Telegram/Discord notifications for this grind? [Y/n]")
    send_notifications = read(values=["y", "Y", "n", "N"], default="y") not in ["n", "N"]

    # the task reads the island, the cities and the units' data again: the config keeps ids
    return {
        "session": session,
        "island_id": str(island["id"]),
        "city_id": str(city["id"]),
        "float_city_id": str(float_city["id"]) if float_city is not None else None,
        "schematic": "default" if schematic is DEFAULT_SCHEMATICS["WITHOUT_HEPHAESTUS"] else schematic,
        "send_notifications": send_notifications,
    }
