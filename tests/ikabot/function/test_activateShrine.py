import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.activateShrine import WAIT_TIME, prepare_activateShrine
from ikabot.helpers.decorators import _TASK_REGISTRY


@patch("ikabot.function.activateShrine.findShrine", return_value=("111", 7))
class TestPrepareActivateShrine(unittest.TestCase):
    def test_is_registered_for_the_cli(self, _mock_shrine):
        self.assertIs(_TASK_REGISTRY["activateShrine"].prepare, prepare_activateShrine)

    def test_fills_in_the_god_names_and_the_wait_time(self, _mock_shrine):
        self.assertEqual(
            prepare_activateShrine(MagicMock(), godids=[2, "4"], mode=3, times=2),
            {
                "godids": [2, 4],
                "mode": 3,
                "times": 2,
                "selected_gods": "Dionysus, Plutus",
                "wait_time": WAIT_TIME,
            },
        )

    def test_mode_two_ignores_times(self, _mock_shrine):
        self.assertEqual(prepare_activateShrine(MagicMock(), godids=[1], mode=2)["times"], 0)

    def test_modes_one_and_three_need_times(self, _mock_shrine):
        with self.assertRaisesRegex(ValueError, "times must be at least 1, got 0"):
            prepare_activateShrine(MagicMock(), godids=[1], mode=1)

    def test_rejects_unknown_gods(self, _mock_shrine):
        with self.assertRaisesRegex(ValueError, "godids must be at most 6, got 7"):
            prepare_activateShrine(MagicMock(), godids=[7], mode=2)
        with self.assertRaisesRegex(ValueError, "godids must be a list of gods"):
            prepare_activateShrine(MagicMock(), godids=[], mode=2)

    def test_rejects_an_unknown_mode(self, _mock_shrine):
        with self.assertRaisesRegex(ValueError, "mode must be at most 3, got 4"):
            prepare_activateShrine(MagicMock(), godids=[1], mode=4)

    def test_needs_the_shrine(self, mock_shrine):
        mock_shrine.return_value = (None, None)
        with self.assertRaisesRegex(ValueError, "Shrine of Olympus"):
            prepare_activateShrine(MagicMock(), godids=[1], mode=2)


if __name__ == "__main__":
    unittest.main()
