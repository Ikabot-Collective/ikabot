#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import traceback

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *



def get_studies(session):
    html = session.get()
    city = getCity(html)
    city_id = city["id"]
    url = "view=researchAdvisor&oldView=updateGlobalData&cityId={0}&backgroundView=city&currentCityId={0}&templateView=researchAdvisor&actionRequest={1}&ajax=1".format(
        city_id, actionRequest
    )
    resp = session.post(url)
    resp = json.loads(resp, strict=False)
    return resp[2][1]


def study(session, studies, num_study):
    html = session.get()
    city = getCity(html)
    city_id = city["id"]
    research_type = studies["js_researchAdvisorChangeResearchType{}".format(num_study)][
        "ajaxrequest"
    ].split("=")[-1]
    url = "action=Advisor&function=doResearch&actionRequest={}&type={}&backgroundView=city&currentCityId={}&templateView=researchAdvisor&ajax=1".format(
        actionRequest, research_type, city_id
    )
    session.post(url)


def experiment(session, experiments, automatic):
    while experiments["qty"] > 0:
        if automatic is True: experiments["qty"] = 999999
        # Validate if material is still there..oterwhise log it and send it via bot
        session.get("view=city&cityId={}".format(experiments["cityID"]), noIndex=True)
        data = session.get("view=updateGlobalData&ajax=1", noIndex=True)
        json_data = json.loads(data, strict=False)
        json_data = json_data[0][1]["headerData"]
        current_glass = int(json_data["currentResources"]["3"])

        if current_glass < 300000:
            if automatic is False:
                sendToBot(
                    session,
                    f"Experiment process ended on {experiments['cityName']}, not enough crystal ({addThousandSeparator(current_glass)})",
                )
                break
            else:
                session.setStatus(
                    f"Experiment skipped in {experiments['cityName']}, not enough crystal ({addThousandSeparator(current_glass)}) @{getDateTime()}"
                )
                time.sleep(241 * 60)# Re-try after 4h1m
                continue

        while True:
            cooldown_url = f'view=academy&cityId={experiments["cityID"]}&position={experiments["pos"]}&backgroundView=city&currentCityId={experiments["cityID"]}&templateView=academy&actionRequest={actionRequest}&ajax=1'
            cooldown_html = session.get(cooldown_url)
            if 'experimentCooldown' in cooldown_html: # Check if a cooldown is still in effect
                session.setStatus(
                    f"Cooldown is still in effect in {experiments['cityName']} @{getDateTime()}",
                )
                time.sleep(300) # Check again after 5 minutes
                continue
            else:
                break

        url = f'action=CityScreen&function=buyResearch&cityId={experiments["cityID"]}&position={experiments["pos"]}&backgroundView=city&currentCityId={experiments["cityID"]}&templateView=academy&actionRequest={actionRequest}&ajax=1'
        session.post(url)

        experiments["qty"] = experiments["qty"] - 1
        if automatic is False:
            session.setStatus(
                f"Experiment done in {experiments['cityName']} @{getDateTime()}, left = {experiments['qty']} time (s)",
            )
        else:
            session.setStatus(
                f"Experiment done in {experiments['cityName']} @{getDateTime()}"
            )

        # Terminate it if no of experiments = 0
        if experiments["qty"] == 0:
            break

        # Every 4h, added 1m extra
        time.sleep(241 * 60)


def find_academy_cities(session):
    cities_ids, cities_info = getIdsOfCities(session)
    academy_cities = []
    for city_id in cities_ids:
        html = session.get(city_url + str(city_id))
        city_data = getCity(html)
        for building in city_data.get("position", []):
            if building.get("building") == "academy":
                academy_cities.append({
                    "cityID": city_data["id"],
                    "cityName": city_data["name"],
                    "pos": building["position"],
                })
                break
    return academy_cities


def experiment_multi(session, cities):
    for city in cities:
        city["qty"] = 999999
        city["last_experiment"] = 0

    COOLDOWN_MINUTES = 235  # 3h55m, slightly less than 4h

    while True:
        done = []
        skipped_crystal = []
        skipped_cooldown = []
        all_done = True
        next_ready_time = float('inf')
        now = time.time()

        for city in cities:
            if city["qty"] <= 0:
                continue

            all_done = False

            # Skip if experiment was done recently (no API check needed)
            minutes_since = (now - city["last_experiment"]) / 60
            if minutes_since < COOLDOWN_MINUTES:
                remaining = COOLDOWN_MINUTES - minutes_since
                next_ready_time = min(next_ready_time, now + remaining * 60)
                skipped_cooldown.append(city['cityName'])
                continue

            # API checks
            session.get("view=city&cityId={}".format(city["cityID"]), noIndex=True)
            data = session.get("view=updateGlobalData&ajax=1", noIndex=True)
            json_data = json.loads(data, strict=False)
            json_data = json_data[0][1]["headerData"]
            current_glass = int(json_data["currentResources"]["3"])

            if current_glass < 300000:
                skipped_crystal.append(f"{city['cityName']} ({addThousandSeparator(current_glass)})")
                next_ready_time = min(next_ready_time, now + 30 * 60)
                continue

            cooldown_url = f'view=academy&cityId={city["cityID"]}&position={city["pos"]}&backgroundView=city&currentCityId={city["cityID"]}&templateView=academy&actionRequest={actionRequest}&ajax=1'
            cooldown_html = session.get(cooldown_url)
            if 'experimentCooldown' in cooldown_html:
                skipped_cooldown.append(city['cityName'])
                next_ready_time = min(next_ready_time, now + 5 * 60)
                continue

            url = f'action=CityScreen&function=buyResearch&cityId={city["cityID"]}&position={city["pos"]}&backgroundView=city&currentCityId={city["cityID"]}&templateView=academy&actionRequest={actionRequest}&ajax=1'
            session.post(url)

            done.append(city['cityName'])
            city["last_experiment"] = now
            next_ready_time = min(next_ready_time, now + COOLDOWN_MINUTES * 60)

        if all_done:
            break

        parts = []
        if len(cities) <= 3:
            if done:
                parts.append(f"Done: {', '.join(done)}")
            if skipped_crystal:
                parts.append(f"No crystal: {', '.join(skipped_crystal)}")
            if skipped_cooldown:
                parts.append(f"Cooldown: {', '.join(skipped_cooldown)}")
        else:
            if done:
                parts.append(f"Done: {len(done)}")
            if skipped_crystal:
                parts.append(f"No crystal: {len(skipped_crystal)}")
            if skipped_cooldown:
                parts.append(f"Cooldown: {len(skipped_cooldown)}")
        summary = " | ".join(parts) if parts else "No experiments possible"
        session.setStatus(f"{summary} @{getDateTime()}")

        if not done:
            wait = max(60, next_ready_time - now)
            time.sleep(wait)


