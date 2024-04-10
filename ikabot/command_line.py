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
from ikabot.function.updateStatus import updateStatus, setStatus
from ikabot.function.cookieConf import cookieConf
from ikabot.helpers.checker import checker
from ikabot.function.proxyList import proxyList
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
from ikabot.helpers.botComm import telegramDataIsValid, updateTelegramData
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.process import updateProcessList
from ikabot.web.session import *

t = gettext.translation("command_line", localedir, languages=languages, fallback=True)
_ = t.gettext


def menu(session, checkUpdate=False):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    checkUpdate : bool
    """
    if checkUpdate:
        checker(session)
        checkForUpdate()

    show_proxy(session)

    #statusbanner(session) # DISABLED DUE TO A BUG
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
        1:            constructionList,
        2:            sendResources,
        3:            distributeResources,
        4:            getStatus,
        6:            searchForIslandSpaces,
        7:            loginDaily,
        101:            alertAttacks,
        102:            alertLowWine,
        111:            buyResources,
        112:            sellResources,
        121:            donate,
        122:            donationBot,
        11:            vacationMode,
        12:            activateMiracle,
        131:            trainArmy,
        132:            stationArmy,
        14:            shipMovements,
        15:            constructBuilding,
        16:            importExportCookie,
        17:            autoPirate,
        18:            investigate,
        19:            attackBarbarians,
        20:            dumpWorld,
        141:            proxyConf,
        142:            updateTelegramData,
        143:            killTasks,
        144:            decaptchaConf,
        145:            updateStatus,
        146:            setStatus,
        147:            cookieConf,
        148:            proxyList,
        149:            logs,
        150:            testTelegramBot
                    }

    print(_('(0)  Exit'))
    print(_('(1)  Construction list'))
    print(_('(2)  Send resources'))
    print(_('(3)  Distribute resources'))
    print(_('(4)  Account status'))
    print(_('(5)  Update tasklist'))
    print(_('(6)  Monitor islands'))
    print(_('(7)  Login daily'))
    print(_('(8)  Alerts / Notifications'))
    print(_('(9)  Marketplace'))
    print(_('(10) Donate'))
    print(_('(11) Activate vacation mode'))
    print(_('(12) Activate miracle'))
    print(_('(13) Military actions'))
    print(_('(14) See movements'))
    print(_('(15) Construct building'))
    print(_('(16) Import / Export cookie'))
    print(_('(17) Auto-Pirate'))
    print(_('(18) Investigate'))
    print(_('(19) Attack barbarians'))
    print(_('(20) Dump / View world'))
    print(_('(21) Options / Settings'))

    total_options = len(menu_actions) + 1
    selected = read(min=0, max=total_options, digit=True)
    
    if selected == 5:
        print(f'Task list has been updated.\n{config.version}')
        time.sleep(1)
        menu(session)
        return
    
    if selected == 8:
        banner()
        print(_("(0) Back"))
        print(_("(1) Alert attacks"))
        print(_("(2) Alert wine running out"))

        selected = read(min=0, max=2, digit=True)
        if selected == 0:
            menu(session)
            return
        if selected > 0:
            selected += 100
            
    if selected == 9:
        banner()
        print(_("(0) Back"))
        print(_("(1) Buy resources"))
        print(_("(2) Sell resources"))

        selected = read(min=0, max=2, digit=True)
        if selected == 0:
            menu(session)
            return
        if selected > 0:
            selected += 110
            
    if selected == 10:
        banner()
        print(_("(0) Back"))
        print(_("(1) Donate once"))
        print(_("(2) Donate automatically"))

        selected = read(min=0, max=2, digit=True)
        if selected == 0:
            menu(session)
            return
        if selected > 0:
            selected += 120
            
    if selected == 13:
        banner()
        print(_("(0) Back"))
        print(_("(1) Train Army"))
        print(_("(2) Send Troops/Ships"))
        selected = read(min=0, max=2, digit=True)
        if selected == 0:
            menu(session)
            return
        if selected > 0:
            selected += 130

    if selected == 21:
        banner()
        print(_("(0) Back"))
        print(_("(1) Configure Proxy"))
        if telegramDataIsValid(session):
            print(_("(2) Change the Telegram data"))
        else:
            print(_('(2) Enter the Telegram data'))
            print(_('(3) Kill tasks'))
            print(_('(4) Configure captcha resolver'))
            print(_('(5) Toggle Status Banner'))
            print(_('(6) Update Status Banner'))
            print(_('(7) Cookie data file'))
            print(_('(8) Proxy list'))
            print(_('(9) Logs'))
            print(_('(10) Message Telegram Bot'))

        selected = read(min=0, max=10, digit=True)
        
        if selected == 0:
            menu(session)
            return
        if selected == 5:
            print(" This function has been disabled due to a bug.")
            time.sleep(1)
            menu(session)
            return
        if selected == 6:
            print(" This function has been disabled due to a bug.")
            time.sleep(1)
            menu(session)
            return
        if selected != 0 and selected != 5 and selected != 6:
            selected += 140

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
        session_data = session.getSessionData()
        session_data['status']['data'] = config.default_bner
        session_data['status']['set'] = False
        session.setSessionData(session_data)
        os._exit(0)  # kills the process which executes this statement, but it does not kill it's child processes


def init():
    if getattr(sys, 'frozen', False):
        home = os.path.dirname(sys.executable)#'USERPROFILE' if isWindows else 'HOME'
    elif __file__:
        home = os.path.dirname(__file__)
    os.chdir(str(home))
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
        menu(session, checkUpdate=True)
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
