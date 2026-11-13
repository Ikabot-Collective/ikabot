import unittest
import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
)

from ikabot.function.trainSpies import (
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


class TestParseSafehouse(unittest.TestCase):
    def test_reads_the_train_slider(self):
        """The slider maxValue is in the script, not in translated text"""
        html = '<script>create_slider({ id: "slider_spy", maxValue: 30, minValue: 0 });</script>'

        self.assertEqual(parseSafehouse(html)["orderMax"], 30)

    def test_empty_html_gives_nothing(self):
        self.assertIsNone(parseSafehouse("")["orderMax"])


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
        self.assertEqual(notes["B"], "2/6, gold floor")

    def test_crystal_floor_is_per_city(self):
        cities = [
            city("A", safehouse(capacity=40, free=10, order_max=40), crystal=5200),
            city("B", safehouse(capacity=40, free=10, order_max=40), crystal=100000),
        ]

        orders, notes = planSpyTraining(cities, 1000000, settings(crystal_floor=5000))

        self.assertEqual({o["name"]: o["amount"] for o in orders}, {"A": 5, "B": 10})
        self.assertEqual(notes["A"], "5/10, crystal floor")

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
        self.assertEqual(notes["B"], "2/8, spies per pass limit")
        self.assertEqual(notes["C"], "0/3, spies per pass limit")

    def test_no_gold_left_orders_nothing(self):
        cities = [city("A", safehouse(capacity=40, free=10, order_max=40))]

        orders, notes = planSpyTraining(cities, 5000, settings(gold_floor=10000))

        self.assertEqual(orders, [])
        self.assertEqual(notes["A"], "0/10, gold floor")

    def test_unknown_cost_skips_the_city(self):
        """The cost is read from the page, without it nothing is ordered"""
        cities = [city("A", safehouse(capacity=40, free=10, order_max=40, gold=None))]

        orders, notes = planSpyTraining(cities, 1000000, settings())

        self.assertEqual(orders, [])
        self.assertEqual(notes["A"], "could not read the cost of a spy")

    def test_cities_with_nothing_to_train_are_left_out(self):
        cities = [city("A", safehouse(capacity=40, free=0, order_max=0))]

        orders, notes = planSpyTraining(cities, 1000000, settings())

        self.assertEqual((orders, notes), ([], {}))


class TestOrderAccepted(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
