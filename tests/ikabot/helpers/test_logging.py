import unittest
import logging
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.helpers.logging import (
    PLAYER_ENV_VAR,
    PlayerNameFilter,
    UNKNOWN_PLAYER,
    setLoggedInPlayer,
)


class TestPlayerNameFilter(unittest.TestCase):
    """Test that the player name is added to every log record"""

    def setUp(self):
        """Set up test fixtures"""
        os.environ.pop(PLAYER_ENV_VAR, None)
        self.filter = PlayerNameFilter()
        self.record = logging.LogRecord(
            name='ikabot.test',
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg='something broke',
            args=None,
            exc_info=None,
        )

    def tearDown(self):
        """Leave the environment as the tests found it"""
        os.environ.pop(PLAYER_ENV_VAR, None)

    def test_player_is_unknown_before_login(self):
        """Records written before the login are marked as unknown"""
        self.filter.filter(self.record)

        self.assertEqual(self.record.player, UNKNOWN_PLAYER)

    def test_player_is_added_after_login(self):
        """Once the player is set, it is added to the record"""
        setLoggedInPlayer('Herakles69')

        self.filter.filter(self.record)

        self.assertEqual(self.record.player, 'Herakles69')

    def test_filter_never_drops_records(self):
        """The filter only adds information, it must not filter anything out"""
        self.assertTrue(self.filter.filter(self.record))

    def test_empty_player_falls_back_to_unknown(self):
        """An empty or missing name must not leave the field blank"""
        setLoggedInPlayer('Herakles69')
        setLoggedInPlayer(None)

        self.filter.filter(self.record)

        self.assertEqual(self.record.player, UNKNOWN_PLAYER)

    def test_name_is_published_to_the_environment(self):
        """Background tasks are spawned, so they only inherit the name through the
        environment"""
        setLoggedInPlayer('Herakles69')

        self.assertEqual(os.environ[PLAYER_ENV_VAR], 'Herakles69')

    def test_name_is_read_from_the_environment(self):
        """A spawned task picks up the name set by the parent before it started"""
        os.environ[PLAYER_ENV_VAR] = 'InheritedName'

        self.filter.filter(self.record)

        self.assertEqual(self.record.player, 'InheritedName')

    def test_record_is_formatted_with_the_player_name(self):
        """The name shows up in the formatted line"""
        setLoggedInPlayer('Herakles69')
        formatter = logging.Formatter(
            '%(asctime)s - %(player)s - %(name)s - %(levelname)s - %(message)s'
        )

        self.filter.filter(self.record)
        line = formatter.format(self.record)

        self.assertIn(' - Herakles69 - ikabot.test - ERROR - something broke', line)


if __name__ == '__main__':
    unittest.main()
