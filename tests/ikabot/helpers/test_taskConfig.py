import unittest
from unittest.mock import MagicMock, patch

from ikabot.helpers.taskConfig import (
    asBool,
    asId,
    asInt,
    findBuildingPosition,
    getCityById,
    requireNotifications,
    requireOwnCity,
)

OWN_CITIES = (
    ["111", "222"],
    {"111": {"id": 111, "name": "Alpha"}, "222": {"id": 222, "name": "Beta"}},
)


class TestCityHelpers(unittest.TestCase):
    @patch("ikabot.helpers.taskConfig.getCity", return_value={"id": "123"})
    def test_get_city_by_id_accepts_a_numeric_id(self, mock_get_city):
        session = MagicMock()
        session.get.return_value = "<html>"
        self.assertEqual(getCityById(session, 123), {"id": "123"})
        session.get.assert_called_once_with("view=city&cityId=123")
        mock_get_city.assert_called_once_with("<html>")

    def test_find_building_position(self):
        city = {"position": [
            {"position": 0, "building": "townHall"},
            {"position": 1, "building": "empty"},
            {"position": 4, "building": "academy"},
            {"position": 7, "building": "academy"},
        ]}
        self.assertEqual(findBuildingPosition(city, "academy"), 4)
        self.assertIsNone(findBuildingPosition(city, "barracks"))


class TestValueChecks(unittest.TestCase):
    def test_as_id(self):
        self.assertEqual(asId(12345, "cityId"), "12345")
        self.assertEqual(asId(" 12345 ", "cityId"), "12345")
        for bad in (None, "", "abc", "12a", -5, True, 1.5):
            with self.assertRaisesRegex(ValueError, "cityId must be an id"):
                asId(bad, "cityId")

    def test_as_int(self):
        self.assertEqual(asInt(20, "minutes"), 20)
        self.assertEqual(asInt(20.0, "minutes"), 20)
        self.assertEqual(asInt(" 20 ", "minutes"), 20)
        self.assertEqual(asInt("-1", "limit"), -1)
        for bad in (2.5, "abc", "--1", None, True, [20]):
            with self.assertRaisesRegex(ValueError, "minutes must be a whole number"):
                asInt(bad, "minutes")

    def test_as_int_limits(self):
        self.assertEqual(asInt(3, "minutes", minimum=3, maximum=60), 3)
        with self.assertRaisesRegex(ValueError, "minutes must be at least 3, got 2"):
            asInt(2, "minutes", minimum=3)
        with self.assertRaisesRegex(ValueError, "mode must be at most 3, got 4"):
            asInt(4, "mode", maximum=3)

    def test_as_bool(self):
        for value in (True, 1, "y", "Yes", "true", "1"):
            self.assertIs(asBool(value, "fights"), True)
        for value in (False, 0, "n", "NO", "false", "0"):
            self.assertIs(asBool(value, "fights"), False)
        for bad in ("maybe", None, 2, [True]):
            with self.assertRaisesRegex(ValueError, "fights must be true or false"):
                asBool(bad, "fights")


@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN_CITIES)
class TestRequireOwnCity(unittest.TestCase):
    def test_an_own_city_is_returned_as_text(self, _mock_ids):
        self.assertEqual(requireOwnCity(MagicMock(), 222, "wineCityId"), "222")

    def test_another_city_lists_the_own_ones(self, _mock_ids):
        with self.assertRaisesRegex(ValueError, r"wineCityId 999 is not one of your cities\. Your cities: 111 \(Alpha\), 222 \(Beta\)"):
            requireOwnCity(MagicMock(), "999", "wineCityId")


class TestRequireNotifications(unittest.TestCase):
    @patch("ikabot.helpers.taskConfig.discordDataIsValid", return_value=False)
    @patch("ikabot.helpers.taskConfig.telegramDataIsValid", return_value=False)
    def test_fails_without_any_bot(self, _mock_tg, _mock_dc):
        with self.assertRaisesRegex(ValueError, "Telegram or Discord"):
            requireNotifications(MagicMock())

    @patch("ikabot.helpers.taskConfig.discordDataIsValid", return_value=True)
    @patch("ikabot.helpers.taskConfig.telegramDataIsValid", return_value=False)
    def test_discord_is_enough(self, _mock_tg, _mock_dc):
        requireNotifications(MagicMock())


if __name__ == "__main__":
    unittest.main()
