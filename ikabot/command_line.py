#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import gettext
import multiprocessing
import time
import datetime
from ikabot.config import *
from ikabot.web.session import *
from ikabot.helpers.gui import *
from ikabot.function.donate import donate
from ikabot.function.update import update
from ikabot.helpers.pedirInfo import read
from ikabot.function.getStatus import getStatus
from ikabot.function.donationBot import donationBot
from ikabot.helpers.botComm import updateTelegramData, telegramDataIsValid
from ikabot.helpers.process import updateProcessList
from ikabot.function.constructionList import constructionList
from ikabot.function.searchForIslandSpaces import searchForIslandSpaces
from ikabot.function.alertAttacks import alertAttacks
from ikabot.function.vacationMode import vacationMode
from ikabot.function.activateMiracle import activateMiracle
from ikabot.function.trainArmy import trainArmy
from ikabot.function.sellResources import sellResources
from ikabot.function.checkForUpdate import checkForUpdate
from ikabot.function.distributeResources import distributeResources
from ikabot.function.alertLowWine import alertLowWine
from ikabot.function.buyResources import buyResources
from ikabot.function.loginDaily import loginDaily
from ikabot.function.sendResources import sendResources
from ikabot.function.constructBuilding import constructBuilding
from ikabot.function.shipMovements import shipMovements
from ikabot.function.importExportCookie import importExportCookie
from ikabot.function.autoPirate import autoPirate
from ikabot.function.investigate import investigate
from ikabot.function.attackBarbarians import attackBarbarians
from ikabot.function.proxyConf import proxyConf, show_proxy
from ikabot.function.killTasks import killTasks
from ikabot.function.decaptchaConf import decaptchaConf
from ikabot.function.dumpWorld import dumpWorld

t = gettext.translation('command_line', localedir, languages=languages, fallback=True)
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
        print('|{:^6}|{:^35}|{:^15}|'.format('pid', 'task', 'date'))
        print('_'*60)
        for process in process_list:
            if 'date' in process:
                print('|{:^6}|{:^35}|{:^15}|'.format(process['pid'], process['action'], datetime.datetime.fromtimestamp(process['date']).strftime('%b %d %H:%M:%S')))
            else:
                print('|{:^6}|{:^35}|'.format(process['pid'], process['action']))

        print('')

    menu_actions = {
        1:            constructionList,
        2:            sendResources,
        3:            distributeResources,
        4:            getStatus,
        5:            searchForIslandSpaces,
        6:            loginDaily,
        101:            alertAttacks,
        102:            alertLowWine,
        111:            buyResources,
        112:            sellResources,
        121:            donate,
        122:            donationBot,
        10:            vacationMode,
        11:            activateMiracle,
        12:            trainArmy,
        13:            shipMovements,
        14:            constructBuilding,
        15:            update,
        16:            importExportCookie,
        17:            autoPirate,
        18:            investigate,
        19:            attackBarbarians,
        20:            dumpWorld,
        22:            proxyConf,
        23:            updateTelegramData,
        24:            killTasks,
        25:            decaptchaConf,
                    }

    print(_('(0)  Exit'))
    print(_('(1)  Construction list'))
    print(_('(2)  Send resources'))
    print(_('(3)  Distribute resources'))
    print(_('(4)  Account status'))
    print(_('(5)  Monitor islands'))
    print(_('(6)  Login daily'))
    print(_('(7)  Alerts / Notifications'))
    print(_('(8)  Marketplace'))
    print(_('(9)  Donate'))
    print(_('(10) Activate vacation mode'))
    print(_('(11) Activate miracle'))
    print(_('(12) Train army'))
    print(_('(13) See movements'))
    print(_('(14) Construct building'))
    print(_('(15) Update Ikabot'))
    print(_('(16) Import / Export cookie'))
    print(_('(17) Auto-Pirate'))
    print(_('(18) Investigate'))
    print(_('(19) Attack barbarians'))
    print(_('(20) Dump / View world'))
    print(_('(21) Options / Settings'))
    total_options = len(menu_actions) + 1
    selected = read(min=0, max=total_options, digit=True)
    
    if selected == 7:
        banner()
        print(_('(0) Back'))
        print(_('(1) Alert attacks'))
        print(_('(2) Alert wine running out'))

        selected = read(min=0, max=2, digit=True)
        if selected == 0:
            menu(session)
            return
        if selected > 0:
            selected += 100
            
    if selected == 8:
        banner()
        print(_('(0) Back'))
        print(_('(1) Buy resources'))
        print(_('(2) Sell resources'))

        selected = read(min=0, max=2, digit=True)
        if selected == 0:
            menu(session)
            return
        if selected > 0:
            selected += 110
            
    if selected == 9:
        banner()
        print(_('(0) Back'))
        print(_('(1) Donate once'))
        print(_('(2) Donate automatically'))

        selected = read(min=0, max=2, digit=True)
        if selected == 0:
            menu(session)
            return
        if selected > 0:
            selected += 120

    if selected == 21:
        banner()
        print(_('(0) Back'))
        print(_('(1) Configure Proxy'))
        if telegramDataIsValid(session):
            print(_('(2) Change the Telegram data'))
        else:
            print(_('(2) Enter the Telegram data'))
        print(_('(3) Kill tasks'))
        print(_('(4) Configure captcha resolver'))

        selected = read(min=0, max=4, digit=True)
        if selected == 0:
            menu(session)
            return
        if selected > 0:
            selected += 21

    if selected != 0:
        try:
            event = multiprocessing.Event()  # creates a new event
            process = multiprocessing.Process(target=menu_actions[selected], args=(session, event, sys.stdin.fileno(), config.predetermined_input), name=menu_actions[selected].__name__)
            process.start()
            process_list.append({'pid': process.pid, 'action': menu_actions[selected].__name__, 'date': time.time()})
            updateProcessList(session, programprocesslist=process_list)
            event.wait()  # waits for the process to fire the event that's been given to it. When it does  this process gets back control of the command line and asks user for more input
        except KeyboardInterrupt:
            pass
        menu(session, checkUpdate=False)
    else:
        if isWindows:
            # in unix, you can exit ikabot and close the terminal and the processes will continue to execute
            # in windows, you can exit ikabot but if you close the terminal, the processes will die
            print(_('Closing this console will kill the processes.'))
            enter()
        clear()
        os._exit(0)  # kills the process which executes this statement, but it does not kill it's child processes


def init():
    home = 'USERPROFILE' if isWindows else 'HOME'
    os.chdir(os.getenv(home))
    if not os.path.isfile(ikaFile):
        open(ikaFile, 'w')
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


if __name__ == '__main__':
    # On Windows calling this function is necessary.
    if sys.platform.startswith('win'):
        multiprocessing.freeze_support()
    main()
