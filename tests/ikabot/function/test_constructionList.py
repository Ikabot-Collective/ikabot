import unittest
import json
import importlib
from unittest.mock import Mock, call, patch

from ikabot.function.constructionList import (
    _formatRemainingTime,
    _getFreeSpeedupParams,
    _parseConstructionTime,
    tryFreeBuildingSpeedup,
)

construction = importlib.import_module("ikabot.function.constructionList")


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

        with patch.object(construction, "wait"):
            self.assertTrue(tryFreeBuildingSpeedup(session, "14075", {"position": 10}))
        self.assertEqual(session.post.call_count, 2)


class TestConstructionTaskHandoff(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.event = Mock()
        self.buildings = [
            {"name": "Town hall", "level": 1, "isBusy": False, "upgradeTo": 3,
             "constructionTime": 1500, "constructionTimes": [600, 900]},
            {"name": "Warehouse", "level": 2, "isBusy": False, "upgradeTo": 3,
             "constructionTime": 1800, "constructionTimes": [1800]},
        ]
        self.city = {
            "id": "14075", "cityName": "Athens", "position": [],
            "availableResources": [1000] * 5, "endUpgradeTime": 1600,
        }
        self.mocks = {
            "banner": Mock(),
            "chooseCity": Mock(return_value=self.city),
            "getBuildingsToExpand": Mock(return_value=self.buildings),
            "getCostsReducers": Mock(return_value=[0] * 5),
            "getResourcesNeeded": Mock(return_value=[10, 0, 0, 0, 0]),
            "read": Mock(return_value="y"),
            "expandBuilding": Mock(),
            "sendResourcesMenu": Mock(),
            "setInfoSignal": Mock(),
            "sendToBot": Mock(),
        }
        for patcher in (
            patch.multiple(construction, **self.mocks),
            patch.object(construction.time, "time", return_value=1000),
            patch("ikabot.helpers.decorators.set_child_mode"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_configurator(self):
        construction.constructionList(self.session, self.event, None, [])
        self.event.set.assert_called_once()
        self.session.logout.assert_called_once()
        self.mocks["sendToBot"].assert_not_called()

    def test_passes_one_shared_queue_to_all_background_upgrades(self):
        snapshots = []

        def expand(session, city_id, building, wait_resources, queue):
            snapshots.append(list(queue))
            del queue[:len(building["constructionTimes"])]

        self.mocks["expandBuilding"].side_effect = expand
        self.run_configurator()

        self.assertEqual(snapshots, [[600, 900, 1800], [1800]])
        self.session.setStatus.assert_called_once_with(
            "Athens: queued 3 upgrades | total 1H"
        )
        self.mocks["sendResourcesMenu"].assert_not_called()

    def test_excludes_cancelled_buildings_from_queue_and_total(self):
        self.mocks["read"].side_effect = ["y", "n"]
        self.run_configurator()

        self.mocks["expandBuilding"].assert_called_once_with(
            self.session, "14075", self.buildings[0], False, [600, 900]
        )
        self.session.setStatus.assert_called_once_with(
            "Athens: queued 2 upgrades | total 30M"
        )

    def test_skipped_building_does_not_need_construction_times(self):
        del self.buildings[1]["constructionTime"]
        del self.buildings[1]["constructionTimes"]
        self.mocks["getResourcesNeeded"].side_effect = [
            [10, 0, 0, 0, 0], [-2] * 5,
        ]
        self.run_configurator()

        self.mocks["expandBuilding"].assert_called_once_with(
            self.session, "14075", self.buildings[0], False, [600, 900]
        )

    def test_preserves_multiple_resource_shipments_without_upgrading(self):
        self.city["availableResources"] = [0] * 5
        self.mocks["read"].side_effect = ["y", 2, "y", "y", 1, "n"]
        origins = [{0: [{"id": "source1"}]}, {0: [{"id": "source2"}]}]
        self.mocks["sendResourcesMenu"].side_effect = [
            (origins[0], False), (origins[1], False),
        ]
        threads = [Mock(), Mock()]
        with patch.object(construction.threading, "Thread", side_effect=threads) as factory:
            self.run_configurator()

        self.assertEqual(factory.call_args_list, [
            call(target=construction.sendResourcesNeeded,
                 args=(self.session, "14075", origins[0], [10, 0, 0, 0, 0], True, True)),
            call(target=construction.sendResourcesNeeded,
                 args=(self.session, "14075", origins[1], [10, 0, 0, 0, 0], False, False)),
        ])
        for thread in threads:
            thread.start.assert_called_once()
            thread.join.assert_called_once()
        self.mocks["expandBuilding"].assert_not_called()


class TestConstructionSpeedupOptIn(unittest.TestCase):
    def test_speedup_requires_opt_in_and_last_five_minutes(self):
        for enabled, remaining, expected_calls in (
            (False, 200, 0), (True, 200, 1), (True, 301, 0),
        ):
            with self.subTest(enabled=enabled, remaining=remaining):
                session = Mock()
                building = {"name": "Town hall", "level": 2, "completed": 1000 + remaining}
                active = {"cityName": "Athens", "position": [building]}
                finished = {"cityName": "Athens", "position": []}
                with (
                    patch.object(construction, "CONSTRUCTION_FREE_SPEEDUP", enabled),
                    patch.object(construction.time, "time", return_value=1000),
                    patch.object(construction, "getCity", side_effect=[active, finished, finished]),
                    patch.object(construction, "tryFreeBuildingSpeedup", return_value=True) as speedup,
                    patch.object(construction, "sendToBotDebug"),
                    patch.object(construction, "wait"),
                ):
                    result = construction.waitForConstruction(session, "14075", 3, [600])

                self.assertIs(result, finished)
                self.assertEqual(speedup.call_count, expected_calls)
