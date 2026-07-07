import unittest
from unittest.mock import Mock
import sys
import os

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.web.session import Session


def _make_session(own_php_sessid=None):
    """Builds a Session without running __init__ (no real login)."""
    session = object.__new__(Session)
    session.logger = Mock()
    session.s = requests.Session()
    if own_php_sessid is not None:
        session.s.cookies.set("PHPSESSID", own_php_sessid)
    return session


def _differs(session, session_data):
    return session._Session__fileCookiesDiffer(session_data)


class TestFileCookiesDiffer(unittest.TestCase):
    """Decides whether to adopt cookies refreshed by another process (True)
    or to perform a full re-login (False)."""

    def test_same_cookie_means_relogin(self):
        session = _make_session("abc")
        self.assertFalse(_differs(session, {"cookies": {"PHPSESSID": "abc"}}))

    def test_different_cookie_means_adopt(self):
        session = _make_session("abc")
        self.assertTrue(_differs(session, {"cookies": {"PHPSESSID": "xyz"}}))

    def test_no_own_cookie_but_file_has_cookies_means_adopt(self):
        session = _make_session()
        self.assertTrue(_differs(session, {"cookies": {"PHPSESSID": "xyz"}}))

    def test_no_file_cookies_means_relogin(self):
        session = _make_session("abc")
        self.assertFalse(_differs(session, {}))

    def test_nothing_anywhere_means_relogin(self):
        session = _make_session()
        self.assertFalse(_differs(session, {}))


if __name__ == '__main__':
    unittest.main()
