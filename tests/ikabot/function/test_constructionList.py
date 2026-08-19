import unittest

from ikabot.function.constructionList import _parseConstructionTime


class TestParseConstructionTime(unittest.TestCase):
    def test_parses_time_cell(self):
        row = '<td class="level">2</td><td class="costs">100</td><td class="costs"><span title="1D 2H 3M 4S">1D 2H</span></td>'

        self.assertEqual(_parseConstructionTime(row), 93784)

    def test_prefers_seconds_attribute(self):
        row = '<td class="level">2</td><td class="costs"><span data-duration="1234">20M</span></td>'

        self.assertEqual(_parseConstructionTime(row), 1234)
