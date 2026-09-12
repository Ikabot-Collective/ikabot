from ikabot.helpers.decorators import configurator
#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import sys

from ikabot.helpers.botComm import discordDataIsValid, sendToBot
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import enter, read


@configurator
def testDiscordBot(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    try:
        if not discordDataIsValid(session):
            print("No Discord webhook configured. Please set it up first.")
            enter()
            event.set()
            return
        input = read(msg="Enter the message you wish to see: ")
        msg = "Test message: {}".format(input)
        sendToBot(session, msg)
        enter()
        event.set()
    except KeyboardInterrupt:
        event.set()
