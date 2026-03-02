#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""Enhanced bot communication module for ikabot.

Drop-in replacement for ikabot's helpers/botComm.py that adds
Discord webhook and ntfy.sh push notification support alongside
the existing Telegram backend.

All existing public API functions are preserved with the exact same
signatures. The key change is that sendToBot() now routes messages
to ALL configured backends (Telegram, Discord, ntfy.sh).

Adapted from autoIkabot's multi-backend notification system.
"""

from ikabot.helpers.logging import getLogger

logger = getLogger(__name__)
import json
import os
import random
import re
import sys
import time
from requests import get
import ikabot.config as config
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read


# ---------------------------------------------------------------------------
# Internal helpers for Discord and ntfy.sh
# ---------------------------------------------------------------------------

def _get_notification_config(session):
    """Read Discord/ntfy config from session data.

    Discord and ntfy configs are stored flat in ``shared``, the same way
    Telegram is stored at ``shared["telegram"]``.

    Returns
    -------
    config : dict
        Dict with optional ``discord`` and ``ntfy`` keys.
        Empty dict if nothing is configured.
    """
    try:
        sessionData = session.getSessionData()
        shared = sessionData.get("shared", {})
        result = {}
        if "discord" in shared:
            result["discord"] = shared["discord"]
        if "ntfy" in shared:
            result["ntfy"] = shared["ntfy"]
        return result
    except (KeyError, TypeError):
        return {}


def _send_discord(webhook_url, msg):
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


def _send_ntfy(server, topic, token, msg):
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
    try:
        from requests import post

        if not server:
            server = "https://ntfy.sh"
        url = "{}/{}".format(server.rstrip("/"), topic)

        headers = {}
        if token:
            headers["Authorization"] = "Bearer {}".format(token)

        # Use Title header for the first line, body for the rest
        lines = msg.strip().split("\n", 1)
        title = lines[0][:200]  # ntfy title limit
        body = lines[1] if len(lines) > 1 else ""

        headers["Title"] = title

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


def notificationDataIsValid(session):
    """Check whether ANY notification backend is configured.

    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    valid : bool
        True if at least one backend (Telegram, Discord, or ntfy) is configured.
    """
    if telegramDataIsValid(session):
        return True
    notif_config = _get_notification_config(session)
    try:
        if notif_config.get("discord", {}).get("webhookUrl"):
            return True
    except (KeyError, TypeError):
        pass
    try:
        if notif_config.get("ntfy", {}).get("topic"):
            return True
    except (KeyError, TypeError):
        pass
    return False


# ---------------------------------------------------------------------------
# Public API — same signatures as the original botComm.py
# ---------------------------------------------------------------------------

def sendToBotDebug(session, msg, debugON):
    """This function will send the ``msg`` argument passed to it as a message to the user on Telegram, only if ``debugOn`` is ``True``
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    msg : str
        a string representing the message to send to the user on Telegram
    debugON : bool
        a boolean indicating whether or not to send the message.
    """
    if debugON:
        sendToBot(session, msg)


def sendToBot(session, msg, Token=False, Photo=None):
    """Send a notification to all configured backends (Telegram, Discord, ntfy.sh).

    This is an enhanced drop-in replacement. The original only supported Telegram.
    Now messages are routed to every configured backend. If a backend fails,
    other backends still receive the message.

    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    msg : str
        a string representing the message to send
    Token : bool
        if False, the process id, server, world and username are prepended to the message
    Photo : bytes
        a bytes object representing a picture to be sent (Telegram only).
    """

    logger.warning("MESSAGE TO BOT: %s", msg, exc_info=True)

    has_any_backend = False

    # Build the formatted message with header (shared across all backends)
    if Token is False:
        infoUser = "Server:{}, World:{}, Player:{}".format(
            session.servidor, session.word, session.username
        )
        formatted_msg = "pid:{}\n{}\n{}".format(os.getpid(), infoUser, msg)
    else:
        formatted_msg = msg

    # --- 1. Telegram (original behavior preserved exactly) ---
    if telegramDataIsValid(session):
        has_any_backend = True
        try:
            sessionData = session.getSessionData()
            telegram_data = sessionData["shared"]["telegram"]
            if Photo is None:
                get(
                    "https://api.telegram.org/bot{}/sendMessage".format(
                        telegram_data["botToken"]
                    ),
                    params={
                        "chat_id": telegram_data["chatId"],
                        "text": formatted_msg,
                    },
                )
            else:
                # Clear headers for Telegram compatibility (original behavior)
                headers = session.s.headers.copy()
                session.s.headers.clear()
                session.s.post(
                    "https://api.telegram.org/bot{}/sendDocument".format(
                        telegram_data["botToken"]
                    ),
                    files={"document": ("captcha.png", Photo)},
                    data={
                        "chat_id": telegram_data["chatId"],
                        "caption": formatted_msg,
                    },
                )
                session.s.headers = headers
        except Exception:
            logger.error("Failed to send Telegram message", exc_info=True)

    # --- 2. Discord webhook ---
    notif_config = _get_notification_config(session)

    discord_config = notif_config.get("discord")
    if discord_config:
        webhook_url = discord_config.get("webhookUrl", "")
        if webhook_url:
            has_any_backend = True
            try:
                _send_discord(webhook_url, formatted_msg)
            except Exception:
                logger.error("Failed to send Discord notification", exc_info=True)

    # --- 3. ntfy.sh push ---
    ntfy_config = notif_config.get("ntfy")
    if ntfy_config:
        topic = ntfy_config.get("topic", "")
        if topic:
            has_any_backend = True
            try:
                _send_ntfy(
                    ntfy_config.get("server", "https://ntfy.sh"),
                    topic,
                    ntfy_config.get("token", ""),
                    formatted_msg,
                )
            except Exception:
                logger.error("Failed to send ntfy notification", exc_info=True)

    if not has_any_backend:
        logger.error(
            "Tried to message bot without any notification backend configured!",
            exc_info=True,
        )


def telegramDataIsValid(session):
    """This function checks whether or not there is any Telegram data stored in the .ikabot file
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    valid : bool
        a boolean indicating whether or not there is any Telegram data stored in the .ikabot file

    """
    sessionData = session.getSessionData()
    try:
        return (
            len(sessionData["shared"]["telegram"]["botToken"]) > 0
            and len(sessionData["shared"]["telegram"]["chatId"]) > 0
        )
    except KeyError:
        return False


def getUserResponse(session, fullResponse=False):
    """This function will retrieve a list of messages the user sent to the bot on Telegram.
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    updates : list[str]
        a list containing all the messages the user sent to the bot on Telegram
    """
    # returns messages that the user sends to the telegram bot

    if checkTelegramData(session) is False:
        return []

    sessionData = session.getSessionData()
    telegram_data = sessionData["shared"]["telegram"]

    try:
        updates = get(
            "https://api.telegram.org/bot{}/getUpdates".format(
                telegram_data["botToken"]
            )
        ).text
        updates = json.loads(updates, strict=False)
        if updates["ok"] is False:
            return []
        updates = updates["result"]
        # only return messages from the chatId of our user
        if fullResponse:
            return [
                update["message"]
                for update in updates
                if "message" in update
                and update["message"]["chat"]["id"] == int(telegram_data["chatId"])
            ]
        else:
            return [
                update["message"]["text"]
                for update in updates
                if "message" in update
                and update["message"]["chat"]["id"] == int(telegram_data["chatId"])
            ]
    except KeyError:
        return []


def checkTelegramData(session):
    """Check if any notification backend is configured.

    Returns True if Telegram, Discord, or ntfy.sh is configured.
    If nothing is configured and the process is interactive (session.padre),
    prompts the user to set up Telegram credentials.

    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    valid : bool
        a boolean indicating whether or not there is valid notification data.
    """
    if notificationDataIsValid(session):
        return True
    else:
        if not session.padre:  # stop asking people if process is detached
            return False
        banner()
        print("You must configure at least one notification backend.")
        print("Supported: Telegram, Discord webhook, ntfy.sh")
        print(
            "For more information about how to obtain Telegram credentials read the readme at https://github.com/Ikabot-Collective/ikabot"
        )
        rta = read(
            msg="Will you provide Telegram credentials now? [y/N]",
            values=["y", "Y", "n", "N", ""],
        )
        if rta.lower() != "y":
            return False
        else:
            return updateTelegramData(session)


def updateTelegramData(session, event=None, stdin_fd=None, predetermined_input=[]):
    """This function asks the user to input the Telegram bot's token. After the user has input the token, this function will generate a random 4 digit number, and request of the user to send it as a command to their bot. Once the command has been sent to the bot, ikabot will save the incoming message's sender's chatid and save it into the session data.
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    event : multiprocessing.Event
        an event which, when fired, gives back control of the terminal to the main process
    stdin_fd : int
        the standard input file descriptor passed to the function as a means of gaining control of the terminal
    predetermined_input : multiprocessing.managers.SyncManager.list
        a process synced list of predetermined inputs

    Returns
    -------
    valid : bool
        a boolean indicating whether or not the Telegram data has been successfully updated
    """
    if event is not None and stdin_fd is not None:
        sys.stdin = os.fdopen(stdin_fd)  # give process access to terminal
    config.predetermined_input = predetermined_input
    banner()
    print(
        "To create your own Telegram bot, read this: https://core.telegram.org/bots#3-how-do-i-create-a-bot"
    )
    print(
        "1. Just talk to @botfather in Telegram, send /newbot and then choose the bot's name."
    )
    print("2. Obtain your new bot's token")
    print("3. Remember to keep the token secret!\n")
    botToken = read(msg="Bot's token: ")

    updates = get(
        "https://api.telegram.org/bot{}/getUpdates".format(botToken)
    ).json()
    me = get("https://api.telegram.org/bot{}/getMe".format(botToken)).json()
    if "ok" not in updates or updates["ok"] is False:
        print("Invalid Telegram bot, try again.")
        enter()
        if event is not None and stdin_fd is not None:
            event.set()
        return False

    rand = str(random.randint(0, 9999)).zfill(4)
    print(
        "\n{}SUCCESS!{} Telegram token is good!".format(
            bcolors.GREEN, bcolors.ENDC
        )
    )
    print(
        "\n4. Now send your bot the command {}/ikabot {}{} on Telegram.\nYour bot's username is @{}".format(
            bcolors.BLUE, rand, bcolors.ENDC, me["result"]["username"]
        )
    )

    start = time.time()
    user_id = None
    try:
        while True:
            print(
                "Waiting to receive the command on Telegram... Press CTRL + C to abort.\tdt:{}s".format(
                    round(time.time() - start)
                ),
                end="\r",
            )
            updates = get(
                "https://api.telegram.org/bot{}/getUpdates".format(botToken)
            ).json()

            for update in updates["result"]:
                if "message" in update:
                    if "text" in update["message"]:
                        if (
                            update["message"]["text"].strip()
                            == "/ikabot {}".format(rand)
                        ):
                            user_id = update["message"]["from"]["id"]
                            break
            time.sleep(2)
            print(" " * 100, end="\r")
            if user_id:
                break
    except KeyboardInterrupt:
        print(
            "{}FAILURE!{} Did not find command {}/ikabot {}{} among received messages!\n\n{}".format(
                bcolors.RED,
                bcolors.ENDC,
                bcolors.BLUE,
                rand,
                bcolors.ENDC,
                str(updates),
            )
        )
        enter()
        if event is not None and stdin_fd is not None:
            event.set()
        return False

    telegram_data = {}
    telegram_data["telegram"] = {}
    telegram_data["telegram"]["botToken"] = botToken.replace(" ", "")
    telegram_data["telegram"]["chatId"] = str(user_id)
    session.setSessionData(telegram_data, shared=True)

    sendToBot(
        session, "You have successfully set up Telegram with ikabot.", Token=True
    )

    print(
        "\nA message was sent to you on Telegram informing you about the successful setup of the Telegram bot."
    )
    print(
        "If you did not receive any message on Telegram then something has gone wrong and you will need to set up the Telegram data again!"
    )
    enter()

    if event is not None and stdin_fd is not None:
        event.set()  # give main process control before exiting
    return True
