#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import traceback

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getIsland
from ikabot.helpers.gui import enter
from ikabot.helpers.pedirInfo import getIslandsIds
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import getDateTime, wait


def searchForIslandSpaces(session, event, stdin_fd, predetermined_input):
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
        print(
            "Do you want to search for spaces on your islands or a specific set of islands?"
        )
        print("(0) Exit")
        print("(1) Search all islands I have colonised")
        print("(2) Search a specific set of islands")
        choice = read(min=0, max=2)
        islandList = []
        if choice == 0:
            event.set()
            return
        elif choice == 2:
            banner()
            print(
                "Insert the coordinates of each island you want searched like so: X1:Y1, X2:Y2, X3:Y3..."
            )
            coords_string = read()
            coords_string = coords_string.replace(" ", "")
            coords = coords_string.split(",")
            for coord in coords:
                coord = "&xcoord=" + coord
                coord = coord.replace(":", "&ycoord=")
                html = session.get("view=island" + coord)
                island = getIsland(html)
                islandList.append(island["id"])
        else:
            pass

        banner()
        print(
            "How frequently should the islands be searched in minutes (minimum is 3)?"
        )
        time = read(min=3, digit=True)
        banner()
        print(
            "Do you wish to be notified when a fight breaks out and stops on a city on these islands? (Y|N)"
        )
        fights = read(values=["y", "Y", "n", "N"])
        banner()
        print("I will search for changes in the selected islands")
        enter()
    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()

    info = "\nI search for new spaces each hour\n"
    setInfoSignal(session, info)
    try:
        do_it(session, islandList, time, fights)
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def do_it(session, islandList, time, fights):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    islandList : list[dict]
        A list containing island objects which should be searched, if an empty list is passed, all the user's colonised islands are searched
    time : int
        The time in minutes between two consecutive seraches
    fights : str
        String that can either be y or n. Indicates whether or not to scan for fight activity on islands
    """

    # this dict will contain all the cities from each island
    # as they where in last scan
    cities_before_per_island = {}

    while True:
        # this is done inside the loop because the user may colonize in a new island
        if islandList != []:
            islandsIds = islandList
        else:
            islandsIds = getIslandsIds(session)
        for islandId in islandsIds:
            html = session.get(island_url + islandId)
            island = getIsland(html)
            # cities in the current island
            cities_now = [
                city_space
                for city_space in island["cities"]
                if city_space["type"] != "empty"
            ]  # loads the islands non empty cities into ciudades

            # if we haven't scaned this island before,
            # save it and do nothing
            if islandId not in cities_before_per_island:
                cities_before_per_island[islandId] = cities_now.copy()
            else:
                cities_before = cities_before_per_island[islandId]

                # someone disappeared
                for city_before in cities_before:
                    if city_before["id"] not in [
                        city_now["id"] for city_now in cities_now
                    ]:
                        # we didn't find the city_before in the cities_now
                        msg = "The city {} of the player {} disappeared in {}:{}.\n{}-{} / S.M. lvl: {} / L.G. lvl: {}.".format(
                            city_before["name"],
                            city_before["Name"],
                            island["x"],
                            island["y"],
                            materials_names[int(island["tradegood"])],
                            island["wonderName"],
                            island["resourceLevel"],
                            island["tradegoodLevel"],
                        )
                        sendToBot(session, msg)

                    if fights.lower() == "y":
                        for city_now in cities_now:
                            if city_now["id"] == city_before["id"]:
                                if (
                                    "infos" in city_now
                                    and "infos" not in city_before
                                    and "armyAction" in city_now["infos"]
                                    and city_now["infos"]["armyAction"] == "fight"
                                ):
                                    msg = "A fight started in the city {} of the player {} on island {} {}:{} {}".format(
                                        city_before["name"],
                                        city_before["Name"],
                                        materials_names[int(island["tradegood"])],
                                        island["x"],
                                        island["y"],
                                        island["name"],
                                    )
                                    sendToBot(session, msg)
                                if (
                                    "infos" not in city_now
                                    and "infos" in city_before
                                    and "armyAction" in city_before["infos"]
                                    and city_before["infos"]["armyAction"] == "fight"
                                ):
                                    msg = "A fight stopped in the city {} of the player {} on island {} {}:{} {}".format(
                                        city_before["name"],
                                        city_before["Name"],
                                        materials_names[int(island["tradegood"])],
                                        island["x"],
                                        island["y"],
                                        island["name"],
                                    )
                                    sendToBot(session, msg)

                # someone colonised
                for city_now in cities_now:
                    if city_now["id"] not in [
                        city_before["id"] for city_before in cities_before
                    ]:
                        # we didn't find the city_now in the cities_before
                        msg = "Player {} created a new city {} in {} {}:{} {}".format(
                            city_now["Name"],
                            city_now["name"],
                            materials_names[int(island["tradegood"])],
                            island["x"],
                            island["y"],
                            island["name"],
                        )
                        sendToBot(session, msg)

                cities_before_per_island[islandId] = (
                    cities_now.copy()
                )  # update cities_before_per_island for the current island
        session.setStatus(
            f'Checked islands {str([int(i) for i in islandsIds]).replace(" ","")} @ {getDateTime()[-8:]}'
        )
        wait(time * 60)
