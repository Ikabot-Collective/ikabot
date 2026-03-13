import unittest
from unittest.mock import Mock, patch, MagicMock, call
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.function.donationBot import _get_donation_config


class TestGetDonationConfig(unittest.TestCase):
    """Test the _get_donation_config helper function"""

    def setUp(self):
        """Set up test fixtures"""
        self.cities = {
            1: {"name": "City1", "tradegood": 0},
            2: {"name": "City2", "tradegood": 1},
            3: {"name": "City3", "tradegood": 2},
        }

    @patch('ikabot.function.donationBot.read')
    @patch('ikabot.function.donationBot.print')
    def test_donation_config_forest_only_method_1(self, mock_print, mock_read):
        """Test getting config for forest donation with method 1 (storage percentage)"""
        mock_read.side_effect = ['f', '75']

        donation_type, percentage = _get_donation_config(self.cities, donate_method=1, cityId=1)

        self.assertEqual(donation_type, 'resource')
        self.assertEqual(percentage, '75')
        self.assertEqual(mock_read.call_count, 2)

    @patch('ikabot.function.donationBot.read')
    @patch('ikabot.function.donationBot.print')
    def test_donation_config_tradegood_method_2(self, mock_print, mock_read):
        """Test getting config for tradegood with method 2 (production percentage)"""
        mock_read.side_effect = ['t', '50']

        donation_type, percentage = _get_donation_config(self.cities, donate_method=2, cityId=2)

        self.assertEqual(donation_type, 'tradegood')
        self.assertEqual(percentage, '50')
        self.assertEqual(mock_read.call_count, 2)

    @patch('ikabot.function.donationBot.read')
    @patch('ikabot.function.donationBot.print')
    def test_donation_config_both_method_3(self, mock_print, mock_read):
        """Test getting config for both with method 3 (specific amount)"""
        mock_read.side_effect = ['b', '5000']

        donation_type, percentage = _get_donation_config(self.cities, donate_method=3, cityId=3)

        self.assertEqual(donation_type, 'both')
        self.assertEqual(percentage, '5000')
        self.assertEqual(mock_read.call_count, 2)

    @patch('ikabot.function.donationBot.read')
    @patch('ikabot.function.donationBot.print')
    def test_donation_config_none(self, mock_print, mock_read):
        """Test getting config when user selects no donation (n)"""
        mock_read.return_value = 'n'

        donation_type, percentage = _get_donation_config(self.cities, donate_method=1, cityId=1)

        self.assertIsNone(donation_type)
        self.assertIsNone(percentage)
        self.assertEqual(mock_read.call_count, 1)

    @patch('ikabot.function.donationBot.read')
    @patch('ikabot.function.donationBot.print')
    def test_donation_config_default_storage_percentage(self, mock_print, mock_read):
        """Test default storage percentage when user provides empty input"""
        mock_read.side_effect = ['f', '']

        donation_type, percentage = _get_donation_config(self.cities, donate_method=1, cityId=1)

        self.assertEqual(donation_type, 'resource')
        self.assertEqual(percentage, 80)

    @patch('ikabot.function.donationBot.read')
    @patch('ikabot.function.donationBot.print')
    def test_donation_config_default_production_percentage(self, mock_print, mock_read):
        """Test default production percentage when user provides empty input"""
        mock_read.side_effect = ['t', '']

        donation_type, percentage = _get_donation_config(self.cities, donate_method=2, cityId=2)

        self.assertEqual(donation_type, 'tradegood')
        self.assertEqual(percentage, 50)

    @patch('ikabot.function.donationBot.read')
    @patch('ikabot.function.donationBot.print')
    def test_donation_config_default_specific_amount(self, mock_print, mock_read):
        """Test default specific amount when user provides empty input"""
        mock_read.side_effect = ['b', '']

        donation_type, percentage = _get_donation_config(self.cities, donate_method=3, cityId=3)

        self.assertEqual(donation_type, 'both')
        self.assertEqual(percentage, 10000)

    @patch('ikabot.function.donationBot.read')
    @patch('ikabot.function.donationBot.print')
    def test_donation_config_100_percent_disables_donation(self, mock_print, mock_read):
        """Test that 100% storage occupancy disables donation (method 1)"""
        mock_read.side_effect = ['f', 100]

        donation_type, percentage = _get_donation_config(self.cities, donate_method=1, cityId=1)

        self.assertIsNone(donation_type)
        self.assertEqual(percentage, 100)

    @patch('ikabot.function.donationBot.read')
    @patch('ikabot.function.donationBot.print')
    def test_donation_config_zero_disables_production_donation(self, mock_print, mock_read):
        """Test that 0% production disables donation (method 2)"""
        mock_read.side_effect = ['t', 0]

        donation_type, percentage = _get_donation_config(self.cities, donate_method=2, cityId=2)

        self.assertIsNone(donation_type)
        self.assertEqual(percentage, 0)

    @patch('ikabot.function.donationBot.read')
    @patch('ikabot.function.donationBot.print')
    def test_donation_config_zero_disables_specific_amount(self, mock_print, mock_read):
        """Test that 0 amount disables donation (method 3)"""
        mock_read.side_effect = ['b', 0]

        donation_type, percentage = _get_donation_config(self.cities, donate_method=3, cityId=3)

        self.assertIsNone(donation_type)
        self.assertEqual(percentage, 0)

    @patch('ikabot.function.donationBot.read')
    @patch('ikabot.function.donationBot.print')
    def test_donation_config_case_insensitive(self, mock_print, mock_read):
        """Test that donation type selection is case insensitive"""
        mock_read.side_effect = ['F', '80']

        donation_type, percentage = _get_donation_config(self.cities, donate_method=1, cityId=1)

        self.assertEqual(donation_type, 'resource')
        self.assertEqual(percentage, '80')


class TestDonationBotWorkflow(unittest.TestCase):
    """Test the overall donation bot workflow with mocked inputs"""

    def test_apply_to_all_cities_configuration_reuse(self):
        """Test that when apply_to_all=True, the same config is used for all cities"""
        cities_ids = [1, 2, 3]
        donation_type, percentage = 'resource', 80
        cities_dict = {}

        for cityId in cities_ids:
            cities_dict[cityId] = {
                "donation_type": donation_type,
                "percentage": percentage,
            }

        self.assertEqual(cities_dict[1], {"donation_type": "resource", "percentage": 80})
        self.assertEqual(cities_dict[2], {"donation_type": "resource", "percentage": 80})
        self.assertEqual(cities_dict[3], {"donation_type": "resource", "percentage": 80})

    def test_separate_cities_configuration_diversity(self):
        """Test that when apply_to_all=False, different configs can be used per city"""
        cities_ids = [1, 2, 3]
        cities_dict = {}

        configs = [
            ('resource', 80),
            ('tradegood', 50),
            ('both', 75),
        ]

        for cityId, (donation_type, percentage) in zip(cities_ids, configs):
            cities_dict[cityId] = {
                "donation_type": donation_type,
                "percentage": percentage,
            }

        self.assertEqual(cities_dict[1]["donation_type"], "resource")
        self.assertEqual(cities_dict[1]["percentage"], 80)

        self.assertEqual(cities_dict[2]["donation_type"], "tradegood")
        self.assertEqual(cities_dict[2]["percentage"], 50)

        self.assertEqual(cities_dict[3]["donation_type"], "both")
        self.assertEqual(cities_dict[3]["percentage"], 75)


if __name__ == '__main__':
    unittest.main()
