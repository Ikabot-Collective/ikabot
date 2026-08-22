import unittest
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.function.buyResources import (
    BUY_FROM_ANYONE,
    BUY_FROM_CITY,
    BUY_FROM_PLAYER,
    filterOffers,
)


def offer(player, city, amount, price):
    return {
        "jugadorAComprar": player,
        "ciudadDestino": city,
        "amountAvailable": amount,
        "precio": price,
    }


class TestFilterOffers(unittest.TestCase):
    """Test that the user can buy from one seller instead of the cheapest ones"""

    def setUp(self):
        """The offers arrive sorted by price, as the caller sorts them"""
        self.offers = [
            offer("Odysseus", "Ithaca", 1000, 10),
            offer("Priam", "Troy", 2000, 15),
            offer("Odysseus", "Same", 3000, 20),
        ]

    @patch('ikabot.function.buyResources.print')
    @patch('ikabot.function.buyResources.read')
    def test_buying_from_anyone_keeps_every_offer(self, mock_read, mock_print):
        """The default choice must not change the offers at all"""
        mock_read.side_effect = [BUY_FROM_ANYONE]

        (offers, seller) = filterOffers(self.offers)

        self.assertEqual(offers, self.offers)
        self.assertIsNone(seller)

    @patch('ikabot.function.buyResources.print')
    @patch('ikabot.function.buyResources.read')
    def test_buying_from_a_player_keeps_all_of_their_offers(self, mock_read, mock_print):
        """A player selling from several cities must keep every one of their offers"""
        mock_read.side_effect = [BUY_FROM_PLAYER, 1]

        (offers, seller) = filterOffers(self.offers)

        self.assertEqual(seller, "Odysseus")
        self.assertEqual([o["ciudadDestino"] for o in offers], ["Ithaca", "Same"])

    @patch('ikabot.function.buyResources.print')
    @patch('ikabot.function.buyResources.read')
    def test_buying_from_a_city_keeps_only_that_city(self, mock_read, mock_print):
        """Choosing a city must not bring in the other cities of the same player"""
        mock_read.side_effect = [BUY_FROM_CITY, 3]

        (offers, seller) = filterOffers(self.offers)

        self.assertEqual(seller, "Same")
        self.assertEqual(offers, [self.offers[2]])

    @patch('ikabot.function.buyResources.print')
    @patch('ikabot.function.buyResources.read')
    def test_a_player_is_listed_once(self, mock_read, mock_print):
        """A player with several offers must not be listed several times"""
        mock_read.side_effect = [BUY_FROM_PLAYER, 2]

        (offers, seller) = filterOffers(self.offers)

        self.assertEqual(seller, "Priam")

    @patch('ikabot.function.buyResources.print')
    @patch('ikabot.function.buyResources.read')
    def test_sellers_are_listed_by_ascending_price(self, mock_read, mock_print):
        """The list must follow the order of the offers, which is sorted by price"""
        mock_read.side_effect = [BUY_FROM_PLAYER, 1]

        filterOffers(self.offers)

        listed = [str(c) for c in mock_print.call_args_list]
        self.assertLess(
            next(i for i, line in enumerate(listed) if "Odysseus" in line),
            next(i for i, line in enumerate(listed) if "Priam" in line),
        )

    @patch('ikabot.function.buyResources.print')
    @patch('ikabot.function.buyResources.read')
    def test_the_offers_are_never_emptied(self, mock_read, mock_print):
        """The seller is picked from the offers themselves, so there is always a match"""
        for choice in (BUY_FROM_PLAYER, BUY_FROM_CITY):
            mock_read.side_effect = [choice, 1]

            (offers, seller) = filterOffers(self.offers)

            self.assertTrue(len(offers) > 0)
            self.assertIsNotNone(seller)


if __name__ == '__main__':
    unittest.main()
