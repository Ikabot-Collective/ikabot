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
        try:
            resp_text = resp if isinstance(resp, str) else resp.text
        except Exception:
            resp_text = str(resp)

        low = resp_text.lower()

        # a genuinely successful response is a full game-state blob that can
        # legitimately contain a provideFeedback message not recognized below
        # (e.g. "Tu orden se ha cumplido" -- "Your order was fulfilled"), so the
        # success marker must be checked before any failure-keyword matching.
        if resp_text.startswith('[["updateGlobalData"'):
            return True, None

        if "not enough" in low or "insufficient resources" in low or "insufficient" in low:
            return False, "insufficient_resources"

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

                            if combined:
                                if "nivelul" in combined or "level" in combined or "workshop" in combined:
                                    return False, "insufficient_workshop_level"
                                return False, "insufficient_resources"
                            return False, "feedback"
        except Exception:
            pass

        if ("upgrade failed" in low or "cannot upgrade" in low or "invalid request" in low or
            "server error" in low or "exception" in low):
            return False, "server_error"

        return False, "unknown_response"
    except Exception as e:
        session.setStatus(f"Failed to upgrade {unit_id} ({upgrade_type})")
        return False, "exception"

def wait_for_upgrade_completion(session, city_id, position, tab, label=None):
    prefix = "{}: ".format(label) if label else ""
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
                    session.setStatus(f"{prefix}Workshop upgrade in progress (~{mins}m)...")
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
                    session.setStatus(f"{prefix}Upgrade in progress (~{mins}m)...")
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

from ikabot.helpers.decorators import configurator, task
from ikabot.helpers.taskConfig import asId, asInt, getCityById, requireOwnCity

TABS = ("tabUnits", "tabShips")
MAX_UPGRADE_LEVEL = 25


def workshop_tab_data(session, city_id, position, tab):
    """The workshop tab's template data ("completeData", "unitDetails", "inProgress"), or None"""
    html = session.get(city_url + str(city_id))
    response = getWorkshopTab(session, city_id, position, getActionRequestFromHTML(html), tab)
    try:
        data = json.loads(response, strict=False)
    except Exception:
        return None
    return next((b[1] for b in data if isinstance(b, list) and b[0] == "updateTemplateData"), None)


def find_workshop(session, city_id):
    """The city and its workshop (a "position" entry, with "position" and "level"), or None"""
    city = getCityById(session, city_id)
    workshop = next((b for b in city["position"] if b.get("building") == "workshop"), None)
    return city, workshop


def workshop_upgrades(session, city_id, position, tabs=TABS):
    """What the workshop can upgrade, from the game
    Returns
    -------
    upgrades : dict
        {unit id: {"tab", "name", "types": {upgrade type: {"level", "desc"}}}}
    """
    upgrades = {}
    for tab in tabs:
        data = workshop_tab_data(session, city_id, position, tab) or {}
        names = data.get("unitDetails", {})
        for unit_id, types in data.get("completeData", {}).items():
            upgrades[str(unit_id)] = {
                "tab": tab,
                "name": names.get(str(unit_id), {}).get("unitName", "Unit {}".format(unit_id)),
                "types": {
                    upgrade_type: {
                        "level": int(upgrade.get("currentLevel", {}).get("upgradeLevel", 0)),
                        "desc": upgrade.get("upgradeTypeDesc", upgrade_type),
                    }
                    for upgrade_type, upgrade in types.items()
                    if isinstance(upgrade, dict)
                },
            }
    return upgrades


def job_from_saved(job):
    """A job as {"city_id", "upgrades": [{"unitId", "upgradeType", "target"}]}; an older
    menu saved every single level to upgrade in "tasks", with the city's name and workshop"""
    if not isinstance(job, dict) or "tasks" not in job:
        return job
    targets = {}
    for step in job["tasks"]:
        key = (str(step["unitId"]), step["upgradeType"])
        targets[key] = max(targets.get(key, 0), int(step["to"]))
    return {
        "city_id": job["city_id"],
        "upgrades": [{"unitId": unit_id, "upgradeType": upgrade_type, "target": target}
                     for (unit_id, upgrade_type), target in targets.items()],
    }


