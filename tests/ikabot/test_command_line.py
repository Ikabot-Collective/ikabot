import unittest
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from ikabot.command_line import _menu_once


class TestMenuOnce(unittest.TestCase):
    """Test that the main menu handles every kind of input without crashing"""

    def setUp(self):
        self.session = Mock()

    def _run(self, inputs):
        """Run _menu_once with the given sequence of read() return values.
        Returns the multiprocessing.Process mock so callers can assert on it."""
        with patch('ikabot.command_line.updateProcessList', return_value=[]), \
             patch('ikabot.command_line.read', side_effect=inputs), \
             patch('ikabot.command_line.enter'), \
             patch('ikabot.command_line.banner'), \
             patch('ikabot.command_line.telegramDataIsValid', return_value=True), \
             patch('ikabot.command_line.print'), \
             patch('ikabot.command_line.multiprocessing') as mp:
            _menu_once(self.session)
            return mp

    def test_invalid_option_does_not_crash(self):
        """Unmapped numbers (e.g. 25 used to raise KeyError) must return cleanly"""
        # menu_actions has no key 25; read(max=24) blocks it now, but even a
        # future regression in read() must not spawn a process or raise
        for invalid in [25, 30, 42]:
            mp = self._run([invalid])
            mp.Process.assert_not_called()

    def test_empty_input_returns_to_menu(self):
        mp = self._run([''])
        mp.Process.assert_not_called()

    def test_submenu_back_returns_to_menu(self):
        # 7 = Alerts submenu, 0 = Back
        mp = self._run([7, 0])
        mp.Process.assert_not_called()

    def test_valid_option_spawns_process(self):
        # 4 = Account status (getStatus)
        with patch('ikabot.command_line.updateProcessList', return_value=[]), \
             patch('ikabot.command_line.read', side_effect=[4]), \
             patch('ikabot.command_line.enter'), \
             patch('ikabot.command_line.print'), \
             patch('ikabot.command_line.multiprocessing') as mp, \
             patch('ikabot.command_line.sys') as mock_sys:
            mock_sys.stdin.fileno.return_value = 0
            _menu_once(self.session)
            mp.Process.assert_called_once()
            self.assertEqual(mp.Process.call_args.kwargs['target'].__name__, 'getStatus')

    def test_submenu_option_spawns_remapped_process(self):
        # 7 = Alerts submenu, 1 = Alert attacks -> 701
        with patch('ikabot.command_line.updateProcessList', return_value=[]), \
             patch('ikabot.command_line.read', side_effect=[7, 1]), \
             patch('ikabot.command_line.enter'), \
             patch('ikabot.command_line.print'), \
             patch('ikabot.command_line.multiprocessing') as mp, \
             patch('ikabot.command_line.sys') as mock_sys:
            mock_sys.stdin.fileno.return_value = 0
            _menu_once(self.session)
            mp.Process.assert_called_once()
            self.assertEqual(mp.Process.call_args.kwargs['target'].__name__, 'alertAttacks')

    def test_exit_option_calls_exit(self):
        with patch('ikabot.command_line.updateProcessList', return_value=[]), \
             patch('ikabot.command_line.read', side_effect=[0]), \
             patch('ikabot.command_line.enter'), \
             patch('ikabot.command_line.clear'), \
             patch('ikabot.command_line.print'), \
             patch('ikabot.command_line.os._exit') as mock_exit:
            _menu_once(self.session)
            mock_exit.assert_called_once_with(0)


if __name__ == '__main__':
    unittest.main()
