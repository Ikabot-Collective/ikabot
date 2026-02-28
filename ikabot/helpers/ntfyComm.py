#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""ntfy.sh notification backend for ikabot.

Adapted from autoIkabot's notifications/ntfy.py.
ntfy.sh is an open-source push notification service that can be used
with the public instance at https://ntfy.sh or self-hosted.
"""

import json
import os
import sys

from ikabot.helpers.gui import *
from ikabot.helpers.logging import getLogger
from ikabot.helpers.pedirInfo import read

logger = getLogger(__name__)

DEFAULT_SERVER = "https://ntfy.sh"


def sendToNtfy(server, topic, token, msg):
    """Send a push notification via ntfy.sh.

    Parameters
    ----------
    server : str
        The ntfy server URL (e.g. ``https://ntfy.sh``).
    topic : str
        The topic name to publish to.
    token : str
        Access token for authenticated topics (empty string if public).
    msg : str
        The message text to send.

    Returns
    -------
    success : bool
        True if the server returned a success status.
    """
    if not topic:
        return False

    if not server:
        server = DEFAULT_SERVER
    server = server.rstrip("/")
    url = "{}/{}".format(server, topic)

    headers = {}
    if token:
        headers["Authorization"] = "Bearer {}".format(token)

    # Use Title header for the first line, body for the rest
    lines = msg.strip().split("\n", 1)
    title = lines[0][:200]  # ntfy title limit
    body = lines[1] if len(lines) > 1 else ""

    headers["Title"] = title

    try:
        from requests import post

        resp = post(
            url,
            data=body.encode("utf-8"),
            headers=headers,
            timeout=30,
        )
        if 200 <= resp.status_code < 300:
            return True
        logger.warning("ntfy returned %d: %s", resp.status_code, resp.text)
        return False
    except Exception:
        logger.error("Failed to send ntfy notification", exc_info=True)
        return False


def ntfyDataIsValid(session):
    """Check whether ntfy.sh data is stored in the session.

    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    valid : bool
        True if an ntfy topic is configured.
    """
    try:
        sessionData = session.getSessionData()
        return len(sessionData["shared"]["ntfy"]["topic"]) > 0
    except (KeyError, TypeError):
        return False


def getNtfyConfig(session):
    """Retrieve the stored ntfy.sh configuration.

    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    config : dict
        Dict with keys ``server``, ``topic``, ``token``.
        Empty values if not configured.
    """
    try:
        sessionData = session.getSessionData()
        ntfy_data = sessionData["shared"]["ntfy"]
        return {
            "server": ntfy_data.get("server", DEFAULT_SERVER),
            "topic": ntfy_data.get("topic", ""),
            "token": ntfy_data.get("token", ""),
        }
    except (KeyError, TypeError):
        return {"server": DEFAULT_SERVER, "topic": "", "token": ""}


def setupNtfy(session, event=None, stdin_fd=None, predetermined_input=[]):
    """Interactive ntfy.sh setup wizard.

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
        True if ntfy.sh was successfully configured.
    """
    import ikabot.config as config

    if event is not None and stdin_fd is not None:
        sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input

    banner()
    print("ntfy.sh Setup")
    print("=============\n")
    print("ntfy.sh is a simple push notification service.")
    print("Install the ntfy app on your phone (Android/iOS) to receive alerts.")
    print("You can use the public server (ntfy.sh) or self-host your own.\n")
    print("Choose a unique topic name (e.g. 'my-ikabot-alerts-abc123').")
    print(
        "WARNING: Anyone who knows the topic name can read your notifications"
    )
    print("on the public server. Use a long, random topic name.\n")

    topic = read(msg="Topic name: ")
    if not topic:
        if event is not None and stdin_fd is not None:
            event.set()
        return False
    topic = topic.strip()

    print(
        "\nServer URL (press Enter for the default public server: ntfy.sh):"
    )
    server = read(msg="Server URL: ")
    if not server or not server.strip():
        server = DEFAULT_SERVER
    server = server.strip().rstrip("/")

    print("\nAccess token (press Enter to skip if your topic is public):")
    token = read(msg="Token: ")
    token = token.strip() if token else ""

    # Test the setup
    print("  Testing ntfy connection...")
    if sendToNtfy(server, topic, token, "ikabot ntfy notifications set up successfully!"):
        print(
            f"\n{bcolors.GREEN}ntfy setup complete!{bcolors.ENDC} "
            "A test notification was sent to your topic."
        )

        # Save to session data
        ntfy_data = {}
        ntfy_data["ntfy"] = {}
        ntfy_data["ntfy"]["server"] = server
        ntfy_data["ntfy"]["topic"] = topic
        ntfy_data["ntfy"]["token"] = token
        session.setSessionData(ntfy_data, shared=True)

        print(
            "\nIf you did not receive the test notification, "
            "check your topic name and server URL."
        )
        enter()

        if event is not None and stdin_fd is not None:
            event.set()
        return True
    else:
        print(
            f"\n{bcolors.RED}Failed to send test notification. "
            f"Check your topic name and server URL.{bcolors.ENDC}"
        )
        enter()
        if event is not None and stdin_fd is not None:
            event.set()
        return False
