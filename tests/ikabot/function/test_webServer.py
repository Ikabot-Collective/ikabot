import unittest
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.function.webServer import ask_for_port


class TestAskForPort(unittest.TestCase):
    """Test the custom port prompt of the web server"""

    @patch('ikabot.function.webServer.print')
    @patch('ikabot.function.webServer.is_port_in_use', return_value=False)
    @patch('ikabot.function.webServer.read', return_value=1995)
    def test_a_free_port_is_used(self, mock_read, mock_in_use, mock_print):
        """A free port is returned as it was typed"""
        self.assertEqual(ask_for_port(), '1995')

    @patch('ikabot.function.webServer.print')
    @patch('ikabot.function.webServer.is_port_in_use', side_effect=[True, False])
    @patch('ikabot.function.webServer.read', side_effect=[1995, 1996])
    def test_a_busy_port_asks_again(self, mock_read, mock_in_use, mock_print):
        """A busy port asks for another one instead of hanging"""
        self.assertEqual(ask_for_port(), '1996')
        self.assertEqual(mock_read.call_count, 2)

    @patch('ikabot.function.webServer.print')
    @patch('ikabot.function.webServer.read', return_value='')
    def test_an_empty_answer_keeps_the_default_port(self, mock_read, mock_print):
        """An empty answer leaves the port to be derived from the account"""
        self.assertIsNone(ask_for_port())

    @patch('ikabot.function.webServer.print')
    @patch('ikabot.function.webServer.read', return_value=0)
    def test_zero_keeps_the_default_port(self, mock_read, mock_print):
        """Answering 0 leaves the port to be derived from the account"""
        self.assertIsNone(ask_for_port())


if __name__ == '__main__':
    unittest.main()
