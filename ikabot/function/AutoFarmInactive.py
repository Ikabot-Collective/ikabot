#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import math
import re
import time
import random
import traceback
import sys
import os
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.naval import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.naval import getAvailableShips, getTotalShips
from ikabot.helpers.planRoutes import waitForArrival
from ikabot.helpers.process import set_child_mode, updateProcessList
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *
from ikabot.helpers.pedirInfo import chooseEnemyCity
from ikabot.web.session import Session
from ikabot.function.attackBarbarians import (
    get_units,
    get_movements,
    get_current_attacks,
    filter_loading,
    filter_traveling,
    filter_fighting,
    wait_until_attack_is_over
)

# Unit upkeep costs
unit_upkeep = {
    '301': 3,  # Hoplite
    '302': 4,  # Swordsman
    '303': 3,  # Slinger
    '304': 3,  # Archer
    '305': 30,  # Marksman
    '306': 25,  # Light Infantry
    '307': 15,  # Ram
    '308': 30,  # Catapult
    '309': 45,  # Mortar
    '310': 10,  # Gyrocopter
    '311': 20,  # Steam Giant
    '312': 15,  # Balloon-Bombardier
    '313': 5,   # Cook
    '315': 1,   # Spearman
}

def _ensure_current_city(session, city_id):
    """Ensure the `currentCityId` in session is set to the given `city_id`.
    Fetches `actionRequest` token and posts the `headerCity.changeCurrentCity` action if needed.

    This guards against the user or other processes switching the current city between attacks.
    """
    try:
        html = session.get()
        # Detect current city id
        m_city = re.search(r"currentCityId:\s*(\d+),", html)
        current_id = m_city.group(1) if m_city else None
        if str(current_id) == str(city_id):
            return  # already on the correct city

        # Find an actionRequest token
        m_token = re.search(r'actionRequest"\s*:\s*"([a-f0-9]+)"', html)
        if not m_token:
            m_token = re.search(r'actionRequest=([a-f0-9]+)', html)
        if not m_token:
            # Fallback: request city view to obtain token
            city_view_html = session.get(params={
                'view': 'city',
                'cityId': city_id,
                'backgroundView': 'city',
                'ajax': 1
            })
            m_token = re.search(r'actionRequest"\s*:\s*"([a-f0-9]+)"', city_view_html) or re.search(r'actionRequest=([a-f0-9]+)', city_view_html)
        action_request = m_token.group(1) if m_token else ''

        # Switch current city if we have a token
        session.post(params={
            'action': 'headerCity',
            'function': 'changeCurrentCity',
            'actionRequest': action_request,
            'cityId': city_id,
            'backgroundView': 'city',
            'currentCityId': city_id,
            'templateView': 'city',
            'ajax': 1
        })
    except Exception:
        # Non-fatal: in worst case the attack call may fail, and retry logic will handle it
        pass