def prepare_UpgradeUnits(session, jobs):
    """Checks the config of an UpgradeUnits task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    jobs : list
        [{"city_id": city id, "upgrades": [{"unitId": unit id, "upgradeType": "offensive" or
        "defensive", "target": level}, ...]}, ...]

    Returns
    -------
    config : dict
    """
    usage = '{"city_id": ..., "upgrades": [{"unitId": ..., "upgradeType": "offensive", "target": ...}]}'
    if not isinstance(jobs, (list, tuple)) or not jobs:
        raise ValueError("jobs must be a list of {}, got {!r}".format(usage, jobs))
    checked = []
    cities_seen = {}
    pending = False
    for i, job in enumerate(jobs):
        name = "jobs[{}]".format(i)
        job = job_from_saved(job)
        if not isinstance(job, dict):
            raise ValueError("{} must be {}, got {!r}".format(name, usage, job))
        city_id = requireOwnCity(session, job.get("city_id"), name + ".city_id")
        if city_id in cities_seen:
            raise ValueError("{}.city_id {} is already in jobs[{}]".format(name, city_id, cities_seen[city_id]))
        cities_seen[city_id] = i
        upgrades = job.get("upgrades")
        if not isinstance(upgrades, (list, tuple)) or not upgrades:
            raise ValueError(
                '{}.upgrades must be a list of {{"unitId": ..., "upgradeType": "offensive", "target": ...}}, got {!r}'.format(name, upgrades)
            )
        city, workshop = find_workshop(session, city_id)
        city_name = city["name"]
        if workshop is None:
            raise ValueError("{}.city_id {}: {} has no workshop".format(name, city_id, city_name))
        max_level = min(MAX_UPGRADE_LEVEL, int(workshop.get("level") or 0))
        available = workshop_upgrades(session, city_id, workshop["position"])

        checked_upgrades = []
        for j, upgrade in enumerate(upgrades):
            up_name = "{}.upgrades[{}]".format(name, j)
            if not isinstance(upgrade, dict):
                raise ValueError('{} must be {{"unitId": ..., "upgradeType": ..., "target": ...}}, got {!r}'.format(up_name, upgrade))
            unit_id = asId(upgrade.get("unitId"), up_name + ".unitId")
            if unit_id not in available:
                units = ", ".join("{} = {}".format(uid, unit["name"]) for uid, unit in available.items())
                raise ValueError("{}.unitId {} cannot be upgraded in the workshop of {}. Units: {}".format(up_name, unit_id, city_name, units))
            unit = available[unit_id]
            upgrade_type = str(upgrade.get("upgradeType", "")).strip().lower()
            if upgrade_type not in unit["types"]:
                raise ValueError("{}.upgradeType must be {}, got {!r}".format(
                    up_name, " or ".join(unit["types"]), upgrade.get("upgradeType")))
            target = asInt(upgrade.get("target"), up_name + ".target", minimum=1)
            if target > max_level:
                raise ValueError("{}.target {} is above what the workshop of {} allows: {} (workshop level {}, at most {})".format(
                    up_name, target, city_name, max_level, workshop.get("level"), MAX_UPGRADE_LEVEL))
            if unit["types"][upgrade_type]["level"] < target:
                pending = True
            checked_upgrades.append({"unitId": unit_id, "upgradeType": upgrade_type, "target": target})
        checked.append({"city_id": city_id, "upgrades": checked_upgrades})

    if not pending:
        raise ValueError("every upgrade is already at its target level")
    return {"jobs": checked}


