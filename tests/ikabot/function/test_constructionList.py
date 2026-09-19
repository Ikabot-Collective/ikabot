import unittest
import json
from unittest.mock import Mock

from ikabot.function.constructionList import (
    _formatRemainingTime,
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

    def test_formats_remaining_seconds(self):
        self.assertEqual(_formatRemainingTime(927), "15M 27S")


class TestFreeBuildingSpeedup(unittest.TestCase):
    def _response(self, cost):
        popup = '''<a class="button" id="js_buildingSpeedupActivateBtn"
            href="?action=Premium&amp;function=buildingSpeedup&amp;cityId=14075&amp;position=10&amp;level=3&amp;backgroundView=city&amp;currentCityId=14075&amp;actionRequest=old">
            Activate (<span title="Ambrosia" class="ambrosiaIcon">{}</span>)</a>'''.format(cost)
        return json.dumps([["replaceElement", ["#buildingSpeedup", popup]]])

    def test_rejects_nonzero_ambrosia_cost(self):
        self.assertIsNone(_getFreeSpeedupParams(self._response(4), "14075", 10))

    def test_rejects_various_nonzero_ambrosia_costs(self):
        for cost in (1, 4, 20, 100, 1500):
            with self.subTest(cost=cost):
                self.assertIsNone(
                    _getFreeSpeedupParams(self._response(cost), "14075", 10)
                )

    def test_rejects_nonzero_cost_with_surrounding_whitespace(self):
        response = self._response_with_span(
            '<span title="Ambrosia" class="ambrosiaIcon">\n  20\n</span>'
        )

        self.assertIsNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_rejects_nonzero_cost_with_reordered_span_attributes(self):
        response = self._response_with_span(
            '<span class="ambrosiaIcon" title="Ambrosia">20</span>'
        )

        self.assertIsNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_rejects_nonzero_cost_in_raw_popup(self):
        popup = json.loads(self._response(20))[0][1][1]

        self.assertIsNone(_getFreeSpeedupParams(popup, "14075", 10))

    def test_rejects_nonzero_cost_with_non_numeric_text(self):
        response = self._response_with_span(
            '<span title="Ambrosia" class="ambrosiaIcon">20 Ambrosia</span>'
        )

        self.assertIsNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_rejects_zero_outer_span_hiding_nonzero_inner_cost(self):
        response = self._response_with_span(
            '<span class="ambrosiaIcon">0<span class="ambrosiaIcon">20</span></span>'
        )

        self.assertIsNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_rejects_duplicate_spans_with_mixed_zero_and_nonzero_costs(self):
        for spans in (
            '<span class="ambrosiaIcon">0</span> <span class="ambrosiaIcon">20</span>',
            '<span class="ambrosiaIcon">20</span> <span class="ambrosiaIcon">0</span>',
        ):
            with self.subTest(spans=spans):
                response = self._response_with_span(spans)

                self.assertIsNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_builds_guarded_zero_cost_request(self):
        params = _getFreeSpeedupParams(self._response(0), "14075", 10)

        self.assertEqual(params["action"], "Premium")
        self.assertEqual(params["function"], "buildingSpeedup")
        self.assertEqual(params["level"], "3")

    def test_rejects_zero_cost_request_for_another_position(self):
        self.assertIsNone(_getFreeSpeedupParams(self._response(0), "14075", 11))

    def _response_with_span(self, span):
        response = json.loads(self._response(0))
        response[0][1][1] = response[0][1][1].replace(
            '<span title="Ambrosia" class="ambrosiaIcon">0</span>', span
        )
        return json.dumps(response)

    def test_rejects_nested_ambrosia_spans_hiding_nonzero_cost(self):
        response = self._response_with_span(
            '<span class="ambrosiaIcon">20<span class="ambrosiaIcon">0</span></span>'
        )

        self.assertIsNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_rejects_duplicate_ambrosia_spans_in_one_button(self):
        response = self._response_with_span(
            '<span class="ambrosiaIcon">0</span> <span class="ambrosiaIcon">0</span>'
        )

        self.assertIsNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_accepts_raw_popup_with_reordered_span_attributes(self):
        response = self._response(0)
        popup = json.loads(response)[0][1][1].replace(
            'title="Ambrosia" class="ambrosiaIcon"',
            'class="ambrosiaIcon" title="Ambrosia"',
        )

        self.assertIsNotNone(_getFreeSpeedupParams(popup, "14075", 10))

    def test_ignores_earlier_button_reference_in_ajax_response(self):
        response = json.loads(self._response(0))
        response.insert(0, ["update", ["#js_buildingSpeedupActivateBtn"]])

        self.assertIsNotNone(
            _getFreeSpeedupParams(json.dumps(response), "14075", 10)
        )

    def test_allows_popup_to_omit_replaceable_request_metadata(self):
        response = self._response(0).replace(
            "&amp;backgroundView=city&amp;currentCityId=14075&amp;actionRequest=old",
            "",
        )

        self.assertIsNotNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_never_posts_premium_request_for_nonzero_cost(self):
        session = Mock()
        session.post.return_value = self._response(4)

        self.assertFalse(tryFreeBuildingSpeedup(session, "14075", {"position": 10}))
        self.assertEqual(session.post.call_count, 1)

    def test_never_posts_premium_request_for_any_nonzero_cost(self):
        for cost in (1, 20, 1500):
            with self.subTest(cost=cost):
                session = Mock()
                session.post.return_value = self._response(cost)

                self.assertFalse(
                    tryFreeBuildingSpeedup(session, "14075", {"position": 10})
                )
                self.assertEqual(session.post.call_count, 1)

    def test_never_posts_premium_request_for_nested_nonzero_cost(self):
        session = Mock()
        session.post.return_value = self._response_with_span(
            '<span class="ambrosiaIcon">20<span class="ambrosiaIcon">0</span></span>'
        )

        self.assertFalse(tryFreeBuildingSpeedup(session, "14075", {"position": 10}))
        self.assertEqual(session.post.call_count, 1)

    def test_posts_premium_request_for_zero_cost(self):
        session = Mock()
        session.post.side_effect = [self._response(0), "ok"]

        self.assertTrue(tryFreeBuildingSpeedup(session, "14075", {"position": 10}))
        self.assertEqual(session.post.call_count, 2)
