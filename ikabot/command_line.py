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
from ikabot.function.islandWorkplaces import islandWorkplaces
from ikabot.function.update import update
from ikabot.helpers.pedirInfo import read
from ikabot.function.getStatus import getStatus
from ikabot.function.getStatusImproved import getStatusForAllCities
from ikabot.function.donationBot import donationBot
from ikabot.helpers.botComm import updateTelegramData, telegramDataIsValid
from ikabot.helpers.process import IkabotProcessListManager
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
from ikabot.function.stationArmy import stationArmy
from ikabot.function.logs import logs
from ikabot.function.testTelegramBot import testTelegramBot


t = gettext.translation('command_line', localedir, languages=languages, fallback=True)
_ = t.gettext

__function_refresh = 'refresh'
__function_exit = 'exit'

__command_back = ['Back', __function_refresh]

_global_menu = [
    ['Exit', __function_exit],
    ['Construction list', constructionList],
    ['Send resources', sendResources],
    ['Distribute resources', distributeResources],
    ['Account status', [
      ['Simplified', getStatus],
      ['All Cities', getStatusForAllCities],
    ]],
    ['Monitor islands', searchForIslandSpaces],
    ['Login daily', loginDaily],
    ['Alerts / Notifications', [
        __command_back,
        ['Alert attacks', alertAttacks],
        ['Alert wine running out', alertLowWine],
    ]],
    ['Marketplace', [
        __command_back,
        ['Buy resources', buyResources],
        ['Sell resources', sellResources],
    ]],
    ['Donate', [
        __command_back,
        ['Donate once', islandWorkplaces],
        ['Donate automatically', donationBot],
    ]],
    ['Activate vacation mode', vacationMode],
    ['Activate miracle', activateMiracle],
    ['Military actions', [
        __command_back,
        ['Train Army', trainArmy],
        ['Send Troops/Ships', stationArmy],
    ]],
    ['See movements', shipMovements],
    ['Construct building', constructBuilding],
    ['Update Ikabot', update],
    ['Import / Export cookie', importExportCookie],
    ['Auto-Pirate', autoPirate],
    ['Investigate', investigate],
    ['Attack barbarians', attackBarbarians],
    ['Dump / View world', dumpWorld],
    ['Options / Settings', [
        __command_back,
        ['Configure Proxy', proxyConf],
        ['Telegram Bot', [
            __command_back,
            ['Change bot data', updateTelegramData],
            ['Test message the bot', testTelegramBot],
        ]],
        ['Kill tasks', killTasks],
        ['Configure captcha resolver', decaptchaConf],
        ['Logs', logs],
    ]],
    ['Refresh process info', __function_refresh],
]


def choose_from_menu(menu_options, prefix=''):
    for ind, option in enumerate(menu_options):
        print(prefix, "{: >3})".format(ind), option[0])
    selected = read(min=0, max=len(menu_options)-1, digit=True)

    print()
    [name, fn] = menu_options[selected]
    print(prefix, 'Selected {}) {}'.format(selected, name))
    if type(fn) is list:
        return choose_from_menu(fn, prefix + '  ')

    return fn

def menu(session):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    """
    checkForUpdate()
    show_proxy(session)
    process_list_manager = IkabotProcessListManager(session)

    while True:
        banner()

        process_list_manager.print_proces_table()

        try:
            selected = choose_from_menu(_global_menu)

            if selected == __function_exit:
                # Perform exit of the app
                if isWindows:
                    # in unix, you can exit ikabot and close the terminal and the processes will continue to execute
                    # in windows, you can exit ikabot but if you close the terminal, the processes will die
                    print(_('Closing this console will kill the processes.'))
                    enter()
                clear()
                os._exit(0)  # kills the process which executes this statement, but it does not kill it's child processes

            if selected == __function_refresh:
                # we just need to refresh the menu
                continue

            # we've selected a function, let's execute it
            event = multiprocessing.Event()  # creates a new event
            config.has_params = len(config.predetermined_input) > 0
            process = multiprocessing.Process(
                target=selected,
                args=(session, event, sys.stdin.fileno(), config.predetermined_input),
                name=selected.__name__
            )

            process.start()
            process_list_manager.add_process({
                'pid': process.pid,
                'action': selected.__name__,
                'date': time.time(),
                'status': 'started'
            })

            # waits for the process to fire the event that's been given to it.
            # When it does  this process gets back control of the command line
            # and asks user for more input
            event.wait()
        except KeyboardInterrupt:
            pass

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