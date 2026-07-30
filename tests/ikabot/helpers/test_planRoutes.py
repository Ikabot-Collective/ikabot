import unittest
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.helpers.planRoutes import splitCargoBetweenFleets


class TestSplitCargoBetweenFleets(unittest.TestCase):
    """Test the cargo split between trade ships and freighters"""

    def setUp(self):
        """Set up test fixtures"""
        self.session = Mock()

    @patch('ikabot.helpers.planRoutes.getShipCapacity')
    @patch('ikabot.helpers.planRoutes.getAvailableShips')
    @patch('ikabot.helpers.planRoutes.getAvailableFreighters')
    def test_cargo_fits_in_trade_ships(self, mock_freighters, mock_ships, mock_capacity):
        """The whole cargo fits in the available trade ships, freighters get nothing"""
        mock_freighters.return_value = 5
        mock_ships.return_value = 10
        mock_capacity.return_value = (500, 5000)

        toSend = [1000, 1000, 0, 0, 0]
        tradeShipCargo, freighterCargo = splitCargoBetweenFleets(self.session, toSend)

        self.assertEqual(tradeShipCargo, [1000, 1000, 0, 0, 0])
        self.assertEqual(freighterCargo, [0, 0, 0, 0, 0])

    @patch('ikabot.helpers.planRoutes.getShipCapacity')
    @patch('ikabot.helpers.planRoutes.getAvailableShips')
    @patch('ikabot.helpers.planRoutes.getAvailableFreighters')
    def test_leftover_goes_to_freighters(self, mock_freighters, mock_ships, mock_capacity):
        """Whatever doesn't fit in the trade ships is assigned to the freighters"""
        mock_freighters.return_value = 5
        mock_ships.return_value = 2
        mock_capacity.return_value = (500, 5000)

        toSend = [1000, 1000, 0, 0, 0]
        tradeShipCargo, freighterCargo = splitCargoBetweenFleets(self.session, toSend)

        # 2 trade ships * 500 capacity = 1000, taken by the first resource
        self.assertEqual(tradeShipCargo, [1000, 0, 0, 0, 0])
        self.assertEqual(freighterCargo, [0, 1000, 0, 0, 0])
        self.assertEqual(
            [t + f for t, f in zip(tradeShipCargo, freighterCargo)], toSend
        )

    @patch('ikabot.helpers.planRoutes.getShipCapacity')
    @patch('ikabot.helpers.planRoutes.getAvailableShips')
    @patch('ikabot.helpers.planRoutes.getAvailableFreighters')
    def test_partial_split_of_a_single_resource(self, mock_freighters, mock_ships, mock_capacity):
        """A single resource is split between both fleets when it doesn't fit in one"""
        mock_freighters.return_value = 5
        mock_ships.return_value = 1
        mock_capacity.return_value = (500, 5000)

        toSend = [800, 0, 0, 0, 0]
        tradeShipCargo, freighterCargo = splitCargoBetweenFleets(self.session, toSend)

        self.assertEqual(tradeShipCargo, [500, 0, 0, 0, 0])
        self.assertEqual(freighterCargo, [300, 0, 0, 0, 0])

    @patch('ikabot.helpers.planRoutes.getShipCapacity')
    @patch('ikabot.helpers.planRoutes.getAvailableShips')
    @patch('ikabot.helpers.planRoutes.getAvailableFreighters')
    def test_no_freighters_available(self, mock_freighters, mock_ships, mock_capacity):
        """Without freighters the whole cargo is sent with trade ships"""
        mock_freighters.return_value = 0
        mock_ships.return_value = 1
        mock_capacity.return_value = (500, 5000)

        toSend = [10000, 0, 0, 0, 0]
        tradeShipCargo, freighterCargo = splitCargoBetweenFleets(self.session, toSend)

        self.assertEqual(tradeShipCargo, [10000, 0, 0, 0, 0])
        self.assertEqual(freighterCargo, [0, 0, 0, 0, 0])

    @patch('ikabot.helpers.planRoutes.getShipCapacity')
    @patch('ikabot.helpers.planRoutes.getAvailableShips')
    @patch('ikabot.helpers.planRoutes.getAvailableFreighters')
    def test_no_trade_ships_available(self, mock_freighters, mock_ships, mock_capacity):
        """Without trade ships the whole cargo is sent with freighters"""
        mock_freighters.return_value = 5
        mock_ships.return_value = 0
        mock_capacity.return_value = (500, 5000)

        toSend = [10000, 0, 0, 0, 0]
        tradeShipCargo, freighterCargo = splitCargoBetweenFleets(self.session, toSend)

        self.assertEqual(tradeShipCargo, [0, 0, 0, 0, 0])
        self.assertEqual(freighterCargo, [10000, 0, 0, 0, 0])


if __name__ == '__main__':
    unittest.main()
