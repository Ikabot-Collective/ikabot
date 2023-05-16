#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import gettext
import traceback
import sys
from decimal import *
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.process import set_child_mode, updateProcessList, run
from ikabot.helpers.gui import *
from ikabot.helpers.resources import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.varios import *
from ikabot.helpers.naval import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.market import getGold

t = gettext.translation('loginDaily', localedir, languages=languages, fallback=True)
_ = t.gettext


def updateStatus(session, event, stdin_fd, predetermined_input):
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
        session_data = session.getSessionData()
        if session_data['status']['set'] is True:
            session_data['status']['set'] = False
            session_data['status']['data'] = config.default_bner
            session.setSessionData(session_data)
            try:
                process_list = updateProcessList(session)
                for process in process_list:
                    if process['action'] == 'updateStatus':
                        if isWindows:
                            run("taskkill /F /PID {}".format(process['pid']))
                        else:
                            run("kill -9 {}".format(process['pid']))
                    else:
                        print('Process updateStatus was not found!')
                        time.sleep(1)
                        event.set()
                        return
                    print(_('Status update has been disabled.'))
                    time.sleep(1)
                    event.set()
                    return
            except KeyboardInterrupt:
                event.set()
                return
        session_data['status']['set'] = True
        session_data['status']['data'] = 'Updating status, please wait...'
        session.setSessionData(session_data)
        statusbanner(session)
        print(_('I will update the status banner every 30 minutes.'))
        time.sleep(1)
    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()

    info = _('\nI will update the status banner every 30 minutes\n')
    setInfoSignal(session, info)
    try:
        do_it(session)
    except Exception as e:
        msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()
        
        

