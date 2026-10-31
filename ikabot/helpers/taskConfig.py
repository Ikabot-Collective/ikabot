#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helpers for tasks started from a saved config (CLI / --batch).

A config holds what the user decided (ids, amounts, flags); the task fetches the
game state it refers to. The ``as*`` / ``require*`` checks are meant for a task's
``prepare``: they raise ``ValueError`` with a message for the user, which the CLI
returns as an error before the task starts.
"""

import re

from ikabot.config import city_url
from ikabot.helpers.botComm import discordDataIsValid, telegramDataIsValid
from ikabot.helpers.getJson import getCity
from ikabot.helpers.pedirInfo import getIdsOfCities
from ikabot.helpers.varios import decodeUnicodeEscape


def getCityById(session, city_id):
    """Fetches a city
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int or str

    Returns
    -------
    city : dict
    """
    return getCity(session.get(city_url + str(city_id)))


def findBuildingPosition(city, building):
    """Returns the position of the first ``building`` in a city
    Parameters
    ----------
    city : dict
        as returned by getCity
    building : str
        building name used by the game, e.g. ``academy``, ``barracks``, ``shipyard``

    Returns
    -------
    position : int or None
        None when the city does not have that building
    """
    for position in city["position"]:
        if position["building"] == building:
            return position["position"]
    return None


def asId(value, name):
    """Returns a game id as the string the game URLs expect
    Parameters
    ----------
    value : int or str
    name : str
        config key, for the error message

    Returns
    -------
    id : str
    """
    text = "" if value is None or isinstance(value, bool) else str(value).strip()
    if not text.isdigit():
        raise ValueError("{} must be an id, got {!r}".format(name, value))
    return str(int(text))


def asInt(value, name, minimum=None, maximum=None):
    """Returns a whole number within the given limits
    Parameters
    ----------
    value : int, float or str
        a float is accepted only when it is a whole number (e.g. 20.0)
    name : str
        config key, for the error message
    minimum : int, optional
    maximum : int, optional

    Returns
    -------
    number : int
    """
    number = None
    if isinstance(value, int) and not isinstance(value, bool):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    elif isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        number = int(value.strip())
    if number is None:
        raise ValueError("{} must be a whole number, got {!r}".format(name, value))
    if minimum is not None and number < minimum:
        raise ValueError("{} must be at least {}, got {}".format(name, minimum, number))
    if maximum is not None and number > maximum:
        raise ValueError("{} must be at most {}, got {}".format(name, maximum, number))
    return number


_TRUE = {"true", "yes", "y", "1"}
_FALSE = {"false", "no", "n", "0"}


def asBool(value, name):
    """Returns a yes/no value given as a bool, 1/0 or "y"/"n", "yes"/"no", "true"/"false"
    Parameters
    ----------
    value : bool, int or str
    name : str
        config key, for the error message

    Returns
    -------
    flag : bool
    """
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower() if isinstance(value, (int, str)) else None
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ValueError("{} must be true or false, got {!r}".format(name, value))


def requireOwnCity(session, value, name):
    """Returns the id of one of the user's cities
    Parameters
    ----------
    session : ikabot.web.session.Session
    value : int or str
    name : str
        config key, for the error message

    Returns
    -------
    city_id : str
    """
    city_id = asId(value, name)
    ids, cities = getIdsOfCities(session)
    if city_id not in ids:
        own = ", ".join("{} ({})".format(i, decodeUnicodeEscape(cities[i]["name"])) for i in ids)
        raise ValueError("{} {} is not one of your cities. Your cities: {}".format(name, city_id, own))
    return city_id


def requireNotifications(session):
    """Raises ValueError when neither Telegram nor Discord is set up, for tasks whose
    only output is a bot message (alerts, searches)
    Parameters
    ----------
    session : ikabot.web.session.Session
    """
    if not (telegramDataIsValid(session) or discordDataIsValid(session)):
        raise ValueError(
            "this task sends its results to Telegram or Discord, set one of them up first (Options > Notifications)"
        )
