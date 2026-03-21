#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import sys
import os
import json
import threading
from ikabot.config import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *
from ikabot.helpers.botComm import *
from ikabot.helpers.process import set_child_mode
from ikabot.web.session import Session

def getActionRequestFromHTML(html):
    match = re.search(r'name="actionRequest"\s+value="(\w+)"', html)
    if match:
        return match.group(1)
    return None

def getWorkshopTab(session, city_id, position, action_request, tab):
    data = {
        "view": "workshop",
        "activeTab": tab,
        "cityId": city_id,
        "position": position,
        "backgroundView": "city",
        "currentCityId": city_id,
        "templateView": "workshop",
        "actionRequest": action_request,
        "ajax": "1"
    }
    return session.post(params=data)

def send_upgrade_request(session, city_id, position, unit_id, upgrade_type, action_request, tab):
    payload = {
        "action": "StartWorkshopUpgrade",
        "cityId": city_id,
        "position": position,
        "unitId": unit_id,
        "upgradeType": upgrade_type,
        "activeTab": tab,
        "backgroundView": "city",
        "currentCityId": city_id,
        "templateView": "workshop",
        "actionRequest": action_request,
        "ajax": "1"
    }
    try:
        resp = session.post(params=payload)
        # Normalize response text for simple checks. session.post may return raw text or a requests.Response
        try:
            resp_text = resp if isinstance(resp, str) else resp.text
        except Exception:
            resp_text = str(resp)

        low = resp_text.lower()
        # Detect common failure messages related to insufficient resources.
        if "not enough" in low or "insufficient resources" in low or "insufficient" in low:
            return False, "insufficient_resources"

        # Parse any JSON feedback objects (language-agnostic) to handle all locales.
        try:
            resp_json = json.loads(resp_text)
            if isinstance(resp_json, list):
                for entry in resp_json:
                    if isinstance(entry, list) and len(entry) >= 2 and entry[0] == "provideFeedback":
                        feedback_items = entry[1]
                        if isinstance(feedback_items, list) and feedback_items:
                            messages = []
                            for item in feedback_items:
                                if isinstance(item, dict) and "text" in item:
                                    messages.append(item.get("text", ""))
                            combined = " ".join(messages).lower()
                            # numeric or building level outcome fallback.
                            if combined:
                                if "nivelul" in combined or "level" in combined or "workshop" in combined:
                                    return False, "insufficient_workshop_level"
                                return False, "insufficient_resources"
                            return False, "feedback"
        except Exception:
            pass

        # Check for specific server errors, but avoid false positives from HTML content
        if ("upgrade failed" in low or "cannot upgrade" in low or "invalid request" in low or 
            "server error" in low or "exception" in low):
            return False, "server_error"

        # If we get a valid response structure, assume success
        if resp_text.startswith('[["updateGlobalData"'):
            return True, None

        # Otherwise, treat as unknown error
        return False, "unknown_response"
    except Exception as e:
        session.setStatus(f"Failed to upgrade {unit_id} ({upgrade_type})")
        return False, "exception"

def wait_for_upgrade_completion(session, city_id, position, tab):
    first_check = True
    logged_duration = False
    while True:
        html = session.get(city_url + str(city_id))
        action_request = getActionRequestFromHTML(html)
        response = getWorkshopTab(session, city_id, position, action_request, tab)

        try:
            data = json.loads(response, strict=False)
            template_data = next((b[1] for b in data if isinstance(b, list) and b[0] == "updateTemplateData"), None)
            if template_data:
                # Check for building upgrade in progress
                if template_data.get("buildingInProgress"):
                    end_time = int(template_data["buildingInProgress"].get("endTime", 0))
                    current_time = int(template_data.get("currentdate", int(time.time())))
                    seconds_left = max(0, end_time - current_time)
                    mins = seconds_left // 60
                    hours = mins // 60
                    if not logged_duration:
                        logged_duration = True
                    session.setStatus(f"Workshop upgrade in progress (~{mins}m)...")
                    time.sleep(min(300, seconds_left))
                    continue
                # Check for unit/ship upgrade in progress
                if template_data.get("inProgress"):
                    end_time = int(template_data["inProgress"].get("endTime", 0))
                    current_time = int(template_data.get("currentdate", int(time.time())))
                    seconds_left = max(0, end_time - current_time)
                    mins = seconds_left // 60
                    hours = mins // 60
                    if not logged_duration:
                        logged_duration = True
                    session.setStatus(f"Upgrade in progress (~{mins}m)...")
                    time.sleep(min(300, seconds_left))
                    continue
        except Exception:
            session.setStatus("Error checking upgrade/building progress")

        break

