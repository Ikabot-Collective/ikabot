import collections
import json
import logging
import os
import sys
import unittest
from unittest import mock

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.web import session as session_module
from ikabot.web.session import Session

BASE = "https://s1-en.ikariam.gameforge.com/index.php?"
GAME_PAGE = '<html>... actionRequest: "0123456789abcdef0123456789abcdef" ...</html>'
ERROR_PAGE = (
    '<html><a class="logout" href="https://lobby.ikariam.gameforge.com/en_GB" id="logoimg"></a>'
    '<p>There was an error loading your island empire. Please try again.</p>'
    '<a class="btn logout returnToStartPage" href="https://lobby.ikariam.gameforge.com/en_GB">Lobby</a></html>'
)
ALIVE = '[["updateGlobalData",{"headerData":{}}],["popupData",null]]'
RELOAD = '[["custom",["reload",{"link":"https:\\/\\/lobby.ikariam.gameforge.com\\/en_GB","isDevHost":0}]]]'
LOBBY = "https://lobby.ikariam.gameforge.com/en_GB"


def response(body, status=200, location=None):
    r = requests.models.Response()
    r.status_code = status
    r._content = body.encode()
    r.encoding = "utf-8"
    r.url = BASE
    if location:
        r.headers["Location"] = location
    return r


class ScriptedHttp(requests.Session):
    """Answers each request with the next scripted response"""

    def __init__(self, script):
        super().__init__()
        self.script = collections.deque(script)
        self.urls = []
        self.cookies.set("PHPSESSID", "old")

    def _next(self, url, params):
        self.urls.append(url + "&".join(f"{k}={v}" for k, v in (params or {}).items()))
        item = self.script.popleft()
        if isinstance(item, Exception):
            raise item
        return item

    def get(self, url, params=None, **kwargs):
        return self._next(url, params)

    def post(self, url, data=None, params=None, **kwargs):
        return self._next(url, params)


class TestFalseSessionExpiry(unittest.TestCase):
    """A page that looks expired only causes a new login if the session is really expired"""

    def setUp(self):
        sleep = mock.patch.object(session_module.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)

    def make_session(self, script, stored=None):
        session = object.__new__(Session)
        logger = logging.getLogger("test_session_expiry")
        logger.propagate = False
        session.logger = logger
        session.urlBase = BASE
        session.host = "s1-en.ikariam.gameforge.com"
        session.padre = False
        session.requestHistory = collections.deque(maxlen=5)
        session.s = ScriptedHttp(script)
        session.stored = stored or {"cookies": {"PHPSESSID": "old"}, "actionRequestToken": "storedtoken"}
        session.getSessionData = lambda: json.loads(json.dumps(session.stored))

        def set_session_data(data, shared=False):
            session.stored = json.loads(json.dumps(data))

        session.setSessionData = set_session_data
        session.relogins = 0

        def session_expired():
            # what a new login does
            session.relogins += 1
            session.stored["cookies"]["PHPSESSID"] = "new"
            session.s.cookies.set("PHPSESSID", "new")

        session._Session__sessionExpired = session_expired
        return session

    def test_normal_page_sends_no_extra_request(self):
        session = self.make_session([response(GAME_PAGE)])
        self.assertEqual(session.get(), GAME_PAGE)
        self.assertEqual(len(session.s.urls), 1)

    def test_error_page_with_valid_session_is_retried_without_login(self):
        session = self.make_session([response(ERROR_PAGE), response(ALIVE), response(GAME_PAGE)])
        self.assertEqual(session.get(), GAME_PAGE)
        self.assertEqual(session.relogins, 0)
        self.assertIn("view=updateGlobalData&ajax=1", session.s.urls[1])

    def test_repeated_error_page_with_valid_session_raises_without_login(self):
        session = self.make_session(
            [response(ERROR_PAGE), response(ALIVE), response(ERROR_PAGE), response(ALIVE)]
        )
        with self.assertRaises(Exception):
            session.get()
        self.assertEqual(session.relogins, 0)

    def test_expired_session_answered_with_reload_logs_in_again(self):
        session = self.make_session([response(ERROR_PAGE), response(RELOAD), response(GAME_PAGE)])
        self.assertEqual(session.get(), GAME_PAGE)
        self.assertEqual(session.relogins, 1)

    def test_expired_session_answered_with_redirect_logs_in_again(self):
        session = self.make_session(
            [response(ERROR_PAGE), response("", 302, LOBBY), response(GAME_PAGE)]
        )
        session.get()
        self.assertEqual(session.relogins, 1)

    def test_logout_page_logs_in_again(self):
        page = '<html><a href="index.php?logout">logout</a></html>'
        session = self.make_session([response(page), response(page), response(GAME_PAGE)])
        session.get()
        self.assertEqual(session.relogins, 1)

    def test_network_error_while_checking_logs_in_again(self):
        session = self.make_session(
            [response(ERROR_PAGE), requests.exceptions.ConnectionError(), response(GAME_PAGE)]
        )
        session.get()
        self.assertEqual(session.relogins, 1)

    def test_ignore_expire_sends_no_extra_request(self):
        session = self.make_session([response(ERROR_PAGE)])
        self.assertEqual(session.get(ignoreExpire=True), ERROR_PAGE)
        self.assertEqual(len(session.s.urls), 1)

    def test_post_error_page_with_valid_session_is_not_sent_again(self):
        session = self.make_session([response(ERROR_PAGE), response(ALIVE)])
        with self.assertRaises(Exception):
            session.post("action=Something&function=do")
        self.assertEqual(session.relogins, 0)
        self.assertEqual(len(session.s.urls), 2)

    def test_post_expired_session_logs_in_again(self):
        session = self.make_session([response(ERROR_PAGE), response(RELOAD), response(GAME_PAGE)])
        session.post("view=something")
        self.assertEqual(session.relogins, 1)

    def test_reload_to_lobby_is_detected_as_session_rotated(self):
        session = self.make_session([])
        self.assertTrue(session._Session__isSessionRotated(RELOAD))
        self.assertTrue(session._Session__isSessionRotated(RELOAD.replace("\\/", "/")))
        self.assertFalse(session._Session__isSessionRotated(ALIVE))
        self.assertFalse(session._Session__isSessionRotated(GAME_PAGE))

    def test_new_token_does_not_restore_the_old_cookies(self):
        session = self.make_session(
            [response(ERROR_PAGE), response(RELOAD), response(GAME_PAGE)],
            stored={"cookies": {"PHPSESSID": "old"}},
        )
        token = session._Session__token()
        self.assertEqual(token, "0123456789abcdef0123456789abcdef")
        self.assertEqual(session.stored["cookies"]["PHPSESSID"], "new")
        self.assertEqual(session.stored["actionRequestToken"], token)


if __name__ == "__main__":
    unittest.main()
