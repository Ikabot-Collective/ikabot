#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import sys

from ikabot.helpers.botComm import discordDataIsValid, sendToDiscord
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import enter, read


def testDiscordBot(session, event, stdin_fd, predetermined_input):
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
        if not discordDataIsValid(session):
            print("No Discord webhook configured. Please set it up first.")
            enter()
            event.set()
            return
        input = read(msg="Enter the message you wish to see: ")
        msg = "Test message: {}".format(input)
        sendToDiscord(session, msg)
        enter()
        event.set()
    except KeyboardInterrupt:
        event.set()