def AutoFarmInactive(session, event, stdin_fd, predetermined_input):
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
    
    banner()

    try:
        # Get the source city (our city we'll attack from)
        print('\nSelect the city you want to attack from:')
        source_city = chooseCity(session)  # Show our cities


        # Select multiple target cities, with custom trips per target
        target_plans = []  # list of tuples (city, trips_for_city)
        while True:
            print('\nEnter coordinates and select a city to attack:')
            city = chooseEnemyCity(session)
            print(f'Selected: {city["cityName"]} (Player: {city.get("Name", "Unknown")})')
            trips_for_city = read(msg='How many attacks for this target? (max 100): ', min=1, max=100, digit=True)
            target_plans.append((city, trips_for_city))
            print('Add another target city? [y/N]')
            add_more = read(values=["y", "Y", "n", "N", ""])
            if add_more.lower() != "y":
                break

        print(f'\nAttacking from: {source_city["cityName"]}')
        for idx, plan in enumerate(target_plans, 1):
            city, trips_for_city = plan
            print(f'Target {idx}: {city["cityName"]} (Player: {city.get("Name", "Unknown")}) | attacks: {trips_for_city}')

        print('\nIs this correct? [Y/n]')
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            event.set()
            return

        # Get available units in the source city
        print('\nChecking available units in the city...')
        total_units = get_units(session, source_city)

        if sum([total_units[unit_id]["amount"] for unit_id in total_units]) == 0:
            print("You don't have any troops in this city!")
            event.set()
            return

        # Select units to send
        print('\nWhich troops do you want to send in each attack?')
        attack_units = {}
        for unit_id in total_units:
            unit_amount = total_units[unit_id]["amount"]
            unit_name = total_units[unit_id]["name"]
            if unit_amount > 0:
                amount_to_send = read(
                    msg=f"{unit_name} (max: {unit_amount}): ",
                    max=unit_amount,
                    default=0
                )
                if amount_to_send > 0:
                    attack_units[unit_id] = amount_to_send

        # Get cargo ships
        total_ships = getTotalShips(session)
        available_ships = getAvailableShips(session)
        print(f'Ships available: {available_ships}/{total_ships}')
        cargo_ships = read(msg='Cargo ships per attack: ', min=0, max=total_ships, digit=True)

        # Get ship capacity
        ship_capacity = getShipCapacity(session)
        print(f'Ship capacity: {ship_capacity} resources/ship')

        # Get wait time between trips
        wait_time = read(msg='Wait between attacks (seconds, min 60): ', min=60, max=3600, digit=True)

        print('Starting farming operation...')
    # ...removed debug prints...

        set_child_mode(session)
        # notify parent that child setup is complete so PID table gets updated
        event.set()
        # ensure this child is registered in the shared process list (robust against races/overwrites)
        try:
            process_entry = {
                "pid": os.getpid(),
                "action": AutoFarmInactive.__name__,
                "date": time.time(),
                "status": "running",
            }
            updateProcessList(session, programprocesslist=[process_entry])
        except Exception:
            pass
        # Show concise PID-table-friendly status: source -> targets, trips per target, ships per trip
        try:
            target_summaries = [f"{city['cityName']}({trips}x)" for city, trips in target_plans]
            target_names = ', '.join(target_summaries)
            pid_status = f'AutoFarmInactive: {source_city["cityName"]} -> {target_names} | ships/trip {cargo_ships}'
        except Exception:
            pid_status = 'AutoFarmInactive: running'
        setInfoSignal(session, pid_status)

        try:
            # Start farming process (runs in this child process)
            # If user's cargo ships are currently engaged in other transports, wait for them to return
            if cargo_ships and cargo_ships > 0:
                ships_now = getAvailableShips(session)
                if ships_now < cargo_ships:
                    msg = f'Waiting for transports: need {cargo_ships}, have {ships_now}'
                    print(msg)
                    sendToBot(session, msg)
                    # waitForArrival will wait until at least one ship is available; loop until we have enough
                    while True:
                        ships_now = waitForArrival(session)
                        if ships_now >= cargo_ships:
                            break
                        time.sleep(30)

            total_farmed = 0
            total_attacks = 0
            for idx, plan in enumerate(target_plans, 1):
                target_city, trips_for_city = plan
                msg = f'🎯 Starting attacks on: {target_city["cityName"]} ({trips_for_city} attacks)'
                print(msg)
                sendToBot(session, msg)
                # Ensure current city is the selected source before this target's batch
                _ensure_current_city(session, source_city['id'])
                # Check cargo ships availability before attacking each target
                if cargo_ships and cargo_ships > 0:
                    ships_now = getAvailableShips(session)
                    if ships_now < cargo_ships:
                        while True:
                            ships_now = waitForArrival(session)
                            if ships_now >= cargo_ships:
                                break
                            time.sleep(15)
                farmed = _do_farming(session, source_city, target_city, attack_units, total_units, cargo_ships, trips_for_city, wait_time)
                total_farmed += farmed
                total_attacks += trips_for_city
            final_msg = f'✅ Farming complete! Total: {total_farmed} resources from {total_attacks} attacks'
            print(final_msg)
            sendToBot(session, final_msg)
        except Exception as e:
            # report error to bot
            try:
                sendToBot(session, f'❌ Error during farming: {traceback.format_exc()}')
            except Exception:
                pass
        finally:
            # Ensure the session logs out and child process exits cleanly
            try:
                session.logout()
            except Exception:
                pass
            return

    except KeyboardInterrupt:
        event.set()
        return

