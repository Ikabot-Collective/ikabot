#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys

from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import enter, read


def logs(session, event, stdin_fd, predetermined_input):
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
        while True:
            banner()
            print("0) Back")
            print("1) Set log level")
            print("2) View logs")
            choice = read(min=0, max=2, digit=True)
            if choice == 0:
                event.set()
                return
            elif choice == 1:
                # TODO changing the log level doesn't work because of multiprocessing. When the switch to multithreading is made, this will work.
                banner()
                print(
                    "The current log level is: "
                    + logging.getLevelName(logging.getLogger().getEffectiveLevel())
                    + "\n"
                )
                print("0) DEBUG")
                print("1) INFO")
                print("2) WARN")
                print("3) ERROR")
                choice = read(min=0, max=3, digit=True)
                if choice == 0:
                    logging.getLogger().setLevel(logging.DEBUG)
                elif choice == 1:
                    logging.getLogger().setLevel(logging.INFO)
                elif choice == 2:
                    logging.getLogger().setLevel(logging.WARN)
                elif choice == 3:
                    logging.getLogger().setLevel(logging.ERROR)
                print(
                    "The log level for this session has been set to: "
                    + logging.getLevelName(logging.getLogger().getEffectiveLevel())
                    + "\n"
                )
                enter()
            else:
                viewLogs()

    except KeyboardInterrupt:
        event.set()
        return


def viewLogs():
    banner()
    
    # Display last 10kb of log form logfile
    with open(LOGS_DIRECTORY_FILE, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 10000))
        print(f.read().decode("utf-8"))
    
    print(bcolors.DARK_GREEN + f"Above are displayed the last 10kb of the log file. The log file can be found at {LOGS_DIRECTORY_FILE}" + bcolors.ENDC)
    enter()