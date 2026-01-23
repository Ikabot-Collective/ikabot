#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
import time
from datetime import datetime

import requests

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read


def wait_for_key_or_timeout(key, timeout_seconds):
    """Wait for a specific key or timeout, whichever comes first.
    
    Parameters
    ----------
    key : str
        The key to wait for
    timeout_seconds : int
        Maximum seconds to wait before returning
    
    Returns
    -------
    bool
        True if the key was pressed, False if timeout occurred
    """
    if isWindows:
        # Windows implementation using msvcrt
        import msvcrt
        start_time = time.time()
        while (time.time() - start_time) < timeout_seconds:
            if msvcrt.kbhit():
                pressed = msvcrt.getch().decode('utf-8', errors='ignore')
                if pressed == key:
                    return True
            time.sleep(0.1)
        return False
    else:
        # Unix/Linux implementation using select
        import select
        import termios
        import tty
        
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            start_time = time.time()
            while (time.time() - start_time) < timeout_seconds:
                rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
                if rlist:
                    pressed = sys.stdin.read(1)
                    if pressed == key:
                        return True
            return False
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def importExportCookie(session, event, stdin_fd, predetermined_input):
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
    banner()
    try:
        print("Do you want to import or export the cookie?")
        print("(0) Exit")
        print("(1) Import")
        print("(2) Export")
        action = read(min=0, max=2)
        if action == 1:
            importCookie(session)
        elif action == 2:
            exportCookie(session)

        event.set()
    except KeyboardInterrupt:
        event.set()
        return


def importCookie(session):
    banner()
    print(
        "{}⚠️ INSERTING AN INVALID COOKIE WILL LOG YOU OUT OF YOUR OTHER SESSIONS ⚠️{}\n\n".format(
            bcolors.WARNING, bcolors.ENDC
        )
    )
    print("Go ahead and export the cookie from another ikabot instance now and then")
    print('type your "ikariam" cookie below:')
    newcookie = read()
    newcookie = newcookie.strip()
    newcookie = newcookie.replace("ikariam=", "")
    cookies = session.getSessionData()["cookies"]
    cookies["ikariam"] = newcookie
    if session.host in session.s.cookies._cookies:
        session.s.cookies.set("ikariam", newcookie, domain=session.host, path="/")
    else:
        session.s.cookies.set("ikariam", newcookie, domain="", path="/")

    html = session.s.get(session.urlBase).text

    if session.isExpired(html):
        print(
            "{}Failure!{} All your other sessions have just been invalidated!".format(
                bcolors.RED, bcolors.ENDC
            )
        )
        enter()
    else:
        print(
            "{}Success!{} This ikabot session will now use the cookie you provided".format(
                bcolors.GREEN, bcolors.ENDC
            )
        )
        sessionData = session.getSessionData()
        sessionData["cookies"]["ikariam"] = newcookie
        session.setSessionData(sessionData)
        enter()
    session.get()


def exportCookie(session):
    banner()
    session.get()  # get valid cookie in case user has logged the bot out before running this feature
    ikariam = session.getSessionData()["cookies"]["ikariam"]
    print(
        "Use this cookie to synchronise two ikabot instances on 2 different machines\n\n"
    )
    print("ikariam=" + ikariam + "\n\n")

    cookie = json.dumps(
        {"ikariam": ikariam}
    )  # get ikariam cookie, only this cookie is invalidated when the bot logs the user out.
    cookies_js = 'cookies={};i=0;for(let cookie in cookies){{document.cookie=Object.keys(cookies)[i]+"="+cookies[cookie];i++}}'.format(
        cookie
    )
    print(
        """To prevent ikabot from logging you out while playing Ikariam do the following:
    1. Be on the "Your session has expired" screen
    2. Open Chrome javascript console by pressing CTRL + SHIFT + J
    3. Copy the text below, paste it into the console and press enter
    4. Press F5
    """
    )
    print(cookies_js)
    print("\n")
    print("(t) Send to Telegram")
    print("(') Return to main menu")
    
    choice = read(values=["t", "T", "'"])
    
    if choice.lower() == "t":
        sendCookieToTelegram(session, cookies_js)


def sendCookieToTelegram(session, cookies_js):
    """Send the cookie JavaScript code to Telegram.
    
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    cookies_js : str
        The JavaScript code to send
    """
    banner()
    
    # Check if Telegram is configured
    if not telegramDataIsValid(session):
        print("Telegram is not configured.")
        print("You need to set up Telegram to use this feature.\n")
        
        # Prompt user to configure Telegram
        result = updateTelegramData(session)
        
        if not result:
            print("\nTelegram setup was not completed. Cannot export cookie.")
            enter()
            return
        
        banner()
        print("Telegram configured successfully!\n")
    
    # Build the message with date/time
    now = datetime.now()
    date_time_str = now.strftime("%H:%M %d %b %Y")  # e.g., "03:14 23 Jan 2025"
    
    msg = "Server:{}, World:{}, Player:{}, {}\n\n{}".format(
        session.servidor,
        session.word,
        session.username,
        date_time_str,
        cookies_js
    )
    
    # Send to Telegram
    sendToBot(session, msg, Token=True)
    
    # Display success message
    banner()
    print("Press ' to return to main menu or wait 10 seconds\n")
    print("{}Sent successfully!{}".format(bcolors.GREEN, bcolors.ENDC))
    print("\nThe cookie has been sent to your Telegram bot.")
    print("Paste it into the browser console while on the Ikariam website.\n")
    
    # Wait for ' key or 10 seconds
    wait_for_key_or_timeout("'", 10)
