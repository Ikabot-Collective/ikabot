#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import gettext
import requests
import time
import json
import random
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.gui import *
import ikabot.config as config

t = gettext.translation('proxy', config.localedir, languages=config.languages, fallback=True)
_ = t.gettext


def test_proxy(proxy_dict):
    try:
        requests.get('https://lobby.ikariam.gameforge.com/', proxies=proxy_dict, verify=config.do_ssl_verify)
    except Exception:
        return False
    return True


def read_proxy():
    print(_('Enter the proxy (examples: socks5://127.0.0.1:9050, https://45.117.163.22:8080):'))
    proxy_str = read(msg='proxy: ')
    proxy_dict = proxy_str
    proxy_dict_test = {'http': proxy_str, 'https': proxy_str}
    if test_proxy(proxy_dict_test) is False:
        print(_('The proxy does not work.'))
        enter()
        return None
    print(_('The proxy works and it will be added into the proxy list.'))
    enter()
    return proxy_dict
    
    
def read_file():
    print(_('Enter the proxy list file location (example: C:\Folder\Ikariam\proxies.json):'))
    proxyfile_str = read(msg='File: ')
    proxyfile_dict = [proxyfile_str.lstrip('\\')]
    print(_("The given file will be used to load and save proxies."))
    time.sleep(1)
    return proxyfile_dict
    
    
def disable_proxy(session):
    session_data = session.getSessionData()
    json_dir = session_data['proxylist']['conf'][0]
    current_proxy = session_data['proxy']['conf']['https']
    if current_proxy is not None:
        with open(json_dir) as json_file:
            data = json.load(json_file)
        data[current_proxy] = 'free'
        with open(json_dir, 'w') as json_file:
            json.dump(data, json_file, indent=0)
        session_data['proxy']['set'] = False
        session_data['proxy']['conf'] = None
        session.setSessionData(session_data)
        print(_('Current proxy from the proxy list has been disabled.'))
    else:
        return print('There is no proxy set.')
    
    
def enable_proxy(session):
    session_data = session.getSessionData()
    json_dir = session_data['proxylist']['conf'][0]
    with open(json_dir) as json_file:
        data = json.load(json_file)
        free_proxies = [k for k, v in data.items() if v == 'free']
        if free_proxies:
            random_proxy = random.choice(free_proxies)
            random_proxy_availability = data[random_proxy]
            proxy_formatted = {'http': random_proxy, 'https': random_proxy}
            data[random_proxy] = 'reserved'
            with open(json_dir, 'w') as json_file:
                json.dump(data, json_file, indent=0)
            proxy_formatted = {'http': random_proxy, 'https': random_proxy}
            session_data['proxy']['conf'] = proxy_formatted
            session_data['proxy']['set'] = True
            print(_('Random proxy from the proxy list has been enabled. Testing proxy...'))
            session.setSessionData(session_data)
            network_check(session)
        else:
            print("There are no available proxies in the list.")
            time.sleep(2)
            return
            
            
def network_check(session):
    session_data = session.getSessionData()
    print('Testing connection without proxy...')
    current_proxy = session_data['proxy']['conf']
    network_test = test_proxy(None)
    print(f'\nCurrent proxy is: {current_proxy}\n')
    if network_test is False:
        print('Network error, try again later.')
        enter()
        return
    else: 
        print('Connection works without proxy. Testing proxy connection...')
    if current_proxy is not None:
        proxy_test = test_proxy(current_proxy)
        if proxy_test is False:
            print('Connection error using proxy, disabling proxy and marking it as broken in the list.')
            json_dir = session_data['proxylist']['conf'][0]
            current_proxy = session_data['proxy']['conf']['https']
            default_proxy = 'socks5://127.0.0.1:9050'
            if current_proxy != default_proxy:
                with open(json_dir) as json_file:
                    data = json.load(json_file)
                data[current_proxy] = 'broken'
                with open(json_dir, 'w') as json_file:
                    json.dump(data, json_file, indent=0)
            session_data['proxy']['set'] = False
            session_data['proxy']['conf'] = None
            session.setSessionData(session_data)
            print('Would you like to switch to another proxy from the list? [Y/n]')
            rta = read(values=['y', 'Y', 'n', 'N', ''])
            if rta.lower() == 'n':
                return False
            return enable_proxy(session)
        else:
            print('Current proxy is working.')
    else:
        print('No proxy has been set.')
        
        