def wait_for_upgrade_start(session, city_id, position, tab):
    session.setStatus("Waiting for upgrade to start...")
    max_attempts = 30  # ~30 seconds with 1-second sleeps
    attempts = 0
    while attempts < max_attempts:
        html = session.get(city_url + str(city_id))
        action_request = getActionRequestFromHTML(html)
        response = getWorkshopTab(session, city_id, position, action_request, tab)

        try:
            data = json.loads(response, strict=False)
            template_data = next((b[1] for b in data if isinstance(b, list) and b[0] == "updateTemplateData"), None)
            if template_data and template_data.get("inProgress"):
                return
        except Exception:
            pass

        time.sleep(1)
        attempts += 1
    
    # If we reach here, timeout occurred - no upgrade has started yet.

def execute_sequential_upgrades(session, city_id, city_name, position, tab, tasks):
    while tasks:
        wait_for_upgrade_completion(session, city_id, position, tab)
        html = session.get(city_url + str(city_id))
        action_request = getActionRequestFromHTML(html)

        task = tasks.pop(0)
        # display both current and target level when available
        from_lvl = task.get('from', '?')
        to_lvl = task.get('to', '?')
        session.setStatus(f"Upgrading {task['unit']} ({task['type']}) {from_lvl}→{to_lvl}")
        success, error = send_upgrade_request(session, city_id, position, task['unitId'], task['upgradeType'], action_request, tab)
        if not success:
            # If the failure is because of insufficient resources, stop and notify via Telegram bot.
            if error in ("insufficient_resources", "insufficient_workshop_level", "feedback"):
                session.setStatus(f"Upgrade aborted: {error}")
                city_name_str = city_name if isinstance(city_name, str) else str(city_name)
                try:
                    sendToBot(session, f"Upgrade aborted in city {city_name_str}: {error} for {task['unit']} ({task['type']}).")
                except Exception:
                    session.setStatus("Failed to send Telegram notification")
                return
            # For transient server errors, requeue and retry after a short delay
            tasks.insert(0, task)
            time.sleep(60)
        else:
            # Wait for the upgrade to actually start before proceeding
            wait_for_upgrade_start(session, city_id, position, tab)

    session.setStatus("All workshop upgrades completed")

def UpgradeUnits(session, event, stdin_fd, predetermined_input):
    # The original implementation only handled the first city containing a
    # workshop.  It now collects *all* cities with workshops and allows the
    # user to select one, several, or 'all' of them.  Each chosen city will
    # spawn its own background thread for the actual upgrade sequence, so
    # upgrades can proceed in parallel across multiple cities while the user
    # continues interacting with the bot.
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input

    cities_ids, cities_info = getIdsOfCities(session)

    # gather all cities that contain a workshop
    workshops = []
    for city_id in cities_ids:
        html = session.get(city_url + str(city_id))
        action_request = getActionRequestFromHTML(html)
        city_data = getCity(html)
        for building in city_data.get("position", []):
            if building.get("building") == "workshop":
                workshops.append({
                    "city_id": city_id,
                    "position": building.get("position"),
                    "level": building.get("level", 0),
                    "action_request": action_request,
                    "name": cities_info.get(city_id, cities_info.get(str(city_id), {})).get("name", str(city_id)),
                })
                break

    if not workshops:
        print("\nNo workshop found in any city.")
        enter()
        event.set()
        return

    # if more than one workshop, ask the user which cities to operate on
    selected_workshops = workshops
    if len(workshops) > 1:
        print("\nCities with a workshop:")
        for idx, w in enumerate(workshops, start=1):
            lvl = w.get("level", 0)
            print(f"[{idx}] {w['name']}, workshop level {lvl}")
        print("\nEnter numbers separated by space (e.g. 1 3) or 'all' to pick every city:")
        sel = read().split()
        if "all" in sel:
            selected_workshops = workshops
        else:
            selected_workshops = []
            for token in sel:
                if token.isdigit():
                    i = int(token)
                    if 0 < i <= len(workshops):
                        selected_workshops.append(workshops[i - 1])
        if not selected_workshops:
            enter()
            event.set()
            return

    # run interface for each chosen city; only set the event after the last one
    for idx, w in enumerate(selected_workshops):
        # make it clear to the user which city we're working on
        print(f"\n=== City {w['name']} (id {w['city_id']}) ===")
        finalize = idx == len(selected_workshops) - 1
        run_workshop_upgrade_interface(
            session,
            w["city_id"],
            w["name"],
            w["position"],
            w["action_request"],
            event,
            finalize,
            w.get("level", 0),
        )

