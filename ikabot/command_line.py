#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import gettext
import multiprocessing
import os
import sys
import time

from ikabot.config import *
from ikabot.function.activateMiracle import activateMiracle
from ikabot.function.alertAttacks import alertAttacks
from ikabot.function.alertLowWine import alertLowWine
from ikabot.function.attackBarbarians import attackBarbarians
from ikabot.function.autoPirate import autoPirate
from ikabot.function.buyResources import buyResources
from ikabot.function.checkForUpdate import checkForUpdate
from ikabot.function.constructBuilding import constructBuilding
from ikabot.function.constructionList import constructionList
from ikabot.function.decaptchaConf import decaptchaConf
from ikabot.function.distributeResources import distributeResources
from ikabot.function.donate import donate
from ikabot.function.donationBot import donationBot
from ikabot.function.dumpWorld import dumpWorld
from ikabot.function.getStatus import getStatus
from ikabot.function.importExportCookie import importExportCookie
from ikabot.function.investigate import investigate
from ikabot.function.killTasks import killTasks
from ikabot.function.loginDaily import loginDaily
from ikabot.function.logs import logs
from ikabot.function.proxyConf import proxyConf, show_proxy
from ikabot.function.searchForIslandSpaces import searchForIslandSpaces
from ikabot.function.sellResources import sellResources
from ikabot.function.sendResources import sendResources
from ikabot.function.shipMovements import shipMovements
from ikabot.function.stationArmy import stationArmy
from ikabot.function.testTelegramBot import testTelegramBot
from ikabot.function.trainArmy import trainArmy
from ikabot.function.update import update
from ikabot.function.vacationMode import vacationMode
from ikabot.function.webServer import webServer
from ikabot.function.loadCustomModule import loadCustomModule
from ikabot.function.activateShrine import activateShrine
from ikabot.helpers.botComm import telegramDataIsValid, updateTelegramData
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.process import updateProcessList
from ikabot.web.session import *

t = gettext.translation("command_line", localedir, languages=languages, fallback=True)
_ = t.gettext


