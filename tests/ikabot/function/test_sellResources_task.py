import json
import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.sellResources import (
    BUY, SELL, do_it, next_sale, offers_payload, own_offers, prepare_sellResources,
)
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN = (["111", "222"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}})
MARKET = {"id": "111", "name": "Alpha", "pos": 4, "rango": 10, "availableResources": [9000, 5000, 3000, 0, 0]}


def buy_offer(price, amount, city_id=9000, city="Shop", player="Buyer"):
    """as getOffers returns them: city name, player name, amount, price, distance, city id"""
    return (city, player, amount, price, 2, city_id)


def own_offers_page(offers):
    """the parts of the trading post's own offers page that own_offers reads"""
    html = ""
    for key, (trade_type, amount, price) in zip(("resource", "tradegood1", "tradegood2", "tradegood3", "tradegood4"), offers):
        html += '<select name="{0}TradeType" id="{0}TradeType" size="1">\n'.format(key)
        for value in (BUY, SELL):
            html += '    <option\n        value="{}" {}>x</option>\n'.format(value, "selected" if value == trade_type else "")
        html += '</select>\n<input type="text" class="textfield"\n    size="4"\n    name="{0}"\n    id="{0}"\n    value="{1}"/>\n'.format(key, amount)
        html += '<input type="text" class="textfield"\n    size="2"\n    name="{0}Price"\n    id="{0}Price"\n    maxlength="2"\n    value="{1}"/>\n'.format(key, price)
    return html + "{'upper': 9, 'lower': 4}, {'upper': 6, 'lower': 3}, {'upper': 21, 'lower': 8}, {'upper': 18, 'lower': 7}, {'upper': 11, 'lower': 4}"


class TestNextSale(unittest.TestCase):
    def test_sells_to_the_best_paid_offer_first(self):
        offer, amount = next_sale([buy_offer(10, 1000), buy_offer(14, 300), buy_offer(12, 5000)], 2000, 10000, 9000)
        self.assertEqual((offer[3], amount), (14, 300))

    def test_never_below_min_price(self):
        self.assertEqual(next_sale([buy_offer(10, 1000)], 500, 10000, 9000, min_price=11), (None, 0))
        self.assertEqual(next_sale([buy_offer(11, 1000)], 500, 10000, 9000, min_price=11)[1], 500)

    def test_only_to_the_chosen_cities(self):
        offers = [buy_offer(20, 100, city_id=1), buy_offer(10, 100, city_id=2)]
        self.assertEqual(next_sale(offers, 50, 10000, 9000, buyers=["2"])[0][3], 10)
        self.assertEqual(next_sale(offers, 50, 10000, 9000, buyers=["3"]), (None, 0))

    def test_as_much_as_the_ships_carry_and_the_city_has(self):
        self.assertEqual(next_sale([buy_offer(10, 9000)], 8000, 2500, 9000)[1], 2500)
        self.assertEqual(next_sale([buy_offer(10, 9000)], 8000, 10000, 700)[1], 700)
        self.assertEqual(next_sale([buy_offer(10, 9000)], 8000, 10000, 0)[1], 0)


class TestOwnOffers(unittest.TestCase):
    def test_the_other_offers_are_kept(self):
        # the game sets the five goods at once: it used to send them all at 0, removing the user's
        # other offers, also offers to buy
        page = own_offers_page([(SELL, 0, 7), (BUY, 2000, 5), (SELL, 0, 15), (SELL, 500, 16), (SELL, 0, 8)])
        offers = own_offers(page)
        self.assertEqual(offers[1], {"type": BUY, "amount": 2000, "price": 5})
        payload = offers_payload(MARKET, offers, 0, 3000, 9)
        self.assertEqual((payload["resourceTradeType"], payload["resource"], payload["resourcePrice"]), (SELL, 3000, 9))
        self.assertEqual((payload["tradegood1TradeType"], payload["tradegood1"], payload["tradegood1Price"]), (BUY, 2000, 5))
        self.assertEqual((payload["tradegood3TradeType"], payload["tradegood3"], payload["tradegood3Price"]), (SELL, 500, 16))

    def test_an_unreadable_page_stops_instead_of_guessing(self):
        with self.assertRaisesRegex(ValueError, "could not read the offers of the trading post"):
            own_offers("<html>maintenance</html>")


