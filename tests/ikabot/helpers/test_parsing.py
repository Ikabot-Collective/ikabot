import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.helpers.parsing import ParseError, search_or_raise
from ikabot.helpers.getJson import getCity, getIsland


class TestSearchOrRaise(unittest.TestCase):

    def test_match_returned(self):
        match = search_or_raise(r"currentCityId:\s(\d+),", "currentCityId: 42,", "city id")
        self.assertEqual(match.group(1), "42")

    def test_no_match_raises_parse_error(self):
        with self.assertRaises(ParseError) as ctx:
            search_or_raise(r"currentCityId:\s(\d+),", "<html>503 error</html>", "city id")
        self.assertIn("city id", str(ctx.exception))
        self.assertIn("503 error", str(ctx.exception))

    def test_snippet_is_truncated(self):
        with self.assertRaises(ParseError) as ctx:
            search_or_raise(r"never-matches", "x" * 10000, "something")
        self.assertLess(len(str(ctx.exception)), 1000)


class TestParsersRaiseParseError(unittest.TestCase):
    """Unexpected pages used to kill tasks with
    "'NoneType' object has no attribute 'group'" """

    def test_get_city_with_error_page(self):
        with self.assertRaises(ParseError):
            getCity("<html>maintenance</html>")

    def test_get_island_with_error_page(self):
        with self.assertRaises(ParseError):
            getIsland("<html>maintenance</html>")


if __name__ == '__main__':
    unittest.main()
