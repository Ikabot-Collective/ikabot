#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re

import ikabot.config as config
from ikabot.helpers.process import run


def checkForUpdate():
    upgrade = run("python3 -m pip search ikabot")
    if "ikabot" not in upgrade:
        return

    upgrade = upgrade.split("\n")
    if len(upgrade) != 3:
        return

    upgrade = upgrade[2]
    match = re.search(r" +.*?: +(.*)", upgrade)
    if match is None:
        return

    new = match.group(1)
    config.update_msg = "[+] ikabot version {} is available\n".format(new)
