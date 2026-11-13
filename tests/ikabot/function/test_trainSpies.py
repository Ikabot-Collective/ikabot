import json
import unittest
from unittest.mock import Mock, call, patch
import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
)

from ikabot.function.trainSpies import (
    CRYSTAL_FLOOR,
    GOLD_FLOOR,
    ORDER_DELAY,
    PASS_LIMIT,
    UNKNOWN_COST,
    describeShortfall,
    READ_DELAY,
    SpyTrainer,
    cityNeed,
    orderAccepted,
    parseSafehouse,
    planSpyTraining,
)


def safehouse(capacity=None, free=None, order_max=None, gold=150, crystal=40):
    return {
        "capacity": capacity,
        "freeSlots": free,
        "orderMax": order_max,
        "goldPerSpy": gold,
        "crystalPerSpy": crystal,
    }


def city(name, house, crystal=100000, city_id=None):
    return {
        "id": city_id or name,
        "name": name,
        "position": 7,
        "crystal": crystal,
        "safehouse": house,
    }


def settings(target=0, gold_floor=0, crystal_floor=0, max_per_pass=1000):
    return {
        "target": target,
        "goldFloor": gold_floor,
        "crystalFloor": crystal_floor,
        "maxPerPass": max_per_pass,
    }


# markup captured from a real safehouse (Brazilian server), only the parts the parser reads
STATS = """<div class="spy_stats_content"> <b>{capacity}</b> <ul class="disc-list">
 <li>{free}</li> <li>{defence}</li> <li>{used}</li> </ul> </div>"""
COSTS = """<div class="costs"> <ul class="resources"> <li class="gold" id="js_spygold">{gold}</li>
 <li class="glass" id="js_spyglass">{crystal}</li> <li class="time" id="js_spycompletion">1m 56s</li>
 </ul> </div>"""
SLIDER = """<script>create_slider({{ dir: 'ltr', id: "slider_spy", maxValue: {max},
 overcharge: 0, iniValue: 0, bg: "sliderbg_spy" }});</script>"""
# a city with spies on missions lists them below the stats, in the same kind of list
SPYINFO = """<div class="spyinfo"><ul><li>4 estão em uso</li></ul></div>"""


def safehouseHtml(capacity, free, defence, used, gold="150", crystal="40", slider=None):
    html = STATS.format(capacity=capacity, free=free, defence=defence, used=used)
    html += COSTS.format(gold=gold, crystal=crystal)
    if slider is not None:
        html += SLIDER.format(max=slider)
    return html + SPYINFO


class TestParseSafehouse(unittest.TestCase):
    def test_reads_a_safehouse_with_room(self):
        html = safehouseHtml(
            "Podes treinar 40",
            "36 esperam por treino",
            "4 estão a trabalhar na defesa",
            "0 estão em uso",
            slider=36,
        )

        self.assertEqual(
            parseSafehouse(html),
            {
                "orderMax": 36,
                "capacity": 40,
                "freeSlots": 36,
                "goldPerSpy": 150,
                "crystalPerSpy": 40,
            },
        )

    def test_a_full_safehouse_has_no_train_form(self):
        """With no free slot the game leaves the slider out, nothing can be ordered"""
        html = safehouseHtml(
            "Podes treinar 40",
            "0 esperam por treino",
            "6 estão a trabalhar na defesa",
            "4 estão em uso",
        )

        result = parseSafehouse(html)
        self.assertEqual(result["orderMax"], 0)
        self.assertEqual(result["freeSlots"], 0)

    def test_does_not_depend_on_the_language(self):
        """The labels are translated, the numbers are taken by position"""
        html = safehouseHtml(
            "You can train 40",
            "Waiting for training: 12",
            "3 working in defence",
            "5 in use",
            slider=12,
        )

        result = parseSafehouse(html)
        self.assertEqual(result["capacity"], 40)
        self.assertEqual(result["freeSlots"], 12)

    def test_thousands_separator_in_the_cost(self):
        html = safehouseHtml(
            "40", "10", "30", "0", gold="1.500", crystal="1,200", slider=10
        )

        result = parseSafehouse(html)
        self.assertEqual(result["goldPerSpy"], 1500)
        self.assertEqual(result["crystalPerSpy"], 1200)

    def test_missions_list_does_not_count_as_free_slots(self):
        """The spies abroad are listed after the stats and must not be read as free slots"""
        html = safehouseHtml("40", "30", "6", "4", slider=30)

        self.assertEqual(parseSafehouse(html)["freeSlots"], 30)

    def test_empty_html_gives_nothing(self):
        result = parseSafehouse("")
        self.assertIsNone(result["orderMax"])
        self.assertIsNone(result["capacity"])


