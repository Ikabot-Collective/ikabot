import unittest
import json
from unittest.mock import Mock

from ikabot.function.constructionList import (
    _getFreeSpeedupParams,
    _parseConstructionTime,
    tryFreeBuildingSpeedup,
)


class TestParseConstructionTime(unittest.TestCase):
    def test_parses_time_cell(self):
        row = '<td class="level">2</td><td class="costs">100</td><td class="costs"><span title="1D 2H 3M 4S">1D 2H</span></td>'

        self.assertEqual(_parseConstructionTime(row), 93784)

    def test_prefers_seconds_attribute(self):
        row = '<td class="level">2</td><td class="costs"><span data-duration="1234">20M</span></td>'

        self.assertEqual(_parseConstructionTime(row), 1234)


class TestFreeBuildingSpeedup(unittest.TestCase):
    def _response(self, cost):
        popup = '''<a class="button" id="js_buildingSpeedupActivateBtn"
            href="?action=Premium&amp;function=buildingSpeedup&amp;cityId=14075&amp;position=10&amp;level=3&amp;backgroundView=city&amp;currentCityId=14075&amp;actionRequest=old">
            Activate (<span title="Ambrosia" class="ambrosiaIcon">{}</span>)</a>'''.format(cost)
        return json.dumps([["replaceElement", ["#buildingSpeedup", popup]]])

    def test_rejects_nonzero_ambrosia_cost(self):
        self.assertIsNone(_getFreeSpeedupParams(self._response(4), "14075", 10))

    def test_builds_guarded_zero_cost_request(self):
        params = _getFreeSpeedupParams(self._response(0), "14075", 10)

        self.assertEqual(params["action"], "Premium")
        self.assertEqual(params["function"], "buildingSpeedup")
        self.assertEqual(params["level"], "3")

    def test_rejects_zero_cost_request_for_another_position(self):
        self.assertIsNone(_getFreeSpeedupParams(self._response(0), "14075", 11))

    def test_never_posts_premium_request_for_nonzero_cost(self):
        session = Mock()
        session.post.return_value = self._response(4)

        self.assertFalse(tryFreeBuildingSpeedup(session, "14075", {"position": 10}))
        self.assertEqual(session.post.call_count, 1)

    def test_posts_premium_request_for_zero_cost(self):
        session = Mock()
        session.post.side_effect = [self._response(0), "ok"]

        self.assertTrue(tryFreeBuildingSpeedup(session, "14075", {"position": 10}))
        self.assertEqual(session.post.call_count, 2)
