import unittest
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.function.modifyProduction import modifyTempleWorkers

# the temple reports the priests in js_TempleSlider, the same place the academy reports
# the scientists in js_AcademySlider
TEMPLE_RESPONSE = (
    '[["changeView",["temple",""]],["updateGlobalData",{}],["updateTemplateData",'
    '{"js_TempleSlider":{"slider":{"id":"slider_temple","max_value":943,'
    '"overcharge":false,"ini_value":600,"textfield":"inputPriests",'
    '"callback_data":{"citizens_per_priest":5}}}}]]'
)


def city(name, position):
    """A city whose temple sits on the given position, plus a building that is not one"""
    return {
        "id": "30823",
        "name": name,
        "position": [
            {"position": 0, "building": "townHall"},
            {"position": position, "building": "temple"},
        ],
    }


def cityWithoutTemple(name):
    return {"id": "40000", "name": name, "position": [{"position": 0, "building": "townHall"}]}


def assignCalls(session):
    """The POSTs that assign the priests, the other POST reads the temple view"""
    return [
        call.kwargs["params"]
        for call in session.post.call_args_list
        if call.kwargs.get("params") is not None
    ]


class TestModifyTempleWorkers(unittest.TestCase):
    """Test assigning the priests of the temple city by city"""

    def setUp(self):
        """Set up test fixtures"""
        self.session = Mock()
        self.session.post.return_value = TEMPLE_RESPONSE

    def run_with(self, cities, percentage):
        """Runs the feature over the given cities answering the percentage prompt"""
        event = Mock()
        with patch('ikabot.function.modifyProduction.ignoreCities',
                   return_value=([c["id"] for c in cities], None)), \
             patch('ikabot.function.modifyProduction.getCity', side_effect=cities), \
             patch('ikabot.function.modifyProduction.read', return_value=percentage), \
             patch('ikabot.function.modifyProduction.wait'), \
             patch('ikabot.function.modifyProduction.banner'), \
             patch('ikabot.function.modifyProduction.enter'), \
             patch('ikabot.function.modifyProduction.os.fdopen'), \
             patch('builtins.print'):
            modifyTempleWorkers(self.session, event, 0, [])
        return event

    def test_full_percentage_uses_the_maximum_of_the_slider(self):
        """100% must send the max_value the temple reports, not the current value"""
        self.run_with([city("Crowcifix", 23)], 100)

        self.assertEqual(assignCalls(self.session)[0]["priests"], 943)

    def test_a_percentage_is_taken_from_the_maximum(self):
        """50% of 943 truncates to 471"""
        self.run_with([city("Crowcifix", 23)], 50)

        self.assertEqual(assignCalls(self.session)[0]["priests"], 471)

    def test_zero_percent_empties_the_temple(self):
        """0% is a valid choice, it sends the citizens back to work"""
        self.run_with([city("Crowcifix", 23)], 0)

        self.assertEqual(assignCalls(self.session)[0]["priests"], 0)

    def test_the_temple_position_of_the_city_is_used(self):
        """The temple is not always on the same plot, so the position comes from the city"""
        self.run_with([city("Crowcifix", 7)], 100)

        self.assertEqual(assignCalls(self.session)[0]["position"], 7)

    def test_the_priests_are_assigned_through_the_city_screen(self):
        """The temple uses CityScreen/assignPriests, unlike the academy which uses
        IslandScreen/workerPlan"""
        self.run_with([city("Crowcifix", 23)], 100)

        params = assignCalls(self.session)[0]
        self.assertEqual(params["action"], "CityScreen")
        self.assertEqual(params["function"], "assignPriests")
        self.assertEqual(params["cityId"], "30823")

    def test_a_city_without_a_temple_is_skipped(self):
        """Nothing must be assigned for a city that has no temple"""
        self.run_with([cityWithoutTemple("Nowhere")], 100)

        self.assertEqual(assignCalls(self.session), [])

    def test_a_city_without_a_temple_does_not_stop_the_others(self):
        """The cities after the one that is skipped must still be set"""
        self.run_with([cityWithoutTemple("Nowhere"), city("Crowcifix", 23)], 100)

        assigned = assignCalls(self.session)
        self.assertEqual(len(assigned), 1)
        self.assertEqual(assigned[0]["cityId"], "30823")


if __name__ == '__main__':
    unittest.main()
