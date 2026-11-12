#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import traceback

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.decorators import configurator, task
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.taskConfig import asInt, findBuildingPosition, getCityById, requireOwnCity
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


EXPERIMENT_CRYSTAL = 300000


def ids_from_saved_config(experiments=None, cities=None):
    """(cities_ids, qty) of a config saved by an older menu, which held the academy cities"""
    if experiments:
        return [experiments["cityID"]], experiments["qty"]
    if cities:
        return [city["cityID"] for city in cities], None
    return None, None


def academy_city(session, city_id):
    """{"cityID", "cityName", "pos"} of a city with an academy, None when it has none"""
    city = getCityById(session, city_id)
    pos = findBuildingPosition(city, "academy")
    if pos is None:
        return None
    return {"cityID": city["id"], "cityName": city["name"], "pos": pos}


def prepare_research(session, cities_ids=None, qty=None, mode=None, experiments=None, automatic=None, cities=None, info=""):
    """Checks the config of a research (experiments) task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    cities_ids : list
        cities whose academy does the experiments; None uses every city with an academy
    qty : int or None
        a number does that many experiments in the only city of cities_ids, every 4 hours, and
        stops when the crystal runs out; None keeps doing them in every city, every 4 hours
    mode, experiments, automatic, cities, info
        a config saved by an older menu; turned into cities_ids and qty

    Returns
    -------
    config : dict
    """
    if cities_ids is None and qty is None:
        cities_ids, qty = ids_from_saved_config(experiments, cities)
    if qty is not None:
        qty = asInt(qty, "qty", minimum=1)
    if cities_ids is not None and not isinstance(cities_ids, (list, tuple)):
        cities_ids = [cities_ids]

    if cities_ids is None:
        if qty is not None:
            raise ValueError("qty needs the city to do the experiments in, in cities_ids")
        academies = find_academy_cities(session)
        if not academies:
            raise ValueError("none of your cities has an academy")
        return {"cities_ids": [str(city["cityID"]) for city in academies], "qty": None}

    cities_ids = list(dict.fromkeys(requireOwnCity(session, city_id, "cities_ids") for city_id in cities_ids))
    if not cities_ids:
        raise ValueError("cities_ids is empty; leave it out to use every city with an academy")
    if qty is not None and len(cities_ids) != 1:
        raise ValueError("qty works on one city, got {} in cities_ids".format(len(cities_ids)))
    for city_id in cities_ids:
        city = getCityById(session, city_id)
        if findBuildingPosition(city, "academy") is None:
            raise ValueError("cities_ids {} ({}) has no academy".format(city_id, city["name"]))
        if qty is not None and int(city["availableResources"][3]) < EXPERIMENT_CRYSTAL:
            raise ValueError(
                "not enough crystal in {} for an experiment: {} of {}".format(
                    city["name"],
                    addThousandSeparator(int(city["availableResources"][3])),
                    addThousandSeparator(EXPERIMENT_CRYSTAL),
                )
            )
    return {"cities_ids": cities_ids, "qty": qty}


@task("research", prepare=prepare_research)
def do_it(session, cities_ids=None, qty=None, mode=None, experiments=None, automatic=None, cities=None, info=""):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    cities_ids : list
        cities whose academy does the experiments; None uses every city with an academy
    qty : int or None
        number of experiments in the only city of cities_ids; None keeps doing them in every city
    mode, experiments, automatic, cities, info
        a config saved by an older menu
    """
    if cities_ids is None and qty is None:
        cities_ids, qty = ids_from_saved_config(experiments, cities)
    if cities_ids is None:
        academies = find_academy_cities(session)
    else:
        academies = [city for city in (academy_city(session, city_id) for city_id in cities_ids) if city]
    names = ", ".join(city["cityName"] for city in academies)

    if qty is not None:
        setInfoSignal(session, f"Process: Experiments\n\nWill excecute {qty} times every 4h in {names}")
        experiment(session, dict(academies[0], qty=qty), False)
    else:
        setInfoSignal(session, f"Process: Experiments (automatic)\n\nCities: {names}\nWill execute every 4h per city")
        experiment_multi(session, academies)

@configurator
def research(session, event, stdin_fd, predetermined_input):
    while True:
        banner()

        print("\nSelect an option:")
        print("0) Back")
        print("1) Study")
        print("2) Conduct experiment")
        print("3) Conduct automatically")
        option = read(min=0, max=3)

        if option == 0:
            return None

        if option == 1:
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
        else:
            if option == 3:
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
                    print("\nEnter numbers separated by space or comma (e.g. 1 3) or 'all':")
                    sel = read().strip().lower().replace(",", " ").split()
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

                city_names = ", ".join(c["cityName"] for c in selected_cities)
                info = f"Process: Experiments (automatic)\n\nCities: {city_names}\nWill execute every 4h per city"
                sendToBot(session, info)
                return {
                    "session": session,
                    "cities_ids": [c["cityID"] for c in selected_cities],
                    "qty": None,
                }
            else:
                found_academy = -1

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

                info = f"Process: Experiments\n\nWill excecute {choice} times every 4h"
                sendToBot(session, info)
                # the task finds the academy again: the saved config only holds the city id
                return {
                    "session": session,
                    "cities_ids": [city["id"]],
                    "qty": choice,
                }
