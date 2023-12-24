#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import random
from decimal import *
from datetime import datetime

getcontext().prec = 30


def addThousandSeparator(num, character='.', include_sign=False):
    """Formats the number into a string and adds a `character` for every thousand (eg. 3000 -> 3.000)
    Parameters
    ----------
    num : int
        integer number to format
    character : str
        character to act as the thousand separator
    include_sign : bool
        Show + infront of the number
    Returns
    -------
    number : str
        a string representing that number with added `character` for every thousand
    """
    sign = '+' if include_sign else ''
    return format(int(num), sign+',').replace(',', character)


def daysHoursMinutes(totalSeconds):
    """Formats the total number of seconds into days hours minutes (eg. 321454 -> 3D 17H)
    Parameters
    ----------
    totalSeconds : int
        total number of seconds

    Returns
    -------
    text : str
        formatted string (D H M)
    """
    if totalSeconds == 0:
        return '0 s'
    dias = int(totalSeconds / Decimal(86400))
    totalSeconds -= dias * Decimal(86400)
    horas = int(totalSeconds / Decimal(3600))
    totalSeconds -= horas * Decimal(3600)
    minutos = int(totalSeconds / Decimal(60))
    texto = ''
    if dias > 0:
        texto = str(dias) + 'D '
    if horas > 0:
        texto = texto + str(horas) + 'H '
    if minutos > 0 and dias == 0:
        texto = texto + str(minutos) + 'M '
    return texto[:-1]


def wait(seconds, maxrandom=0):
    """This function will wait the provided number of seconds plus a random number of seconds between 0 and maxrandom
    Parameters
    -----------
    seconds : int
        the number of seconds to wait for
    maxrandom : int
        the maximum number of additional seconds to wait for
    """
    if seconds <= 0:
        return
    randomTime = random.randint(0, maxrandom)
    ratio = (1 + 5 ** 0.5) / 2 - 1  # 0.6180339887498949
    comienzo = time.time()
    fin = comienzo + seconds
    restantes = seconds
    while restantes > 0:
        time.sleep(restantes * ratio)
        restantes = fin - time.time()
    time.sleep(randomTime)


def getCurrentCityId(session):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    """
    html = session.get()
    return re.search(r'currentCityId:\s(\d+),', html).group(1)

def getDateTime(timestamp = None):
    """Returns a string of the current date and time in the YYYY-mm-dd_HH-MM-SS, if `timestamp` is provided then it converts it into the given format.
    Parameters
    ----------
    timestamp : int
        Unix timestamp to be converted
    
    Returns
    -------
    text : str
        Formatted string YYYY-mm-dd_HH-MM-SS
    """
    timestamp = timestamp if timestamp else time.time()
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d_%H-%M-%S')

def normalizeDicts(list_of_dicts):
    """Returns a list of dicts that all have the same keys. Keys will be initialized to None
    Parameters
    ----------
    list_of_dicts : [dict]
        List of dicts that may have different keys (one dict has some keys that another doesn't)
    
    Returns
    -------
    normalized_dicts : [dict]
        List of dicts that all have the same keys, with new ones initialized to None.
    """
    all_keys = set().union(*[d.keys() for d in list_of_dicts])
    return [ {k: (d[k] if k in d else None) for k in all_keys} for d in list_of_dicts]

def decodeUnicodeEscape(input_string):
    """
    Replace Unicode escape sequences (e.g., u043c) with corresponding UTF-8 characters.

    Parameters:
    - input_string (str): The original string.

    Returns:
    - str: The string with replaced Unicode escape sequences.
    """
    return re.sub(r'u([0-9a-fA-F]{4})', lambda x: chr(int(x.group(1), 16)), input_string)
