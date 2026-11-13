#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import time

from ikabot.config import *
from ikabot.helpers.getJson import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.resources import *
from ikabot.helpers.varios import *
from ikabot.helpers.botComm import *
from ikabot.helpers.decorators import configurator, task


def findShrine(session):
    """Finding the city with Shrine and it's position
    Parameters
    ----------
    session : ikabot.web.session.Session

    Returns
    -------
    shrineCity[int], shrinePos[int]
    """
    cities_ids = getIdsOfCities(session)[0]
    for city_id in cities_ids:
        html = session.get(city_url + city_id)
        city = getCity(html)
        for pos, building in enumerate(city["position"]):
            if building["building"] == "shrineOfOlympus":
                shrineCity = city_id
                shrinePos = pos
                return (
                    shrineCity,
                    shrinePos,
                )  # Return as soon as Shrine and it's position is found
    return None, None  # Return None if not found


def gods(godid):
    """Converts godid into it's respectable name
    Parameters
    ----------
    session : ikabot.web.session.Session
    godid : int
    """
    names = {
        1: "Pan",
        2: "Dionysus",
        3: "Tyche",
        4: "Plutus",
        5: "Theia",
        6: "Hephaestus",
    }
    return names.get(godid, None)


def getFavor(session, cityid, pos):
    """Extracts the currentFavor amount from Ikariam
    Parameters
    ----------
    session : ikabot.web.session.Session
    cityid : int
    pos : int
    Returns
    -------
    favor[int]
    """
    try:
        fav_url = f"view=shrineOfOlympus&cityId={cityid}&position={pos}&activeTab=tabOverview&backgroundView=city&currentCityId={cityid}&templateView=shrineOfOlympus&actionRequest={actionRequest}&ajax=1"
        get_fav = session.get(fav_url, noIndex=True)
        load_fav = json.loads(get_fav, strict=False)
        favor = load_fav[2][1]["currentFavor"]
        return favor
    except Exception as e:
        print(e)
        return 0


def donateShrine(session, godid, cityid, pos, selected_gods):
    """Donates to the selected Gods and updates the task status accordingly
    Parameters
    ----------
    session : ikabot.web.session.Session
    godid : int
    cityid : int
    pos : int
    selected_gods : str
    """
    url = f"action=DonateFavorToGod&godId={godid}&position={pos}&backgroundView=city&currentCityId={cityid}&templateView=shrineOfOlympus&currentTab=tabOverview&actionRequest={actionRequest}&ajax=1"
    session.post(url)
    current_favor = getFavor(session, cityid, pos)
    last_donation_time = getDateTime()
    last_donation_status = f"Activated {selected_gods} @{last_donation_time}, current favor: {current_favor}"
    session.setStatus(last_donation_status)
    return current_favor, last_donation_time, last_donation_status


@task("activateShrine")
def do_it(session, godids, mode, times, selected_gods, wait_time):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    godids : tuple[int]
    mode : int
    times : int
    selected_gods : str
    wait_time : int
    """
    last_donation_status = ""
    last_donation_time = ""
    current_favor = ""
    try:
        favor_needed = (
            len(godids) * 100
        )  # Calculate the required amount of favor to donate all selected gods at once
        shrineCity, shrinePos = findShrine(session)
        if shrineCity is not None and shrinePos is not None:
            cityid, pos = shrineCity, shrinePos
        else:
            msg = "Shrine city or building position was not found."
            sendToBot(session, msg)
            return

        if mode == 1 or mode == 3:
            for _ in range(times):
                favor = getFavor(session, cityid, pos)
                while favor < favor_needed:
                    session.setStatus(
                        f"Not enough favor @{getDateTime()}, re-trying in 3h."
                    )
                    time.sleep(wait_time / 4)  # 12h / 4 = 3 hours
                    favor = getFavor(session, cityid, pos)
                for godid in godids:
                    current_favor, last_donation_time, last_donation_status = donateShrine(session, godid, cityid, pos, selected_gods)
                    time.sleep(2)

            if mode == 1:
                return
            mode = 2  # If mode is both, set mode for loop

        if mode == 2:
            while True:
                favor = getFavor(session, cityid, pos)
                while favor < favor_needed:
                    session.setStatus(
                        f"Not enough favor @{getDateTime()}, re-trying in 3h."
                    )
                    time.sleep(wait_time / 4)  # 12h / 4 = 3 hours
                    favor = getFavor(session, cityid, pos)
                for godid in godids:
                    current_favor, last_donation_time, last_donation_status = donateShrine(session, godid, cityid, pos, selected_gods)
                    time.sleep(2)
                for i in range(6):  # 12h * 6 = 72 hours
                    time.sleep(wait_time)  # 12h
                    current_favor = getFavor(session, cityid, pos)
                    last_donation_status = f"Activated {selected_gods} @{last_donation_time}, current favor: {current_favor}"
                    session.setStatus(
                        last_donation_status
                    )  # Update only current favor value in the task status message, activation/donation time remains

    except Exception as e:
        msg = f"Error in activateShrine:\n\n{e}"
        sendToBot(session, msg)
        return


@configurator
def activateShrine(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd : int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    banner()
    godids = []
    selected_gods = ""
    wait_time = 60 * 60 * 12  # 12 hours, wait_time*6 equals total shrine grace time of 72h

    while True:
        print(
            """Which God(s) would you like to activate autonomously? 
    (0) Continue
    (1) Pan (Wood)
    (2) Dionysus (Wine)
    (3) Tyche (Marble)
    (4) Plutus (Gold)
    (5) Theia (Crystal)
    (6) Hephaestus (Sulphur)
    """
        )
        god = read(min=0, max=6, digit=True)
        if god == 0:
            if len(godids) == 0:
                return None
            named_gods = [gods(godid) for godid in godids]
            gods_str = ", ".join(named_gods) if len(named_gods) > 1 else named_gods[0]
            selected_gods = gods_str
            break
        else:
            godids.append(god)
            continue

    print("")
    print(
        """Would you like to activate the selected God(s) a specific amount of times or autonomously every 70 hours?
(1) Specific amount of times in a row
(2) Autonomously every 70 hours
(3) Both
"""
    )
    mode = read(min=1, max=3, digit=True)
    if mode == 1 or mode == 3:
        print("How many times would you like to activate the selected God(s)?")
        times = read(min=1, max=10, digit=True)
    if mode == 2:
        mode = 2
        times = 0

    return {
        "session": session,
        "godids": tuple(godids),
        "mode": mode,
        "times": times,
        "selected_gods": selected_gods,
        "wait_time": wait_time,
    }

