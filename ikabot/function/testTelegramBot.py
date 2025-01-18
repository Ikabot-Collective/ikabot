#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from ikabot.helpers.botComm import sendToBot
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import enter, read

from typing import TYPE_CHECKING, TypedDict, Union
if TYPE_CHECKING:
    from ikabot.web.session import Session

def testTelegramBot(session: Session):
        input = read(msg="Enter the massage you wish to see: ")
        msg = "Test message: {}".format(input)
        sendToBot(session, msg)
        enter()
