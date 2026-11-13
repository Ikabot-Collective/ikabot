#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import getpass
import os

from ikabot import config
from ikabot.config import *

def enter():
    """Wait for the user to press Enter"""
    try:
        if len(config.predetermined_input) > 0:
            return
    except Exception:
        pass
    if isWindows:
        input("\n[Enter]")  # TODO improve this
    else:
        getpass.getpass("\n[Enter]")


def clear():
    """Clears all text on the console"""
    if isWindows:
        os.system("cls")
    else:
        os.system("clear")


def banner():
    """Clears all text on the console and displays the Ikabot ASCII art banner"""
    clear()
    bner = f"""
    `7MMF'  `7MM                       `7MM\"""Yp,                 mm
      MM      MM                         MM    Yb                 MM
      MM      MM  ,MP'   ,6"Yb.          MM    dP    ,pW"Wq.    mmMMmm
      MM      MM ;Y     8)   MM          MM\"""bg.   6W'   `Wb     MM
      MM      MM;Mm      ,pm9MM          MM    `Y   8M     M8     MM
      MM      MM `Mb.   8M   MM          MM    ,9   YA.   ,A9     MM
    .JMML.  .JMML. YA.  `Moo9^Yo.      .JMMmmmd9     `Ybmd9'      `Mbmo
                                                            {IKABOT_VERSION_TAG}"""
    print("\n{}\n\n{}\n{}".format(bner, config.infoUser, config.update_msg))


def printChoiceList(list):
    """Prints the list with padded numbers next to each list entry.
    Parameters
    ----------
    list : list
        list to be printed
    """
    [
        print("{:>{pad}}) ".format(str(i + 1), pad=len(str(len(list)))) + str(item))
        for i, item in enumerate(list)
    ]


class bcolors:
    HEADER = "\033[95m"
    STONE = "\033[37m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    RED = "\033[91m"
    BLACK = "\033[90m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    DARK_RED = "\033[31m"
    DARK_BLUE = "\033[34m"
    DARK_GREEN = "\033[32m"
    CYAN = "\033[36m"
    YELLOW = "\033[33m"
