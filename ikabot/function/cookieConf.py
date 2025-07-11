#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import gettext
import requests
import time
import os
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.gui import *
from ikabot.helpers.botComm import *
from ikabot import config
from ikabot.config import *

t = gettext.translation('proxy', config.localedir, languages=config.languages, fallback=True)
_ = t.gettext


def read_cookie():
    print(_('Enter the cookie file location (example: C:\Folder\Ikariam\cookies.json):'))
    cookie_str = read(msg='File: ')
    cookie_dict = [cookie_str.lstrip('\\')]
    print(_("The given file will be used to save the account's cookie data into."))
    time.sleep(2)
    return cookie_dict
    

def cookieConf(session, event, stdin_fd, predetermined_input):
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
        banner()

        session_data = session.getSessionData()
        if 'cookie' not in session_data or session_data['cookie']['set'] is False:
            print(_('Right now, there is no cookie data file configured.'))
            cookie_dict = read_cookie()
            if cookie_dict is None:
                event.set()
                return
            session_data['cookie'] = {}
            session_data['cookie']['conf'] = cookie_dict
            session_data['cookie']['set'] = True
        else:
            curr_cookie = session_data['cookie']['conf']
            curr_user = session_data['cookie']['user']
            print(_('Current cookie data file: {}').format(curr_cookie))
            print(_('Current saved username: {}').format(curr_user))
            print(_('What do you want to do?'))
            print(_('0) Exit'))
            print(_('1) Set a new cookie data file'))
            print(_('2) Remove the current cookie data file settings'))
            rta = read(min=0, max=2)

            if rta == 0:
                event.set()
                return
            if rta == 1:
                cookie_dict = read_cookie()
                if cookie_dict is None:
                    event.set()
                    return
                session_data['cookie']['conf'] = cookie_dict
                session_data['cookie']['set'] = True
            if rta == 2:
                session_data['cookie']['set'] = False
                print(_('The cookie data file settings has been removed.'))
                enter()

        session.setSessionData(session_data)
        event.set()
    except KeyboardInterrupt:
        event.set()
        return


def saveCookie(session):

    session_data = session.getSessionData()
    if 'cookie' in session_data and session_data['cookie']['set'] is True:
        try:
            json_dir = session_data['cookie']['conf'][0]
            if not os.path.isfile(json_dir):
                with open(json_dir, 'w') as f:
                    f.write('{}')
            with open(f'{json_dir}') as json_file:
                data = json.load(json_file)
            ikariam = session.getSessionData()['cookies']['ikariam']
            cookie = json.dumps({'ikariam': ikariam}).replace('"', "'")
            cookies_js = "cookies={};i=0;for(let cookie in cookies){{document.cookie=Object.keys(cookies)[i]+'='+cookies[cookie];i++}}".format(cookie)
            var = session_data['cookie']['user']
            data[var] = cookies_js
            with open(f'{json_dir}', 'w') as json_file:
                json.dump(data, json_file, indent=0, separators=(',\n', ': \n'))
        except Exception as e:
            print(f'{e}')
            sendToBot(session, e)
    else:
        print('ERROR: Cookie data file is not set, cannot copy cookie into the JSON file.')
        time.sleep(2)