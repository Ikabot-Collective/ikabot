#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import sys
import os
import json
import multiprocessing
from ikabot.config import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *
from ikabot.helpers.botComm import *
from ikabot.helpers.process import set_child_mode

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
        session.post(params=payload)
        return True
    except Exception as e:
        print(f" Error sending upgrade request for unitId={unit_id}, type={upgrade_type}: {e}")
        return False

def wait_for_upgrade_completion(session, city_id, position, tab):
    while True:
        html = session.get(city_url + str(city_id))
        action_request = getActionRequestFromHTML(html)
        response = getWorkshopTab(session, city_id, position, action_request, tab)

        try:
            data = json.loads(response, strict=False)
            template_data = next((b[1] for b in data if isinstance(b, list) and b[0] == "updateTemplateData"), None)
            if template_data and "inProgress" in template_data:
                end_time = int(template_data["inProgress"].get("endTime", 0))
                current_time = int(template_data.get("currentdate", int(time.time())))
                seconds_left = max(0, end_time - current_time)
                mins = seconds_left // 60
                print(f" Waiting for ongoing upgrade to finish (~{mins}m)...")
                time.sleep(min(300, seconds_left))
                continue
        except Exception as e:
            print(f" Error while checking upgrade progress: {e}")

        break

def background_upgrade_worker(session, city_id, position, filter_type, selected_tasks):
    set_child_mode(session)
    info = f"Workshop upgrade: {len(selected_tasks)} upgrades queued"
    setInfoSignal(session, info)

    while selected_tasks:
        wait_for_upgrade_completion(session, city_id, position, filter_type)
        html = session.get(city_url + str(city_id))
        action_request = getActionRequestFromHTML(html)

        task = selected_tasks.pop(0)
        success = send_upgrade_request(session, city_id, position, task['unitId'], task['upgradeType'], action_request, filter_type)
        if success:
            print(f" {task['unit']} ({task['type']}) upgrade sent!")
        else:
            print(f" {task['unit']} ({task['type']}) failed. Will retry later.")
            selected_tasks.insert(0, task)
            time.sleep(60)

def UpgradeUnits(session, event, stdin_fd, predetermined_input):
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input

    cities_ids, _ = getIdsOfCities(session)

    for city_id in cities_ids:
        html = session.get(city_url + str(city_id))
        action_request = getActionRequestFromHTML(html)
        city_data = getCity(html)

        for building in city_data["position"]:
            if building["building"] == "workshop":
                position = building["position"]
                run_workshop_upgrade_interface(session, city_id, position, action_request, event)
                return

    print("No workshop building found.")
    enter()
    event.set()

def run_workshop_upgrade_interface(session, city_id, position, action_request, event):
    print("\nWhat would you like to upgrade?")
    print("[1] Units")
    print("[2] Ships")

    while True:
        choice_input = read(msg="Select an option (1 or 2): ").strip()
        if choice_input in ["1", "2"]:
            break
        print("Invalid option. Please choose 1 or 2.")

    choice = int(choice_input)
    filter_type = "tabUnits" if choice == 1 else "tabShips"
    task_label = "units" if choice == 1 else "ships"

    print(f"\n Loading upgrades for {task_label}...")
    response = getWorkshopTab(session, city_id, position, action_request, filter_type)

    try:
        data = json.loads(response, strict=False)
    except Exception as e:
        print("Error parsing JSON response.")
        print(e)
        enter()
        event.set()
        return

    template_data = next((b[1] for b in data if isinstance(b, list) and b[0] == "updateTemplateData"), None)
    if not template_data:
        print("No valid data found.")
        enter()
        event.set()
        return

    complete_data = template_data.get("completeData", {})
    unit_details = template_data.get("unitDetails", {})
    tasks = []

    for unit_id, upgrades in complete_data.items():
        unit_name = unit_details.get(str(unit_id), {}).get("unitName", f"Unit {unit_id}")
        for upgrade_type in ["offensive", "defensive"]:
            upgrade = upgrades.get(upgrade_type)
            if not upgrade:
                continue

            cur = upgrade.get("currentLevel", {})
            nxt = upgrade.get("nextLevel", {})
            tasks.append({
                "unit": unit_name,
                "type": upgrade.get("upgradeTypeDesc", ""),
                "from": int(cur.get("upgradeLevel", 0)),
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
        print("No upgrades available.")
        enter()
        event.set()
        return

    print("\n📋 Select upgrades (enter numbers):")
    for idx, task in enumerate(tasks, start=1):
        print(f"[{idx}] {task['unit']} ({task['type']}): Level {task['from']} -> {task['to']} | +{task['effect_from']} -> +{task['effect_to']} | {task['gold']} gold, {task['crystal']} crystal | {task['duration']}")

    print("\nEnter numbers separated by space for upgrades (e.g., 1 3 5):")
    selected_indexes = read().split()
    selected_tasks = [tasks[int(i)-1] for i in selected_indexes if i.isdigit() and 0 < int(i) <= len(tasks)]

    if not selected_tasks:
        print("No valid upgrades selected.")
        enter()
        event.set()
        return

    total_gold = 0
    total_crystal = 0
    for task in selected_tasks:
        try:
            total_gold += int(task['gold'].replace(',', '').replace('.', ''))
            total_crystal += int(task['crystal'].replace(',', '').replace('.', ''))
        except Exception:
            pass

    print("\nEstimated total costs:")
    print(f" - Gold: {total_gold:,} gold")
    print(f" - Crystal: {total_crystal:,} crystal")

    print("\nThe task has been started in the background. You can return to the main menu.")
    enter()
    event.set()

    # Start background execution using multiprocessing
    process = multiprocessing.Process(target=background_upgrade_worker, args=(session, city_id, position, filter_type, selected_tasks))
    process.start()
    return