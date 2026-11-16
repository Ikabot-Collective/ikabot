import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.activateMiracle import do_it, prepare_activateMiracle, wonder_type
from ikabot.helpers.decorators import _TASK_REGISTRY


def wonder(number, name, level, city_id="111", available=True):
    return {
        "id": "44" + number,
        "wonder": number,
        "wonderName": name,
        "wonderActivationLevel": level,
        "available": available,
        "available_in": None if available else 3600,
        "ciudad": {"id": city_id, "name": "City " + city_id, "islandId": "44" + number, "pos": "4"},
    }


HERMES = wonder("5", "Temple of Hermes", 3)
FORGE = wonder("1", "Hephaistos' Forge", 2, city_id="222")


class TestWonderType(unittest.TestCase):
    def test_a_number_or_a_gods_name(self):
        for value, expected in [(5, "5"), ("5", "5"), ("05", "5"), ("Hermes", "5"), (" hermes ", "5"),
                                ("athena", "4"), ("Athène", "4"), ("COLOSSUS", "8")]:
            with self.subTest(value):
                self.assertEqual(wonder_type(value), expected)

    def test_rejects_anything_else(self):
        for value in [0, 9, "zeus", "", None, True]:
            with self.subTest(value):
                with self.assertRaisesRegex(ValueError, "wonder must be a number from 1 to 8 or a god's name"):
                    wonder_type(value)


@patch("ikabot.function.activateMiracle.obtainMiraclesAvailable", return_value=[HERMES, FORGE])
class TestPrepareActivateMiracle(unittest.TestCase):
    def test_is_registered_for_the_cli(self, _mock):
        self.assertIs(_TASK_REGISTRY["activateMiracle"].prepare, prepare_activateMiracle)

    def test_keeps_only_the_wonder_type_and_the_iterations(self, _mock):
        self.assertEqual(prepare_activateMiracle(MagicMock(), wonder="hermes", iterations="3"), {"wonder": "5", "iterations": 3})
        self.assertEqual(prepare_activateMiracle(MagicMock(), wonder=1), {"wonder": "1", "iterations": 1})

    def test_accepts_a_config_saved_by_an_older_menu(self, _mock):
        self.assertEqual(prepare_activateMiracle(MagicMock(), island=HERMES, iterations=2), {"wonder": "5", "iterations": 2})

    def test_rejects_bad_values(self, _mock):
        with self.assertRaisesRegex(ValueError, "wonder is needed"):
            prepare_activateMiracle(MagicMock())
        with self.assertRaisesRegex(ValueError, "iterations must be at least 1, got 0"):
            prepare_activateMiracle(MagicMock(), wonder=5, iterations=0)

    def test_the_wonder_must_be_on_an_island_with_one_of_your_temples(self, _mock):
        with self.assertRaisesRegex(
            ValueError,
            "none of your cities with a temple is on an island with the ares wonder. "
            "Your wonders: hermes = Temple of Hermes \\(level 3\\), hephaistos = Hephaistos' Forge \\(level 2\\)",
        ):
            prepare_activateMiracle(MagicMock(), wonder="ares")

    def test_without_temples(self, mock_available):
        mock_available.return_value = []
        with self.assertRaisesRegex(ValueError, "None of your cities has a temple"):
            prepare_activateMiracle(MagicMock(), wonder=5)


@patch("ikabot.function.activateMiracle.setInfoSignal")
@patch("ikabot.function.activateMiracle.sendToBot")
@patch("ikabot.function.activateMiracle.sendToBotDebug")
@patch("ikabot.function.activateMiracle.refresh_best_city")
@patch("ikabot.function.activateMiracle.wait_for_miracle")
@patch("ikabot.function.activateMiracle.activateMiracleHttpCall", return_value=[None, [None, ["ok"]]])
@patch("ikabot.function.activateMiracle.obtainMiraclesAvailable", return_value=[HERMES, FORGE])
class TestActivateMiracleTask(unittest.TestCase):
    def test_finds_the_island_and_activates_it_each_time(self, _available, mock_activate, mock_wait, _refresh, _debug, _bot, _info):
        session = MagicMock()
        do_it.__wrapped__(session, wonder="5", iterations=2)
        self.assertEqual(mock_activate.call_count, 2)
        self.assertEqual(mock_activate.call_args.args[1]["ciudad"]["id"], "111")
        self.assertIn("iterations left: 0", session.setStatus.call_args.args[0])

    def test_a_config_saved_by_an_older_menu(self, _available, mock_activate, *_mocks):
        do_it.__wrapped__(MagicMock(), island=FORGE, iterations=1)
        self.assertEqual(mock_activate.call_args.args[1]["wonder"], "1")

    def test_reports_a_wonder_that_is_no_longer_reachable(self, mock_available, mock_activate, mock_wait, _refresh, _debug, mock_bot, _info):
        mock_available.return_value = [FORGE]
        session = MagicMock()
        do_it.__wrapped__(session, wonder="5", iterations=1)
        mock_activate.assert_not_called()
        mock_wait.assert_not_called()
        self.assertIn("The miracle was not activated: none of your cities", session.setStatus.call_args.args[0])
        self.assertIn("hermes wonder", mock_bot.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
