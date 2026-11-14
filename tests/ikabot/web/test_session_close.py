import json
import os
import tempfile
import unittest
from unittest import mock

from ikabot.helpers.sessionStorage import get_task_pids_by_account
from ikabot.web.session import Session

MY_PID = 11
OWN_TASK = 12  # another task of the account whose session was lost
OTHER_ACCOUNT_TASK = 21
MANAGER = 99  # multiprocessing manager of the menu, in no process list


def proc(pid):
    p = mock.MagicMock()
    p.pid = pid
    return p


class TestCloseIkabot(unittest.TestCase):
    def setUp(self):
        self.session = Session.__new__(Session)
        self.session.mail = ""
        self.session.username = "PlayerOne"
        self.session.mundo = "74"
        self.session.servidor = "es"
        self.session.padre = False

        self.parent = mock.MagicMock()
        self.parent.name.return_value = "python.exe"
        self.parent.cmdline.return_value = ["python.exe", "-m", "ikabot"]
        self.children = {pid: proc(pid) for pid in (MY_PID, OWN_TASK, OTHER_ACCOUNT_TASK, MANAGER)}
        self.parent.children.return_value = list(self.children.values())

    def close(self, pids_by_account):
        with mock.patch("psutil.Process", return_value=self.parent), \
                mock.patch("ikabot.web.session.os.getpid", return_value=MY_PID), \
                mock.patch("ikabot.web.session.os._exit", side_effect=SystemExit), \
                mock.patch("ikabot.web.session.get_task_pids_by_account", return_value=pids_by_account):
            with self.assertRaises(SystemExit):
                self.session._Session__closeIkabot()

    def terminated(self):
        return {pid for pid, p in self.children.items() if p.terminate.called}

    def test_shared_parent_only_closes_this_account(self):
        self.close({
            ("", "PlayerOne", "74", "es"): {MY_PID, OWN_TASK},
            ("", "PlayerTwo", "74", "es"): {OTHER_ACCOUNT_TASK},
        })
        self.assertEqual(self.terminated(), {OWN_TASK})
        self.parent.terminate.assert_not_called()

    def test_single_account_parent_closes_everything(self):
        self.close({
            ("", "PlayerOne", "74", "es"): {MY_PID, OWN_TASK, OTHER_ACCOUNT_TASK},
            ("", "PlayerTwo", "74", "es"): set(),
        })
        self.assertEqual(self.terminated(), {OWN_TASK, OTHER_ACCOUNT_TASK, MANAGER})
        self.parent.terminate.assert_called_once()

    def test_menu_waiting_for_the_configurator_is_closed(self):
        # padre is still True before the configurator hands the task over: the menu waits on it
        self.session.padre = True
        self.close({
            ("", "PlayerOne", "74", "es"): {MY_PID, OWN_TASK},
            ("", "PlayerTwo", "74", "es"): {OTHER_ACCOUNT_TASK},
        })
        self.assertEqual(self.terminated(), {OWN_TASK, OTHER_ACCOUNT_TASK, MANAGER})
        self.parent.terminate.assert_called_once()


class TestTaskPidsByAccount(unittest.TestCase):
    def test_reads_every_saved_account(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("ikabot.helpers.sessionStorage.get_users_dir", return_value=tmp):
                with open(os.path.join(tmp, "default_user.json"), "w", encoding="utf-8") as f:
                    json.dump({"email": "", "players": {
                        "PlayerOne": {"74": {"es": {"processList": [{"pid": 1}, {"pid": 2}]}}},
                        "PlayerTwo": {"74": {"es": {"processList": [{"pid": 3}]}}},
                    }}, f)
                with open(os.path.join(tmp, "a_b.com.json"), "w", encoding="utf-8") as f:
                    json.dump({"email": "A@b.com", "players": {
                        "PlayerThree": {"1": {"en": {"processList": [{"pid": 4}]}}},
                    }}, f)
                self.assertEqual(get_task_pids_by_account(), {
                    ("", "PlayerOne", "74", "es"): {1, 2},
                    ("", "PlayerTwo", "74", "es"): {3},
                    ("a@b.com", "PlayerThree", "1", "en"): {4},
                })


if __name__ == "__main__":
    unittest.main()