def research(session, event, stdin_fd, predetermined_input):
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
        while True:
            banner()

            print("\nSelect an option:")
            print("0) Back")
            print("1) Study")
            print("2) Conduct experiment")
            print("3) Conduct automatically")
            option = read(min=0, max=3)

            if option == 0:
                event.set()
                return

            if option == 1:
                try:
                    studies = get_studies(session)
                    keys = list(studies.keys())
                    num_studies = len(
                        [
                            key
                            for key in keys
                            if "js_researchAdvisorChangeResearchTypeTxt" in key
                        ]
                    )

                    available = []
                    for num_study in range(num_studies):
                        if "js_researchAdvisorProgressTxt{}".format(num_study) in studies:
                            available.append(num_study)

                    if len(available) == 0:
                        print("There are no available studies.")
                        enter()
                        continue

                    print("Which one do you wish to study?")
                    print("0) None")
                    for index, num_study in enumerate(available):
                        print(
                            "{:d}) {}".format(
                                index + 1,
                                studies[
                                    "js_researchAdvisorNextResearchName{}".format(num_study)
                                ],
                            )
                        )
                    choice = read(min=0, max=len(available))

                    if choice == 0:
                        continue

                    study(session, studies, available[choice - 1])
                    print("Done.")
                    enter()
                except KeyboardInterrupt:
                    continue
            else:
                if option == 3:
                    try:
                        banner()
                        academy_cities = find_academy_cities(session)

                        if not academy_cities:
                            print("No academy found in any city.")
                            enter()
                            continue

                        if len(academy_cities) == 1:
                            selected_cities = academy_cities
                        else:
                            print("\nCities with an academy:")
                            for idx, ac in enumerate(academy_cities, start=1):
                                print(f"[{idx}] {ac['cityName']}")
                            print("\nEnter numbers separated by space (e.g. 1 3) or 'all':")
                            sel = read().strip().lower().split()
                            if "all" in sel:
                                selected_cities = academy_cities
                            else:
                                selected_cities = []
                                for token in sel:
                                    if token.isdigit():
                                        i = int(token)
                                        if 0 < i <= len(academy_cities):
                                            selected_cities.append(academy_cities[i - 1])

                            if not selected_cities:
                                continue

                    except KeyboardInterrupt:
                        continue

                    set_child_mode(session)
                    event.set()

                    city_names = ", ".join(c["cityName"] for c in selected_cities)
                    info = f"Process: Experiments (automatic)\n\nCities: {city_names}\nWill execute every 4h per city"

                    try:
                        sendToBot(session, info)
                        experiment_multi(session, selected_cities)
                    except Exception as e:
                        error_msg = f"Error in:\n{info}\nCause:\n{traceback.format_exc()}"
                        sendToBot(session, error_msg)
                    finally:
                        session.logout()
                else:
                    automatic = False
                    experiments = {}
                    found_academy = -1

                    try:
                        while True:
                            banner()
                            print("Pick city: (Ctrl+C to go back)")
                            city = chooseCity(session)

                            found_academy = -1
                            for building in city["position"]:
                                if building["building"] == "academy":
                                    found_academy = building["position"]
                                    break

                            if found_academy < 0:
                                print(f"No academy found in {city['name']}, try another city.")
                                enter()
                                continue

                            total_glass = int(city["availableResources"][3])
                            if total_glass < 300000:
                                print(f"Not enough crystal in {city['name']} ({addThousandSeparator(total_glass)}), min=300k. Try another city.")
                                enter()
                                continue

                            break

                        max_experiments = total_glass // 300000
                        banner()
                        print(f"How many experiments? Min=1, Max={max_experiments}")
                        choice = read(min=1, max=max_experiments)

                        experiments["cityID"] = city["id"]
                        experiments["cityName"] = city["name"]
                        experiments["pos"] = found_academy
                        experiments["qty"] = choice

                    except KeyboardInterrupt:
                        continue

                    set_child_mode(session)
                    event.set()

                    info = f"Process: Experiments\n\nWill excecute {choice} times every 4h"

                    try:
                        sendToBot(session, info)
                        experiment(session, experiments, automatic)
                    except Exception as e:
                        error_msg = f"Error in:\n{info}\nCause:\n{traceback.format_exc()}"
                        sendToBot(session, error_msg)
                    finally:
                        session.logout()

    except KeyboardInterrupt:
        event.set()
        return
