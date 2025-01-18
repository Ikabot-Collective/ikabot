#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from ikabot.config import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read

from typing import TYPE_CHECKING, TypedDict, Union
if TYPE_CHECKING:
    from ikabot.web.session import Session


def vacationMode(session: Session):
        banner()
        print("Activate vacation mode? [Y/n]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            return

        activateVacationMode(session)

        print("Vacation mode has been activated.")
        enter()

def do_it(session: Session):
    ...


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