#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from ikabot.config import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read


def activateVacationMode(session):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    """
    html = session.get()
    city = getCity(html)

    data = {
        "action": "Options",
        "function": "activateVacationMode",
        "actionRequest": actionRequest,
        "backgroundView": "city",
        "currentCityId": city["id"],
        "templateView": "options_umod_confirm",
    }
    session.post(params=data, ignoreExpire=True)


def vacationMode(session, event, stdin_fd, predetermined_input):
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
        print("Activate vacation mode? [Y/n]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            event.set()
            return

        activateVacationMode(session)

        print("Vacation mode has been activated.")
        enter()
        event.set()
        clear()
        sys.exit()
    except KeyboardInterrupt:
        event.set()
        return
