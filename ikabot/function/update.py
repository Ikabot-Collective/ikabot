#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.process import run
from ikabot.helpers.gui import *
from ikabot.config import *


def update(session, event, stdin_fd, predetermined_input):
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
        print(f'Task list has been updated.\n{config.version}')
        time.sleep(1)
        event.set()
    except KeyboardInterrupt:
        event.set()
        return