class TestCityNeed(unittest.TestCase):
    def test_fill_mode_orders_the_empty_slots(self):
        self.assertEqual(cityNeed(safehouse(capacity=40, free=12, order_max=40), 0), 12)

    def test_fill_mode_falls_back_to_the_slider(self):
        """Without the slot count the slider still says how many can be trained"""
        self.assertEqual(cityNeed(safehouse(order_max=9), 0), 9)

    def test_the_slider_caps_the_order(self):
        self.assertEqual(cityNeed(safehouse(capacity=40, free=30, order_max=10), 0), 10)

    def test_target_mode_orders_the_gap(self):
        """40 slots, 30 free means 10 spies are there, 25 wanted means 15 more"""
        self.assertEqual(
            cityNeed(safehouse(capacity=40, free=30, order_max=40), 25), 15
        )

    def test_target_above_capacity_fills_up(self):
        self.assertEqual(cityNeed(safehouse(capacity=20, free=5, order_max=20), 50), 5)

    def test_target_already_reached(self):
        self.assertEqual(cityNeed(safehouse(capacity=40, free=10, order_max=40), 20), 0)

    def test_target_needs_the_counts(self):
        """Guessing could train spies the user did not want"""
        self.assertEqual(cityNeed(safehouse(order_max=30), 10), 0)

    def test_full_safehouse(self):
        self.assertEqual(cityNeed(safehouse(capacity=40, free=0, order_max=0), 0), 0)


class TestPlanSpyTraining(unittest.TestCase):
    def test_orders_what_every_city_needs(self):
        cities = [
            city("A", safehouse(capacity=40, free=5, order_max=40)),
            city("B", safehouse(capacity=40, free=20, order_max=40)),
        ]

        orders, notes = planSpyTraining(cities, 1000000, settings())

        self.assertEqual(
            [(o["name"], o["amount"]) for o in orders], [("B", 20), ("A", 5)]
        )
        self.assertEqual(orders[0]["gold"], 20 * 150)
        self.assertEqual(orders[0]["crystal"], 20 * 40)
        self.assertEqual(notes, {})

    def test_gold_floor_limits_the_orders(self):
        """1500 gold above the floor pays for 10 spies, shared by the biggest need first"""
        cities = [
            city("A", safehouse(capacity=40, free=8, order_max=40)),
            city("B", safehouse(capacity=40, free=6, order_max=40)),
        ]

        orders, notes = planSpyTraining(cities, 11500, settings(gold_floor=10000))

        self.assertEqual(
            [(o["name"], o["amount"]) for o in orders], [("A", 8), ("B", 2)]
        )
        self.assertEqual(notes["B"], {"amount": 2, "need": 6, "reason": GOLD_FLOOR})

    def test_crystal_floor_is_per_city(self):
        cities = [
            city("A", safehouse(capacity=40, free=10, order_max=40), crystal=5200),
            city("B", safehouse(capacity=40, free=10, order_max=40), crystal=100000),
        ]

        orders, notes = planSpyTraining(cities, 1000000, settings(crystal_floor=5000))

        self.assertEqual({o["name"]: o["amount"] for o in orders}, {"A": 5, "B": 10})
        self.assertEqual(notes["A"], {"amount": 5, "need": 10, "reason": CRYSTAL_FLOOR})

    def test_max_per_pass_is_shared_by_all_cities(self):
        cities = [
            city("A", safehouse(capacity=40, free=10, order_max=40)),
            city("B", safehouse(capacity=40, free=8, order_max=40)),
            city("C", safehouse(capacity=40, free=3, order_max=40)),
        ]

        orders, notes = planSpyTraining(cities, 1000000, settings(max_per_pass=12))

        self.assertEqual(
            [(o["name"], o["amount"]) for o in orders], [("A", 10), ("B", 2)]
        )
        self.assertEqual(notes["B"], {"amount": 2, "need": 8, "reason": PASS_LIMIT})
        self.assertEqual(notes["C"], {"amount": 0, "need": 3, "reason": PASS_LIMIT})

    def test_a_missing_resource_wins_over_the_pass_limit(self):
        """When both stop at the same number, the next run would not fix the missing gold"""
        cities = [city("A", safehouse(capacity=40, free=10, order_max=40))]

        orders, notes = planSpyTraining(cities, 750, settings(max_per_pass=5))

        self.assertEqual(orders[0]["amount"], 5)
        self.assertEqual(notes["A"]["reason"], GOLD_FLOOR)

    def test_no_gold_left_orders_nothing(self):
        cities = [city("A", safehouse(capacity=40, free=10, order_max=40))]

        orders, notes = planSpyTraining(cities, 5000, settings(gold_floor=10000))

        self.assertEqual(orders, [])
        self.assertEqual(notes["A"], {"amount": 0, "need": 10, "reason": GOLD_FLOOR})

    def test_unknown_cost_skips_the_city(self):
        """The cost is read from the page, without it nothing is ordered"""
        cities = [city("A", safehouse(capacity=40, free=10, order_max=40, gold=None))]

        orders, notes = planSpyTraining(cities, 1000000, settings())

        self.assertEqual(orders, [])
        self.assertEqual(notes["A"]["reason"], UNKNOWN_COST)

    def test_cities_with_nothing_to_train_are_left_out(self):
        cities = [city("A", safehouse(capacity=40, free=0, order_max=0))]

        orders, notes = planSpyTraining(cities, 1000000, settings())

        self.assertEqual((orders, notes), ([], {}))


