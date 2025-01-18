#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import traceback

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.varios import *

from typing import TYPE_CHECKING, TypedDict, Union
if TYPE_CHECKING:
    from ikabot.web.session import Session

Experiments = TypedDict("Experiments", {"cityID": int, "cityName": str, "pos": int, "qty": int})
InvestigateConfig = TypedDict("InvestigateConfig", {"experiments": Experiments, "automatic": bool})
def investigate(session: Session) -> Union[InvestigateConfig, None]:
    banner()

    print("\nSelect an option:")
    print("1) Study")
    print("2) Conduct experiment")
    print("3) Conduct automatically")
    option = read(min=1, max=3)

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
            return

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
            return

        study(session, studies, available[choice - 1])
        print("Done.")
        enter()
    else:
        if option == 3:
            max_experiments = 9999999
            automatic = True
        else:
            automatic = False
        # Experiment
        experiments = {}
        total_glass = 0
        found_academy = -1

        # while (total_glass < 300000 or found_academy < 0):
        banner()
        print("Pick city: ")
        city = chooseCity(session)
        total_glass = int(city["availableResources"][3])

        # Check if enough glass
        if automatic is False:
            if total_glass < 300000:
                print(
                    f"Not enough glass ({addThousandSeparator(total_glass)}), try another city. Min=300k"
                )
                time.sleep(2)
                enter()
                return

        # Search for Academy
        for building in city["position"]:
            if building["building"] == "academy":
                found_academy = building["position"]

        if found_academy < 0:
            print(f"No academy in this town, pick another one")
            time.sleep(2)
            enter()
            return

        if automatic is False:
            max_experiments = total_glass // 300000
            automatic = False
            banner()
            print(f"How many experiments? Min=1, Max={max_experiments}")
            choice = read(min=1, max=max_experiments)

        if automatic is True:
            choice = 999999

        # Build experiments dict
        experiments["cityID"] = city["id"]
        experiments["cityName"] = city["name"]
        experiments["pos"] = found_academy
        experiments["qty"] = choice

        return {"experiments": experiments, "automatic": automatic}

def do_it(session: Session, experiments: Experiments, automatic: bool):
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






