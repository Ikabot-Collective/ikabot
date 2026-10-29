#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from ikabot.helpers.logging import getLogger, setLoggedInPlayer
import base64
import datetime
import getpass
import json
import os
import random
import re
import sys
import time
import traceback
import urllib.parse
from collections import deque

import requests
from urllib3.exceptions import InsecureRequestWarning

from ikabot import config
from ikabot.config import *
from ikabot.helpers.aesCipher import *
from ikabot.helpers.sessionStorage import (
    get_session_data,
    set_session_data,
    delete_session_data,
    migrate_legacy_account,
    get_saved_users,
    get_user_file_path,
    get_users_dir,
    find_user_file_for_email,
    session_data_lock,
    read_json_file,
    get_task_pids_by_account,
)
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import banner, enter
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.varios import getDateTime, lastloginTimetoString
from ikabot.helpers.apiComm import getNewBlackBoxToken
from ikabot.helpers.lobbyDecaptcha import break_interactive_captcha


class IkariamErrorPage(Exception):
    """Ikariam returned an error page, but the session is not known to be expired"""


class Session:
    def __init__(self):
        self.padre = True
        self.logged = False
        self.blackbox = None
        self.api_user_agent = None
        self.mail = None
        self.password = None
        self.locale = config.IKABOT_LOCALE
        self.gf_lang = config.IKABOT_GF_LANG
        self.accept_language = config.build_accept_language(self.locale, self.gf_lang)
        self.timezone_id = config.IKABOT_TIMEZONE_ID
        self.logger = getLogger(__name__)
        self.requestHistory = deque(maxlen=5)  # keep last 5 requests in history
        # disable ssl verification warning
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
        self.__login()

    def setStatus(self, message):
        """This function will modify the current tasks status message that appears in the table on the main menu
        Parameters
        ----------
        message : Message to be displayed in the table in main menu
        """
        self.logger.info(f"Changing status to {message}")

        self.updateProcessEntry(os.getpid(), status=message)

    def updateProcessEntry(self, pid, **fields):
        """Updates fields (status, action, ...) of one row of the main menu process list
        Parameters
        ----------
        pid : int
            pid of the process whose row is modified
        """
        with session_data_lock():
            sessionData = self.getSessionData()
            fileList = sessionData.get("processList", [])
            [p.update(fields) for p in fileList if p["pid"] == pid]
            sessionData["processList"] = fileList
            self.setSessionData(sessionData, keep_process_list=False)

    def __genRand(self):
        return hex(random.randint(0, 65535))[2:]

    def __genCookie(self):
        return (
            self.__genRand()
            + self.__genRand()
            + hex(int(round(time.time() * 1000)))[2:]
            + self.__genRand()
            + self.__genRand()
        )

    def __fp_eval_id(self):
        return (
            self.__genRand()
            + self.__genRand()
            + "-"
            + self.__genRand()
            + "-"
            + self.__genRand()
            + "-"
            + self.__genRand()
            + "-"
            + self.__genRand()
            + self.__genRand()
            + self.__genRand()
        )

    def __logout(self, html):
        if html is not None:
            idCiudad = getCity(html)["id"]
            token = re.search(r'actionRequest"?:\s*"(.*?)"', html).group(1)
            urlLogout = "action=logoutAvatar&function=logout&sideBarExt=undefined&startPageShown=1&detectedDevice=1&cityId={0}&backgroundView=city&currentCityId={0}&actionRequest={1}".format(
                idCiudad, token
            )
            self.s.get(self.urlBase + urlLogout, verify=config.do_ssl_verify)

    def __isInVacation(self, html):
        return "nologin_umod" in html

    def __isExpired(self, html):
        return "index.php?logout" in html or '<a class="logout"' in html

    def __isSessionRotated(self, html, response=None):
        """Detects a session takeover by another device/browser via the actual
        redirect/host, not by scanning page content (which false-positived on
        ordinary pages containing normal marketing/cookie-banner strings)."""
        if not isinstance(html, str):
            return False
        if re.search(
            r'"reload"\s*,\s*\{\s*"link"\s*:\s*"https:\\?/\\?/lobby\.ikariam\.gameforge\.com',
            html,
        ):
            return True
        if response is not None:
            try:
                candidate_urls = [response.url] + [
                    h.headers.get("Location", "") for h in response.history
                ]
                for candidate in candidate_urls:
                    if (urllib.parse.urlsplit(candidate).hostname or "") == "lobby.ikariam.gameforge.com":
                        return True
            except Exception:
                pass
        return False

    def __printSessionRotated(self):
        if getattr(self, "_session_rotated_printed", False):
            return
        self._session_rotated_printed = True
        msg = (
            "\n"
            "[ERROR] The bot's session has expired.\n"
            "\n"
            "If you logged into Ikariam from another browser or device, the bot's "
            "session is closed automatically: it's not possible to keep both "
            "sessions active at the same time.\n"
            "\n"
            "Alternatives:\n"
            "  1) Use the Web Server module, which emulates the Ikariam web server "
            "and lets you control the bot from a local URL.\n"
            "  2) Export the browser cookies (or the other way around) from the "
            "Settings > Import/Export cookies menu.\n"
            "\n"
            "At this point ikabot cannot log in again, so it will close once you "
            "press [Enter].\n"
        )
        self.logger.error("Session expired: closing ikabot")
        print(msg)
        try:
            enter()
        except Exception:
            pass
        self.__closeIkabot()

    def __closeIkabot(self):
        """Terminates the whole ikabot application. Child processes cannot simply
        call os._exit(1): the main menu process is blocked on event.wait() waiting
        for the event that a killed child never fires, so it would hang forever.
        If the parent process is another ikabot process (menu / webServer launcher),
        terminate it as well. If we are the top-level menu process, the parent is
        just the terminal/shell and is left alone.
        A parent that also runs tasks of other accounts (tasks started through the
        CLI / IPC) is left alone too, and only this account's tasks are terminated."""
        try:
            import psutil
            parent = psutil.Process(os.getppid())
            parent_name = parent.name().lower()
            is_python_like = parent_name.startswith("python") or "ikabot" in parent_name
            if is_python_like:
                parent_cmd = " ".join(parent.cmdline()).lower()
                if "command_line" in parent_cmd or "ikabot" in parent_cmd:
                    my_pid = os.getpid()
                    siblings = [
                        proc for proc in parent.children(recursive=True) if proc.pid != my_pid
                    ]
                    own_pids, other_pids = self.__accountTaskPids()
                    # padre is still True while the menu waits for this task's configurator
                    shared_parent = not self.padre and any(
                        proc.pid in other_pids for proc in siblings
                    )
                    for proc in siblings:
                        if shared_parent and proc.pid not in own_pids:
                            continue
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                    if not shared_parent:
                        parent.terminate()
                        parent.wait(timeout=5)
        except Exception:
            pass
        os._exit(1)

    def __accountTaskPids(self):
        """Returns (pids of this account's tasks, pids of every other account's tasks)"""
        own_key = (
            (getattr(self, "mail", None) or "").lower(),
            getattr(self, "username", None),
            str(getattr(self, "mundo", "")),
            getattr(self, "servidor", None),
        )
        own_pids, other_pids = set(), set()
        for key, pids in get_task_pids_by_account().items():
            if key == own_key:
                own_pids |= pids
            else:
                other_pids |= pids
        return own_pids, other_pids

    def isExpired(self, html):
        return self.__isExpired(html)

    def __saveNewCookies(self):
        sessionData = self.getSessionData()

        cookie_dict = dict(self.s.cookies.items())
        sessionData["cookies"] = cookie_dict

        self.setSessionData(sessionData)

    def __getCookie(self, sessionData=None):
        if sessionData is None:
            sessionData = self.getSessionData()
        try:
            cookie_dict = sessionData["cookies"]
            self.s = requests.Session()
            self.__update_proxy(sessionData=sessionData)
            self.s.headers.clear()
            self.s.headers.update(self.headers)
            requests.cookies.cookiejar_from_dict(
                cookie_dict, cookiejar=self.s.cookies, overwrite=True
            )
        except KeyError:
            self.__login(3)

    def __test_lobby_cookie(self):
        if "gf-token-production" in self.s.cookies:
            self.headers = {
                "Host": "lobby.ikariam.gameforge.com",
                "User-Agent": self.user_agent,
                "Accept": "*/*",
                "Accept-Language": self.accept_language,
                "Accept-Encoding": "gzip, deflate",
                "DNT": "1",
                "Connection": "close",
                "Referer": "https://lobby.ikariam.gameforge.com/",
                "Authorization": "Bearer " + self.s.cookies["gf-token-production"],
            }
            self.s.headers.clear()
            self.s.headers.update(self.headers)
            if (
                self.s.get(
                    "https://lobby.ikariam.gameforge.com/api/users/me"
                ).status_code
                == 200
            ):
                return True
            self.s.cookies.clear()
        return False

    def __test_server_maintenace(self, html):
        match = re.search(
            r'\[\["provideFeedback",\[{"location":1,"type":11,"text":([\S\s]*)}\]\]\]',
            html,
        )
        if (
            match
            and '[["provideFeedback",[{"location":1,"type":11,"text":'
            + match.group(1)
            + "}]]]"
            == html
        ):
            return True
        if "backupLockTimer" in html:
            return True
        return False

    def __set_manual_blackbox_token(self, manual_value):
        manual_value = manual_value.strip()
        token = manual_value

        try:
            payload = json.loads(manual_value)
            if not isinstance(payload, dict):
                raise ValueError("Manual blackbox payload must be an object")

            token = payload.get("blackbox") or payload.get("token")
            if not token:
                raise ValueError("Manual blackbox payload is missing blackbox")

            user_agent = payload.get("user_agent") or payload.get("userAgent")
            if isinstance(user_agent, str) and user_agent:
                self.user_agent = user_agent

            locale = payload.get("locale")
            if not os.environ.get("IKABOT_LOCALE") and isinstance(locale, str) and locale.strip():
                self.locale = locale.strip()
                if not os.environ.get("IKABOT_GF_LANG"):
                    self.gf_lang = self.locale.split("-")[0]
                self.accept_language = config.build_accept_language(
                    self.locale, self.gf_lang
                )

            timezone_id = payload.get("timezone_id") or payload.get("timezoneId")
            if not os.environ.get("IKABOT_TIMEZONE_ID") and isinstance(timezone_id, str) and timezone_id.strip():
                self.timezone_id = timezone_id.strip()

        except json.JSONDecodeError:
            pass

        token = token.strip()
        self.blackbox = token if token.startswith("tra:") else "tra:" + token

    def __ask_manual_blackbox_payload(self, allow_skip=False):
        print("You can obtain a manual blackbox payload here:")
        print("https://ikabot-collective.github.io/IkabotAPI/")
        print("Paste the full JSON payload so Ikabot can reuse the same browser context.")
        print("Raw blackbox tokens are still accepted for compatibility.")
        if allow_skip:
            print("Press Enter to skip this step and use gf-token-production instead.")
        msg = "Paste the manual blackbox payload or raw blackbox token (e.g. JVq...):"
        if allow_skip:
            msg = "Paste the manual blackbox payload or raw blackbox token, or press Enter to skip:"
        manual_value = read(
            msg=msg
        )
        if not manual_value or not manual_value.strip():
            return False
        self.__set_manual_blackbox_token(manual_value)
        return True

    def __ask_lobby_cookie(self):
        print(
            "Falling back to gf-token-production. This is the most reliable login fallback."
        )
        print(
            "Log into the lobby via browser and then press CTRL + SHIFT + J to open up the javascript console"
        )
        print(
            "If you can not open the console using CTRL + SHIFT + J then press F12 to open Dev Tools"
        )
        print(
            'In the dev tools there should be a tab called "Console". Press this tab.'
        )
        print("Paste in the script below and press enter")
        print(
            "document.cookie.split(';').forEach(x => {if (x.includes('production')) console.log(x)})"
        )

        auth_token = read(msg="\nEnter gf-token-production manually:").split(
            "="
        )[-1]
        cookie_obj = requests.cookies.create_cookie(
            domain=".gameforge.com",
            name="gf-token-production",
            value=auth_token,
        )
        self.s.cookies.set_cookie(cookie_obj)
        if not self.__test_lobby_cookie():
            sys.exit("The provided gf-token-production cookie is invalid or expired\n")
        return auth_token

    def __ask_password_if_needed(self):
        """
        If the user resumed a saved session without a password (empty mail /
        saved account selection), asking it on the first prompt would defeat
        the cookie-based login. But if the lobby cookie has expired we now do
        need the real credentials to re-authenticate via mauth. Ask for them
        only in that moment, and only in the parent process.
        """
        if not self.password and self.padre:
            if not self.mail:
                print("\nThe stored session has expired and no account mail was provided.")
                self.mail = read(msg="Mail: ")
            print("\nThe stored session has expired. Enter the password for '{}':".format(self.mail))
            self.password = getpass.getpass("Password: ")

    def __load_new_blackbox_token(self, allow_lobby_cookie_fallback=False):
        try:
            if self.padre:
                print("Obtaining new blackbox token, please wait...")
            blackbox_token = getNewBlackBoxToken(self)
            if self.api_user_agent:
                self.user_agent = self.api_user_agent
            assert any(
                c.isupper() for c in blackbox_token
            ), "The token must contain uppercase letters."
            assert any(
                c.islower() for c in blackbox_token
            ), "The token must contain lowercase letters."
            assert any(
                c.isdigit() for c in blackbox_token
            ), "The token must contain digits."
            self.blackbox = blackbox_token
            return True
        except Exception as e:
            self.logger.error("Failed to obtain new blackbox token from API: ", exc_info=True)
            if not self.padre: # only exit if running in a child process because user won't be looking at the console to provide the cookies
                sys.exit('Failed to regenerate blackbox token')
            print(f'{bcolors.RED}[ERROR]{bcolors.ENDC} Failed to obtain new blackbox token from API: ' + str(e)) # using expired fallback token here so that user can insert cookie manually since blackbox generation failed at this point
            print('Please report this issue to developers on github or the discord server!!')
            print('')
            if allow_lobby_cookie_fallback:
                print('You can provide a manual blackbox payload or skip to gf-token-production:')
            else:
                print('You will need to obtain the manual blackbox payload:')
            if self.__ask_manual_blackbox_payload(allow_skip=allow_lobby_cookie_fallback):
                enter()
                return True
            if allow_lobby_cookie_fallback:
                self.__ask_lobby_cookie()
                self.blackbox = None
                return False
            sys.exit('Manual blackbox payload was empty')

    def __login(self, retries=0):
        if not self.logged:
            banner()

            self.mail = read(msg="Mail:")
            entered_mail = self.mail

            if not entered_mail:
                # No mail provided (Enter/Enter). Never ask for a password:
                # use the stored cookies from default_user.json, or if that
                # does not exist but other accounts are saved, let the user
                # pick one so its cookies are reused.
                default_user_file = get_user_file_path("")
                saved_users = get_saved_users()
                if saved_users and not os.path.exists(default_user_file):
                    if len(saved_users) == 1:
                        selected = saved_users[0]
                        print("\nNo default account found, using saved account: {}".format(selected))
                    else:
                        print("\nNo default account found. Select a saved account:")
                        for i, user in enumerate(saved_users, start=1):
                            print("  {}. {}".format(i, user))
                        selected = saved_users[read(min=1, max=len(saved_users), digit=True) - 1]
                    self.mail = selected
                # Cookies are already stored, skip password prompt (unless we
                # already learned the password during a previous retry)
                if not self.password:
                    self.password = ""
            else:
                # Mail was typed. If it matches a saved account, reuse its cookies
                # instead of asking for a password.
                matching_path, has_duplicates = find_user_file_for_email(entered_mail)
                if matching_path:
                    if has_duplicates:
                        print("\n[Warning] '{}' is present in multiple session files. Using the most recently modified one.".format(entered_mail))
                    self.password = ""
                else:
                    # No saved session for this mail
                    print("\nNo saved session found for '{}'.".format(entered_mail))
                    print("Check the files in: {}".format(get_users_dir()))
                    print("If they are outdated or corrupted, delete them and log in manually.")
                    if len(config.predetermined_input) != 0:
                        self.password = config.predetermined_input.pop(0)
                    else:
                        self.password = getpass.getpass("Password:")

            banner()

        #choose one user agent from user_agents list based on provided mail
        selected_user_agent = user_agents[sum(ord(c) for c in self.mail) % len(user_agents)]
        self.api_user_agent = selected_user_agent
        self.user_agent = selected_user_agent

        self.s = requests.Session()
        self.cipher = AESCipher(self.mail, self.password)
        migrate_legacy_account(self.mail, self.password, self.logger)
        self.logger.info("__login()")

        # test to see if the lobby cookie in the session file is valid, this will save time on login and will reduce use of blackbox token
        sessionData = self.getSessionData()
        if "shared" in sessionData and "lobby" in sessionData["shared"]:
            cookie_obj = requests.cookies.create_cookie(
                domain=".gameforge.com",
                name="gf-token-production",
                value=sessionData["shared"]["lobby"]["gf-token-production"],
            )
            self.s.cookies.set_cookie(cookie_obj)

        if not self.__test_lobby_cookie():

            self.logger.warning("Getting new lobby cookie")
            self.__ask_password_if_needed()
            blackbox_loaded = self.__load_new_blackbox_token(allow_lobby_cookie_fallback=True)
            if not blackbox_loaded:
                auth_token = self.s.cookies["gf-token-production"]
            else:

                # get gameEnvironmentId and platformGameId
                self.headers = {
                    "Host": "lobby.ikariam.gameforge.com",
                    "User-Agent": self.user_agent,
                    "Accept": "*/*",
                    "Accept-Language": self.accept_language,
                    "Accept-Encoding": "gzip, deflate",
                    "DNT": "1",
                    "Connection": "close",
                    "Referer": "https://lobby.ikariam.gameforge.com/",
                }
                self.s.headers.clear()
                self.s.headers.update(self.headers)
                r = self.s.get(
                    "https://lobby.ikariam.gameforge.com/config/configuration.js"
                )

                js = r.text
                gameEnvironmentId = re.search(r'"gameEnvironmentId":"(.*?)"', js)
                if gameEnvironmentId is None:
                    sys.exit("gameEnvironmentId not found")
                gameEnvironmentId = gameEnvironmentId.group(1)
                platformGameId = re.search(r'"platformGameId":"(.*?)"', js)
                if platformGameId is None:
                    sys.exit("platformGameId not found")
                platformGameId = platformGameId.group(1)

                # get __cfduid cookie
                self.headers = {
                    "User-Agent": self.user_agent,
                    "Accept": "*/*",
                    "Accept-Language": self.accept_language,
                    "Accept-Encoding": "gzip, deflate",
                    "DNT": "1",
                    "Connection": "close",
                    "Referer": "https://lobby.ikariam.gameforge.com/",
                }
                self.s.headers.clear()
                self.s.headers.update(self.headers)
                r = self.s.get("https://gameforge.com/js/connect.js")
                html = r.text
                captcha = re.search(r"Attention Required", html)
                if captcha is not None:
                    sys.exit("Captcha error!")

                # update __cfduid cookie
                self.headers = {
                    "User-Agent": self.user_agent,
                    "Accept": "*/*",
                    "Accept-Language": self.accept_language,
                    "Accept-Encoding": "gzip, deflate",
                    "Referer": "https://lobby.ikariam.gameforge.com/",
                    "Origin": "https://lobby.ikariam.gameforge.com",
                    "DNT": "1",
                    "Connection": "close",
                }
                self.s.headers.clear()
                self.s.headers.update(self.headers)
                r = self.s.get("https://gameforge.com/config")

                __fp_eval_id_1 = self.__fp_eval_id()
                __fp_eval_id_2 = self.__fp_eval_id()
                try:
                    # get pc_idt cookie
                    self.headers = {
                        "Host": "pixelzirkus.gameforge.com",
                        "User-Agent": self.user_agent,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Language": self.accept_language,
                        "Accept-Encoding": "gzip, deflate",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": "https://lobby.ikariam.gameforge.com",
                        "DNT": "1",
                        "Connection": "close",
                        "Referer": "https://lobby.ikariam.gameforge.com/",
                        "Upgrade-Insecure-Requests": "1",
                    }
                    self.s.headers.clear()
                    self.s.headers.update(self.headers)
                    data = {
                        "product": "ikariam",
                        "server_id": "1",
                        "language": self.gf_lang,
                        "location": "VISIT",
                        "replacement_kid": "",
                        "fp_eval_id": __fp_eval_id_1,
                        "page": "https%3A%2F%2Flobby.ikariam.gameforge.com%2F",
                        "referrer": "",
                        "fingerprint": "2175408712",
                        "fp_exec_time": "1.00",
                    }
                    r = self.s.post(
                        "https://pixelzirkus.gameforge.com/do/simple", data=data
                    )

                    # update pc_idt cookie
                    self.headers = {
                        "Host": "pixelzirkus.gameforge.com",
                        "User-Agent": self.user_agent,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Language": self.accept_language,
                        "Accept-Encoding": "gzip, deflate",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": "https://lobby.ikariam.gameforge.com",
                        "DNT": "1",
                        "Connection": "close",
                        "Referer": "https://lobby.ikariam.gameforge.com/",
                        "Upgrade-Insecure-Requests": "1",
                    }
                    self.s.headers.clear()
                    self.s.headers.update(self.headers)
                    data = {
                        "product": "ikariam",
                        "server_id": "1",
                        "language": self.gf_lang,
                        "location": "fp_eval",
                        "fp_eval_id": __fp_eval_id_2,
                        "fingerprint": "2175408712",
                        "fp2_config_id": "1",
                        "page": "https%3A%2F%2Flobby.ikariam.gameforge.com%2F",
                        "referrer": "",
                        "fp2_value": "921af958be7cf2f76db1e448c8a5d89d",
                        "fp2_exec_time": "96.00",
                    }
                    r = self.s.post(
                        "https://pixelzirkus.gameforge.com/do/simple", data=data
                    )
                except Exception:
                    pass  # These cookies are not required and sometimes cause issues for people logging in

                # options req (not really needed)
                self.headers = {
                    "Accept": "*/*",
                    "Accept-Language": self.accept_language,
                    "Accept-Encoding": "gzip, deflate, br",
                    "Access-Control-Request-Headers": "content-type,tnt-installation-id",
                    "Access-Control-Request-Method": "POST",
                    "Origin": "https://lobby.ikariam.gameforge.com",
                    "Referer": "https://lobby.ikariam.gameforge.com/",
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "no-cors",
                    "Sec-Fetch-Site": "same-site",
                    "TE": "trailers",
                    "User-Agent": self.user_agent,
                }
                self.s.headers.clear()
                self.s.headers.update(self.headers)
                r = self.s.options("https://gameforge.com/api/v1/auth/thin/sessions")

                # send creds
                self.headers = {
                    "Accept": "*/*",
                    "Accept-Language": self.accept_language,
                    "Accept-Encoding": "gzip, deflate, br",
                    "Access-Control-Request-Headers": "content-type,tnt-installation-id",
                    "Access-Control-Request-Method": "POST",
                    "Origin": "https://lobby.ikariam.gameforge.com",
                    "Referer": "https://lobby.ikariam.gameforge.com/",
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "no-cors",
                    "Sec-Fetch-Site": "same-site",
                    "TE": "trailers",
                    "TNT-Installation-Id": "",
                    "User-Agent": self.user_agent,
                }
                self.s.headers.clear()
                self.s.headers.update(self.headers)
                data = {
                    "identity": self.mail,
                    "password": self.password,
                    "locale": self.locale,
                    "gfLang": self.gf_lang,
                    "gameId": platformGameId,
                    "gameEnvironmentId": gameEnvironmentId,
                    "blackbox": self.blackbox,
                }
                r = self.s.post(
                    "https://spark-web.gameforge.com/api/v2/authProviders/mauth/sessions", json=data
                )

                # MFA / 2FA Check. If the server responds with 409, it means 2FA is required.
                if r.status_code == 409 and 'OTP_REQUIRED' in r.text:
                    if self.padre:
                        print("Two-factor authentication (2FA) is required.")
                        mfa_code = read(msg="Enter your 2FA code: ")
                    else:
                        self.logger.error("2FA is required, but it cannot be requested in a child process.")
                        sys.exit("Login failure: 2FA is required in a non-interactive process.")

                    # Add the OTP code to the original data and send the request again
                    # to the same endpoint.
                    data['otpCode'] = mfa_code

                    r = self.s.post(
                        "https://spark-web.gameforge.com/api/v2/authProviders/mauth/sessions", json=data
                    )

                if "gf-challenge-id" in r.headers and 'token' not in r.text:
                    while True:
                        self.headers = {
                            "Accept": "*/*",
                            "Accept-Language": self.accept_language,
                            "Accept-Encoding": "gzip, deflate, br",
                            "Access-Control-Request-Headers": "content-type,tnt-installation-id",
                            "Access-Control-Request-Method": "POST",
                            "Origin": "https://lobby.ikariam.gameforge.com",
                            "Referer": "https://lobby.ikariam.gameforge.com/",
                            "Sec-Fetch-Dest": "empty",
                            "Sec-Fetch-Mode": "no-cors",
                            "Sec-Fetch-Site": "same-site",
                            "TE": "trailers",
                            "TNT-Installation-Id": "",
                            "User-Agent": self.user_agent,
                        }
                        self.s.headers.clear()
                        self.s.headers.update(self.headers)
                        data = {
                                "identity": self.mail,
                                "password": self.password,
                                "locale": self.locale,
                                "gfLang": self.gf_lang,
                                "gameId": platformGameId,
                                "gameEnvironmentId": gameEnvironmentId,
                                "blackbox": self.blackbox,
                            }
                        r = self.s.post(
                            "https://spark-web.gameforge.com/api/v2/authProviders/mauth/sessions", json=data
                        )

                        challenge_id = r.headers["gf-challenge-id"].split(";")[0]
                        self.headers = {
                            "accept": "*/*",
                            "accept-encoding": "gzip, deflate, br",
                            "accept-language": self.accept_language,
                            "dnt": "1",
                            "origin": "https://lobby.ikariam.gameforge.com",
                            "referer": "https://lobby.ikariam.gameforge.com/",
                            "sec-fetch-dest": "empty",
                            "sec-fetch-mode": "cors",
                            "sec-fetch-site": "same-site",
                            "user-agent": self.user_agent,
                        }
                        self.s.headers.clear()
                        self.s.headers.update(self.headers)
                        request1 = self.s.get(
                            "https://challenge.gameforge.com/challenge/{}".format(
                                challenge_id
                            )
                        )
                        request2 = self.s.get(
                            "https://image-drop-challenge.gameforge.com/index.js"
                        )
                        try:
                            request3 = self.s.post(
                                "https://pixelzirkus.gameforge.com/do2/simple"
                            )
                        except Exception as e:
                            pass

                        captcha_time = self.s.get(
                            "https://image-drop-challenge.gameforge.com/challenge/{}/en-GB".format(
                                challenge_id
                            )
                        ).json()["lastUpdated"]
                        text_image = self.s.get(
                            "https://image-drop-challenge.gameforge.com/challenge/{}/en-GB/text?{}".format(
                                challenge_id, captcha_time
                            )
                        ).content
                        drag_icons = self.s.get(
                            "https://image-drop-challenge.gameforge.com/challenge/{}/en-GB/drag-icons?{}".format(
                                challenge_id, captcha_time
                            )
                        ).content
                        drop_target = self.s.get(
                            "https://image-drop-challenge.gameforge.com/challenge/{}/en-GB/drop-target?{}".format(
                                challenge_id, captcha_time
                            )
                        ).content
                        data = {}
                        try:
                            captcha = break_interactive_captcha(text_image, drag_icons)
                            data = {"answer": captcha}
                        except Exception as e:
                            print(
                                "The interactive captcha has been presented. Automatic captcha resolution failed because: {}".format(
                                    str(e)
                                )
                            )
                            print("Do you want to solve it via Telegram? (Y/n)")
                            config.predetermined_input[:] = (
                                []
                            )  # Unholy way to clear a ListProxy object
                            answer = read(values=["y", "Y", "n", "N"], default="y")
                            if answer.lower() == "n":
                                sys.exit("Captcha error! (Interactive)")

                            sendToBot(self, "", Photo=text_image)
                            sendToBot(
                                self,
                                "Please send the number of the correct image (1, 2, 3 or 4)",
                                Photo=drag_icons,
                            )
                            print("Check your Telegram and do it fast. The captcha expires quickly")
                            captcha_time = time.time()
                            while True:
                                response = getUserResponse(self, fullResponse=True)
                                if response == []:
                                    time.sleep(5)
                                    continue
                                response = response[-1]
                                if response["date"] < captcha_time:
                                    time.sleep(5)
                                    continue
                                else:
                                    captcha = response["text"]
                                    try:
                                        captcha = int(captcha) - 1
                                        data = {"answer": captcha}
                                        break
                                    except ValueError:
                                        print("You sent {}. Please send only a number (1, 2, 3 or 4)".format(captcha))
                                        time.sleep(5)
                                        continue
                                time.sleep(5)
                        captcha_sent = self.s.post(
                            "https://image-drop-challenge.gameforge.com/challenge/{}/en-GB".format(
                                challenge_id
                            ),
                            json=data,
                        ).json()
                        if captcha_sent["status"] == "solved":
                            self.headers = {
                                "Accept": "*/*",
                                "Accept-Language": self.accept_language,
                                "Accept-Encoding": "gzip, deflate, br",
                                "Access-Control-Request-Headers": "content-type,tnt-installation-id",
                                "Access-Control-Request-Method": "POST",
                                "Origin": "https://lobby.ikariam.gameforge.com",
                                "Referer": "https://lobby.ikariam.gameforge.com/",
                                "Sec-Fetch-Dest": "empty",
                                "Sec-Fetch-Mode": "no-cors",
                                "Sec-Fetch-Site": "same-site",
                                "TE": "trailers",
                                "TNT-Installation-Id": "",
                                "Gf-Challenge-Id": challenge_id,
                                "User-Agent": self.user_agent,
                            }
                            self.s.headers.clear()
                            self.s.headers.update(self.headers)
                            data = {
                                "identity": self.mail,
                                "password": self.password,
                                "locale": self.locale,
                                "gfLang": self.gf_lang,
                                "gameId": platformGameId,
                                "gameEnvironmentId": gameEnvironmentId,
                                "blackbox": self.blackbox,
                            }
                            r = self.s.post(
                                "https://spark-web.gameforge.com/api/v2/authProviders/mauth/sessions", json=data
                            )
                            if "gf-challenge-id" in r.headers:
                                self.logger.error("Failed to solve interactive captcha!")
                                print("Failed to solve interactive captcha, trying again!")
                                continue
                            else:
                                break

                if 'token' not in r.text:
                    print("Failed to log in...")
                    print(f"Expected to get token in response to login request but instead got code {r.status_code} and body {r.text}")
                    print(
                        "Login failed. This may be caused by invalid credentials, a rejected manual blackbox payload/token, or a Gameforge challenge."
                    )
                    if self.padre:
                        print(
                            "Before using the cookie fallback, you can try a browser-generated manual blackbox payload."
                        )
                        if self.__ask_manual_blackbox_payload(allow_skip=True):
                            print("Retrying lobby login with the manual blackbox payload...")
                            self.headers = {
                                "Accept": "*/*",
                                "Accept-Language": self.accept_language,
                                "Accept-Encoding": "gzip, deflate, br",
                                "Access-Control-Request-Headers": "content-type,tnt-installation-id",
                                "Access-Control-Request-Method": "POST",
                                "Origin": "https://lobby.ikariam.gameforge.com",
                                "Referer": "https://lobby.ikariam.gameforge.com/",
                                "Sec-Fetch-Dest": "empty",
                                "Sec-Fetch-Mode": "no-cors",
                                "Sec-Fetch-Site": "same-site",
                                "TE": "trailers",
                                "TNT-Installation-Id": "",
                                "User-Agent": self.user_agent,
                            }
                            self.s.headers.clear()
                            self.s.headers.update(self.headers)
                            data["locale"] = self.locale
                            data["gfLang"] = self.gf_lang
                            data["blackbox"] = self.blackbox
                            r = self.s.post(
                                "https://spark-web.gameforge.com/api/v2/authProviders/mauth/sessions", json=data
                            )
                            if 'token' not in r.text:
                                print("Manual blackbox payload login failed.")
                                print(f"Expected to get token in response to login request but instead got code {r.status_code} and body {r.text}")

                if 'token' not in r.text:
                    auth_token = self.__ask_lobby_cookie()
                else:
                    # get the authentication token and set the cookie
                    ses_json = json.loads(r.text, strict=False)
                    auth_token = ses_json["token"]
                    cookie_obj = requests.cookies.create_cookie(
                        domain=".gameforge.com",
                        name="gf-token-production",
                        value=auth_token,
                    )
                    self.s.cookies.set_cookie(cookie_obj)

            # set the lobby cookie in shared for all world server accounts

            lobby_data = dict()
            lobby_data["lobby"] = dict()
            lobby_data["lobby"]["gf-token-production"] = auth_token
            self.setSessionData(lobby_data, shared=True)
        else:
            self.logger.info("Using old lobby cookie")

        # get accounts
        self.headers = {
            "Host": "lobby.ikariam.gameforge.com",
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Language": self.accept_language,
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://lobby.ikariam.gameforge.com/{}/hub".format(self.locale.replace('-', '_')),
            "Authorization": "Bearer {}".format(self.s.cookies["gf-token-production"]),
            "DNT": "1",
            "Connection": "close",
        }
        self.s.headers.clear()
        self.s.headers.update(self.headers)
        r = self.s.get("https://lobby.ikariam.gameforge.com/api/users/me/accounts")
        accounts = json.loads(r.text, strict=False)

        # get servers
        self.headers = {
            "Host": "lobby.ikariam.gameforge.com",
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Language": self.accept_language,
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://lobby.ikariam.gameforge.com/{}/hub".format(self.locale.replace('-', '_')),
            "Authorization": "Bearer {}".format(self.s.cookies["gf-token-production"]),
            "DNT": "1",
            "Connection": "close",
        }
        self.s.headers.clear()
        self.s.headers.update(self.headers)
        r = self.s.get("https://lobby.ikariam.gameforge.com/api/servers")
        servers = json.loads(r.text, strict=False)

        if not self.logged:

            if (
                len([account for account in accounts if account["blocked"] is False])
                == 1
            ):
                self.account = [
                    account for account in accounts if account["blocked"] is False
                ][0]
            else:
                print("With which account do you want to log in?\n")

                max_name = max(
                    [
                        len(account["name"])
                        for account in accounts
                        if account["blocked"] is False
                    ]
                )
                i = 0
                for account in [
                    account for account in accounts if account["blocked"] is False
                ]:
                    server = account["server"]["language"]
                    mundo = account["server"]["number"]
                    account_group = account["accountGroup"]
                    server_lang = None
                    world, server_lang = [
                        (srv["name"], srv["language"])
                        for srv in servers
                        if srv["accountGroup"] == account_group
                    ][0]
                    try: lastlogin =  lastloginTimetoString(account["lastLogin"])
                    except: lastlogin = 'Unknown'

                    i += 1
                    pad = " " * (max_name - len(account["name"]))
                    print(
                        "({:d}) {}{} [{} - {} - {}]".format(
                            i, account["name"], pad, lastlogin, server_lang, world
                        )
                    )
                num = read(min=1, max=i)
                self.account = [
                    account for account in accounts if account["blocked"] is False
                ][num - 1]
            self.username = self.account["name"]
            self.login_servidor = self.account["server"]["language"]
            self.account_group = self.account["accountGroup"]
            self.mundo = str(self.account["server"]["number"])

            self.word, self.servidor = [
                (srv["name"], srv["language"])
                for srv in servers
                if srv["accountGroup"] == self.account_group
            ][0]

            config.infoUser = "Server:{}".format(self.servidor)
            config.infoUser += ", World:{}".format(self.word)
            config.infoUser += ", Player:{}".format(self.username)
            setLoggedInPlayer(self.username)
            banner()

        self.host = "s{}-{}.ikariam.gameforge.com".format(self.mundo, self.servidor)
        self.urlBase = "https://{}/index.php?".format(self.host)

        self.headers = {
            "Host": self.host,
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Accept-Language": self.accept_language,
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://{}".format(self.host),
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://{}".format(self.host),
            "DNT": "1",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        }

        sessionData = self.getSessionData()

        used_old_cookies = False
        # if there are cookies stored, try to use them
        if "cookies" in sessionData and self.logged is False:
            # create a new temporary session object
            old_s = requests.Session()
            # set the headers
            old_s.headers.clear()
            old_s.headers.update(self.headers)
            # set the cookies to test
            cookie_dict = sessionData["cookies"]
            requests.cookies.cookiejar_from_dict(
                cookie_dict, cookiejar=old_s.cookies, overwrite=True
            )
            self.__update_proxy(obj=old_s, sessionData=sessionData)
            try:
                # make a request to check the connection
                old_resp = old_s.get(self.urlBase, verify=config.do_ssl_verify)
                html = old_resp.text
            except Exception:
                self.__proxy_error()

            cookies_are_valid = self.__isExpired(html) is False
            # A valid-looking response that is actually the session-rotation
            # payload (or a 404) means the stored cookies belong to a session
            # that another login (browser/device) already took over. In that
            # case the bot should not reuse them: a fresh login will win the
            # session back from the other device.
            if cookies_are_valid and self.__isSessionRotated(html, response=old_resp):
                self.logger.warning("Stored cookies were invalidated by another active session; performing a fresh login")
                cookies_are_valid = False
            if cookies_are_valid and old_resp.status_code == 404:
                self.logger.warning("Stored cookies returned 404; performing a fresh login")
                cookies_are_valid = False
            if cookies_are_valid:
                self.logger.info("using old cookies")
                used_old_cookies = True
                # assign the old cookies to the session object
                requests.cookies.cookiejar_from_dict(
                    cookie_dict, cookiejar=self.s.cookies, overwrite=True
                )
                # set the proxy
                self.__update_proxy(sessionData=sessionData)
                # set the headers
                self.s.headers.clear()
                self.s.headers.update(self.headers)

        # login as normal and get new cookies
        if used_old_cookies is False:
            self.__load_new_blackbox_token()
            self.logger.warning("using new cookies")
            self.headers = {
                "authority": "lobby.ikariam.gameforge.com",
                "method": "POST",
                "path": "/api/users/me/loginLink",
                "scheme": "https",
                "accept": "application/json",
                "accept-encoding": "gzip, deflate, br",
                "accept-language": self.accept_language,
                "authorization": "Bearer " + self.s.cookies["gf-token-production"],
                "content-type": "application/json",
                "origin": "https://lobby.ikariam.gameforge.com",
                "referer": "https://lobby.ikariam.gameforge.com/{}/accounts".format(self.locale.replace('-', '_')),
                "user-agent": self.user_agent,
            }
            self.s.headers.clear()
            self.s.headers.update(self.headers)
            data = {
                "server": {"language": self.login_servidor, "number": self.mundo},
                "clickedButton": "account_list",
                "id": self.account["id"],
                "blackbox": self.blackbox,
            }
            resp = self.s.post(
                "https://lobby.ikariam.gameforge.com/api/users/me/loginLink", json=data
            )
            respJson = json.loads(resp.text)
            skipGetCookie = False
            if "url" not in respJson:
                if retries > 0:
                    return self.__login(retries - 1)
                else:  # 403 is for bad user/pass and 400 is bad blackbox token?
                    msg = (
                        "Login Error: "
                        + str(resp.status_code)
                        + " "
                        + str(resp.reason)
                        + " "
                        + str(resp.text)
                    )
                    if resp.status_code in [400, 403, 409]:
                        msg += (
                            "\nGameforge may have rejected the blackbox payload/token or the current lobby session. "
                            "Manual browser cookie login is the recommended fallback."
                        )
                    self.logger.error(msg)
                    if self.padre:
                        print(msg)
                        print(
                            "Failed to log in... Do you want to provide the cookie manually? (Y|N): "
                        )
                        choice = read(values=["y", "Y", "n", "N"], empty=False)
                        if choice in ["n", "N"]:
                            sys.exit(msg)
                        while True:
                            print("• Log into the account via browser")
                            print("• Load your city view")
                            print("• Press F12 to open up the dev tools")
                            print(
                                '• In the dev tools click the tab "Application" if on Chrome or "Storage" if on Firefox'
                            )
                            print(
                                '• Within this window, there should be a dropdown menu called "Cookies" on the far left'
                            )
                            print(
                                '• Select the row "https://s[nubmer]-[region].ikariam.gameforge.com"'
                            )
                            print(
                                '• Look in the table on the right for the entry named "ikariam"'
                            )
                            print("• Copy its value and paste it just below")

                            ikariam_cookie = read(
                                msg="\nEnter ikariam cookie manually: "
                            ).split("=")[-1]
                            cookie_obj = requests.cookies.create_cookie(
                                domain=self.host, name="ikariam", value=ikariam_cookie
                            )
                            self.s.cookies.set_cookie(cookie_obj)
                            try:
                                # make a request to check the connection
                                html = self.s.get(
                                    self.urlBase, verify=config.do_ssl_verify
                                ).text
                            except Exception:
                                self.__proxy_error()
                            skipGetCookie = cookies_are_valid = (
                                self.__isExpired(html) is False
                            )
                            if not cookies_are_valid:
                                print(
                                    "This cookie is expired. Do you want to try again? (Y|N): "
                                )
                                choice = read(values=["y", "Y", "n", "N"], empty=False)
                                if choice in ["n", "N"]:
                                    sys.exit(msg)
                                continue
                            # TODO check if account is actually the one associated with this email / pass
                            break
                    else:
                        self.logger.error("I wanted to ask user for ikariam cookie, but he wasn't looking")
                        sys.exit(msg)

            if not skipGetCookie:
                url = respJson["url"]
                match = re.search(
                    r"https://s\d+-\w{2}\.ikariam\.gameforge\.com/index\.php\?", url
                )
                if match is None:
                    sys.exit("Error")

                # set the headers
                self.s.headers.clear()
                self.s.headers.update(self.headers)

                # set the proxy
                self.__update_proxy(sessionData=sessionData)

                # use the new cookies instead, invalidate the old ones
                try:
                    html = self.s.get(url, verify=config.do_ssl_verify).text
                except Exception:
                    self.__proxy_error()

        if self.__isInVacation(html):
            msg = "The account went into vacation mode"
            if self.padre:
                print(msg)
            else:
                sendToBot(self, msg)
            os._exit(0)
        if self.__isExpired(html):
            if retries > 0:
                return self.__login(retries - 1)
            if self.padre:
                msg = "Login error."
                print(msg)
                os._exit(0)
            raise Exception("Couldn't log in")

        if not used_old_cookies:
            self.__saveNewCookies()

        self.logged = True

        # --- Developer runtime info ---
        self.dev_api_host = self.host
        self.dev_url_base = self.urlBase

        cookies = self.s.cookies.get_dict()
        self.dev_ikariam_cookie = cookies.get("ikariam")
        self.dev_gf_token = cookies.get("gf-token-production")

    def __backoff(self):
        self.logger.info("__backoff()")
        if self.padre is False:
            time.sleep(5 * random.randint(0, 10))

    def __isSessionAlive(self):
        """Checks with a light request whether the session is still valid. Some error
        pages look like an expired session, and logging in again would invalidate the
        session of every other running task
        Returns
        -------
        alive : bool or None
            None if it could not be determined
        """
        try:
            response = self.s.get(
                self.urlBase + "view=updateGlobalData&ajax=1",
                verify=config.do_ssl_verify,
                timeout=60,
                allow_redirects=False,
            )
        except requests.exceptions.RequestException:
            return None
        # an expired session gets a redirect or a reload command to the lobby
        location = response.headers.get("Location", "")
        if (urllib.parse.urlsplit(location).hostname or "") == "lobby.ikariam.gameforge.com":
            return False
        if self.__isSessionRotated(response.text, response=response):
            return False
        try:
            alive = response.status_code == 200 and json.loads(response.text)[0][0] == "updateGlobalData"
        except (ValueError, IndexError, KeyError, TypeError):
            alive = False
        return True if alive else None

    def __sessionExpired(self):
        self.logger.info("__sessionExpired()")
        self.__backoff()

        sessionData = self.getSessionData()

        try:
            if self.s.cookies["PHPSESSID"] != sessionData["cookies"]["PHPSESSID"]:
                self.__getCookie(sessionData)
            else:
                try:
                    self.__login(3)
                except Exception:
                    self.__sessionExpired()
        except KeyError:
            try:
                self.__login(3)
            except Exception:
                self.__sessionExpired()

    def __proxy_error(self):
        sessionData = self.getSessionData()
        if "proxy" not in sessionData or sessionData["proxy"]["set"] is False:
            sys.exit("network error")
        elif self.padre is True:
            print("There seems to be a problem connecting to ikariam.")
            print("Do you want to disable the proxy? [Y/n]")
            rta = read(values=["y", "Y", "n", "N", ""])
            if rta.lower() == "n":
                sys.exit()
            else:
                sessionData["proxy"]["set"] = False
                self.setSessionData(sessionData)
                print("Proxy disabled, try again.")
                enter()
                sys.exit()
        else:
            msg = "Network error. Consider disabling the proxy."
            sendToBot(self, msg)
            sys.exit()

    def __update_proxy(self, *, obj=None, sessionData=None):
        # set the proxy
        if obj is None:
            obj = self.s
        if sessionData is None:
            sessionData = self.getSessionData()
        if "proxy" in sessionData and sessionData["proxy"]["set"] is True:
            obj.proxies.update(sessionData["proxy"]["conf"])
        else:
            # update({}) wouldn't remove an already-set proxy; clear() does.
            obj.proxies.clear()

    def __checkCookie(self):
        self.logger.info("__checkCookie()")
        sessionData = self.getSessionData()

        try:
            stored_ikariam = sessionData["cookies"].get("ikariam")
            imported = getattr(self, "_stored_ikariam", None) != stored_ikariam
            self._stored_ikariam = stored_ikariam
            if imported or self.s.cookies["PHPSESSID"] != sessionData["cookies"]["PHPSESSID"]:
                self.__getCookie(sessionData)
        except KeyError:
            try:
                self.__login(3)
            except Exception:
                self.__sessionExpired()

    def __token(self):
        """Generates a valid actionRequest token from the session, or reuses
        the one already stored for this account/world/server if it has one
        Returns
        -------
        token : str
            a string representing a valid actionRequest token
        """
        sessionData = self.getSessionData()
        token = sessionData.get("actionRequestToken")
        if token:
            return token
        html = self.get()
        if self.__isSessionRotated(html):
            self.__printSessionRotated()
            sys.exit(1)
        match = re.search(r'actionRequest"?:\s*"(.*?)"', html)
        if match is None:
            self.__printSessionRotated()
            sys.exit(1)
        token = match.group(1)
        # self.get() may have logged in again, don't write back the old cookies
        sessionData = self.getSessionData()
        sessionData.pop("shared", None)
        sessionData["actionRequestToken"] = token
        self.setSessionData(sessionData)
        return token

    def get(
        self, url='', params={}, ignoreExpire=False, noIndex=False, fullResponse=False, noQuery=False, **kwargs
    ):
        """Sends get request to ikariam
        Parameters
        ----------
        url : str
            this string will be appended to the end of the urlBase of the Session object. urlBase will look like: 'https://s(number)-(country).ikariam.gameforge.com/index.php?'
        params : dict
            dictionary containing key-value pairs which represent the parameteres of the get request
        ignoreExpire: bool
            if set to True it will ignore if the current session is expired and will simply return whatever response it gets. If it's set to False, it will make sure that the current session is not expired before sending the get request, if it's expired it will login again. If the page only looks expired and the session is not known to be expired, the request is retried once and then IkariamErrorPage is raised
        noIndex : bool
            if set to True it will remove 'index.php' from the end of urlBase before appending url params and sending the get request
        fullResponse : bool
            if set to True it will retrn the full response object instead of the string containing html or json data

        Returns
        -------
        html : str
            response from the server
        """
        self.__checkCookie()
        self.__update_proxy()

        if noIndex:
            url = self.urlBase.replace("index.php", "") + url
        else:
            url = self.urlBase + url
        if noQuery:
            url = url.replace('?','')
        error_page_retried = False
        while True:
            try:
                self.requestHistory.append(
                    {
                        "method": "GET",
                        "url": url,
                        "params": params,
                        "payload": None,
                        "proxies": self.s.proxies,
                        "headers": dict(self.s.headers),
                        "response": None,
                    }
                )
                self.logger.debug(f"About to send: {str(self.requestHistory[-1])}")
                response = self.s.get(
                    url, params=params, verify=config.do_ssl_verify, timeout=300, **kwargs
                )
                self.requestHistory[-1]["response"] = {
                    "status": response.status_code,
                    "elapsed": response.elapsed.total_seconds(),
                    "headers": dict(response.headers),
                    "text": response.text,
                }
                html = response.text

                # modifica redirect 302
                if response.status_code == 302:
                    location = response.headers.get('Location', '')
                    if 'lobby.ikariam.gameforge.com' in location:
                        self.logger.error(f"Redirected to lobby: {location}")
                        self.__printSessionRotated()
                        sys.exit(1)

                # session rotated, redirect followed by requests (final status 200)
                for resp in response.history:
                    if resp is not None and resp.status_code == 302:
                        location = resp.headers.get('Location', '')
                        if 'lobby.ikariam.gameforge.com' in location:
                            self.logger.error(f"Redirected to lobby: {location}")
                            self.__printSessionRotated()
                            sys.exit(1)

                # handle 404 processes
                if response.status_code == 404:
                    # Check if the 404 is coming from the actual Ikariam host
                    if self.host in url:
                        self.logger.error(f"404 Not Found received from Ikariam: {url}")
                        # Only expire session if the main entry point fails
                        if "index.php" in url:
                            self.__printSessionRotated()
                            sys.exit(1)
                    else:
                        # Local Web Server or external 404 should not trigger re-login
                        self.logger.warning(f"Local/External 404 detected at: {url}. Ignoring.")
                        return response if fullResponse else html

                if self.__test_server_maintenace(html):
                    self.logger.warning("Ikariam world backup is in progress, waiting 10 mins.")
                    time.sleep(10 * 60)
                    raise requests.exceptions.ConnectionError  # repeat after 10 minutes
                if ignoreExpire is False and self.__isExpired(html) and self.__isSessionAlive() is not False:
                    if error_page_retried:
                        raise IkariamErrorPage(url)
                    self.logger.warning(f"Ikariam returned an error page, retrying: {url}")
                    error_page_retried = True
                    time.sleep(5)
                    continue
                if ignoreExpire is False:
                    assert self.__isExpired(html) is False
                if self.__isSessionRotated(html, response=response):
                    self.__printSessionRotated()
                    sys.exit(1)
                # --- update developer runtime info ---
                try:
                    self.dev_api_host = self.host
                    self.dev_url_base = self.urlBase
                    cookies = self.s.cookies.get_dict()
                    self.dev_ikariam_cookie = cookies.get("ikariam")
                    self.dev_gf_token = cookies.get("gf-token-production")
                except Exception:
                    pass

                if fullResponse:
                    return response
                else:
                    return html
            except AssertionError:
                self.__sessionExpired()
            except requests.exceptions.ConnectionError:
                self.logger.warning(f"Connection error occured, retrying in {ConnectionError_wait}s\n{str(params) + ' --> ' + url}")
                time.sleep(ConnectionError_wait)
            except requests.exceptions.Timeout:
                self.logger.warning(f"5 minute timeout occured on request, retrying in {ConnectionError_wait}s\n{str(params) + ' --> ' + url}")
                time.sleep(ConnectionError_wait)

    def post(
        self, url='', payloadPost={}, params={}, ignoreExpire=False, noIndex=False, fullResponse = False, noQuery=False, **kwargs
    ):
        """Sends post request to ikariam
        Parameters
        ----------
        url : str
            this string will be appended to the end of the urlBase of the Session object. urlBase will look like: 'https://s(number)-(country).ikariam.gameforge.com/index.php?'
        payloadPost : dict
            dictionary containing key-value pairs which represent the payload of the post request
        params : dict
            dictionary containing key-value pairs which represent the parameteres of the post request
        ignoreExpire: bool
            if set to True it will ignore if the current session is expired and will simply return whatever response it gets. If it's set to False, it will make sure that the current session is not expired before sending the post request, if it's expired it will login again. If the page only looks expired and the session is not known to be expired, IkariamErrorPage is raised without sending the request again
        noIndex : bool
            if set to True it will remove 'index.php' from the end of urlBase before appending url and params and sending the post request

        Returns
        -------
        html : str
            response from the server
        """
        url_original = url
        payloadPost_original = payloadPost
        params_original = params
        self.__checkCookie()
        self.__update_proxy()

        # add the request id
        token = self.__token()
        url = url.replace(actionRequest, token)
        if "actionRequest" in payloadPost:
            payloadPost["actionRequest"] = token
        if "actionRequest" in params:
            params["actionRequest"] = token

        if noIndex:
            url = self.urlBase.replace("index.php", "") + url
        else:
            url = self.urlBase + url
        if noQuery:
            url = url.replace('?','')
        while True:
            try:
                self.requestHistory.append(
                    {
                        "method": "POST",
                        "url": url,
                        "params": params,
                        "payload": payloadPost,
                        "proxies": self.s.proxies,
                        "headers": dict(self.s.headers),
                        "response": None,
                    }
                )
                self.logger.debug(f"About to send: {str(self.requestHistory[-1])}")
                response = self.s.post(
                    url,
                    data=payloadPost,
                    params=params,
                    verify=config.do_ssl_verify,
                    timeout=300,
                    **kwargs,
                )
                self.requestHistory[-1]["response"] = {
                    "status": response.status_code,
                    "elapsed": response.elapsed.total_seconds(),
                    "headers": dict(response.headers),
                    "text": response.text,
                }
                resp = response.text

                #  modifica redirect 302
                if response.status_code == 302:
                    location = response.headers.get('Location', '')
                    if 'lobby.ikariam.gameforge.com' in location:
                        self.logger.error(f"Redirected to lobby: {location}")
                        self.__printSessionRotated()
                        sys.exit(1)

                # session rotated, redirect followed by requests (final status 200)
                for resp_hist in response.history:
                    if resp_hist is not None and resp_hist.status_code == 302:
                        location = resp_hist.headers.get('Location', '')
                        if 'lobby.ikariam.gameforge.com' in location:
                            self.logger.error(f"Redirected to lobby: {location}")
                            self.__printSessionRotated()
                            sys.exit(1)

                # handle 404 processes
                if response.status_code == 404:
                    # If the POST was to Ikariam and failed, it's a session issue
                    if self.host in url:
                        self.logger.error(f"404 Not Found received from Ikariam POST: {url}")
                        self.__printSessionRotated()
                        sys.exit(1)
                    else:
                        # Probably a request to the local web server's invalid route
                        self.logger.warning(f"Local 404 detected on POST: {url}. Ignoring.")
                        return response if fullResponse else resp

                if self.__test_server_maintenace(resp):
                    self.logger.warning("Ikariam world backup is in progress, waiting 10 mins.")
                    time.sleep(10 * 60)
                    raise requests.exceptions.ConnectionError  # repeat after 10 minutes
                if ignoreExpire is False and self.__isExpired(resp) and self.__isSessionAlive() is not False:
                    # not sent again, it may be an action, which may also have used up the token
                    sessionData = self.getSessionData()
                    if sessionData.pop("actionRequestToken", None) is not None:
                        sessionData.pop("shared", None)
                        self.setSessionData(sessionData)
                    raise IkariamErrorPage(url)
                if ignoreExpire is False:
                    assert self.__isExpired(resp) is False
                if self.__isSessionRotated(resp, response=response):
                    self.__printSessionRotated()
                    sys.exit(1)
                if "TXT_ERROR_WRONG_REQUEST_ID" in resp:
                    self.logger.info("got TXT_ERROR_WRONG_REQUEST_ID, bad actionRequest")
                    sessionData = self.getSessionData()
                    if sessionData.pop("actionRequestToken", None) is not None:
                        sessionData.pop("shared", None)
                        self.setSessionData(sessionData)
                    return self.post(
                        url=url_original,
                        payloadPost=payloadPost_original,
                        params=params_original,
                        ignoreExpire=ignoreExpire,
                        noIndex=noIndex,
                        fullResponse=fullResponse,
                        noQuery=noQuery,
                    )
                # --- update developer runtime info ---
                try:
                    self.dev_api_host = self.host
                    self.dev_url_base = self.urlBase
                    cookies = self.s.cookies.get_dict()
                    self.dev_ikariam_cookie = cookies.get("ikariam")
                    self.dev_gf_token = cookies.get("gf-token-production")
                except Exception:
                    pass

                # an action consumes the token and the response carries the next one
                if "action" in payloadPost or "action" in params:
                    new_token = re.search(r'actionRequest"?:\s*"(.*?)"', resp)
                    sessionData = self.getSessionData()
                    if new_token:
                        sessionData.pop("shared", None)
                        sessionData["actionRequestToken"] = new_token.group(1)
                        self.setSessionData(sessionData)
                    elif sessionData.pop("actionRequestToken", None) is not None:
                        sessionData.pop("shared", None)
                        self.setSessionData(sessionData)

                return resp if not fullResponse else response
            except AssertionError:
                self.__sessionExpired()
            except requests.exceptions.ConnectionError:
                self.logger.warning(f"Connection error occured, retrying in {ConnectionError_wait}s\n{str(params) + ' --> ' + url}")
                time.sleep(ConnectionError_wait)
            except requests.exceptions.Timeout:
                self.logger.warning(f"5 minute timeout occured on request, retrying in {ConnectionError_wait}s\n{str(params) + ' --> ' + url}")
                time.sleep(ConnectionError_wait)

    def logout(self):
        """This function kills the current (chlid) process"""
        self.logger.info("logout()")
        if self.padre is False:
            os._exit(0)

    def setSessionData(self, sessionData, shared=False, keep_process_list=True):
        """Writes relevant session data to disk formatted as JSON (indent=2)
        Parameters
        ----------
        sessionData : dict
            dictionary containing relevant session data
        shared : bool
            Indicates if the new data should be shared among all accounts associated with the user-password
        keep_process_list : bool
            If True (default), keeps the process list already stored on disk. Only pass False, inside
            session_data_lock(), to modify the list on purpose (see updateProcessEntry)
        """
        set_session_data(self, sessionData, shared=shared, keep_process_list=keep_process_list)

    def getSessionData(self):
        """Gets fresh session data from disk (hot-reloaded)"""
        return get_session_data(self)

    def deleteSessionData(self):
        """Deletes session data for this user from disk"""
        delete_session_data(self)

    @classmethod
    def from_saved(cls, mail=None, world=None, server=None, player=None):
        """Create an authenticated Session non-interactively using saved credentials/cookies.
        ``player`` (in-game name) picks one account when the lobby has several on the same world."""
        want_player = str(player).strip().lower() if player else None
        if mail and str(mail).strip() and str(mail).strip() != "default_user":
            matching_path, _ = find_user_file_for_email(mail)
            if not matching_path:
                raise ValueError(
                    f"No saved session found for '{mail}'. Please log in interactively first."
                )
            user_data = read_json_file(matching_path, {})
            resolved_mail = user_data.get("email") or str(mail).strip()
        else:
            default_path = get_user_file_path("")
            if os.path.exists(default_path):
                user_data = read_json_file(default_path, {})
                resolved_mail = ""
            else:
                saved_users = get_saved_users()
                if len(saved_users) == 1:
                    resolved_mail = saved_users[0]
                    matching_path, _ = find_user_file_for_email(resolved_mail)
                    user_data = read_json_file(
                        matching_path or get_user_file_path(resolved_mail), {}
                    )
                elif not saved_users:
                    raise ValueError(
                        "No saved accounts found. Please log in interactively first."
                    )
                else:
                    raise ValueError(
                        f"Multiple saved accounts found ({', '.join(saved_users)}); please specify --email."
                    )

        self = cls.__new__(cls)
        self.padre = False
        self.logged = False
        self.blackbox = None
        self.mail = resolved_mail
        self.password = ""
        self.locale = config.IKABOT_LOCALE
        self.gf_lang = config.IKABOT_GF_LANG
        self.accept_language = config.build_accept_language(self.locale, self.gf_lang)
        self.timezone_id = config.IKABOT_TIMEZONE_ID
        self.logger = getLogger(__name__)
        self.requestHistory = deque(maxlen=5)
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

        selected_ua = user_agents[sum(ord(c) for c in self.mail) % len(user_agents)]
        self.api_user_agent = selected_ua
        self.user_agent = selected_ua
        self.s = requests.Session()
        self.cipher = AESCipher(self.mail, self.password)
        self.account = None

        want_mundo, want_servidor, raw_world = parse_world_spec(world, server)

        def _world_headers():
            return {
                "Host": self.host,
                "User-Agent": self.user_agent,
                "Accept": "*/*",
                "Accept-Language": self.accept_language,
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": f"https://{self.host}",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": f"https://{self.host}",
                "DNT": "1",
                "Connection": "keep-alive",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache",
            }

        def _try_world_cookies(cookie_dict, session_data):
            old_s = requests.Session()
            old_s.headers.clear()
            old_s.headers.update(self.headers)
            requests.cookies.cookiejar_from_dict(
                cookie_dict, cookiejar=old_s.cookies, overwrite=True
            )
            self.__update_proxy(obj=old_s, sessionData=session_data)
            try:
                old_resp = old_s.get(self.urlBase, verify=config.do_ssl_verify)
                html = old_resp.text
            except Exception as exc:
                raise RuntimeError(f"Network/proxy error connecting to {self.host}: {exc}")
            if self.__isInVacation(html):
                raise RuntimeError("The account is in vacation mode.")
            if (
                not self.__isExpired(html)
                and not self.__isSessionRotated(html, response=old_resp)
                and old_resp.status_code != 404
            ):
                requests.cookies.cookiejar_from_dict(
                    cookie_dict, cookiejar=self.s.cookies, overwrite=True
                )
                self.__update_proxy(sessionData=session_data)
                self.s.headers.clear()
                self.s.headers.update(self.headers)
                return True
            return False

        def _finalize():
            self.logged = True
            self.dev_api_host = self.host
            self.dev_url_base = self.urlBase
            cookies = self.s.cookies.get_dict()
            self.dev_ikariam_cookie = cookies.get("ikariam")
            self.dev_gf_token = cookies.get("gf-token-production")
            return self

        gf_token = (
            user_data.get("shared", {}).get("lobby", {}).get("gf-token-production")
        )
        lobby_ok = False
        if gf_token:
            cookie_obj = requests.cookies.create_cookie(
                domain=".gameforge.com",
                name="gf-token-production",
                value=gf_token,
            )
            self.s.cookies.set_cookie(cookie_obj)
            try:
                lobby_ok = self.__test_lobby_cookie()
            except Exception:
                lobby_ok = False

        if lobby_ok:
            lobby_headers = {
                "Host": "lobby.ikariam.gameforge.com",
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Accept-Language": self.accept_language,
                "Accept-Encoding": "gzip, deflate",
                "Referer": "https://lobby.ikariam.gameforge.com/{}/hub".format(
                    self.locale.replace("-", "_")
                ),
                "Authorization": f"Bearer {self.s.cookies['gf-token-production']}",
                "DNT": "1",
                "Connection": "close",
            }
            self.s.headers.clear()
            self.s.headers.update(lobby_headers)
            accounts = json.loads(
                self.s.get("https://lobby.ikariam.gameforge.com/api/users/me/accounts").text,
                strict=False,
            )
            servers = json.loads(
                self.s.get("https://lobby.ikariam.gameforge.com/api/servers").text,
                strict=False,
            )
            srv_by_group = {
                srv["accountGroup"]: (srv["name"], srv["language"])
                for srv in servers
                if isinstance(srv, dict) and "accountGroup" in srv
            }
            candidates = []
            for acc in accounts:
                if not isinstance(acc, dict) or acc.get("blocked") is not False:
                    continue
                num = str(acc["server"]["number"])
                login_lang = acc["server"]["language"]
                wname, slang = srv_by_group.get(
                    acc.get("accountGroup"), (f"s{num}", login_lang)
                )
                candidates.append((acc, num, slang, login_lang, wname))

            if not candidates:
                raise ValueError(
                    f"No unblocked game accounts found for '{self.mail or 'default_user'}'."
                )

            avail_str = ", ".join(
                f"s{num}-{slang} ({wname}) - {acc.get('name', '?')}"
                for acc, num, slang, _, wname in candidates
            )
            if want_player:
                candidates = [
                    c
                    for c in candidates
                    if str(c[0].get("name", "")).lower() == want_player
                ]
                if not candidates:
                    raise ValueError(
                        f"Player '{player}' not found on '{self.mail or 'default_user'}'. Available: {avail_str}"
                    )
            if not raw_world:
                matches = [
                    c
                    for c in candidates
                    if want_servidor is None
                    or c[2].lower() == want_servidor
                    or c[3].lower() == want_servidor
                ]
                if len(matches) != 1:
                    raise ValueError(
                        f"Please specify --world and/or --player (available: {avail_str})."
                    )
            else:
                matches = []
                for c in candidates:
                    _, num, slang, login_lang, wname = c
                    if want_mundo is not None:
                        if num == want_mundo and (
                            want_servidor is None
                            or slang.lower() == want_servidor
                            or login_lang.lower() == want_servidor
                        ):
                            matches.append(c)
                    elif wname.strip().lower() == raw_world.strip().lower() and (
                        want_servidor is None
                        or slang.lower() == want_servidor
                        or login_lang.lower() == want_servidor
                    ):
                        matches.append(c)
                if not matches:
                    raise ValueError(
                        f"World '{world}' not found on '{self.mail or 'default_user'}'. Available: {avail_str}"
                    )
                if len(matches) > 1:
                    matched_str = ", ".join(
                        f"s{num}-{slang} - {acc.get('name', '?')}"
                        for acc, num, slang, _, _ in matches
                    )
                    if len({(num, slang.lower()) for _, num, slang, _, _ in matches}) == 1:
                        hint = "specify --player"
                    else:
                        hint = f"specify e.g. --world=s{want_mundo or '<number>'}-<lang>"
                    raise ValueError(
                        f"World '{world}' matches multiple accounts ({matched_str}); {hint}."
                    )

            acc, num, slang, login_lang, wname = matches[0]
            self.account = acc
            self.username = acc["name"]
            self.login_servidor = login_lang
            self.account_group = acc["accountGroup"]
            self.mundo = num
            self.word = wname
            self.servidor = slang
            self.host = f"s{self.mundo}-{self.servidor}.ikariam.gameforge.com"
            self.urlBase = f"https://{self.host}/index.php?"
            self.headers = _world_headers()

            session_data = self.getSessionData()
            if "cookies" in session_data and _try_world_cookies(
                session_data["cookies"], session_data
            ):
                return _finalize()

            blackbox_token = getNewBlackBoxToken(self)
            if self.api_user_agent:
                self.user_agent = self.api_user_agent
            if not (
                any(c.isupper() for c in blackbox_token)
                and any(c.islower() for c in blackbox_token)
                and any(c.isdigit() for c in blackbox_token)
            ):
                raise RuntimeError("Invalid blackbox token returned from API.")
            self.blackbox = blackbox_token

            link_headers = {
                "authority": "lobby.ikariam.gameforge.com",
                "method": "POST",
                "path": "/api/users/me/loginLink",
                "scheme": "https",
                "accept": "application/json",
                "accept-encoding": "gzip, deflate, br",
                "accept-language": self.accept_language,
                "authorization": "Bearer " + self.s.cookies["gf-token-production"],
                "content-type": "application/json",
                "origin": "https://lobby.ikariam.gameforge.com",
                "referer": "https://lobby.ikariam.gameforge.com/{}/accounts".format(
                    self.locale.replace("-", "_")
                ),
                "user-agent": self.user_agent,
            }
            self.s.headers.clear()
            self.s.headers.update(link_headers)
            data = {
                "server": {"language": self.login_servidor, "number": self.mundo},
                "clickedButton": "account_list",
                "id": self.account["id"],
                "blackbox": self.blackbox,
            }
            resp = self.s.post(
                "https://lobby.ikariam.gameforge.com/api/users/me/loginLink", json=data
            )
            resp_json = json.loads(resp.text, strict=False)
            if "url" not in resp_json:
                raise RuntimeError(
                    f"Lobby loginLink failed ({resp.status_code}): {resp.text}"
                )
            url = resp_json["url"]
            if not re.search(
                r"https://s\d+-\w{2}\.ikariam\.gameforge\.com/index\.php\?", url
            ):
                raise RuntimeError(f"Unexpected loginLink URL: {url}")

            self.headers = _world_headers()
            self.s.headers.clear()
            self.s.headers.update(self.headers)
            self.__update_proxy(sessionData=session_data)
            html = self.s.get(url, verify=config.do_ssl_verify).text
            if self.__isInVacation(html):
                raise RuntimeError("The account is in vacation mode.")
            if self.__isExpired(html):
                raise RuntimeError("Game login failed (session immediately expired).")
            self.__saveNewCookies()
            return _finalize()

        # Fallback: lobby token missing/expired — try stored per-world cookies directly
        players = user_data.get("players", {})
        stored_candidates = []
        if isinstance(players, dict):
            for uname, mundos in players.items():
                if not isinstance(mundos, dict):
                    continue
                for mundo_k, srvs in mundos.items():
                    if not isinstance(srvs, dict):
                        continue
                    for srv_k, pdata in srvs.items():
                        if isinstance(pdata, dict) and "cookies" in pdata:
                            stored_candidates.append(
                                (uname, str(mundo_k), str(srv_k), pdata)
                            )

        matched_stored = []
        for item in stored_candidates:
            uname, mundo_k, srv_k, _ = item
            if want_player and str(uname).lower() != want_player:
                continue
            if not raw_world:
                if want_servidor is None or srv_k.lower() == want_servidor:
                    matched_stored.append(item)
            elif want_mundo is not None and mundo_k == want_mundo and (
                want_servidor is None or srv_k.lower() == want_servidor
            ):
                matched_stored.append(item)

        if len(matched_stored) == 1:
            uname, mundo_k, srv_k, pdata = matched_stored[0]
            self.username = uname
            self.mundo = mundo_k
            self.servidor = srv_k
            self.login_servidor = srv_k
            self.account_group = f"{srv_k}_{mundo_k}"
            self.word = f"s{mundo_k}-{srv_k}"
            self.host = f"s{mundo_k}-{srv_k}.ikariam.gameforge.com"
            self.urlBase = f"https://{self.host}/index.php?"
            self.headers = _world_headers()
            session_data = self.getSessionData()
            if _try_world_cookies(pdata["cookies"], session_data):
                return _finalize()

        raise RuntimeError(
            f"Saved session for '{self.mail or 'default_user'}' has expired or has no valid saved cookies for world '{world or ''}'. Please log in interactively first."
        )


