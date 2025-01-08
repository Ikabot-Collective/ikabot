#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import time
import traceback

from ikabot.function.vacationMode import activateVacationMode
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import enter
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import daysHoursMinutes


def alertAttacks(session, event, stdin_fd, predetermined_input):
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
        if checkTelegramData(session) is False:
            event.set()
            return

        banner()
        default = 20
        minutes = read(
            msg=
                "How often should I search for attacks?(min:3, default: {:d}): ".format(default),
            min=3,
            default=default,
        )
        # min_units = read(msg=_('Attacks with less than how many units should be ignored? (default: 0): '), digit=True, default=0)
        print("I will check for attacks every {:d} minutes".format(minutes))
        enter()
    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()

    info = "\nI check for attacks every {:d} minutes\n".format(minutes)
    setInfoSignal(session, info)
    try:
        do_it(session, minutes)
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def respondToAttack(session):
    """
    Parameters
    ---------
    session : ikabot.web.session.Session
    """

    # this allows the user to respond to an attack via telegram
    while True:
        time.sleep(60 * 3)
        responses = getUserResponse(session)
        for response in responses:
            # the response should be in the form of:
            # <pid>:<action number>
            rta = re.search(r"(\d+):?\s*(\d+)", response)
            if rta is None:
                continue

            pid = int(rta.group(1))
            action = int(rta.group(2))

            # if the pid doesn't match, we ignore it
            if pid != os.getpid():
                continue

            # currently just one action is supported
            if action == 1:
                # mv
                activateVacationMode(session)
            else:
                sendToBot(session, "Invalid command: {:d}".format(action))


def do_it(session, minutes):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    minutes : int
    """

    # this thread lets the user react to an attack once the alert is sent
    thread = threading.Thread(target=respondToAttack, args=(session,))
    thread.start()

    knownAttacks = []
    while True:
        ##Catch errors inside the function to not exit for any reason.
        currentAttacks = []
        try:
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

        except Exception as e:
            info = "\nI check for attacks every {:d} minutes\n".format(minutes)
            msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
            sendToBot(session, msg)

        # remove old attacks from knownAttacks
        for event_id in list(knownAttacks):
            if event_id not in currentAttacks:
                knownAttacks.remove(event_id)

        time.sleep(minutes * 60)
