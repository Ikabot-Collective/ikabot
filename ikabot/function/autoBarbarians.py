#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
import math
import traceback
from decimal import *

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.naval import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planRoutes import waitForArrival
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *

from ikabot.function.activateMiracle import obtainMiraclesAvailable
from ikabot.function.attackBarbarians import get_barbarians_lv,get_units,get_unit_data


DEFAULT_SCHEMATICS = {
    "WITH_HEPHAESTUS" : (
        #TODO Develop the preset here for when Hephaestus is available
    ),
    "WITHOUT_HEPHAESTUS" : (
        {
            "level" : (1,9), 
            "waves" : [
                {
                    "send": [
                        {"from_float": False, "units": [{"id": 302, "amount": 90},{"id": 304, "amount": 21}]}
                    ],
                    "looting": [{"from_float": False, "units": [{"id": 302, "amount": 1}]}]
                }
            ]
        },
        {
            "level" : (10,19), 
            "waves" : [
                {
                    "send": [
                        {"from_float": False, "units": ({"id": 302, "amount": 60},{"id": 304, "amount": 35},{"id": 305, "amount": 12},{"id": 308, "amount": 50})},
                    ],
                    "looting": [{"from_float": False, "units": ({"id": 305, "amount": 12},{"id": 308, "amount": 50})}]
                },
            ]
        },
        {
            "level" : (20,29), 
            "waves" : [
                {
                    "send": [
                        {"from_float": False, "units": [{"id": 302, "amount": 60},{"id": 304, "amount": 70},{"id": 305, "amount": 12},{"id": 307, "amount": 12},{"id": 308, "amount": 100},{"id": 309, "amount": 30},{"id": 310, "amount": 5}]},
                    ],
                    "looting": [{"from_float": False, "units": [{"id": 305, "amount": 12},{"id": 308, "amount": 100}]}]
                },
            ]
        },
        {
            "level" : (30,39), 
            "waves" : [
                {
                    "send": [
                        {"from_float": False, "units": [{"id": 302, "amount": 300},{"id": 304, "amount": 147},{"id": 305, "amount": 24},{"id": 307, "amount": 18},{"id": 308, "amount": 300},{"id": 310, "amount": 5},{"id": 311, "amount": 10}]},
                    ],
                    "looting": [{"from_float": False, "units": [{"id": 305, "amount": 24},{"id": 308, "amount": 150}]}]
                },
            ]
        },
    )
}

t = gettext.translation(
    "autoBarbarians", localedir, languages=languages, fallback=True
)
_ = t.gettext