def do_it(session):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    """
    while True: 
        try:
            color_arr = [bcolors.ENDC, bcolors.HEADER, bcolors.STONE, bcolors.BLUE, bcolors.WARNING]

            (ids, __) = getIdsOfCities(session)
            total_resources = [0] * len(materials_names)
            total_production = [0] * len(materials_names)
            total_wine_consumption = 0
            available_ships = 0
            total_ships = 0
            for id in ids:
                session.get('view=city&cityId={}'.format(id), noIndex=True)
                data = session.get("view=updateGlobalData&ajax=1", noIndex=True)
                json_data = json.loads(data, strict=False)
                json_data = json_data[0][1]['headerData']
                if json_data['relatedCity']['owncity'] != 1:
                    continue
                wood = Decimal(json_data['resourceProduction'])
                good = Decimal(json_data['tradegoodProduction'])
                typeGood = int(json_data['producedTradegood'])
                total_production[0] += wood * 3600
                total_production[typeGood] += good * 3600
                total_wine_consumption += json_data['wineSpendings']
                total_resources[0] += json_data['currentResources']['resource']
                total_resources[1] += json_data['currentResources']['1']
                total_resources[2] += json_data['currentResources']['2']
                total_resources[3] += json_data['currentResources']['3']
                total_resources[4] += json_data['currentResources']['4']
                available_ships = json_data['freeTransporters']
                total_ships = json_data['maxTransporters']
                total_gold = int(Decimal(json_data['gold']))
                total_gold_production = int(Decimal(json_data['scientistsUpkeep'] + json_data['income'] + json_data['upkeep']))
            status_output = _('Ships {:d}/{:d}').format(int(available_ships), int(total_ships)) + "\n"
            status_output += (_("\nTotal:")) + "\n"
            status_output += '{:>10}'.format(' ')
            for i in range(len(materials_names)):
                status_output += '{:>12}'.format(materials_names_english[i]) + '|'
            status_output += "\n"
            status_output += '{:>10}'.format('Available') + '|'
            for i in range(len(materials_names)):
                status_output += '{:>12}'.format(addThousandSeparator(total_resources[i], ' ')) + '|'
            status_output += "\n"
            status_output += '{:>10}'.format('Production') + '|'
            for i in range(len(materials_names)):
                status_output += '{:>12}'.format(addThousandSeparator(total_production[i], ' ')) + '|'
            status_output += "\n"
            status_output += "Gold : {}, Gold production : {}".format(addThousandSeparator(total_gold, ' '), addThousandSeparator(total_gold_production, ' ')) + "\n"
            status_output += "Wine consumption : {}".format(addThousandSeparator(total_wine_consumption, ' '))

            session_data = session.getSessionData()
            session_data['status']['data'] = status_output
            session_data['status']['set'] = True
            session.setSessionData(session_data)
            if config.debugON_updateStatus == True:
                msg = 'Status was updated automatically.'
                sendToBot(session, msg)
        except Exception as e:
            msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
            sendToBot(session, msg)
            session_data = session.getSessionData()
            session_data['status']['set'] = False
            session_data['status']['data'] = config.default_bner
            session.setSessionData(session_data)
        time.sleep(60*30)


def setStatus(session, event, stdin_fd, predetermined_input):
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
        color_arr = [bcolors.ENDC, bcolors.HEADER, bcolors.STONE, bcolors.BLUE, bcolors.WARNING]

        (ids, __) = getIdsOfCities(session)
        total_resources = [0] * len(materials_names)
        total_production = [0] * len(materials_names)
        total_wine_consumption = 0
        available_ships = 0
        total_ships = 0
        for id in ids:
            session.get('view=city&cityId={}'.format(id), noIndex=True)
            data = session.get("view=updateGlobalData&ajax=1", noIndex=True)
            json_data = json.loads(data, strict=False)
            json_data = json_data[0][1]['headerData']
            if json_data['relatedCity']['owncity'] != 1:
                continue
            wood = Decimal(json_data['resourceProduction'])
            good = Decimal(json_data['tradegoodProduction'])
            typeGood = int(json_data['producedTradegood'])
            total_production[0] += wood * 3600
            total_production[typeGood] += good * 3600
            total_wine_consumption += json_data['wineSpendings']
            total_resources[0] += json_data['currentResources']['resource']
            total_resources[1] += json_data['currentResources']['1']
            total_resources[2] += json_data['currentResources']['2']
            total_resources[3] += json_data['currentResources']['3']
            total_resources[4] += json_data['currentResources']['4']
            available_ships = json_data['freeTransporters']
            total_ships = json_data['maxTransporters']
            total_gold = int(Decimal(json_data['gold']))
            total_gold_production = int(Decimal(json_data['scientistsUpkeep'] + json_data['income'] + json_data['upkeep']))
        status_output = _('Ships {:d}/{:d}').format(int(available_ships), int(total_ships)) + "\n"
        status_output += (_("\nTotal:")) + "\n"
        status_output += '{:>10}'.format(' ')
        for i in range(len(materials_names)):
            status_output += '{:>12}'.format(materials_names_english[i]) + '|'
        status_output += "\n"
        status_output += '{:>10}'.format('Available') + '|'
        for i in range(len(materials_names)):
            status_output += '{:>12}'.format(addThousandSeparator(total_resources[i], ' ')) + '|'
        status_output += "\n"
        status_output += '{:>10}'.format('Production') + '|'
        for i in range(len(materials_names)):
            status_output += '{:>12}'.format(addThousandSeparator(total_production[i], ' ')) + '|'
        status_output += "\n"
        status_output += "Gold : {}, Gold production : {}".format(addThousandSeparator(total_gold, ' '), addThousandSeparator(total_gold_production, ' ')) + "\n"
        status_output += "Wine consumption : {}".format(addThousandSeparator(total_wine_consumption, ' '))

        session_data = session.getSessionData()
        session_data['status']['data'] = status_output
        session.setSessionData(session_data)
        print('Status has been updated.')
        if config.debugON_setStatus == True:
            msg = 'Status was updated manually.'
            sendToBot(session, msg)
        time.sleep(1)
        event.set()
    except KeyboardInterrupt:
        event.set()
        return