#! /usr/bin/env python3
# -*- coding: utf-8 -*-

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
    """This function will send the ``msg`` argument passed to it as a message to the user on Telegram
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    msg : str
        a string representing the message to send to the user on Telegram
    Token : bool
        a boolean indicating whether or not to attach the process id, the users server, world and Ikariam username to the message
    Photo : bytes
        a bytes object representing a picture to be sent.
    """

    logger.warning(f"MESSAGE TO TG BOT: {msg}", exc_info=True)

    if checkTelegramData(session) is False:
        logger.error("Tried to message TG bot without correct tg data!", exc_info=True)
        return
    if Token is False:
        msg = "pid:{}\n{}\n{}".format(os.getpid(), config.infoUser, msg)

    sessionData = session.getSessionData()
    telegram_data = sessionData["shared"]["telegram"]
    if Photo is None:
        return get(
            "https://api.telegram.org/bot{}/sendMessage".format(
                telegram_data["botToken"]
            ),
            params={"chat_id": telegram_data["chatId"], "text": msg},
        )
    else:
        # we need to clear the headers here because telegram doesn't like keep-alive, might as well get rid of all headers
        headers = session.s.headers.copy()
        session.s.headers.clear()
        resp = session.s.post(
            "https://api.telegram.org/bot{}/sendDocument".format(
                telegram_data["botToken"]
            ),
            files={"document": ("captcha.png", Photo)},
            data={"chat_id": telegram_data["chatId"], "caption": msg},
        )
        session.s.headers = headers
        return resp


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
    """This function doesn't actually check any data itself, that is done by the ``telegramDataIsValid`` function. This function returns ``True`` if there is any Telegram data in the .ikabot file, and if there is none, it will ask the user to input it.
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    valid : bool
        a boolean indicating whether or not there is valid Telegram data in the .ikabot file.
    """
    if telegramDataIsValid(session):
        return True
    else:
        if not session.padre:  # stop asking people if process is detached
            return False
        banner()
        print("You must provide valid credentials to communicate by telegram.")
        print("You require the token of the bot you are going to use.")
        print("For more information about how to obtain them read the readme at https://github.com/Ikabot-Collective/ikabot"
        )
        rta = read(
            msg="Will you provide the credentials now? [y/N]",
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
    print("To create your own Telegram bot, read this: https://core.telegram.org/bots#3-how-do-i-create-a-bot")
    print("1. Just talk to @botfather in Telegram, send /newbot and then choose the bot's name.")
    print("2. Obtain your new bot's token")
    print("3. Remember to keep the token secret!\n")
    botToken = read(msg="Bot's token: ")

    updates = get(
        "https://api.telegram.org/bot{}/getUpdates".format(botToken)
    ).json()
    me = get(
        "https://api.telegram.org/bot{}/getMe".format(botToken)
    ).json()
    if "ok" not in updates or updates["ok"] is False:
        print("Invalid Telegram bot, try again.")
        enter()
        if event is not None and stdin_fd is not None:
            event.set()
        return False

    rand = str(random.randint(0, 9999)).zfill(4)
    print(f"\n{bcolors.GREEN}SUCCESS!{bcolors.ENDC} Telegram token is good!")
    print(
        f"\n4. Now send your bot the command {bcolors.BLUE}/ikabot {rand}{bcolors.ENDC} on Telegram.\nYour bot's username is @{me['result']['username']}"
    )

    start = time.time()
    user_id = None
    try:
        while True:
            print(
                f"Waiting to receive the command on Telegram... Press CTRL + C to abort.\tdt:{round(time.time()-start)}s",
                end="\r",
            )
            updates = get(
                "https://api.telegram.org/bot{}/getUpdates".format(botToken)
            ).json()

            for update in updates["result"]:
                if "message" in update:
                    if "text" in update["message"]:
                        if update["message"]["text"].strip() == f"/ikabot {rand}":
                            user_id = update["message"]["from"]["id"]
                            break
            time.sleep(2)
            print(" " * 100, end="\r")
            if user_id:
                break
    except KeyboardInterrupt:
        print(
            f"{bcolors.RED}FAILURE!{bcolors.ENDC} Did not find command {bcolors.BLUE}/ikabot {rand}{bcolors.ENDC} among received messages!\n\n{str(updates)}"
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

    sendToBot(session, "You have successfully set up Telegram with ikabot.", Token=True)

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
