import importlib.util
import os
import socket
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.webServer import do_webServer, prepare_webServer, resolve_task_port
from ikabot.helpers.decorators import _TASK_REGISTRY

needs_flask = unittest.skipIf(importlib.util.find_spec("flask") is None, "flask not installed")


class TestResolveTaskPort(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()

    @patch("ikabot.config.IKABOT_WEB_PORT", "")
    @patch("ikabot.function.webServer.derived_port", return_value="43123")
    def test_no_port_uses_the_derived_port(self, _mock_derived):
        self.assertEqual(resolve_task_port(self.session, None), "43123")

    @patch("ikabot.config.IKABOT_WEB_PORT", "1995")
    @patch("ikabot.function.webServer.get_env_port", return_value="1995")
    def test_no_port_uses_ikabot_web_port(self, _mock_env):
        self.assertEqual(resolve_task_port(self.session, None), "1995")

    @patch("ikabot.config.IKABOT_WEB_PORT", "1995")
    @patch("ikabot.function.webServer.derived_port", return_value="43123")
    @patch("ikabot.function.webServer.get_env_port", return_value=None)
    def test_a_busy_ikabot_web_port_falls_back_to_the_derived_port(self, _mock_env, _mock_derived):
        self.assertEqual(resolve_task_port(self.session, None), "43123")

    @patch("ikabot.config.IKABOT_WEB_PORT", "ask")
    @patch("ikabot.function.webServer.derived_port", return_value="43123")
    def test_ask_cannot_prompt_in_a_task(self, _mock_derived):
        self.assertEqual(resolve_task_port(self.session, ""), "43123")

    def test_a_given_port_is_normalized(self):
        self.assertEqual(resolve_task_port(self.session, 8080), "8080")
        self.assertEqual(resolve_task_port(self.session, " 08080 "), "8080")

    def test_an_invalid_port_is_rejected(self):
        for port in ("abc", 0, "70000", -5):
            self.assertIsNone(resolve_task_port(self.session, port))


@needs_flask
class TestPrepareWebServer(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()

    def test_is_registered_for_the_cli(self):
        self.assertIs(_TASK_REGISTRY["webServer"].prepare, prepare_webServer)

    @patch("ikabot.function.webServer.get_local_network_ip", return_value="10.0.0.5")
    @patch("ikabot.function.webServer.is_port_in_use", return_value=False)
    @patch("ikabot.function.webServer.derived_port", return_value="43123")
    @patch("ikabot.config.IKABOT_WEB_PORT", "")
    def test_fills_in_the_port_and_the_ip(self, _mock_derived, _mock_in_use, _mock_ip):
        self.assertEqual(
            prepare_webServer(self.session),
            {"port": "43123", "local_network_ip": "10.0.0.5"},
        )

    @patch("ikabot.function.webServer.is_port_in_use", return_value=False)
    def test_keeps_a_given_ip(self, _mock_in_use):
        self.assertEqual(
            prepare_webServer(self.session, port=8090, local_network_ip="192.168.0.2"),
            {"port": "8090", "local_network_ip": "192.168.0.2"},
        )

    def test_rejects_an_invalid_port(self):
        with self.assertRaisesRegex(ValueError, "'abc' is not a valid port"):
            prepare_webServer(self.session, port="abc")

    @patch("ikabot.function.webServer.is_port_in_use", return_value=True)
    def test_rejects_a_busy_port(self, _mock_in_use):
        with self.assertRaisesRegex(ValueError, "port 8080 is already in use"):
            prepare_webServer(self.session, port=8080)

    @patch("ikabot.function.webServer.importlib.util.find_spec", return_value=None)
    def test_rejects_a_missing_flask(self, _mock_spec):
        with self.assertRaisesRegex(ValueError, "flask is not installed"):
            prepare_webServer(self.session, port=8080)


@needs_flask
@patch("ikabot.function.webServer.sendToBot")
class TestWebServerTask(unittest.TestCase):
    def setUp(self):
        # a listening socket stands in for a web server already running on the port
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.session = MagicMock()

    def tearDown(self):
        self.listener.close()

    def run_task(self, **config):
        with patch("flask.Flask") as mock_flask, self.assertLogs("ikabot.function.webServer", "ERROR") as logs:
            do_webServer.__wrapped__(self.session, **config)
        mock_flask.assert_not_called()
        return logs.output[0]

    def test_a_busy_port_is_refused(self, mock_send):
        self.assertIn("already in use", self.run_task(port=str(self.port)))
        self.assertIn("already in use", mock_send.call_args.args[1])

    def test_an_invalid_port_is_refused(self, mock_send):
        self.assertIn("'abc' is not a valid port", self.run_task(port="abc"))
        mock_send.assert_called_once()

    @patch("ikabot.function.webServer.threading.Thread")
    @patch("ikabot.function.webServer.is_port_in_use", return_value=False)
    @patch("ikabot.function.webServer.get_local_network_ip", return_value="10.0.0.5")
    def test_starts_with_a_numeric_port_and_no_ip(self, _mock_ip, _mock_in_use, _mock_thread, mock_send):
        with tempfile.TemporaryDirectory() as tmp, \
                patch("ikabot.function.webServer.web_cache_file", os.path.join(tmp, "webcache")), \
                patch("flask.Flask") as mock_flask:
            do_webServer.__wrapped__(self.session, port=8080)
        mock_flask.return_value.run.assert_called_once_with(
            host="0.0.0.0", port=8080, threaded=True, use_reloader=False
        )
        status = self.session.setStatus.call_args.args[0]
        self.assertIn("http://127.0.0.1:8080", status)
        self.assertIn("http://10.0.0.5:8080", status)
        mock_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
