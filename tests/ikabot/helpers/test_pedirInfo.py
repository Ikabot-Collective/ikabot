import unittest
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot import config
from ikabot.helpers.pedirInfo import read


class TestRead(unittest.TestCase):

    def setUp(self):
        config.predetermined_input = []

    @patch('builtins.print')
    @patch('builtins.input', return_value='5')
    def test_valid_digit_input(self, mock_input, _):
        self.assertEqual(read(min=0, max=10), 5)

    @patch('builtins.print')
    @patch('builtins.input', side_effect=EOFError())
    def test_closed_stdin_raises_runtime_error(self, mock_input, _):
        """Closed stdin used to make read() return None after 20 retries,
        crashing callers with cryptic TypeErrors later on"""
        with self.assertRaises(RuntimeError):
            read(digit=True)

    @patch('builtins.print')
    @patch('builtins.input', return_value='not-a-number')
    def test_persistent_invalid_input_raises_runtime_error(self, mock_input, _):
        with self.assertRaises(RuntimeError):
            read(digit=True)

    @patch('builtins.print')
    def test_min_greater_than_max_raises_value_error(self, _):
        with self.assertRaises(ValueError):
            read(min=10, max=5)

    @patch('builtins.print')
    @patch('builtins.input')
    def test_predetermined_input_is_used(self, mock_input, _):
        config.predetermined_input = [7]
        self.assertEqual(read(min=0, max=10), 7)
        mock_input.assert_not_called()


if __name__ == '__main__':
    unittest.main()
