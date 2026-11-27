import unittest
from unittest.mock import patch
from types import SimpleNamespace
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.function.webServer import derived_port, get_env_port


@patch('ikabot.function.webServer.print')
@patch('ikabot.function.webServer.is_port_in_use', return_value=False)
class TestGetEnvPort(unittest.TestCase):
    """Test the web server port set with IKABOT_WEB_PORT"""

    @patch('ikabot.config.IKABOT_WEB_PORT', '1995')
    def test_a_valid_port_is_used(self, mock_in_use, mock_print):
        """A valid port is returned"""
        self.assertEqual(get_env_port(), '1995')
        mock_print.assert_not_called()

    @patch('ikabot.config.IKABOT_WEB_PORT', '01995')
    def test_leading_zeros_are_dropped(self, mock_in_use, mock_print):
        """The port is returned without leading zeros"""
        self.assertEqual(get_env_port(), '1995')

    @patch('ikabot.config.IKABOT_WEB_PORT', 'abc')
    def test_text_is_not_a_port(self, mock_in_use, mock_print):
        """A value that is not a number is ignored with a warning"""
        self.assertIsNone(get_env_port())
        self.assertIn('not a valid port', mock_print.call_args[0][0])

    @patch('ikabot.config.IKABOT_WEB_PORT', '0')
    def test_zero_is_not_a_port(self, mock_in_use, mock_print):
        """Port 0 is ignored"""
        self.assertIsNone(get_env_port())

    @patch('ikabot.config.IKABOT_WEB_PORT', '70000')
    def test_a_port_above_the_range_is_ignored(self, mock_in_use, mock_print):
        """A port above 65535 is ignored"""
        self.assertIsNone(get_env_port())

    @patch('ikabot.config.IKABOT_WEB_PORT', '1995')
    def test_a_busy_port_is_ignored(self, mock_in_use, mock_print):
        """A port already in use is ignored with a warning"""
        mock_in_use.return_value = True
        self.assertIsNone(get_env_port())
        self.assertIn('already in use', mock_print.call_args[0][0])


class TestDerivedPort(unittest.TestCase):
    """Test the web server port derived from the account"""

    session = SimpleNamespace(mail='player@example.com', host='s1-en.ikariam.gameforge.com', username='player')

    @patch('ikabot.function.webServer.is_port_in_use', return_value=False)
    def test_the_same_account_gets_the_same_port(self, mock_in_use):
        """The port depends only on the account and stays in the 43000-44999 range"""
        port = derived_port(self.session)
        self.assertEqual(port, derived_port(self.session))
        self.assertTrue(43000 <= int(port) < 45000)

    def test_a_busy_port_moves_to_the_next_one(self):
        """When the port is in use, the next free one is returned"""
        with patch('ikabot.function.webServer.is_port_in_use', return_value=False):
            first = int(derived_port(self.session))
        with patch('ikabot.function.webServer.is_port_in_use', side_effect=[True, True, False]):
            self.assertEqual(int(derived_port(self.session)), first + 2)


if __name__ == '__main__':
    unittest.main()