def run_workshop_upgrade_interface(session, city_id, city_name, position, action_request, event, finalize=True, workshop_level=0):
    print("\nWhat would you like to upgrade?")
    print("[1] Units")
    print("[2] Ships")

    while True:
        choice_input = read(msg="Choose option (1 or 2): ").strip()
        if choice_input in ["1", "2"]:
            break
        print("Invalid option. Please choose 1 or 2.")

    choice = int(choice_input)
    filter_type = "tabUnits" if choice == 1 else "tabShips"
    label = "units" if choice == 1 else "ships"

    # report workshop level to user; will be used when limiting upgrades
    print(f"Workshop level: {workshop_level}")

    response = getWorkshopTab(session, city_id, position, action_request, filter_type)

    try:
        data = json.loads(response, strict=False)
    except Exception as e:
        enter()
        if finalize:
            event.set()
        return

    template_data = next((b[1] for b in data if isinstance(b, list) and b[0] == "updateTemplateData"), None)
    if not template_data:
        enter()
        if finalize:
            event.set()
        return

    complete_data = template_data.get("completeData", {})
    unit_details = template_data.get("unitDetails", {})
    tasks = []

    for unit_id, upgrades in complete_data.items():
        unit_name = unit_details.get(str(unit_id), {}).get("unitName", f"Unit {unit_id}")

        # Some units/ships may only offer one type of upgrade (e.g. cargo capacity
        # improvements). The API can return arbitrary upgrade types, so iterate
        # all available ones rather than assuming only "offensive"/"defensive".
        for upgrade_type, upgrade in upgrades.items():
            if not isinstance(upgrade, dict):
                continue

            cur = upgrade.get("currentLevel", {})
            nxt = upgrade.get("nextLevel", {})
            current_level = int(cur.get("upgradeLevel", 0))
            # the templated data may include upgrades regardless of workshop
            # level; skip anything we can't start due to a low workshop.
            if workshop_level <= current_level:
                continue

            tasks.append({
                "unit": unit_name,
                "type": upgrade.get("upgradeTypeDesc", ""),
                "from": current_level,
                "to": int(nxt.get("upgradeLevel", 0)),
                "effect_from": int(cur.get("upgradeEffect", 0)),
                "effect_to": int(nxt.get("upgradeEffect", 0)),
                "gold": nxt.get("goldCosts", "0"),
                "crystal": nxt.get("crystalCosts", "0"),
                "duration": nxt.get("duration", "?"),
                "unitId": unit_id,
                "upgradeType": upgrade_type
            })

    if not tasks:
        print("\nNo upgrade options available in this city (workshop level may be too low).")
        enter()
        if finalize:
            event.set()
        return

    for idx, task in enumerate(tasks, start=1):
        print(f"[{idx}] {task['unit']} ({task['type']}): Level {task['from']}")

    print("\nEnter numbers separated by space (e.g., 1 3 5):")
    selected_indexes = list(set(read().split()))  # deduplicate to avoid multiple selections of the same upgrade
    selected_tasks = [tasks[int(i)-1] for i in selected_indexes if i.isdigit() and 0 < int(i) <= len(tasks)]

    if not selected_tasks:
        enter()
        if finalize:
            event.set()
        return

    # Ask for target level for each selected task.
    upgrade_levels = {}
    print("\nFor each selected unit, enter the desired target level.")
    for idx, task in enumerate(selected_tasks):
        current_level = int(task['from'])
        # Ensure absolute unit level cap is 25, regardless of workshop level value.
        max_target_level = min(25, workshop_level)
        max_levels = max_target_level - current_level
        if max_levels <= 0:
            # should not happen because of earlier filtering, but just in case
            print(f"Cannot upgrade {task['unit']} ({task['type']}) - workshop too low or already max level ({current_level}).")
            continue

        while True:
            target_input = read(msg=f"{idx + 1}. {task['unit']} ({task['type']}) - current level {current_level}, target level (max {max_target_level}), 0 to skip: ").strip()
            try:
                target_level = int(target_input)
                if target_level == 0:
                    # skip this task
                    break

                if current_level < target_level <= max_target_level:
                    levels = target_level - current_level
                    upgrade_levels[idx] = levels
                    break

                print(f"Please enter a level between {current_level + 1} and {max_target_level}, or 0 to skip.")
            except ValueError:
                print("Invalid input. Please enter a number.")

    # build a flat queue of individual upgrade tasks; this avoids the confusing
    # "expanded_tasks" calculation previously used and guarantees that each
    # choice is upgraded the correct number of times without accidentally
    # combining levels for the first selection only.
    queued_tasks = []
    # accumulate cost using the base cost from each level and multiply by
    # requested levels so the totals reflect all of the work being queued.
    total_gold = 0
    total_crystal = 0

    for idx, base_task in enumerate(selected_tasks):
        levels = upgrade_levels.get(idx, 0)
        if levels <= 0:
            # a skipped or invalid response, do not queue this task
            continue
        

        # base cost strings might contain commas or dots; parse safely
        try:
            cost_gold = int(base_task['gold'].replace(',', '').replace('.', ''))
        except Exception:
            cost_gold = 0
        try:
            cost_crystal = int(base_task['crystal'].replace(',', '').replace('.', ''))
        except Exception:
            cost_crystal = 0

        total_gold += cost_gold * levels
        total_crystal += cost_crystal * levels

        # each individual level upgrade is represented by a copy of the base
        # task with its level fields adjusted so the status messages remain
        # meaningful.
        current_level = int(base_task['from'])
        effect_step = int(base_task.get('effect_to', 0)) - int(base_task.get('effect_from', 0))
        for n in range(levels):
            new_task = base_task.copy()
            new_task['from'] = str(current_level + n)
            new_task['to'] = str(current_level + n + 1)
            new_task['effect_from'] = str(int(base_task.get('effect_from', 0)) + effect_step * n)
            new_task['effect_to'] = str(int(base_task.get('effect_from', 0)) + effect_step * (n + 1))
            queued_tasks.append(new_task)

    # replace the selected_tasks list with the fully expanded queue
    selected_tasks = queued_tasks

    if not selected_tasks:
        print("\nNo upgrades selected after target evaluation. Nothing to do.")
        enter()
        if finalize:
            event.set()
        return

    # show the user exactly what will be queued so they can catch any
    # mis-ordering or duplicate entries before we launch the background thread
    print("\nThe following individual upgrades will be queued:")
    for i, t in enumerate(selected_tasks, start=1):
        print(f" [{i}] {t['unit']} ({t['type']}): Level {t.get('from','?')} -> {t.get('to','?')}")

    print("\nTotal estimated cost for all requested upgrades:")
    print(f" - Gold: {total_gold:,} gold")
    print(f" - Crystal: {total_crystal:,} crystal")

    confirm = read(msg="\nProceed with these upgrades? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Operation cancelled by user.")
        enter()
        if finalize:
            event.set()
        return
    session.setStatus(f"Queued {len(selected_tasks)} upgrades | Gold: {total_gold:,} | Crystal: {total_crystal:,}")
    info = f"Workshop upgrade: {len(selected_tasks)} upgrades queued"
    set_child_mode(session)
    setInfoSignal(session, info)
    thread = threading.Thread(target=execute_sequential_upgrades, args=(session, city_id, city_name, position, filter_type, selected_tasks))
    thread.start()
    if finalize:
        event.set()