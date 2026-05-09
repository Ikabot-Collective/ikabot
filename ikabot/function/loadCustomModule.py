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
    # Fix for Linux: Reopen stdin to ensure terminal interaction works in threads
    if sys.platform != "win32":
        try:
            sys.stdin = open('/dev/tty', 'r')
        except Exception:
            sys.stdin = os.fdopen(stdin_fd)
    else:
        sys.stdin = os.fdopen(stdin_fd)

    config.predetermined_input = predetermined_input
    
    while True:
        try:
            banner()
            sessionData = session.getSessionData()
            shared_data = sessionData.get('shared', {})
            
            # Load only files that actually exist on the system
            modules = [path for path in shared_data.get('customModules', []) if os.path.exists(path)]
            
            print("0) Back")
            print("1) Add new module")
            print("2) Remove a module")
            
            # List custom modules starting from index 3
            for i, module in enumerate(modules):
                print(f"{i + 3}) {module}")

            choice = read(min=0, max=len(modules) + 2, digit=True)

            if choice == 0:
                event.set()
                return

            elif choice == 1:
                banner()
                print(f'        {bcolors.WARNING}[WARNING]{bcolors.ENDC} Running third party code can be dangerous.')
                print('Enter the full path to the .py module:')
                path = read().strip().replace('\\', '/')
                
                if not path.endswith('.py'):
                    print('Error: The file must be a .py file!')
                    enter()
                    continue
                
                # Validation: check if the file actually exists on the system
                if not os.path.isfile(path):
                    print(f'\nError: file not found at {path}')
                    enter()
                    continue
                
                if path not in modules:
                    modules.append(path)
                    shared_data['customModules'] = modules
                    # Persist changes to session file
                    session.setSessionData(shared_data, shared=True)
                    print("\nModule added successfully.")
                    enter()
                continue

            elif choice == 2:
                banner()
                if not modules:
                    print("No modules available to remove.")
                    enter()
                    continue
                
                print("Select the module to remove:")
                for i, m in enumerate(modules):
                    print(f"{i}) {m}")
                
                del_choice = read(min=0, max=len(modules) - 1, digit=True)
                removed = modules.pop(del_choice)
                
                shared_data['customModules'] = modules
                # Persist deletion to session file
                session.setSessionData(shared_data, shared=True)
                
                print(f"\nModule {os.path.basename(removed)} removed.")
                enter()
                continue

            else:
                # Execution logic
                path = modules[choice - 3]
                name = os.path.basename(path).replace('.py', '')

                # Rewrite our entry in processList so ikabot's running-task
                # display (main menu, killTasks, web server) shows the actual
                # module name instead of 'loadCustomModule'. The processList
                # row was created by the menu launcher with action set to the
                # loader's __name__; replace it now that we know which module
                # was picked.
                try:
                    sd = session.getSessionData()
                    plist = sd.get('processList', [])
                    my_pid = os.getpid()
                    for p in plist:
                        if p.get('pid') == my_pid:
                            p['action'] = 'lcm_' + name
                            break
                    sd['processList'] = plist
                    session.setSessionData(sd)
                    if hasattr(session, 'write_status'):
                        session.write_status(f'Module: {name}')
						
                except Exception:
                    pass

                banner()
                print(f'Running module: {name}...\n')

                # Dynamic module loading
                module = SourceFileLoader(name, path).load_module()

                # Execute the function (must match filename)
                getattr(module, name)(session, event, stdin_fd, predetermined_input)

                event.set()
                return

        except Exception:
            print('\n>> Error in Custom Module Manager:')
            traceback.print_exc()
            enter()
            event.set()
            break
