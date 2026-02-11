#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import re
import sys
import traceback

from ikabot import config
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *


def tavernManager(session, event, stdin_fd, predetermined_input):
    """
    Advanced tavern management:
    - Set single or all taverns to max/zero
    - Equilibrium mode: optimize wine usage when population maxed

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

        print("=" * 60)
        print("ADVANCED TAVERN WINE CONSUMPTION MANAGER")
        print("=" * 60)
        print()

        # Main menu
        print("Select operation mode:")
        print()
        print("1. Set tavern level (single city or all cities)")
        print("2. Equilibrium mode (optimize wine usage)")
        print()
        print("(') Back to main menu")

        mode = read(msg="Select mode (1 or 2): ", min=1, max=2, digit=True, additionalValues=["'"])

        if mode == "'":
            event.set()
            return

        print()

        if mode == 1:
            # Simple set mode
            run_set_mode(session, event)
        else:
            # Equilibrium mode
            run_equilibrium_mode(session, event, stdin_fd, predetermined_input)

    except KeyboardInterrupt:
        event.set()
        return

    event.set()


def run_set_mode(session, event):
    """Simple mode: set taverns to max or zero"""

    print("=" * 60)
    print("SET TAVERN LEVELS")
    print("=" * 60)
    print()

    # Select cities
    print("Which cities?")
    print("1. Single city")
    print("2. All cities")
    print()
    print("(') Back to main menu")
    city_choice = read(msg="Select (1 or 2): ", min=1, max=2, digit=True, additionalValues=["'"])

    if city_choice == "'":
        return

    print()

    if city_choice == 1:
        cities_to_process = [chooseCity(session)]
    else:
        cities_ids, cities = getIdsOfCities(session)
        cities_to_process = [cities[cid] for cid in cities_ids]

    # Select level
    print("Set to:")
    print("1. Maximum consumption")
    print("2. Zero consumption")
    print()
    print("(') Back to main menu")
    level_choice = read(msg="Select (1 or 2): ", min=1, max=2, digit=True, additionalValues=["'"])

    if level_choice == "'":
        return

    target_is_max = (level_choice == 1)
    print()

    print(f"Will set {len(cities_to_process)} cities to {'MAXIMUM' if target_is_max else 'ZERO'}")
    print()
    print("Proceed? [Y/n]")
    confirm = read(values=["y", "Y", "n", "N", ""])
    if confirm.lower() == "n":
        print("Cancelled.")
        print()
        enter()
        return

    print()
    print("Processing cities...")
    print()

    success_count = 0
    for city in cities_to_process:
        result = set_tavern_level(session, city, target_is_max)
        if result:
            success_count += 1

    print()
    print(f"{bcolors.GREEN}Complete!{bcolors.ENDC}")
    print(f"Successfully updated {success_count}/{len(cities_to_process)} cities")
    print()
    enter()


def run_equilibrium_mode(session, event, stdin_fd, predetermined_input):
    """Equilibrium mode: optimize wine when population is maxed"""

    print("=" * 60)
    print("EQUILIBRIUM MODE")
    print("=" * 60)
    print()
    print("This mode optimizes wine consumption when population is maxed.")
    print("It maintains satisfaction just above zero (+5 buffer).")
    print()

    # Select notification mode
    print("Telegram notifications:")
    print("1. Notify on every change")
    print("2. Notify only on errors")
    print("3. No notifications")
    print()
    print("(') Back to main menu")
    notification_mode = read(msg="Select (1-3): ", min=1, max=3, digit=True, additionalValues=["'"])

    if notification_mode == "'":
        return

    print()

    # Select cities
    print("Which cities?")
    print("1. Select cities to exclude")
    print("2. All cities")
    print()
    print("(') Back to main menu")
    city_choice = read(msg="Select (1 or 2): ", min=1, max=2, digit=True, additionalValues=["'"])

    if city_choice == "'":
        return

    print()

    if city_choice == 1:
        cities_ids, cities = ignoreCities(session)
    else:
        cities_ids, cities = getIdsOfCities(session)

    # Select run mode
    print("Run mode:")
    print("0. Run once and exit")
    print("1-24. Run continuously, checking every X hours")
    print()
    print("(') Back to main menu")
    run_hours = read(msg="Enter hours (0 for once, 1-24 for continuous): ", min=0, max=24, digit=True, additionalValues=["'"])

    if run_hours == "'":
        return

    print()

    if run_hours == 0:
        # Run once
        print(f"Processing {len(cities_ids)} cities...")
        print()

        # Track statistics
        changes_made = process_equilibrium(session, cities_ids, cities, notification_mode)

        print()
        print("=" * 60)
        print(f"{bcolors.GREEN}EQUILIBRIUM MODE COMPLETE{bcolors.ENDC}")
        print("=" * 60)
        print(f"Processed: {len(cities_ids)} cities")
        if changes_made:
            print(f"Changes made: {len(changes_made)}")
            print()
            print("Cities adjusted:")
            for change in changes_made:
                print(f"  - {change}")
        else:
            print("No changes needed - all cities already optimal")
        print("=" * 60)
        print()
        enter()
    else:
        # Run continuously
        print(f"Will check {len(cities_ids)} cities every {run_hours} hour(s)")
        print("Starting continuous mode...")
        print()
        print("Running first check...")
        print()

        # Run first check before going to background
        changes_made = process_equilibrium(session, cities_ids, cities, notification_mode)

        print()
        print("=" * 60)
        print(f"{bcolors.GREEN}FIRST CHECK COMPLETE{bcolors.ENDC}")
        print("=" * 60)
        print(f"Processed: {len(cities_ids)} cities")
        if changes_made:
            print(f"Changes made: {len(changes_made)}")
            print()
            print("Cities adjusted:")
            for change in changes_made:
                print(f"  - {change}")
        else:
            print("No changes needed - all cities already optimal")
        print("=" * 60)
        print()
        print(f"Will continue checking every {run_hours} hour(s) in background...")
        print()
        enter()

        # Switch to background
        set_child_mode(session)
        event.set()

        info = f"\nTavern Equilibrium: {len(cities_ids)} cities, every {run_hours}h\n"
        setInfoSignal(session, info)

        try:
            while True:
                wait(run_hours * 3600)
                process_equilibrium(session, cities_ids, cities, notification_mode)
                session.setStatus(f"Equilibrium check @{getDateTime()}")
        except Exception as e:
            msg = f"Error in:\n{info}\nCause:\n{traceback.format_exc()}"
            if notification_mode <= 2:  # Notify on errors or all changes
                sendToBot(session, msg)
        finally:
            session.logout()


def process_equilibrium(session, cities_ids, cities, notification_mode):
    """Process equilibrium for selected cities

    Returns:
        list: List of change descriptions made
    """

    changes_made = []

    for city_id in cities_ids:
        city = cities[city_id]

        # Get city data
        html = session.get(city_url + city_id)
        city_data = getCity(html)

        # Check if city has tavern
        tavern = None
        for building in city_data["position"]:
            if building["building"] == "tavern":
                tavern = building
                break

        if not tavern:
            print(f"  {city['name']}: No tavern, skipping")
            continue

        # Check if population is maxed
        citizens_match = re.search(r'id="js_GlobalMenu_citizens">([0-9,]+)</span>[^<]*<[^>]*id="js_GlobalMenu_population">([0-9,]+)', html)
        if not citizens_match:
            print(f"  {city['name']}: Could not read population, skipping")
            continue

        current_citizens = int(citizens_match.group(1).replace(',', ''))
        max_citizens = int(citizens_match.group(2).replace(',', ''))

        # Only proceed if at max population
        if current_citizens < max_citizens:
            # Population not maxed - set tavern to maximum to boost growth
            print(f"  {city['name']}: Population not maxed ({current_citizens}/{max_citizens}), setting to MAX")

            # Get tavern level and set to max
            tavern_level = tavern["level"]
            change_result = set_tavern_to_level(session, city, tavern, tavern_level)
            if change_result:
                changes_made.append(change_result)
            continue

        # Get town hall data
        town_hall_position = None
        for building in city_data["position"]:
            if building["building"] == "townHall":
                town_hall_position = building["position"]
                break

        if not town_hall_position:
            print(f"  {city['name']}: No town hall found, skipping")
            continue

        # Get town hall page
        th_params = f"view=townHall&cityId={city_id}&position={town_hall_position}&backgroundView=city&currentCityId={city_id}&ajax=1"
        th_response = session.post(th_params)

        try:
            th_data = json.loads(th_response, strict=False)
            th_html = None
            for item in th_data:
                if isinstance(item, list) and item[0] == "changeView" and len(item[1]) >= 2:
                    th_html = item[1][1]
                    break

            if not th_html:
                print(f"  {city['name']}: Could not load town hall, skipping")
                continue

            # Get growth rate
            growth_match = re.search(r'id="js_TownHallPopulationGrowthValue">([0-9.]+)', th_html)
            if not growth_match:
                print(f"  {city['name']}: Could not read growth rate, skipping")
                continue

            growth_rate = float(growth_match.group(1))

            # Get total satisfaction
            satisfaction_match = re.search(r'id="js_TownHallHappinessLargeValue"[^>]*>([0-9,.-]+)', th_html)
            if not satisfaction_match:
                print(f"  {city['name']}: Could not read satisfaction, skipping")
                continue

            total_satisfaction = int(satisfaction_match.group(1).replace(',', ''))

            # Check if we need to adjust
            if growth_rate > 0:
                print(f"  {city['name']}: Growing ({growth_rate}/h), satisfaction: {total_satisfaction}, OK")
                continue

            # Growth is 0, need to reduce wine
            print(f"  {city['name']}: Growth=0, satisfaction: {total_satisfaction}, optimizing...")

            # Calculate how much we can reduce
            change_result = optimize_tavern_for_satisfaction(session, city, tavern, total_satisfaction)
            if change_result:
                changes_made.append(change_result)

        except Exception as e:
            error_msg = f"  {city['name']}: Error - {str(e)}"
            print(error_msg)
            if notification_mode <= 2:  # Notify on errors or all changes
                sendToBot(session, f"Tavern Equilibrium Error\n{city['name']}: {str(e)}")
            continue

    # Send notification for changes if mode 1
    if notification_mode == 1 and changes_made:
        msg = "Tavern Equilibrium Changes\n\n"
        for change in changes_made:
            msg += f"{change}\n"
        sendToBot(session, msg)

    return changes_made


def set_tavern_to_level(session, city, tavern, target_level):
    """
    Set tavern to a specific level and return change info for notifications

    Returns:
        String describing the change, or None if no change made
    """
    city_id = city['id']
    city_name = city['name']
    building_position = tavern["position"]

    # Get tavern page
    tavern_params = f"view=tavern&cityId={city_id}&position={building_position}&backgroundView=city&currentCityId={city_id}&ajax=1"
    tavern_response = session.post(tavern_params)

    try:
        response_data = json.loads(tavern_response, strict=False)
    except Exception:
        print(f"    Could not parse tavern response")
        return None

    # Extract current level, action code, and consumption values
    current_level = 0
    action_code = None
    consumption_values = []

    for item in response_data:
        if not isinstance(item, list) or len(item) < 2:
            continue

        if item[0] == "changeView" and isinstance(item[1], list) and len(item[1]) >= 2:
            tavern_html = item[1][1]
            # Parse consumption from dropdown
            dropdown_pattern = re.findall(r'<option[^>]*value="(\d+)"[^>]*>(\d+)\s+Wine per hour', tavern_html)
            for level_str, wine_str in dropdown_pattern:
                consumption_values.append((int(level_str), int(wine_str)))

        if item[0] == "updateTemplateData" and isinstance(item[1], dict):
            load_js = item[1].get("load_js", {})
            if isinstance(load_js, dict) and "params" in load_js:
                try:
                    js_data = json.loads(load_js["params"], strict=False)
                    if "wineServeLevel" in js_data:
                        current_level = int(js_data["wineServeLevel"])
                except Exception:
                    pass

        elif item[0] == "updateGlobalData" and isinstance(item[1], dict):
            if "actionRequest" in item[1]:
                action_code = item[1]["actionRequest"]

    if not action_code:
        print(f"    Could not get action code")
        return None

    # Check if already at target level
    if current_level == target_level:
        print(f"    Already at level {target_level}")
        return None

    # Get wine consumption values
    current_wine = next((w for l, w in consumption_values if l == current_level), current_level * 10)
    new_wine = next((w for l, w in consumption_values if l == target_level), target_level * 10)

    # Apply change
    params = {
        'action': 'CityScreen',
        'function': 'assignWinePerTick',
        'cityId': city_id,
        'position': building_position,
        'amount': target_level,
        'backgroundView': 'city',
        'currentCityId': city_id,
        'templateView': 'tavern',
        'actionRequest': action_code,
        'ajax': '1'
    }

    try:
        response = session.post(params=params)
        print(f"    Changed from level {current_level} ({current_wine}/h) to level {target_level} ({new_wine}/h)")

        # Return change information for notification
        return f"{city_name}: L{current_level} ({current_wine}/h) -> L{target_level} ({new_wine}/h) [MAX for growth]"

    except Exception as e:
        print(f"    Failed to apply change: {e}")
        return None


def optimize_tavern_for_satisfaction(session, city, tavern, current_satisfaction):
    """Reduce tavern wine to keep satisfaction just above +5"""

    city_id = city['id']
    city_name = city['name']
    building_position = tavern["position"]

    # Get tavern data
    tavern_params = f"view=tavern&cityId={city_id}&position={building_position}&backgroundView=city&currentCityId={city_id}&ajax=1"
    tavern_response = session.post(tavern_params)

    try:
        response_data = json.loads(tavern_response, strict=False)
    except Exception:
        print(f"    Could not parse tavern response")
        return None

    # Extract data
    current_level = 0
    sat_per_wine = []
    action_code = None
    consumption_values = []

    for item in response_data:
        if not isinstance(item, list) or len(item) < 2:
            continue

        if item[0] == "changeView" and isinstance(item[1], list) and len(item[1]) >= 2:
            tavern_html = item[1][1]
            # Parse consumption from dropdown
            dropdown_pattern = re.findall(r'<option[^>]*value="(\d+)"[^>]*>(\d+)\s+Wine per hour', tavern_html)
            for level_str, wine_str in dropdown_pattern:
                consumption_values.append((int(level_str), int(wine_str)))

        if item[0] == "updateTemplateData" and isinstance(item[1], dict):
            load_js = item[1].get("load_js", {})
            if isinstance(load_js, dict) and "params" in load_js:
                try:
                    js_data = json.loads(load_js["params"], strict=False)
                    if "wineServeLevel" in js_data:
                        current_level = int(js_data["wineServeLevel"])
                    if "satPerWine" in js_data:
                        sat_per_wine = js_data["satPerWine"]
                except Exception:
                    pass

        elif item[0] == "updateGlobalData" and isinstance(item[1], dict):
            if "actionRequest" in item[1]:
                action_code = item[1]["actionRequest"]

    if not sat_per_wine or not action_code:
        print(f"    Could not get tavern data")
        return None

    # Find optimal level: LOWEST level where satisfaction stays above +5
    target_satisfaction = 5
    optimal_level = current_level  # fallback: don't change

    # Calculate base satisfaction without current wine boost
    if current_level < len(sat_per_wine):
        base_satisfaction = current_satisfaction - sat_per_wine[current_level]
    else:
        base_satisfaction = current_satisfaction

    for level in range(len(sat_per_wine)):
        projected_satisfaction = base_satisfaction + sat_per_wine[level]

        if projected_satisfaction >= target_satisfaction:
            optimal_level = level
            break  # Take the FIRST (lowest) level that satisfies the condition

    if optimal_level == current_level:
        print(f"    Already at optimal level {optimal_level}")
        return None

    # Get wine consumption values
    current_wine = next((w for l, w in consumption_values if l == current_level), current_level * 10)
    new_wine = next((w for l, w in consumption_values if l == optimal_level), optimal_level * 10)

    # Apply change
    params = {
        'action': 'CityScreen',
        'function': 'assignWinePerTick',
        'cityId': city_id,
        'position': building_position,
        'amount': optimal_level,
        'backgroundView': 'city',
        'currentCityId': city_id,
        'templateView': 'tavern',
        'actionRequest': action_code,
        'ajax': '1'
    }

    try:
        response = session.post(params=params)
        print(f"    Changed from level {current_level} ({current_wine}/h) to level {optimal_level} ({new_wine}/h)")

        # Return change information for notification
        return f"{city_name}: L{current_level} ({current_wine}/h) -> L{optimal_level} ({new_wine}/h)"

    except Exception as e:
        print(f"    Failed to apply change: {e}")
        return None


def set_tavern_level(session, city, set_to_max):
    """Set a single tavern to max or zero"""

    city_id = city['id']

    # Get city data
    html = session.get(city_url + city_id)
    city_data = getCity(html)

    # Find tavern
    tavern = None
    for building in city_data["position"]:
        if building["building"] == "tavern":
            tavern = building
            break

    if not tavern:
        print(f"  {city['name']}: No tavern")
        return False

    building_position = tavern["position"]
    tavern_level = tavern["level"]

    # Get tavern page
    tavern_params = f"view=tavern&cityId={city_id}&position={building_position}&backgroundView=city&currentCityId={city_id}&ajax=1"
    tavern_response = session.post(tavern_params)

    try:
        response_data = json.loads(tavern_response, strict=False)
    except Exception:
        print(f"  {city['name']}: Could not parse tavern response")
        return False

    # Get action code
    action_code = None
    for item in response_data:
        if isinstance(item, list) and item[0] == "updateGlobalData" and isinstance(item[1], dict):
            if "actionRequest" in item[1]:
                action_code = item[1]["actionRequest"]
                break

    if not action_code:
        print(f"  {city['name']}: Could not get action code")
        return False

    # Set level
    target_level = tavern_level if set_to_max else 0

    params = {
        'action': 'CityScreen',
        'function': 'assignWinePerTick',
        'cityId': city_id,
        'position': building_position,
        'amount': target_level,
        'backgroundView': 'city',
        'currentCityId': city_id,
        'templateView': 'tavern',
        'actionRequest': action_code,
        'ajax': '1'
    }

    try:
        response = session.post(params=params)
        print(f"  {city['name']}: Set to level {target_level}")
        return True
    except Exception as e:
        print(f"  {city['name']}: Failed - {e}")
        return False
