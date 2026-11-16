import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.dumpWorld import do_dumpWorld, prepare_dumpWorld
from ikabot.helpers.decorators import _TASK_REGISTRY


class TestPrepareDumpWorld(unittest.TestCase):
    def test_is_registered_for_the_cli(self):
        self.assertIs(_TASK_REGISTRY["dumpWorld"].prepare, prepare_dumpWorld)

    def test_defaults_to_a_full_dump_of_the_whole_map(self):
        self.assertEqual(
            prepare_dumpWorld(MagicMock()),
            {"waiting_time": 1.5, "coords": None, "radius": None, "shallow": False, "non_empty_islands": False},
        )

    def test_a_part_of_the_map(self):
        config = prepare_dumpWorld(MagicMock(), coords="50:60", non_empty_islands="y")
        self.assertEqual((config["coords"], config["radius"], config["non_empty_islands"]), ([50, 60], 15, True))
        self.assertEqual(prepare_dumpWorld(MagicMock(), coords=[50, 60], radius=5)["radius"], 5)
        self.assertEqual(prepare_dumpWorld(MagicMock(), coords="(50, 60)")["coords"], [50, 60])

    def test_the_menu_progress_screen_is_never_used_from_the_cli(self):
        # a config saved from the menu has show_progress on
        self.assertNotIn("show_progress", prepare_dumpWorld(MagicMock(), shallow=True, show_progress=True))

    def test_rejects_bad_values(self):
        with self.assertRaisesRegex(ValueError, "waiting_time must be between 0 and 10 seconds, got 1500$"):
            prepare_dumpWorld(MagicMock(), waiting_time=1500)
        with self.assertRaisesRegex(ValueError, "waiting_time must be a number of seconds"):
            prepare_dumpWorld(MagicMock(), waiting_time="fast")
        with self.assertRaisesRegex(ValueError, "coords must be"):
            prepare_dumpWorld(MagicMock(), coords="50")
        with self.assertRaisesRegex(ValueError, "coords x must be at most 100"):
            prepare_dumpWorld(MagicMock(), coords=[150, 60])
        with self.assertRaisesRegex(ValueError, "radius needs coords"):
            prepare_dumpWorld(MagicMock(), radius=10)
        with self.assertRaisesRegex(ValueError, "only work with shallow false"):
            prepare_dumpWorld(MagicMock(), shallow=True, coords="50:60")


@patch("ikabot.function.dumpWorld.setInfoSignal")
@patch("ikabot.function.dumpWorld.sendToBot")
@patch("ikabot.function.dumpWorld.enter")
@patch("ikabot.function.dumpWorld.do_it", return_value="/home/user/ikabot_world_dumps/s301-en/dump.json.gz")
class TestDumpWorldTask(unittest.TestCase):
    def test_without_a_console_reports_the_file_and_does_not_wait_for_enter(self, _mock_do_it, mock_enter, mock_bot, _mock_info):
        session = MagicMock()
        do_dumpWorld.__wrapped__(session, shallow=True)
        mock_enter.assert_not_called()
        self.assertRegex(session.setStatus.call_args.args[0], r"^Dumped to /home/user/ikabot_world_dumps/s301-en/dump.json.gz in \d+s$")
        self.assertIn("dump.json.gz", mock_bot.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
