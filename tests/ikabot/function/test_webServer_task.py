import importlib.util
import socket
import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.webServer import _port_is_taken, do_webServer


class TestWebServerPortCheck(unittest.TestCase):
    def setUp(self):
        # a listening socket stands in for a web server already running on the port
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]

    def tearDown(self):
        self.listener.close()

    def test_port_is_taken(self):
        self.assertTrue(_port_is_taken(self.port))
        self.listener.close()
        self.assertFalse(_port_is_taken(self.port))

    @unittest.skipIf(importlib.util.find_spec("flask") is None, "flask not installed")
    @patch("ikabot.function.webServer.sendToBot")
    def test_task_does_not_start_on_busy_port(self, mock_send):
        session = MagicMock()
        with patch("flask.Flask") as mock_flask, self.assertLogs("ikabot.function.webServer", "ERROR") as logs:
            do_webServer.__wrapped__(session, str(self.port), None)
        mock_flask.assert_not_called()
        self.assertIn("already in use", logs.output[0])
        mock_send.assert_called_once()
        self.assertIn("already in use", mock_send.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