def _do_farming(session, source_city, target_city, attack_units, total_units, cargo_ships, trips, wait_time):
    total_farmed = 0
    def get_last_plundered_resources(session, source_city_id, target_city_id):
        """Search for the last plunder report for target_city_id and extract plundered resources."""
        try:
            military_view_params = {
                'view': 'militaryAdvisor',
                'oldView': 'city',
                'backgroundView': 'city',
                'currentCityId': source_city_id,
                'templateView': 'militaryAdvisor',
                'ajax': 1
            }
            for attempt in range(4):
                try:
                    military_data = session.post(params=military_view_params)
                    military_data = json.loads(military_data, strict=False)
                    # Try to navigate the response structure safely
                    if isinstance(military_data, list) and len(military_data) > 2:
                        if isinstance(military_data[1], list) and len(military_data[1]) > 2:
                            if isinstance(military_data[1][2], list) and len(military_data[1][2]) > 0:
                                view_data = military_data[1][2][0]
                            else:
                                view_data = military_data[1][2]
                            if isinstance(view_data, dict) and 'viewScriptParams' in view_data:
                                reports = view_data['viewScriptParams'].get('militaryAndFleetMovements', [])
                                if not reports:
                                    raise ValueError('No military movements found')
                                for report in reports:
                                    mission = report.get('event', {}).get('mission')
                                    if (mission == 'plunder' or str(mission) == 'plunder') and report['target']['cityId'] == target_city_id:
                                        cargo = report.get('cargo', {})
                                        if cargo:
                                            return cargo
                    if attempt < 3:
                        time.sleep(3)
                except (IndexError, KeyError, TypeError, ValueError) as e:
                    if attempt < 3:
                        time.sleep(3)
                    continue
        except Exception as e:
            try:
                sendToBot(session, f'⚠️ Warning: Could not extract plundered resources: {str(e)}')
            except Exception:
                pass
        return {}

    for trip in range(trips):
        try:
            # Ensure current city is correct before each trip
            _ensure_current_city(session, source_city['id'])
            # ...existing code for a single trip...
            # First get the military view to get the action request token
            # First get the military view which will also give us an action request token
            military_view_params = {
                'view': 'militaryAdvisor',
                'oldView': 'city',
                'oldBackgroundView': 'city',
                'backgroundView': 'city',
                'currentCityId': source_city['id'],
                'templateView': 'militaryAdvisor',
                'ajax': 1
            }
            military_data = session.post(params=military_view_params)
            
            # Extract the action request token from the military view
            html = session.get()
            action_request_match = re.search(r'actionRequest"\s*:\s*"([a-f0-9]+)"', html)
            if not action_request_match:
                action_request_match = re.search(r'actionRequest=([a-f0-9]+)', html)
            if action_request_match:
                action_request = action_request_match.group(1)
                # Switch to the source city
                session.post(params={
                    'action': 'headerCity',
                    'function': 'changeCurrentCity',
                    'actionRequest': action_request,
                    'cityId': source_city['id'],
                    'backgroundView': 'city',
                    'currentCityId': source_city['id'],
                    'templateView': 'city',
                    'ajax': 1
                })

            # Continue with the military view operations
            military_view_params = {
                'view': 'militaryAdvisor',
                'oldView': 'city',
                'oldBackgroundView': 'city',
                'backgroundView': 'city',
                'currentCityId': source_city['id'],
                'templateView': 'militaryAdvisor',
                'ajax': 1
            }
            military_data = session.post(params=military_view_params)

            # Ensure we are viewing the source city page to get a valid actionRequest token
            try:
                city_view_html = session.get(params={
                    'view': 'city',
                    'cityId': source_city['id'],
                    'backgroundView': 'city',
                    'ajax': 1
                })
            except Exception:
                # fallback to a generic GET if the param'd get fails
                city_view_html = session.get()

            # Extract actionRequest token from the city view HTML
            action_request_match = re.search(r'actionRequest"\s*:\s*"([a-f0-9]+)"', city_view_html)
            if not action_request_match:
                action_request_match = re.search(r'actionRequest=([a-f0-9]+)', city_view_html)
            if not action_request_match:
                # final fallback to any page content
                fallback_html = session.get()
                action_request_match = re.search(r'actionRequest"\s*:\s*"([a-f0-9]+)"', fallback_html)
                if not action_request_match:
                    action_request_match = re.search(r'actionRequest=([a-f0-9]+)', fallback_html)

            if action_request_match:
                action_request = action_request_match.group(1)
            else:
                action_request = ''

            # Prepare the plunder action data (match network request)
            plunder_action = {
                'action': 'transportOperations',
                'function': 'sendArmyPlunderLand',
                'actionRequest': action_request,
                'islandId': target_city['islandId'],
                'destinationCityId': target_city['id'],
                'currentCityId': source_city['id'],
                'cityId': source_city['id'],
                'barbarianVillage': 0,
                'backgroundView': 'island',
                'currentIslandId': target_city['islandId'],
                'templateView': 'plunder',
                'transporter': cargo_ships,
                'ajax': 1
            }
            for unit_id in unit_upkeep:
                amount = attack_units.get(unit_id, 0)
                plunder_action[f'cargo_army_{unit_id}'] = amount
                plunder_action[f'cargo_army_{unit_id}_upkeep'] = unit_upkeep[unit_id]

            ships_available = waitForArrival(session)

            total_cargo = cargo_ships * getShipCapacity(session)

            # Send attack with retry logic
            plunder_result = None
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    plunder_response = session.post(params=plunder_action)
                    plunder_result = json.loads(plunder_response, strict=False)
                    if 'error' not in plunder_result:
                        break
                    elif attempt < max_retries - 1:
                        time.sleep(5)
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(5)
                    else:
                        plunder_result = {'error': str(e)}

            if plunder_result and 'error' in plunder_result:
                error_msg = f'❌ Attack failed: {plunder_result.get("error", "Unknown")}'
                print(error_msg)
                try:
                    sendToBot(session, error_msg)
                except Exception:
                    pass
                continue  # Continue to next trip instead of breaking

            attack_start_time = time.time()

            # Estimate battle duration by checking the movement with the longest arrival time
            movements = get_movements(session, source_city['id'])
            attacks = [m for m in movements if m['target']['cityId'] == target_city['id']]
            fighting = filter_fighting(attacks)
            loading = filter_loading(attacks)
            traveling = filter_traveling(attacks)

            # Default wait time if no info (fallback)
            estimated_battle_time = 0

            # Movements include an absolute 'eventTime' timestamp; compute remaining by subtracting local time
            now = time.time()
            def max_remaining(movs):
                times = []
                for mv in movs:
                    # movement may have eventTime at top-level or inside 'event'
                    if 'eventTime' in mv:
                        ev = mv['eventTime']
                    elif 'event' in mv and 'eventTime' in mv['event']:
                        ev = mv['event']['eventTime']
                    else:
                        continue
                    try:
                        remaining = int(ev) - int(now)
                    except Exception:
                        continue
                    if remaining > 0:
                        times.append(remaining)
                return max(times) if times else 0

            if len(fighting) > 0:
                estimated_battle_time = max_remaining(fighting)
            elif len(loading) > 0:
                estimated_battle_time = max_remaining(loading)
            elif len(traveling) > 0:
                estimated_battle_time = max_remaining(traveling)
            else:
                estimated_battle_time = 0

            if estimated_battle_time > 0:
                # Sleep until the estimated finish time plus a small buffer to avoid tight polling
                time.sleep(estimated_battle_time + 2)

            # After waiting, poll until all movements are done (should be quick)
            while True:
                movements = get_movements(session, source_city['id'])
                attacks = [m for m in movements if m['target']['cityId'] == target_city['id']]
                fighting = filter_fighting(attacks)
                loading = filter_loading(attacks)
                traveling = filter_traveling(attacks)
                if len(fighting) == 0 and len(loading) == 0 and len(traveling) == 0:
                    break
                time.sleep(3)

            plundered_resources = get_last_plundered_resources(session, source_city['id'], target_city['id'])
            trip_total = sum(plundered_resources.values()) if plundered_resources else 0
            total_farmed += trip_total
            
            # Send Telegram notification with attack results
            resource_details = ', '.join([f"{res}: {amt}" for res, amt in plundered_resources.items() if amt > 0]) if plundered_resources else 'No resources detected'
            attack_msg = f"Attack {trip + 1}/{trips}: {target_city['cityName']}\nPlundered: {resource_details}\nTotal: {trip_total}"
            try:
                sendToBot(session, attack_msg)
            except Exception:
                pass
            # Update status in PID table
            try:
                short_status = (
                    f'AutoFarm: {source_city["cityName"]} -> {target_city["cityName"]} '
                    f'trip {trip + 1}/{trips} cargos:{cargo_ships} plunder:{trip_total} total:{total_farmed}'
                )
            except Exception:
                short_status = f'AutoFarm: trip {trip + 1}/{trips} plunder:{trip_total} total:{total_farmed}'
            process_entry = {
                "pid": os.getpid(),
                "action": AutoFarmInactive.__name__,
                "date": time.time(),
                "status": short_status
            }
            updateProcessList(session, programprocesslist=[process_entry])

            if trip < trips - 1:
                if trip_total == 0:
                    # Do not abort the whole operation on a single empty report - continue to next scheduled attack
                    process_entry["status"] = f'No resources plundered on trip {trip + 1}, continuing to next trip'
                    updateProcessList(session, programprocesslist=[process_entry])
                # wait a random time between 60s (min) and the user-selected wait_time (max)
                wait_seconds = random.randint(60, wait_time) if wait_time >= 60 else 60
                next_activity = time.time() + wait_seconds
                next_ts = time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime(next_activity))
                process_entry["status"] = f'Last attack @{time.strftime("%Y-%m-%d_%H-%M-%S")}, next @{next_ts} | Trip {trip + 1}/{trips}'
                updateProcessList(session, programprocesslist=[process_entry])
                time.sleep(wait_seconds)
        except Exception as e:
            traceback.print_exc()
            try:
                sendToBot(session, f'❌ Error during trip {trip + 1}: {str(e)}')
            except Exception:
                pass
            continue  # Continue to next attack instead of breaking
    return total_farmed