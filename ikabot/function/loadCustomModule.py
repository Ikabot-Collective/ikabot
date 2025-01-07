#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
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
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input
    try:
        banner()
        sessionData = session.getSessionData()
        modules = [path for path in sessionData.get('shared', {}).get('customModules', []) if os.path.isfile(path)]
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
            print(f'        {bcolors.WARNING}[WARNING]{bcolors.ENDC} Running third party code could be dangerous!\n\n')
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
            session.setSessionData(sessionData['shared'], shared = True)

        else:    
            path = modules[choice - 2]

        name = path.split('/')[-1].split('.')[0]

        banner()

        # Load module
        try:
            temp = SourceFileLoader(name,path).load_module()
        except Exception as e:
            print(f'Error while loading {path}: ' + str(e) + '\n' + traceback.format_exc())
            enter()
            event.set()
            return
        
        # Call the function with the same name as the file
        try:
            exec('temp.' + name + '(session, event, stdin_fd, predetermined_input)')
        except Exception as e:
            print(f'Error while running {name} in {path}: ' + str(e) + '\n' + traceback.format_exc())
            enter()
            event.set()
            return
        
        event.set()
        return

      
    except KeyboardInterrupt:
        event.set()
        return
    