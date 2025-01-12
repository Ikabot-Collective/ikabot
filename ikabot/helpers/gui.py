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


def formatTable(data: list[dict], header: bool = True, rowNumbers = False) -> str:
    """
    Formats a list of dictionaries into a string representing the list of dicts as a table.
    List of dicts must be normalized (all keys should be strings and they should exist in every dict in the list).
    """
    if not data:
        return ""
    # Extract keys and determine column widths
    keys = list(data[0].keys())
    col_widths = {key: max(len(str(key)), max(len(str(d[key])) for d in data)) for key in keys}
    if rowNumbers:
        col_widths['#'] = max(1, len(str(len(data))))
    def format_value(value, width):
        if isinstance(value, (int, float)):
            return f"{value:>{width}}"
        else:
            return f"{str(value):^{width}}"
    def format_row(row, row_num=None):
        values = [format_value(row[key], col_widths[key]) for key in keys]
        if row_num is not None:
            values.insert(0, format_value(row_num, col_widths['#']))
        return " | ".join(values)
    table = []
    # Add header
    if header:
        header_row = [format_value(key, col_widths[key]) for key in keys]
        if rowNumbers:
            header_row.insert(0, format_value("#", col_widths['#']))
        table.append(" | ".join(header_row))
        table.append("-+-".join(['-' * col_widths[col] for col in (['#'] if rowNumbers else []) + keys]))
    # Add rows
    for i, row in enumerate(data):
        table.append(format_row(row, i + 1 if rowNumbers else None))
    return "\n".join(table)

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
