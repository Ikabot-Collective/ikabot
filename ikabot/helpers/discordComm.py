#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""Discord webhook notification backend for ikabot.

Adapted from autoIkabot's notifications/discord.py.
Provides functions to send messages via Discord webhooks.
"""

import json
import os
import sys

from ikabot.helpers.gui import *
from ikabot.helpers.logging import getLogger
from ikabot.helpers.pedirInfo import read

logger = getLogger(__name__)


def sendToDiscord(webhook_url, msg):
    """Send a message to a Discord channel via webhook.

    Parameters
    ----------
    webhook_url : str
        The full Discord webhook URL.
    msg : str
        The message text to send.

    Returns
    -------
    success : bool
        True if the webhook returned a success status (2xx).
    """
    if not webhook_url:
        return False

    try:
        from requests import post

        # Discord webhooks accept up to 2000 chars per message
        content = msg[:2000] if len(msg) > 2000 else msg
        resp = post(
            webhook_url,
            json={"content": content},
            timeout=30,
        )
        if 200 <= resp.status_code < 300:
            return True
        logger.warning(
            "Discord webhook returned %d: %s", resp.status_code, resp.text
        )
        return False
    except Exception:
        logger.error("Failed to send Discord message", exc_info=True)
        return False


def discordDataIsValid(session):
    """Check whether Discord webhook data is stored in the session.

    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    valid : bool
        True if a Discord webhook URL is stored.
    """
    try:
        sessionData = session.getSessionData()
        return len(sessionData["shared"]["discord"]["webhookUrl"]) > 0
    except (KeyError, TypeError):
        return False


def getDiscordWebhookUrl(session):
    """Retrieve the stored Discord webhook URL.

    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    url : str
        The webhook URL, or empty string if not configured.
    """
    try:
        sessionData = session.getSessionData()
        return sessionData["shared"]["discord"]["webhookUrl"]
    except (KeyError, TypeError):
        return ""


def setupDiscord(session, event=None, stdin_fd=None, predetermined_input=[]):
    """Interactive Discord webhook setup wizard.

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

    Returns
    -------
    valid : bool
        True if Discord was successfully configured.
    """
    import ikabot.config as config

    if event is not None and stdin_fd is not None:
        sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input

    banner()
    print("Discord Webhook Setup")
    print("=====================\n")
    print("To set up Discord notifications:")
    print("1. Open your Discord server settings")
    print("2. Go to Integrations > Webhooks")
    print("3. Click 'New Webhook', choose a channel, and copy the webhook URL\n")

    webhook_url = read(msg="Webhook URL: ")
    if not webhook_url:
        if event is not None and stdin_fd is not None:
            event.set()
        return False

    webhook_url = webhook_url.strip()

    if not webhook_url.startswith("https://discord.com/api/webhooks/"):
        print(
            f"\n{bcolors.RED}That doesn't look like a valid Discord webhook URL.{bcolors.ENDC}"
        )
        print("Expected format: https://discord.com/api/webhooks/...")
        enter()
        if event is not None and stdin_fd is not None:
            event.set()
        return False

    # Test the webhook
    print("  Testing webhook...")
    if sendToDiscord(webhook_url, "ikabot Discord notifications set up successfully!"):
        print(
            f"\n{bcolors.GREEN}Discord setup complete!{bcolors.ENDC} "
            "A test message was sent to your channel."
        )

        # Save to session data
        discord_data = {}
        discord_data["discord"] = {}
        discord_data["discord"]["webhookUrl"] = webhook_url
        session.setSessionData(discord_data, shared=True)

        print(
            "\nIf you did not receive the test message on Discord, "
            "check your webhook URL and try again."
        )
        enter()

        if event is not None and stdin_fd is not None:
            event.set()
        return True
    else:
        print(
            f"\n{bcolors.RED}Failed to send test message. Check your webhook URL.{bcolors.ENDC}"
        )
        enter()
        if event is not None and stdin_fd is not None:
            event.set()
        return False