def menu(session, checkUpdate=True):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    checkUpdate : bool
    """
    if checkUpdate:
        checkForUpdate()

    show_proxy(session)

    banner()

    process_list = updateProcessList(session)
    if len(process_list) > 0:
        # Insert table header
        table = process_list.copy()
        table.insert(
            0, {"pid": "pid", "action": "task", "date": "date", "status": "status"}
        )
        # Get max length of strings in each category (date is always going to be 15)
        maxPid, maxAction, maxStatus = [
            max(i)
            for i in [
                [len(str(r["pid"])) for r in table],
                [len(str(r["action"])) for r in table],
                [len(str(r["status"])) for r in table],
            ]
        ]
        # Print header
        print(
            "|{:^{maxPid}}|{:^{maxAction}}|{:^15}|{:^{maxStatus}}|".format(
                table[0]["pid"],
                table[0]["action"],
                table[0]["date"],
                table[0]["status"],
                maxPid=maxPid,
                maxAction=maxAction,
                maxStatus=maxStatus,
            )
        )
        # Print process list
        [
            print(
                "|{:^{maxPid}}|{:^{maxAction}}|{:^15}|{:^{maxStatus}}|".format(
                    r["pid"],
                    r["action"],
                    datetime.datetime.fromtimestamp(r["date"]).strftime(
                        "%b %d %H:%M:%S"
                    ),
                    r["status"],
                    maxPid=maxPid,
                    maxAction=maxAction,
                    maxStatus=maxStatus,
                )
            )
            for r in process_list
        ]
        print("")

    menu_actions = {
        1: constructionList,
        2: sendResources,
        3: distributeResources,
        4: getStatus,
        5: activateShrine,
        6: loginDaily,
        701: alertAttacks,
        702: alertLowWine,
        801: buyResources,
        802: sellResources,
        901: donate,
        902: donationBot,
        10: vacationMode,
        11: activateMiracle,
        1201: trainArmy,
        1202: stationArmy,
        13: shipMovements,
        14: constructBuilding,
        15: update,
        16: webServer,
        17: autoPirate,
        18: investigate,
        19: attackBarbarians,
        2001: searchForIslandSpaces,
        2002: dumpWorld,
        2101: proxyConf,
        2102: updateTelegramData,
        2103: killTasks,
        2104: decaptchaConf,
        2105: logs,
        2106: testTelegramBot,
        2107: importExportCookie,
        2108: loadCustomModule
    }

    print(_("(0)  Exit"))
    print(_("(1)  Construction list"))
    print(_("(2)  Send resources"))
    print(_("(3)  Distribute resources"))
    print(_("(4)  Account status"))
    print(_("(5)  Activate Shrine"))
    print(_("(6)  Login daily"))
    print(_("(7)  Alerts / Notifications"))
    print(_("(8)  Marketplace"))
    print(_("(9)  Donate"))
    print(_("(10) Activate vacation mode"))
    print(_("(11) Activate miracle"))
    print(_("(12) Military actions"))
    print(_("(13) See movements"))
    print(_("(14) Construct building"))
    print(_("(15) Update Ikabot"))
    print(_("(16) Ikabot Web Server"))
    print(_("(17) Auto-Pirate"))
    print(_("(18) Investigate"))
    print(_("(19) Attack barbarians"))
    print(_("(20) Dump / Monitor world"))
    print(_("(21) Options / Settings"))
    total_options = len(menu_actions) + 1
    selected = read(min=0, max=total_options, digit=True, empty=True)
    
    # refresh main menu on hitting enter
    if selected == '':
        return menu(session)

    if selected == 7:
        banner()
        print(_("(0) Back"))
        print(_("(1) Alert attacks"))
        print(_("(2) Alert wine running out"))

        selected = read(min=0, max=2, digit=True)
        if selected == 0:
            menu(session)
            return
        if selected > 0:
            selected += 700

    if selected == 8:
        banner()
        print(_("(0) Back"))
        print(_("(1) Buy resources"))
        print(_("(2) Sell resources"))

        selected = read(min=0, max=2, digit=True)
        if selected == 0:
            menu(session)
            return
        if selected > 0:
            selected += 800

    if selected == 9:
        banner()
        print(_("(0) Back"))
        print(_("(1) Donate once"))
        print(_("(2) Donate automatically"))

        selected = read(min=0, max=2, digit=True)
        if selected == 0:
            menu(session)
            return
        if selected > 0:
            selected += 900

    if selected == 12:
        banner()
        print(_("(0) Back"))
        print(_("(1) Train Army"))
        print(_("(2) Send Troops/Ships"))
        selected = read(min=0, max=2, digit=True)
        if selected == 0:
            menu(session)
            return
        if selected > 0:
            selected += 1200

    if selected == 20:
        print(_("(0) Back"))
        print(_("(1) Monitor islands"))
        print(_("(2) Dump & Search world"))
        
        selected = read(min=0, max=2, digit=True)
        if selected == 0:
            menu(session)
            return
        if selected > 0:
            selected += 2000

    if selected == 21:
        banner()
        print(_("(0) Back"))
        print(_("(1) Configure Proxy"))
        if telegramDataIsValid(session):
            print(_("(2) Change the Telegram data"))
        else:
            print(_("(2) Enter the Telegram data"))
        print(_("(3) Kill tasks"))
        print(_("(4) Configure captcha resolver"))
        print(_("(5) Logs"))
        print(_("(6) Message Telegram Bot"))
        print(_("(7) Import / Export cookie"))
        print(_("(8) Load custom ikabot module"))

        selected = read(min=0, max=8, digit=True)
        if selected == 0:
            menu(session)
            return
        if selected > 0:
            selected += 2100

    if selected != 0:
        try:
            event = multiprocessing.Event()  # creates a new event
            config.has_params = len(config.predetermined_input) > 0
            process = multiprocessing.Process(
                target=menu_actions[selected],
                args=(session, event, sys.stdin.fileno(), config.predetermined_input),
                name=menu_actions[selected].__name__,
            )
            process.start()
            process_list.append(
                {
                    "pid": process.pid,
                    "action": menu_actions[selected].__name__,
                    "date": time.time(),
                    "status": "started",
                }
            )
            updateProcessList(session, programprocesslist=process_list)
            event.wait()  # waits for the process to fire the event that's been given to it. When it does  this process gets back control of the command line and asks user for more input
        except KeyboardInterrupt:
            pass
        menu(session, checkUpdate=False)
    else:
        if isWindows:
            # in unix, you can exit ikabot and close the terminal and the processes will continue to execute
            # in windows, you can exit ikabot but if you close the terminal, the processes will die
            print(_("Closing this console will kill the processes."))
            enter()
        clear()
        os._exit(
            0
        )  # kills the process which executes this statement, but it does not kill it's child processes


def init():
    home = "USERPROFILE" if isWindows else "HOME"
    os.chdir(os.getenv(home))
    if not os.path.isfile(ikaFile):
        open(ikaFile, "w")
        os.chmod(ikaFile, 0o600)


def start():
    init()
    config.has_params = len(sys.argv) > 1
    for arg in sys.argv:
        try:
            config.predetermined_input.append(int(arg))
        except ValueError:
            config.predetermined_input.append(arg)
    config.predetermined_input.pop(0)

    session = Session()
    try:
        menu(session)
    finally:
        clear()
        session.logout()


def main():
    manager = multiprocessing.Manager()
    predetermined_input = manager.list()
    config.predetermined_input = predetermined_input
    try:
        start()
    except KeyboardInterrupt:
        clear()


if __name__ == "__main__":
    # On Windows calling this function is necessary.
    if sys.platform.startswith("win"):
        multiprocessing.freeze_support()
    main()

#############################################################
# This is necessary to ensure that flask is frozen together #
# with other requirements when creating ikabot.exe          #
try: import flask                                           #
except: pass                                                #
#############################################################
