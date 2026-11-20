import json
import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.buyResources import buy, do_it, next_purchase, prepare_buyResources, price_cap
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN = (["111", "222"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}})


def offer(price, amount, player="Seller", city="Shop", resource="2"):
    return {"precio": price, "amountAvailable": amount, "jugadorAComprar": player, "ciudadDestino": city,
            "resource": resource, "cityId": "111", "destinationCityId": "9000", "position": "4", "type": "444", "tipo": "marble"}


MARKET = {"id": "111", "name": "Alpha", "pos": 4, "rango": 10, "freeSpaceForResources": [0, 0, 50000, 0, 0]}


class TestNextPurchase(unittest.TestCase):
    def test_buys_from_the_cheapest_offer_first(self):
        chosen, amount = next_purchase([offer(30, 1000), offer(20, 400), offer(25, 5000)], 3000, 10000, 10 ** 9)
        self.assertEqual((chosen["precio"], amount), (20, 400))

    def test_never_above_max_price(self):
        self.assertEqual(next_purchase([offer(30, 1000)], 500, 10000, 10 ** 9, max_price=29), (None, 0))
        self.assertEqual(next_purchase([offer(30, 1000)], 500, 10000, 10 ** 9, max_price=30)[1], 500)

    def test_only_from_the_chosen_seller(self):
        offers = [offer(10, 100, player="Cheap", city="A"), offer(20, 100, player="Chosen", city="B&amp;C")]
        self.assertEqual(next_purchase(offers, 50, 10000, 10 ** 9, seller_player="chosen")[0]["precio"], 20)
        self.assertEqual(next_purchase(offers, 50, 10000, 10 ** 9, seller_city="B&C")[0]["precio"], 20)
        self.assertEqual(next_purchase(offers, 50, 10000, 10 ** 9, seller_player="Nobody"), (None, 0))

    def test_as_much_as_the_ships_carry_and_the_gold_pays(self):
        self.assertEqual(next_purchase([offer(10, 9000)], 8000, 2500, 10 ** 9)[1], 2500)
        self.assertEqual(next_purchase([offer(10, 9000)], 8000, 10000, 1234)[1], 123)
        # the gold does not pay for one unit: nothing to buy
        self.assertEqual(next_purchase([offer(10, 9000)], 8000, 10000, 9)[1], 0)

    def test_sold_out_offers_are_skipped(self):
        self.assertEqual(next_purchase([offer(5, 0), offer(8, 100)], 50, 10000, 10 ** 9)[0]["precio"], 8)
        self.assertEqual(next_purchase([offer(5, 0)], 50, 10000, 10 ** 9), (None, 0))

    def test_price_cap_is_the_highest_price_needed_for_the_amount(self):
        offers = [offer(30, 1000), offer(20, 400), offer(25, 5000)]
        self.assertEqual(price_cap(offers, 400), 20)
        self.assertEqual(price_cap(offers, 401), 25)
        self.assertEqual(price_cap(offers, 6000), 30)


