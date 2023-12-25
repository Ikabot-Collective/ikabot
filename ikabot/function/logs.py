#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import sys

from ikabot.helpers.gui import os, config, banner, enter, LOG_DIR, LOG_FILE
from ikabot.helpers.pedirInfo import read


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

            print("0) Exit")
            print("1) Set log level")
            print("2) View logs")
            choice = read(min=0, max=2, digit=True)
            print()

            if choice == 0:
                event.set()
                return

            elif choice == 1:
                print(
                    "The current log level is: ",
                    logging.getLevelName(logging.getLogger().getEffectiveLevel())
                )

                _levels = [
                    logging.getLevelName(logging.DEBUG),
                    logging.getLevelName(logging.INFO),
                    logging.getLevelName(logging.WARN),
                    logging.getLevelName(logging.ERROR),
                ]
                for i, l in enumerate(_levels):
                    print("{}) {}".format(i, l))
                choice = read(min=0, max=len(_levels) - 1, digit=True)
                session.updateLogLevel(_levels[choice])
                print(
                    "The log level has been set to: ",
                    logging.getLevelName(logging.getLogger().getEffectiveLevel()),
                )
                enter()

            else:
                print("Log files are stored in", LOG_DIR)
                print("Current log file       ", LOG_FILE)
                print("\nPossible commands: less", LOG_FILE)
                enter()
                    
      
    except KeyboardInterrupt:
        event.set()
        return
