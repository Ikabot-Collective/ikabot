#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time

from ikabot.config import *
from ikabot.helpers.getJson import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.resources import *
from ikabot.helpers.varios import *
from ikabot.helpers.botComm import *

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ikabot.web.session import Session

wait_time = 60 * 60 * 12  # 12 hours, wait_time*6 equals total shrine grace time of 72h
last_donation_time = ""

ActivateShrineConfig = TypedDict("ActivateShrineConfig", {"godids": list[int], "mode": int, "times": int})
def activateShrine(session: Session) -> ActivateShrineConfig:
    banner()
    godids = []

    while True:
        print(
            """Which God(s) would you like to activate automatically? 
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
                return
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

    return {"godids": godids, "mode": mode, "times": times}

def do_it(session: Session, godids: list[int], mode: int, times: int):
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
            for godid in godids:
                favor = getFavor(session, cityid, pos)
                while favor < favor_needed:
                    session.setStatus(
                        f"Not enough favor @{getDateTime()}, re-trying in 3h."
                    )
                    time.sleep(wait_time / 4)  # 12h / 4 = 3 hours
                donateShrine(session, godid, cityid, pos)
                time.sleep(2)

        if mode == 1:
            return
        mode = 2  # If mode is both, set mode for loop

    if mode == 2:
        while True:
            for godid in godids:
                favor = getFavor(session, cityid, pos)
                while favor < favor_needed:
                    session.setStatus(
                        f"Not enough favor @{getDateTime()}, re-trying in 3h."
                    )
                    time.sleep(wait_time / 4)  # 12h / 4 = 3 hours
                donateShrine(session, godid, cityid, pos)
                time.sleep(2)
            for i in range(6):  # 12h * 6 = 72 hours
                time.sleep(wait_time)  # 12h
                current_favor = getFavor(session, cityid, pos)
                session.setStatus(
                    f"Activated {", ".join([god_names[godid] for godid in godids])} @{last_donation_time}, current favor: {current_favor}"
                )  # Update only current favor value in the task status message, activation/donation time remains

def findShrine(session: Session) -> tuple[int, int]:
    """Finding the city id with Shrine and it's position"""
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


def getFavor(session: Session, cityid: int, pos: int) -> int:
    """Extracts the currentFavor amount from Ikariam"""
    try:
        fav_url = f"view=shrineOfOlympus&cityId={cityid}&position={pos}&activeTab=tabOverview&backgroundView=city&currentCityId={cityid}&templateView=shrineOfOlympus&actionRequest={actionRequest}&ajax=1"
        get_fav = session.get(fav_url, noIndex=True)
        load_fav = json.loads(get_fav, strict=False)
        favor = load_fav[2][1]["currentFavor"]
        return favor
    except Exception as e:
        print(e)
        return 0


def donateShrine(session: Session, godid: int, cityid: int, pos: int):
    """Donates to the selected Gods and updates the task status accordingly"""
    url = f"action=DonateFavorToGod&godId={godid}&position={pos}&backgroundView=city&currentCityId={cityid}&templateView=shrineOfOlympus&currentTab=tabOverview&actionRequest={actionRequest}&ajax=1"
    session.post(url)
    current_favor = getFavor(session, cityid, pos)
    global last_donation_time
    last_donation_time = getDateTime()
    session.setStatus(f"Activated {god_names[godid]} @{last_donation_time}, current favor: {current_favor}")
