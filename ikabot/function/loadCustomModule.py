#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import traceback
from ikabot.helpers.pedirInfo import read, enter
from ikabot.helpers.gui import *
from ikabot.config import *
from importlib.machinery import SourceFileLoader

def loadCustomModule(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    # FIX GLOBAL FOR LINUX:
    # In Linux, sys.stdin is often closed in threads.
    # We reopen the terminal directly so that read() always works.
    if sys.platform != "win32":
        try:
            sys.stdin = open('/dev/tty', 'r')
        except Exception:
            # If there is no tty (e.g., Docker), we try to use the passed fd
            sys.stdin = os.fdopen(stdin_fd)
    else:
        sys.stdin = os.fdopen(stdin_fd)

    config.predetermined_input = predetermined_input
    try:
        banner()
        sessionData = session.getSessionData()
        modules = [path for path in sessionData.get('shared', {}).get('customModules', []) if os.path.exists(path)]
        print("0) Back")
        print("1) Add new module")
        for module in modules:
            print(str(modules.index(module) + 2) + ") " + module)

        choice = read(min = 0, max = len(modules) + 1, digit = True)
        if choice == 0:
            event.set()
            return
        elif choice == 1:
            banner()
            print(f'        {bcolors.WARNING}[WARNING]{bcolors.ENDC} Running third party code can be dangerous.')
            print('Enter the full path to the module you wish to load. The module must have a function with the same name as the file.')
            print('Enter full path: ')
            path = read().strip().replace('\\', '/')
            if not path.endswith('.py'):
                print('The file must be a .py file!')
                enter()
                event.set()
                return
            
            modules.append(path)
            sessionData = session.getSessionData()
            sessionData['shared'] = sessionData.get('shared', {})
            sessionData['shared']['customModules'] = modules
            session.setSessionData(sessionData, shared = True)
        else:
            path = modules[choice - 2]

        name = os.path.basename(path).replace('.py', '')

        # Load module
        module = SourceFileLoader(name, path).load_module()

        # Run module
        print('Running module...\n')
        getattr(module, name)(session, event, stdin_fd, predetermined_input)

    except Exception:
        print('\n>> Error while running custom module:')
        traceback.print_exc()
        enter()
        event.set()
