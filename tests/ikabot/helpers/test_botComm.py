import unittest
from unittest.mock import Mock, patch
import sys
import os

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.helpers import botComm


def _session_with_telegram():
    session = Mock()
    session.getSessionData.return_value = {
        "shared": {"telegram": {"botToken": "token123", "chatId": "42"}}
    }
    session.servidor = "en"
    session.word = "Alpha"
    session.username = "player"
    return session


class TestSendToBot(unittest.TestCase):

    @patch('ikabot.helpers.botComm.checkTelegramData', return_value=True)
    @patch('ikabot.helpers.botComm.get')
    def test_timeout_does_not_raise(self, mock_get, _):
        """A Telegram outage must not kill the calling task"""
        mock_get.side_effect = requests.exceptions.Timeout()
        result = botComm.sendToBot(_session_with_telegram(), "hello")
        self.assertIsNone(result)

    @patch('ikabot.helpers.botComm.checkTelegramData', return_value=True)
    @patch('ikabot.helpers.botComm.get')
    def test_connection_error_does_not_raise(self, mock_get, _):
        mock_get.side_effect = requests.exceptions.ConnectionError()
        result = botComm.sendToBot(_session_with_telegram(), "hello")
        self.assertIsNone(result)

    @patch('ikabot.helpers.botComm.checkTelegramData', return_value=True)
    @patch('ikabot.helpers.botComm.get')
    def test_success_passes_timeout(self, mock_get, _):
        botComm.sendToBot(_session_with_telegram(), "hello")
        self.assertEqual(
            mock_get.call_args.kwargs['timeout'], botComm.TELEGRAM_REQUEST_TIMEOUT
        )

    @patch('ikabot.helpers.botComm.checkTelegramData', return_value=True)
    def test_photo_failure_restores_headers(self, _):
        """Header restore must happen even if the photo upload raises"""
        session = _session_with_telegram()
        session.s.headers = {"X-Test": "1"}
        session.s.post.side_effect = requests.exceptions.Timeout()
        result = botComm.sendToBot(session, "caption", Photo=b"png-bytes")
        self.assertIsNone(result)
        self.assertEqual(session.s.headers, {"X-Test": "1"})


class TestSendToBotDeduplicated(unittest.TestCase):

    def setUp(self):
        botComm._last_deduplicated_messages.clear()
        self.session = _session_with_telegram()

    @patch('ikabot.helpers.botComm.sendToBot')
    def test_identical_messages_suppressed(self, mock_send):
        self.assertTrue(botComm.sendToBotDeduplicated(self.session, "err", key="k"))
        self.assertFalse(botComm.sendToBotDeduplicated(self.session, "err", key="k"))
        self.assertEqual(mock_send.call_count, 1)

    @patch('ikabot.helpers.botComm.sendToBot')
    def test_different_messages_sent(self, mock_send):
        botComm.sendToBotDeduplicated(self.session, "err1", key="k")
        botComm.sendToBotDeduplicated(self.session, "err2", key="k")
        self.assertEqual(mock_send.call_count, 2)

    @patch('ikabot.helpers.botComm.sendToBot')
    def test_different_keys_do_not_interfere(self, mock_send):
        botComm.sendToBotDeduplicated(self.session, "err", key="a")
        self.assertTrue(botComm.sendToBotDeduplicated(self.session, "err", key="b"))

    @patch('ikabot.helpers.botComm.sendToBot')
    def test_clear_rearms_alert(self, mock_send):
        botComm.sendToBotDeduplicated(self.session, "err", key="k")
        botComm.clearDeduplicatedMessage(key="k")
        self.assertTrue(botComm.sendToBotDeduplicated(self.session, "err", key="k"))
        self.assertEqual(mock_send.call_count, 2)


class TestGetUserResponse(unittest.TestCase):

    @patch('ikabot.helpers.botComm.checkTelegramData', return_value=True)
    @patch('ikabot.helpers.botComm.get')
    def test_network_error_returns_empty_list(self, mock_get, _):
        mock_get.side_effect = requests.exceptions.ConnectionError()
        result = botComm.getUserResponse(_session_with_telegram())
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