def autoBarbarians(session, event, stdin_fd, predetermined_input):
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
        print(_(
            "{}⚠️ BEWARE - THE BARBAROS GRIND TO BE CARRIED OUT MORE EFFICIENTLY REQUIRES THE FOLLOWING RESOURCES ⚠️{}\n".format(
                bcolors.WARNING, bcolors.ENDC
            )
        ))
        print(
            "- You need to leave at least 3 merchant ships available.",
            "- You leave 2 extra rams available in the city of origin.",
            "- It is not recommended that merchant ships be used during the grind, as maximizing their use increases the efficiency and effectiveness of attacks.",
            sep="\n"
        )
        print(_("\nDo you agree that failure to comply with these rules will result in you losing out on resources? [y/N]"))
        if read(values=["y", "Y", "n", "N"], default="n") in ["n", "N"]:
            event.set()
            return
        
        banner()
        island = choose_island(session)
        if island is None:
            event.set()
            return
        
        banner()
        print(_("From which city do you want to attack?"))
        city = chooseCity(session)
        if city is None:
            event.set()
            return
        
        has_rams = has_units_in_city(session,city,{"id": 307, "amount": 2}) 
        if has_rams is False:
            print(_("\nYou do not have 2 or more battering rams in this city, the lack of them may prevent you from collecting all the resources present in the barbarian village, are you sure you want to continue anyway? [y/N]"))
            if read(values=["y", "Y", "n", "N"], default="n") in ["n", "N"]:
                event.set()
                return
        
        banner()
        islands = obtainMiraclesAvailable(session)
        hephaestus_max = is_hephaestus_max(islands)
        auto_activate_hephaestus = False
        if hephaestus_max:
            print(_("Do you want to keep activating your Hephaestus to maximize the grind? [Y/n]"))
            activate_miracle_input = read(values=["y", "Y", "n", "N", ""])
            auto_activate_hephaestus = True if activate_miracle_input in ("y","Y") else False

        banner()
        schematic_option = choose_schematic()
        if schematic_option is None:
            event.set()
            return
    
        banner()
        schematic = DEFAULT_SCHEMATICS["WITHOUT_HEPHAESTUS"]
        if schematic_option == 1:
            if auto_activate_hephaestus:
                schematic = DEFAULT_SCHEMATICS["WITH_HEPHAESTUS"]
            pass
        elif schematic_option == 2:
            # TODO do the part where the user can select a custom structure
            pass
        
        banner()
        success,schematic_units,city_units,schematic_ships = get_units_information(session, city, schematic, is_in_island=True if city["islandId"] == island["id"] else False)
        ships_available = waitForArrival(session)
        print(_("Para está sequencia de ataques você precisa ter as seguintes tropas:\n"))
        print_grid_units(schematic_units, city_units, schematic_ships, ships_available)
        if success is False:
            print(_("\nVocê não possui todas as unidades necessária para iniciar está sequencia de ataque, deseja prosseguir executando ataque somente até aonde for possivel? [Y/n]"))
            if read(values=["y", "Y", "n", "N"], default="y") in ["n", "N"]:
                event.set()
                return
        else:
            print(_("As unidades representadas deverão ficar reservadas para uso do sistema"))
            enter()

        banner()
        
        # TODO This code was developed for testing and will be moved to another part of this same module, left commented only to remind me how to apply it.
        # babarians_info = get_barbarians_lv(session, island)
        # barbarians_plan = get_barbarians_attack_plan(babarians_info,schematic)
        # if barbarians_plan is None:
        #     event.set()
        #     return

        banner()
        need_float_city = check_need_float_city(schematic)
        if need_float_city is True:
            floating_city = choose_float_city(session,island)
            if floating_city is None:
                event.set()
                return
            
        banner()
        print("This function is still incomplete, I appreciate the test and I await any kind of feedback.")
        enter()
        
        #TODO from here to develop the functioning of grindr
        

    except KeyboardInterrupt:
        event.set()
        return
    
    set_child_mode(session)
    event.set()
    
    info = _("\nI grinding the barbarians in [{}:{}]\n").format(island["x"], island["y"])
    setInfoSignal(session, info)

    try:
        while True:

            pass
    except Exception as e:
        msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()

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

    print(_("In which island do you want to attack the barbarians?"))
    print(_(" 0) Exit"))
    for i, island in enumerate(islands):
        num = " " + str(i + 1) if i < 9 else str(i + 1)
        if island["barbarians"]["destroyed"] == 1:
            warn = _("(currently destroyed)")
        else:
            warn = ""
        print(
            _("{}) [{}:{}] {} ({}) : barbarians lv: {} ({}) {}").format(
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
    print(_("Select what type of attack sequence you will do:"))
    print(_("(0) Exit"))
    print(_("(1) Default"))
    print(_("(2) Custom"))
    selected = read(min=0, max=2, digit=True)
    if selected == 0:
        return
    
    return selected

def check_need_float_city(schematic):
    return any(
        any(
            any("from_float" in send for send in wave.get("send", [])) for wave in item.get("waves", [])
        ) for item in schematic
    )

def choose_float_city(session,island):
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
    
    print(_("Select the city where the float will be located:\n"))
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
        menu_cities += "{: >2}: {}{}\n".format(
            i, city_name, pad(city_name)
        )
    menu_cities = menu_cities[:-1]
    print(menu_cities)
    cities_options_index = read(min=1, max=len(cities_options))
    return inslands_cities.get(cities_options[cities_options_index])
    
def collect_max_units(schematic):
    max_units = {}

    for item in schematic:
        waves = item.get("waves", [])
        for wave in waves:
            for key in ("send", "looting"):
                units_list = wave.get(key, [])
                for unit_entry in units_list:
                    for unit in unit_entry["units"]:
                        unit_id = unit["id"]
                        unit_amount = unit["amount"]
                        max_units[str(unit_id)] = {'amount' : max(max_units.get(unit_id, 0), unit_amount)}
    return max_units

def get_units_information(session, city, schematic, float_city=None,is_in_island=False):
    schematic_units = collect_max_units(schematic)
    city_units = get_units(session, city)
    for unit_id in schematic_units.keys():
        unit_data = get_unit_data(session, city["id"], str(unit_id))
        city_units[unit_id]['weight'] = unit_data['weight']

    schematic_weight = 0.0
    schematic_ships = 2
    if is_in_island is True:
        for unit_id,unit_data in schematic_units.items():
            schematic_weight += unit_data["amount"] * city_units.get(unit_id, {"weight": 0.0})["weight"]
        schematic_ships += math.ceil(Decimal(schematic_weight) / Decimal(500))
    return all(city_units.get(unit_id, {'amount': 0})['amount'] >= unit_data['amount'] for unit_id, unit_data in schematic_units.items()),schematic_units,city_units,schematic_ships

def print_grid_units(schematic_units, city_units, schematic_ships, ships_available):
    header = ["Unit", "Required", "Available", "Missing"]
    table = []

    for unit_id, required in schematic_units.items():
        available = city_units.get(unit_id, 0)
        missing = max(0, required['amount'] - available['amount'])
        table.append([available['name'], required['amount'], available['amount'], missing])

    col_widths = [max(len(str(row[i])) for row in table + [header]) for i in range(len(header))]
    separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

    def format_row(row):
        return "| " + " | ".join(f"{str(cell).ljust(col_widths[i])}" for i, cell in enumerate(row)) + " |"

    print(separator)
    print(format_row(header))
    print(separator)
    for row in table:
        print(format_row(row))
    print(separator)    
    footer = ["ships", str(schematic_ships), str(ships_available), max(0, int(schematic_ships) - int(ships_available))]
    print(format_row(footer))
    print(separator)    

def get_barbarians_attack_plan(barbarians_info,schematic):
    barbarians_level = int(barbarians_info['level'])
    selected_scheme = None
    for scheme in schematic:
        if isinstance(scheme['level'], (tuple, list)):
            if barbarians_level in range(scheme['level'][0],scheme['level'][1]):
                selected_scheme = scheme
                break
        elif isinstance(scheme['level'], int) and barbarians_level == scheme['level']:
            selected_scheme = scheme
            break

    if selected_scheme is None:
        return
    
    return {
        'waves' : scheme['waves'],
    }

def has_units_in_city(session, city, units):
    if not isinstance(units, (dict, tuple, list)):
        raise TypeError(f"The type provided for units is invalid, a type (tuple | dict | list) is expected and its type is {type(units)}")
    city_units = get_units(session, city)

    if isinstance(units, dict):
        units = [units]
    elif isinstance(units, tuple):
        units = list(units)

    def has_unit(unit_required):
        unit = city_units.get(str(unit_required["id"]))
        if unit is None:
            return False
        return True if unit["amount"] >= unit_required["amount"] else False

    return all([has_unit(unit) for unit in units])