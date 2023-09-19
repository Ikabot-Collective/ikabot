#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import getpass
import os
import gettext
from ikabot import config
from ikabot.config import *

t = gettext.translation('gui', localedir, languages=languages, fallback=True)
_ = t.gettext


def enter():
    """Wait for the user to press Enter
    """
    try:
        if config.has_params:
            return
    except Exception:
        pass
    if isWindows:
        input(_('\n[Enter]'))  # TODO improve this
    else:
        getpass.getpass(_('\n[Enter]'))


def clear():
    """Clears all text on the console
    """
    if isWindows:
        os.system('cls')
    else:
        os.system('clear')


def banner():
    """Clears all text on the console and displays the Ikabot ASCII art banner
    """
    clear()
    print('{}\n\n{}\n{}'.format(config.default_bner, config.infoUser, config.update_msg))


def statusbanner(session):

    session_data = session.getSessionData()
    if session_data['status']['set'] is False:
        session_data['status']['data'] = config.default_bner
        session.setSessionData(session_data)
        bner = config.default_bner
    else:
        bner = session_data['status']['data']

    clear()
    print('{}\n\n{}\n{}'.format(bner, config.infoUser, config.update_msg))

def printChoiceList(list):
    """Prints the list with padded numbers next to each list entry.
    Parameters
    ----------
    list : list
        list to be printed
    """
    [print('{:>{pad}}) '.format(str(i+1), pad=len(str(len(list)))) + str(item)) for i, item in enumerate(list)]

class bcolors:
    HEADER = '\033[95m'
    STONE = '\033[37m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    RED = '\033[91m'
    BLACK = '\033[90m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    DARK_RED = '\033[31m'
    DARK_BLUE = '\033[34m'
    DARK_GREEN = '\033[32m'