class TestDescribeShortfall(unittest.TestCase):
    def test_pass_limit_is_left_for_the_next_run(self):
        note = {"amount": 0, "need": 35, "reason": PASS_LIMIT}

        self.assertEqual(describeShortfall(note), "35 left for the next run")

    def test_missing_gold(self):
        note = {"amount": 2, "need": 6, "reason": GOLD_FLOOR}

        self.assertEqual(
            describeShortfall(note), "4 not trained, not enough gold above the floor"
        )

    def test_missing_crystal(self):
        note = {"amount": 5, "need": 10, "reason": CRYSTAL_FLOOR}

        self.assertEqual(
            describeShortfall(note), "5 not trained, not enough crystal above the floor"
        )

    def test_unknown_cost(self):
        note = {"amount": 0, "need": 10, "reason": UNKNOWN_COST}

        self.assertEqual(describeShortfall(note), "could not read the cost of a spy")


class TestOrderAccepted(unittest.TestCase):
    def test_real_buildSpy_response(self):
        """Feedback the game sent back when one spy was ordered in a live test"""
        response = [
            ["updateGlobalData", {}],
            ["changeView", ["safehouse", ""]],
            ["updateTemplateData", {}],
            [
                "provideFeedback",
                [{"location": 4, "text": "A tua ordem foi executada.", "type": 10}],
            ],
        ]

        self.assertTrue(orderAccepted(response))

    def test_success_feedback(self):
        response = [
            ["updateGlobalData", {}],
            ["provideFeedback", [{"type": 10, "text": "ok"}]],
        ]

        self.assertTrue(orderAccepted(response))

    def test_error_feedback(self):
        response = [["provideFeedback", [{"type": 11, "text": "no"}]]]

        self.assertFalse(orderAccepted(response))

    def test_no_feedback(self):
        self.assertFalse(orderAccepted([["updateGlobalData", {}]]))


class TestPauses(unittest.TestCase):
    """A pass over many cities must not fire a burst of requests"""

    def run_pass(self, houses):
        session = Mock()
        session.get.return_value = "city html"
        session.post.return_value = json.dumps([["provideFeedback", [{"type": 10}]]])
        city = {
            "position": [{"position": 8, "building": "safehouse"}],
            "availableResources": [0, 0, 0, 100000, 0],
        }
        trainer = SpyTrainer(
            session, {"target": 0, "goldFloor": 0, "crystalFloor": 0, "maxPerPass": 100}
        )
        names = {str(i): {"name": "City{}".format(i)} for i in range(len(houses))}
        with patch("ikabot.function.trainSpies.getCity", return_value=city), patch(
            "ikabot.function.trainSpies.getGold", return_value=(10**7, 0)
        ), patch.object(SpyTrainer, "_read_safehouse", side_effect=houses), patch(
            "ikabot.function.trainSpies.pause"
        ) as pause:
            trainer.run_pass(list(names), names)
        return pause

    def test_pauses_between_cities_and_between_orders(self):
        houses = [safehouse(capacity=40, free=10, order_max=10) for _ in range(3)]

        pause = self.run_pass(houses)

        self.assertEqual(pause.call_args_list.count(call(READ_DELAY)), 2)
        self.assertEqual(pause.call_args_list.count(call(ORDER_DELAY)), 2)

    def test_no_order_pause_for_a_single_order(self):
        pause = self.run_pass([safehouse(capacity=40, free=10, order_max=10)])

        self.assertNotIn(call(ORDER_DELAY), pause.call_args_list)
        self.assertNotIn(call(READ_DELAY), pause.call_args_list)


if __name__ == "__main__":
    unittest.main()