@patch("ikabot.function.sellResources.getOffers", return_value=[buy_offer(12, 400, city_id=1), buy_offer(10, 5000, city_id=2)])
@patch("ikabot.function.sellResources.market_city", side_effect=lambda session, city_id: dict(MARKET))
@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN)
class TestPrepareSellResources(unittest.TestCase):
    def setUp(self):
        page = own_offers_page([(SELL, 0, 7), (BUY, 2000, 5), (SELL, 0, 15), (SELL, 0, 13), (SELL, 0, 8)])
        patcher = patch("ikabot.function.sellResources.getMarketInfo", return_value=page)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_is_registered_for_the_cli(self, *_):
        self.assertIs(_TASK_REGISTRY["sellResources"].prepare, prepare_sellResources)

    def test_sell_to_offers(self, *_):
        config = prepare_sellResources(MagicMock(), mode="sell_to_offers", city_id=111, resource="wood", amount=3000,
                                       min_price="10", buyers=[2, "2", 1])
        self.assertEqual(config, {"mode": "sell_to_offers", "city_id": "111", "resource": "wood", "amount": 3000,
                                  "min_price": 10, "buyers": ["2", "1"]})

    def test_create_offer(self, *_):
        config = prepare_sellResources(MagicMock(), mode="create_offer", city_id=111, resource=0, amount=3000, price=9)
        self.assertEqual(config, {"mode": "create_offer", "city_id": "111", "resource": "wood", "amount": 3000, "price": 9})

    def test_rejects_what_cannot_be_sold(self, *_):
        sell = dict(mode="sell_to_offers", city_id=111, resource="wood", amount=3000)
        create = dict(mode="create_offer", city_id=111, resource="wood", amount=3000, price=9)
        bad = [
            (dict(sell, mode="sell"), 'mode must be "sell_to_offers"'),
            (dict(sell, amount=9001), "Alpha has 9.000 wood, asked to sell 9.001"),
            (dict(sell, min_price=13), "there are no offers to buy wood at 13 gold or more in range of Alpha"),
            (dict(sell, min_price=11, amount=500), "add up to 400, asked to sell 500"),
            (dict(sell, buyers=[]), "buyers must be a list of city ids or null"),
            (dict(sell, buyers=[3]), "there are no offers to buy wood from the cities 3"),
            (dict(create, price=None), "price is needed for create_offer"),
            (dict(create, price=10), "price must be at most 9"),
            (dict(create, price=3), "price must be at least 4"),
            # the trading post has one offer per resource: an offer to buy wine is in the way
            (dict(create, resource="wine", price=5), "Alpha has an offer to buy 2.000 wine: remove it first"),
        ]
        for config, error in bad:
            with self.subTest(error):
                with self.assertRaisesRegex(ValueError, error):
                    prepare_sellResources(MagicMock(), **config)

    def test_configs_saved_by_an_older_menu(self, *_):
        sold_to = {"mode": "sell_to_offers", "amount_to_sell": 300, "resource_type": 0,
                   "offers": [buy_offer(12, 400, city_id=1), buy_offer(11, 900, city_id=2)],
                   "city_to_buy_from": {"id": "111", "name": "Alpha", "position": []}}
        config = prepare_sellResources(MagicMock(), **json.loads(json.dumps(sold_to)))
        self.assertEqual((config["amount"], config["min_price"], config["buyers"]), (300, 11, ["1", "2"]))
        offered = {"mode": "create_offer", "amount_to_sell": 300, "price": 9, "resource_type": 0, "sell_market_capacity": 14400,
                   "city": {"id": "111", "name": "Alpha", "position": []}}
        self.assertEqual(prepare_sellResources(MagicMock(), **offered),
                         {"mode": "create_offer", "city_id": "111", "resource": "wood", "amount": 300, "price": 9})


@patch("ikabot.function.sellResources.sendToBot")
@patch("ikabot.function.sellResources.setInfoSignal")
@patch("ikabot.function.sellResources.getShipCapacity", return_value=(500, 1000))
@patch("ikabot.function.sellResources.waitForArrival", return_value=20)
@patch("ikabot.function.sellResources.getCityById", return_value=dict(MARKET))
@patch("ikabot.function.sellResources.market_city", side_effect=lambda session, city_id: dict(MARKET))
class TestSellTask(unittest.TestCase):
    def test_ends_when_the_offers_run_out(self, *_):
        sold = []
        offers = [[buy_offer(12, 400)], []]
        session = MagicMock()
        with patch("ikabot.function.sellResources.getOffers", side_effect=lambda *a: offers.pop(0)), \
                patch("ikabot.function.sellResources.sell", side_effect=lambda s, c, o, amount, *a: sold.append(amount)):
            do_it.__wrapped__(session, mode="sell_to_offers", city_id="111", resource="wood", amount=3000, min_price=10)
        self.assertEqual(sold, [400])
        self.assertRegex(session.setStatus.call_args.args[0],
                         r"^Sold 400 of 3\.000 wood for 4\.800 gold @.*: there are no more offers to buy wood at 10 gold or more$")

    def test_create_offer_counts_other_goods_against_market_capacity(self, *_):
        from ikabot.function.sellResources import SELL, create_offer

        session = MagicMock()
        session.post.return_value = "[]"
        # trading post capacity is 5000, wine already uses 4000 -> only 1000 room for wood
        other_offers = [
            {"type": SELL, "amount": 0, "price": 5},
            {"type": SELL, "amount": 4000, "price": 10},
            {"type": SELL, "amount": 0, "price": 5},
            {"type": SELL, "amount": 0, "price": 5},
            {"type": SELL, "amount": 0, "price": 5},
        ]
        # pass 1: 4000 wine takes room -> offers 1000 wood; pass 2: all sold -> offers remaining 500; final check: sold
        offers_seq = [
            other_offers,
            other_offers,
            [{"type": SELL, "amount": 0, "price": 5}] * 5,
            [{"type": SELL, "amount": 0, "price": 5}] * 5,
        ]
        posted = []
        session.post.side_effect = lambda params=None: (posted.append(params), "[]")[1]
        with patch("ikabot.function.sellResources.getMarketInfo", return_value=""), \
                patch("ikabot.function.sellResources.own_offers", side_effect=offers_seq), \
                patch("ikabot.function.sellResources.storageCapacityOfMarket", return_value=5000), \
                patch("ikabot.function.sellResources.wait"):
            create_offer(session, dict(MARKET), 0, 1500, 8)
        self.assertEqual([p["resource"] for p in posted], [1000, 500])


if __name__ == "__main__":
    unittest.main()
