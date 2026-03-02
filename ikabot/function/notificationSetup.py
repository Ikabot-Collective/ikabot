#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""Notification backend setup menu for ikabot.

Allows users to configure Telegram, Discord, and ntfy.sh backends
for receiving bot notifications. This module provides an interactive
menu that can be added to ikabot's Settings section.

Adapted from autoIkabot's modules/notificationSetup.py.
"""

import os
import sys

import ikabot.config as config
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.botComm import (
    telegramDataIsValid,
    updateTelegramData,
    sendToBot,
    notificationDataIsValid,
    _get_notification_config,
)
from ikabot.helpers.discordComm import (
    discordDataIsValid,
    sendToDiscord,
    setupDiscord,
)
from ikabot.helpers.ntfyComm import (
    ntfyDataIsValid,
    sendToNtfy,
    getNtfyConfig,
    setupNtfy,
)
from ikabot.helpers.logging import getLogger

logger = getLogger(__name__)


def notificationSetup(session, event, stdin_fd, predetermined_input):
    """Notification setup menu.

    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    event : multiprocessing.Event
        an event which, when fired, gives back control of the terminal to the main process
    stdin_fd : int
        the standard input file descriptor
    predetermined_input : multiprocessing.managers.SyncManager.list
        a process synced list of predetermined inputs
    """
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input
    try:
        _notification_menu(session)
    except KeyboardInterrupt:
        pass
    finally:
        event.set()


def _notification_menu(session):
    """Main notification configuration loop."""
    while True:
        banner()
        print("  Notification Setup")
        print("  ==================\n")

        _show_status(session)
        print()

        print("  1) Set up Telegram bot")
        print("  2) Set up Discord webhook")
        print("  3) Set up ntfy.sh")
        print("  4) Test all notifications")
        print("  5) Remove a notification backend")
        print("  0) Back")
        print()

        choice = read(min=0, max=5, digit=True)

        if choice == 0:
            return
        elif choice == 1:
            updateTelegramData(session)
        elif choice == 2:
            setupDiscord(session)
        elif choice == 3:
            setupNtfy(session)
        elif choice == 4:
            _test_all(session)
        elif choice == 5:
            _remove_backend(session)


def _show_status(session):
    """Display which backends are configured."""
    tg = telegramDataIsValid(session)
    discord_on = discordDataIsValid(session)
    ntfy_on = ntfyDataIsValid(session)

    if not tg and not discord_on and not ntfy_on:
        print(
            "  Status: {}No notification backends configured{}".format(
                bcolors.WARNING, bcolors.ENDC
            )
        )
        return

    print("  Active backends:")
    if tg:
        print(
            "    {}[ON]{}  Telegram".format(bcolors.GREEN, bcolors.ENDC)
        )
    else:
        print("    [--]  Telegram")

    if discord_on:
        print(
            "    {}[ON]{}  Discord".format(bcolors.GREEN, bcolors.ENDC)
        )
    else:
        print("    [--]  Discord")

    if ntfy_on:
        print(
            "    {}[ON]{}  ntfy.sh".format(bcolors.GREEN, bcolors.ENDC)
        )
    else:
        print("    [--]  ntfy.sh")


def _test_all(session):
    """Send a test message to all configured backends."""
    banner()
    print("  Test Notifications")
    print("  ==================\n")

    if not notificationDataIsValid(session):
        print(
            "  {}No backends configured. Set one up first.{}".format(
                bcolors.WARNING, bcolors.ENDC
            )
        )
        enter()
        return

    print("  Sending test message to all configured backends...")
    sendToBot(session, "This is a test notification from ikabot!", Token=True)
    print(
        "\n  {}Test message sent!{} Check your notification services.".format(
            bcolors.GREEN, bcolors.ENDC
        )
    )
    enter()


def _remove_backend(session):
    """Remove a configured notification backend."""
    banner()
    print("  Remove Notification Backend")
    print("  ===========================\n")

    # Build list of removable backends
    backends = []
    if telegramDataIsValid(session):
        backends.append(("telegram", "Telegram"))
    if discordDataIsValid(session):
        backends.append(("discord", "Discord"))
    if ntfyDataIsValid(session):
        backends.append(("ntfy", "ntfy.sh"))

    if not backends:
        print(
            "  {}No backends configured.{}".format(
                bcolors.WARNING, bcolors.ENDC
            )
        )
        enter()
        return

    for i, (key, label) in enumerate(backends, 1):
        print("  {}) Remove {}".format(i, label))
    print("  0) Cancel")
    print()

    choice = read(min=0, max=len(backends), digit=True)
    if choice == 0:
        return

    key, label = backends[choice - 1]

    try:
        # All backends are stored flat under shared (e.g. shared["telegram"],
        # shared["discord"], shared["ntfy"]) — same pattern as Telegram.
        # Setting the key to an empty dict effectively removes it.
        session.setSessionData({key: {}}, shared=True)

        print(
            "\n  {}{} removed.{}".format(bcolors.GREEN, label, bcolors.ENDC)
        )
        logger.info("%s backend removed", label)
    except Exception:
        print(
            "\n  {}Failed to remove {}.{}".format(
                bcolors.RED, label, bcolors.ENDC
            )
        )
        logger.error("Failed to remove %s backend", label, exc_info=True)

    enter()