def parse_world_spec(world_str, server_str=None):
    """Parse world selector like 's301', '301', 's301-en', 'en-s301', or 'Alpha'.
    Returns (mundo: str | None, servidor: str | None, raw_world: str).
    """
    explicit_srv = str(server_str).strip().lower() if server_str else None
    if world_str is None or str(world_str).strip() == "":
        return None, explicit_srv, ""
    raw = str(world_str).strip()
    low = raw.lower()
    m = re.match(r"^s?(\d+)[-_.](\w{2,4})(?:\.ikariam\.gameforge\.com)?$", low)
    if m:
        return m.group(1), explicit_srv or m.group(2), raw
    m = re.match(r"^([a-z]{2,4})[-_.]?s?(\d+)$", low)
    if m and m.group(1) != "s":
        return m.group(2), explicit_srv or m.group(1), raw
    m = re.match(r"^s?(\d+)$", low)
    if m:
        return m.group(1), explicit_srv, raw
    return None, explicit_srv, raw


def normal_get(url, params={}):
    """Sends a get request to provided url
    Parameters
    ----------
    url : str
        a string representing the url to which to send the get request
    params : dict
        a dictionary containing key-value pairs which represent the parameters of the get request

    Returns
    -------
    response : requests.Response
        a requests.Response object which represents the webservers response. For more information on requests.Response refer to https://requests.readthedocs.io/en/master/api/#requests.Response
    """
    try:

        return requests.get(url, params=params)

    except requests.exceptions.ConnectionError:
        sys.exit("Internet connection failed")
