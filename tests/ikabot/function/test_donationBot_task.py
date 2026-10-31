import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.donationBot import checked_status, prepare_donationBot
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN_CITIES = (["111", "222"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}})


class TestCheckedStatus(unittest.TestCase):
    @patch("ikabot.function.donationBot.time.strftime", return_value="14:32")
    def test_shows_the_interval_the_last_check_and_the_total(self, _mock_time):
        self.assertEqual(checked_status(60, 1500), "Every 60 min, last check 14:32 | Total donated: 1500")


@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN_CITIES)
@patch("ikabot.function.donationBot.getIdsOfCities", return_value=OWN_CITIES)
class TestPrepareDonationBot(unittest.TestCase):
    def test_is_registered_for_the_cli(self, _mock_ids, _mock_ids_check):
        self.assertIs(_TASK_REGISTRY["donationBot"].prepare, prepare_donationBot)

    def test_all_applies_to_every_city_with_the_menu_defaults(self, _mock_ids, _mock_ids_check):
        config = prepare_donationBot(MagicMock(), cities_dict={"all": {"donation_type": "both"}})
        self.assertEqual(config["cities_ids"], ["111", "222"])
        self.assertEqual(
            config["cities_dict"],
            {
                "111": {"donation_type": "both", "percentage": 80},
                "222": {"donation_type": "both", "percentage": 80},
            },
        )
        self.assertEqual(config["waiting_time"], 1440)
        self.assertEqual(config["donate_method"], 1)

    def test_a_city_overrides_all(self, _mock_ids, _mock_ids_check):
        config = prepare_donationBot(
            MagicMock(),
            cities_dict={"all": {"donation_type": "forest"}, 222: {"donation_type": "luxury", "percentage": 30}},
            donate_method=2,
            waiting_time="60",
        )
        self.assertEqual(
            config["cities_dict"],
            {
                "111": {"donation_type": "resource", "percentage": 50},
                "222": {"donation_type": "tradegood", "percentage": 30},
            },
        )
        self.assertEqual(config["waiting_time"], 60)

    def test_the_disabling_value_turns_the_donation_off(self, _mock_ids, _mock_ids_check):
        config = prepare_donationBot(
            MagicMock(),
            cities_dict={"111": {"donation_type": "both", "percentage": 100}, "222": {"donation_type": None}},
        )
        self.assertEqual(
            config["cities_dict"],
            {"111": {"donation_type": None, "percentage": None}, "222": {"donation_type": None, "percentage": None}},
        )

    def test_a_fixed_amount_has_no_upper_limit(self, _mock_ids, _mock_ids_check):
        config = prepare_donationBot(
            MagicMock(), cities_dict={"111": {"donation_type": "both", "percentage": 250000}}, donate_method=3
        )
        self.assertEqual(config["cities_dict"]["111"]["percentage"], 250000)

    def test_rejects_bad_values(self, _mock_ids, _mock_ids_check):
        with self.assertRaisesRegex(ValueError, "donation_type must be resource, tradegood, both or none"):
            prepare_donationBot(MagicMock(), cities_dict={"111": {"donation_type": "gold"}})
        with self.assertRaisesRegex(ValueError, r"cities_dict\[111\]\.percentage must be at most 100"):
            prepare_donationBot(MagicMock(), cities_dict={"111": {"donation_type": "both", "percentage": 150}})
        with self.assertRaisesRegex(ValueError, "donate_method must be at most 3"):
            prepare_donationBot(MagicMock(), cities_dict={"all": {"donation_type": "both"}}, donate_method=4)
        with self.assertRaisesRegex(ValueError, "cities_dict must map city ids"):
            prepare_donationBot(MagicMock(), cities_dict={})

    def test_rejects_a_city_of_another_player(self, _mock_ids, _mock_ids_check):
        with self.assertRaisesRegex(ValueError, "cities_dict 999 is not one of your cities"):
            prepare_donationBot(MagicMock(), cities_dict={"999": {"donation_type": "both"}})


if __name__ == "__main__":
    unittest.main()