def run_city_upgrades(session, city_id, upgrades):
    """Takes each upgrade of one city's workshop to its target level, one level at a time"""
    city, workshop = find_workshop(session, city_id)
    city_name = city["name"]
    if workshop is None:
        session.setStatus("{}: no workshop".format(city_name))
        sendToBot(session, "Upgrade aborted in city {}: it has no workshop.".format(city_name))
        return
    position = workshop["position"]
    available = workshop_upgrades(session, city_id, position)
    # the workshop does one upgrade at a time: wait on every tab this city uses
    tabs = sorted({available[str(u["unitId"])]["tab"] for u in upgrades if str(u["unitId"]) in available})

    pending = list(upgrades)
    while pending:
        upgrade = pending[0]
        unit_id, upgrade_type, target = str(upgrade["unitId"]), upgrade["upgradeType"], int(upgrade["target"])
        if unit_id not in available or upgrade_type not in available[unit_id]["types"]:
            session.setStatus("{}: unit {} cannot be upgraded".format(city_name, unit_id))
            sendToBot(session, "Upgrade aborted in city {}: the workshop cannot upgrade unit {} ({}).".format(city_name, unit_id, upgrade_type))
            return
        tab = available[unit_id]["tab"]
        for t in tabs:
            wait_for_upgrade_completion(session, city_id, position, t, label=city_name)

        # the level is read from the game each time, so a relaunched task goes on where it was
        available.update(workshop_upgrades(session, city_id, position, tabs=(tab,)))
        unit = available[unit_id]
        level = unit["types"][upgrade_type]["level"]
        if level >= target:
            pending.pop(0)
            continue

        html = session.get(city_url + str(city_id))
        action_request = getActionRequestFromHTML(html)
        desc = unit["types"][upgrade_type]["desc"]
        session.setStatus("{}: upgrading {} ({}) {}→{}, target {}".format(city_name, unit["name"], desc, level, level + 1, target))
        success, error = send_upgrade_request(session, city_id, position, unit_id, upgrade_type, action_request, tab)
        if not success:
            if error in ("insufficient_resources", "insufficient_workshop_level", "feedback"):
                session.setStatus("{}: upgrade aborted: {}".format(city_name, error))
                try:
                    sendToBot(session, f"Upgrade aborted in city {city_name}: {error} for {unit['name']} ({desc}).")
                except Exception:
                    session.setStatus("Failed to send Telegram notification")
                return
            time.sleep(60)
        else:
            wait_for_upgrade_start(session, city_id, position, tab)

    session.setStatus("{}: all workshop upgrades completed @{}".format(city_name, getDateTime()))