def test_list(session):
    while True:
        session_data = session.getSessionData()
        json_dir = session_data['proxylist']['conf'][0]
        with open(json_dir) as json_file:
            data = json.load(json_file)
            free_proxies = [k for k, v in data.items() if v in ['free', 'broken']]
            if free_proxies:
                random_proxy = random.choice(free_proxies)
                random_proxy_availability = data[random_proxy]
                proxy_formatted = {'http': random_proxy, 'https': random_proxy}
                data[random_proxy] = 'testing'
                with open(json_dir, 'w') as json_file:
                    json.dump(data, json_file, indent=0)
                print(_(f'Testing: {random_proxy}'))
                if test_proxy(proxy_formatted) is True:
                    with open(json_dir) as json_file:
                        data = json.load(json_file)
                    data[random_proxy] = 'working'
                    with open(json_dir, 'w') as json_file:
                        json.dump(data, json_file, indent=0)
                    print(f'Proxy {random_proxy} works. Checking next proxy in the list.')
                else:
                    json_dir = session_data['proxylist']['conf'][0]
                    current_proxy = random_proxy
                    with open(json_dir) as json_file:
                        data = json.load(json_file)
                    data[random_proxy] = 'dead'
                    with open(json_dir, 'w') as json_file:
                        json.dump(data, json_file, indent=0)
                    print(f'Connection error with {random_proxy}, proxy has been disabled. Checking next proxy in the list.')
            else:
                break
    with open(json_dir) as json_file:
        data = json.load(json_file)
    for k, v in data.items():
        if v == 'working':
            data[k] = 'free'
        elif v == 'dead':
            data[k] = 'broken'
    with open(json_dir, 'w') as json_file:
        json.dump(data, json_file, indent=0)
    print('All proxies in the list have been tested.')


def proxyList(session, event, stdin_fd, predetermined_input):
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
        print(_('Warning: The proxy does not apply to the requests sent to the lobby!\n'))

        session_data = session.getSessionData()
        if 'proxylist' not in session_data or session_data['proxylist']['set'] is False:
            print(_('Right now, proxy list is not configured.'))
            proxyfile_dict = read_file()
            if proxyfile_dict is None:
                event.set()
                return
            session_data['proxylist'] = {}
            session_data['proxylist']['conf'] = proxyfile_dict
            session_data['proxylist']['set'] = True
            session.setSessionData(session_data)
        else:
            curr_proxyfile = session_data['proxylist']['conf']
            print(_('Current proxy list file: {}').format(curr_proxyfile))
            print(_('What do you want to do?'))
            print(_('0) Exit'))
            print(_('1) Add a new proxy'))
            print(_('2) Toggle proxy list'))
            print(_('3) Network check'))
            print(_('4) Test all proxies'))
            print(_('5) Set default proxy'))
            rta = read(min=0, max=5)

            if rta == 0:
                event.set()
                return
            if rta == 1:
                proxy_dict = read_proxy()
                if proxy_dict is None:
                    event.set()
                    return
                json_dir = session_data['proxylist']['conf'][0]
                if not os.path.isfile(json_dir):
                    with open(json_dir, 'w') as f:
                        f.write('{}')
                with open(f'{json_dir}') as json_file:
                    data = json.load(json_file)
                data[proxy_dict] = 'free'
                with open(f'{json_dir}', 'w') as json_file:
                    json.dump(data, json_file, indent=0)
            if rta == 2:
                if session_data['proxy']['set'] is True:
                    disable_proxy(session)
                    time.sleep(2)
                else:
                    enable_proxy(session)
                    time.sleep(2)
            if rta == 3:
                network_check(session)
                time.sleep(2)
            if rta == 4:
                test_list(session)
                time.sleep(2)
            if rta == 5:
                session_data = session.getSessionData()
                default_proxy = 'socks5://127.0.0.1:9050'
                proxy_formatted = {'http': default_proxy, 'https': default_proxy}
                session_data['proxy']['conf'] = proxy_formatted
                session_data['proxy']['set'] = True
                session.setSessionData(session_data)
                print('Proxy was set to default. (Tor service)')
                time.sleep(2)
        event.set()
    except KeyboardInterrupt:
        event.set()
        return
