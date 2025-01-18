#! /usr/bin/env python3
# -*- coding: utf-8 -*-


import time

from ikabot.helpers.botComm import *
from ikabot.helpers.gui import enter
from ikabot.helpers.varios import daysHoursMinutes

from typing import TYPE_CHECKING, TypedDict
if TYPE_CHECKING:
    from ikabot.web.session import Session

AlertAttacksConfig = TypedDict("AlertAttacksConfig", {"minutes": int})
def alertAttacks(session: Session) -> AlertAttacksConfig:
    if checkTelegramData(session) is False:
        return

    banner()
    default = 20
    minutes = read(
        msg=
            "How often should I search for attacks?(min:3, default: {:d}): ".format(default),
        min=3,
        default=default,
    )
    print("I will check for attacks every {:d} minutes".format(minutes))
    enter()

    return {"minutes": minutes}

def do_it(session: Session, minutes: int):

    knownAttacks = []
    while True:
        currentAttacks = []
    
        # get the militaryMovements
        html = session.get()
        city_id = re.search(r"currentCityId:\s(\d+),", html).group(1)
        url = "view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1".format(
            city_id, actionRequest
        )
        movements_response = session.post(url)
        postdata = json.loads(movements_response, strict=False)
        militaryMovements = postdata[1][1][2]["viewScriptParams"][
            "militaryAndFleetMovements"
        ]
        timeNow = int(postdata[0][1]["time"])

        for militaryMovement in [
            mov for mov in militaryMovements if mov["isHostile"]
        ]:
            event_id = militaryMovement["event"]["id"]
            currentAttacks.append(event_id)
            # if we already alerted this, do nothing
            if event_id not in knownAttacks:
                knownAttacks.append(event_id)

                # get information about the attack
                missionText = militaryMovement["event"]["missionText"]
                origin = militaryMovement["origin"]
                target = militaryMovement["target"]
                amountTroops = militaryMovement["army"]["amount"]
                amountFleets = militaryMovement["fleet"]["amount"]
                timeLeft = int(militaryMovement["eventTime"]) - timeNow

                # send alert
                msg = "-- ALERT --\n"
                msg += missionText + "\n"
                msg += "from the city {} of {}\n".format(
                    origin["name"], origin["avatarName"]
                )
                msg += "a {}\n".format(target["name"])
                msg += "{} units\n".format(amountTroops)
                msg += "{} fleet\n".format(amountFleets)
                msg += "arrival in: {}\n".format(daysHoursMinutes(timeLeft))
                msg += "If you want to put the account in vacation mode send:\n"
                msg += "{:d}:1".format(os.getpid())
                sendToBot(session, msg)


        # remove old attacks from knownAttacks
        for event_id in list(knownAttacks):
            if event_id not in currentAttacks:
                knownAttacks.remove(event_id)

        time.sleep(minutes * 60)