@patch("ikabot.function.buyResources.getGold", return_value=(1000000, 0))
@patch("ikabot.function.buyResources.live_offers", return_value=[offer(20, 400), offer(25, 5000), offer(40, 9000)])
@patch("ikabot.function.buyResources.market_city", return_value=dict(MARKET))
@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN)
class TestPrepareBuyResources(unittest.TestCase):
    def test_is_registered_for_the_cli(self, *_):
        self.assertIs(_TASK_REGISTRY["buyResources"].prepare, prepare_buyResources)

    def test_valid_config(self, *_):
        config = prepare_buyResources(MagicMock(), city_id=111, resource="Marble", amount="3000", max_price=25)
        self.assertEqual(config, {"city_id": "111", "resource": "marble", "amount": 3000, "max_price": 25,
                                  "seller_player": None, "seller_city": None})
        self.assertEqual(prepare_buyResources(MagicMock(), city_id=111, resource=2, amount=100)["resource"], "marble")

    def test_rejects_what_cannot_be_bought(self, *_):
        bad = [
            (dict(resource="gold"), "resource must be wood, wine, marble, crystal, sulfur"),
            (dict(city_id=999), "city_id 999 is not one of your cities"),
            (dict(amount=0), "amount must be at least 1"),
            (dict(amount=60000), "Alpha has room for 50.000 marble, asked to buy 60.000"),
            (dict(max_price=19), "there are no marble offers at or below 19 gold in range of Alpha"),
            (dict(max_price=20, amount=500), "add up to 400, asked to buy 500"),
            (dict(seller_player=" "), "seller_player must be a name or null"),
            (dict(seller_player="Nobody"), "there are no marble offers from Nobody"),
        ]
        for change, error in bad:
            config = dict(dict(city_id=111, resource="marble", amount=3000), **change)
            with self.subTest(error):
                with self.assertRaisesRegex(ValueError, error):
                    prepare_buyResources(MagicMock(), **config)

    def test_rejects_a_purchase_the_gold_does_not_pay(self, _ids, _market, _offers, mock_gold):
        mock_gold.return_value = (8000 + 2600 * 25 - 1, 0)
        with self.assertRaisesRegex(ValueError, "buying 3.000 marble costs 73.000 gold and you have 72.999"):
            prepare_buyResources(MagicMock(), city_id=111, resource="marble", amount=3000)

    def test_no_trading_post(self, _ids, mock_market, *_):
        mock_market.side_effect = ValueError("Alpha has no trading post")
        with self.assertRaisesRegex(ValueError, "Alpha has no trading post"):
            prepare_buyResources(MagicMock(), city_id=111, resource="marble", amount=100)

    def test_a_config_saved_by_an_older_menu_keeps_the_prices_it_showed(self, *_):
        saved = {"city": {"id": "111", "name": "Alpha", "position": []}, "offers": [offer(20, 400), offer(25, 5000)], "amount_to_buy": 1000}
        config = prepare_buyResources(MagicMock(), **json.loads(json.dumps(saved)))
        self.assertEqual((config["resource"], config["amount"], config["max_price"]), ("marble", 1000, 25))


class TestBuy(unittest.TestCase):
    def test_nothing_is_bought_when_the_seller_raised_the_price(self):
        session = MagicMock()
        session.post.return_value = json.dumps([[], [None, [None, '"tradegood2Price" value="31"']]])
        price, problem = buy(session, MARKET, offer(25, 1000), 500, 10, 500, max_price=30)
        self.assertIsNone(price)
        self.assertIn("now costs 31 gold, above max_price 30", problem)
        # only the offer's page was read: the purchase was not sent
        self.assertEqual(session.post.call_count, 1)

    def test_the_game_rejecting_the_purchase_is_reported(self):
        session = MagicMock()
        session.post.side_effect = [
            json.dumps([[], [None, [None, '"tradegood2Price" value="25"']]]),
            json.dumps([["provideFeedback", [{"location": 1, "type": 11, "text": "Not enough gold"}]]]),
        ]
        self.assertEqual(buy(session, MARKET, offer(25, 1000), 500, 10, 500, max_price=30),
                         (None, "the game did not take the purchase: Not enough gold"))


@patch("ikabot.function.buyResources.sendToBot")
@patch("ikabot.function.buyResources.setInfoSignal")
@patch("ikabot.function.buyResources.getShipCapacity", return_value=(500, 1000))
@patch("ikabot.function.buyResources.waitForArrival", return_value=20)
@patch("ikabot.function.buyResources.getGold", return_value=(1000000, 0))
@patch("ikabot.function.buyResources.market_city", side_effect=lambda session, city_id: dict(MARKET))
class TestBuyTask(unittest.TestCase):
    def test_ends_when_the_offers_run_out(self, *_):
        # it used to go round the sold-out offers forever
        bought = []

        def buy_offer(session, market, chosen, amount, *args):
            bought.append(amount)
            return chosen["precio"], None

        session = MagicMock()
        offers = [[offer(20, 400)], []]
        with patch("ikabot.function.buyResources.live_offers", side_effect=lambda *a: offers.pop(0)), \
                patch("ikabot.function.buyResources.buy", side_effect=buy_offer):
            do_it.__wrapped__(session, city_id="111", resource="marble", amount=3000, max_price=25)
        self.assertEqual(bought, [400])
        status = session.setStatus.call_args.args[0]
        self.assertRegex(status, r"^Bought 400 of 3\.000 marble for 8\.000 gold @.*: there are no more marble offers at or below 25 gold$")


if __name__ == "__main__":
    unittest.main()