@task("UpgradeUnits", prepare=prepare_UpgradeUnits)
def execute_sequential_upgrades(session, jobs):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    jobs : list
        [{"city_id", "upgrades": [{"unitId", "upgradeType", "target"}]}]; the task reads
        the workshop and the current levels from the game
    """
    jobs = [job_from_saved(job) for job in jobs]
    plural = "city" if len(jobs) == 1 else "cities"
    info = f"Workshop upgrade: {len(jobs)} {plural} queued"
    setInfoSignal(session, info)
    threads = []
    for job in jobs:
        t = threading.Thread(
            target=run_city_upgrades,
            args=(session, job["city_id"], job["upgrades"]),
        )
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


@configurator
def UpgradeUnits(session, event, stdin_fd, predetermined_input):
    cities_ids, cities_info = getIdsOfCities(session)

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
        return None

    selected_workshops = workshops
    if len(workshops) > 1:
        print("\nCities with a workshop:")
        for idx, w in enumerate(workshops, start=1):
            lvl = w.get("level", 0)
            print(f"[{idx}] {w['name']}, workshop level {lvl}")
        print("\nEnter numbers separated by space or comma (e.g. 1 3) or 'all' to pick every city:")
        sel = read().strip().lower().replace(",", " ").split()
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
            return None

    jobs = []
    for w in selected_workshops:
        print(f"\n=== City {w['name']} (id {w['city_id']}) ===")
        job = run_workshop_upgrade_interface(
            session,
            w["city_id"],
            w["name"],
            w["position"],
            w["action_request"],
            w.get("level", 0),
        )
        if job:
            jobs.append(job)

    if not jobs:
        return None

    return {
        "session": session,
        "jobs": jobs
    }


def run_workshop_upgrade_interface(session, city_id, city_name, position, action_request, workshop_level=0):
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

    print(f"Workshop level: {workshop_level}")

    response = getWorkshopTab(session, city_id, position, action_request, filter_type)

    try:
        data = json.loads(response, strict=False)
    except Exception as e:
        enter()
        return None

    template_data = next((b[1] for b in data if isinstance(b, list) and b[0] == "updateTemplateData"), None)
    if not template_data:
        enter()
        return None

    complete_data = template_data.get("completeData", {})
    unit_details = template_data.get("unitDetails", {})
    tasks = []

    for unit_id, upgrades in complete_data.items():
        unit_name = unit_details.get(str(unit_id), {}).get("unitName", f"Unit {unit_id}")

        for upgrade_type, upgrade in upgrades.items():
            if not isinstance(upgrade, dict):
                continue

            cur = upgrade.get("currentLevel", {})
            nxt = upgrade.get("nextLevel", {})
            current_level = int(cur.get("upgradeLevel", 0))
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
        return None

    for idx, task in enumerate(tasks, start=1):
        print(f"[{idx}] {task['unit']} ({task['type']}): Level {task['from']}")

    print("\nEnter numbers separated by space (e.g., 1 3 5):")
    selected_indexes = list(set(read().split()))  # deduplicate to avoid multiple selections of the same upgrade
    selected_tasks = [tasks[int(i)-1] for i in selected_indexes if i.isdigit() and 0 < int(i) <= len(tasks)]

    if not selected_tasks:
        enter()
        return None

    upgrade_levels = {}
    print("\nFor each selected unit, enter the desired target level.")
    for idx, task in enumerate(selected_tasks):
        current_level = int(task['from'])
        max_target_level = min(25, workshop_level)
        max_levels = max_target_level - current_level
        if max_levels <= 0:

            print(f"Cannot upgrade {task['unit']} ({task['type']}) - workshop too low or already max level ({current_level}).")
            continue

        while True:
            target_input = read(msg=f"{idx + 1}. {task['unit']} ({task['type']}) - current level {current_level}, target level (max {max_target_level}), 0 to skip: ").strip()
            try:
                target_level = int(target_input)
                if target_level == 0:
                    break
                if current_level < target_level <= max_target_level:
                    levels = target_level - current_level
                    upgrade_levels[idx] = levels
                    break

                print(f"Please enter a level between {current_level + 1} and {max_target_level}, or 0 to skip.")
            except ValueError:
                print("Invalid input. Please enter a number.")

    queued_tasks = []
    total_gold = 0
    total_crystal = 0

    for idx, base_task in enumerate(selected_tasks):
        levels = upgrade_levels.get(idx, 0)
        if levels <= 0:

            continue

        try:
            cost_gold = int(base_task['gold'].replace(',', '').replace('.', '').replace(' ', '').replace('\xa0', ''))
        except Exception:
            cost_gold = 0
        try:
            cost_crystal = int(base_task['crystal'].replace(',', '').replace('.', '').replace(' ', '').replace('\xa0', ''))
        except Exception:
            cost_crystal = 0

        total_gold += cost_gold * levels
        total_crystal += cost_crystal * levels

        current_level = int(base_task['from'])
        effect_step = int(base_task.get('effect_to', 0)) - int(base_task.get('effect_from', 0))
        for n in range(levels):
            new_task = base_task.copy()
            new_task['from'] = str(current_level + n)
            new_task['to'] = str(current_level + n + 1)
            new_task['effect_from'] = str(int(base_task.get('effect_from', 0)) + effect_step * n)
            new_task['effect_to'] = str(int(base_task.get('effect_from', 0)) + effect_step * (n + 1))
            queued_tasks.append(new_task)

    base_tasks = selected_tasks
    selected_tasks = queued_tasks

    if not selected_tasks:
        print("\nNo upgrades selected after target evaluation. Nothing to do.")
        enter()
        return None

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
        return None

    # the task reads the workshop and the current levels again: the config only holds the targets
    return {
        "city_id": city_id,
        "upgrades": [
            {"unitId": str(task["unitId"]), "upgradeType": task["upgradeType"], "target": int(task["from"]) + upgrade_levels[idx]}
            for idx, task in enumerate(base_tasks)
            if upgrade_levels.get(idx, 0) > 0
        ],
    }
