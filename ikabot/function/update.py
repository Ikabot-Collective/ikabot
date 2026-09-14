#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.process import run
from ikabot.helpers.decorators import configurator


@configurator
def update(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    print("To update ikabot run:")
    print("python3 -m pip install --user --upgrade ikabot")
    enter()
