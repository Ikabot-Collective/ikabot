import io
import json
import multiprocessing
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.killTasks import killTasks
from ikabot.helpers.decorators import task
from ikabot.helpers.ipc import (
    IPCServer,
    _resolve_task,
    _validate_task_config,
    is_cli_invocation,
    parse_cli_args,
    parse_config_arg,
    ping_ipc_server,
    send_ipc_request,
)
from ikabot.web.session import parse_world_spec


class TestIPC(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.ika_dir = os.path.join(self.tmp_dir.name, ".ikabot")
        os.makedirs(self.ika_dir, exist_ok=True)
        self.patcher = patch(
            "ikabot.helpers.ipc.get_ikabot_dir", return_value=self.ika_dir
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.tmp_dir.cleanup()

    def test_is_cli_invocation_preserves_predetermined_input(self):
        self.assertFalse(is_cli_invocation(["ikabot"]))
        self.assertFalse(
            is_cli_invocation(["ikabot", "myemail@gmail.com", "1", "7", "1", "20", "0"])
        )
        self.assertFalse(
            is_cli_invocation(["ikabot", "myemail@gmail.com", "--secretpass", "1", "0"])
        )
        self.assertTrue(
            is_cli_invocation(
                [
                    "ikabot",
                    "--email=myemail@gmail.com",
                    "--world=s301",
                    "--task=alertAttacks",
                    '--config={"minutes": 20}',
                ]
            )
        )
        self.assertTrue(is_cli_invocation(["ikabot", "--task", "alertAttacks"]))

    def test_parse_world_spec(self):
        self.assertEqual(parse_world_spec("s301"), ("301", None, "s301"))
        self.assertEqual(parse_world_spec("301"), ("301", None, "301"))
        self.assertEqual(parse_world_spec("s301-en"), ("301", "en", "s301-en"))
        self.assertEqual(parse_world_spec("en-s301"), ("301", "en", "en-s301"))
        self.assertEqual(parse_world_spec("s301", "de"), ("301", "de", "s301"))
        self.assertEqual(parse_world_spec("Alpha"), (None, None, "Alpha"))

    def test_parse_config_arg_variants(self):
        self.assertEqual(parse_config_arg(None), {})
        self.assertEqual(parse_config_arg(""), {})
        self.assertEqual(parse_config_arg('{"minutes": 20}'), {"minutes": 20})
        self.assertEqual(parse_config_arg("{'minutes': 20}"), {"minutes": 20})
        # Windows PowerShell quote-stripping recovery
        raw_cmd = (
            'ikabot --email=a@b.com --world=s301 --task=alertAttacks '
            '"--config={"city_id": "12345", "minutes": 20}"'
        )
        self.assertEqual(
            parse_config_arg("{city_id: 12345, minutes: 20}", raw_cmdline=raw_cmd),
            {"city_id": "12345", "minutes": 20},
        )
        cfg_file = os.path.join(self.tmp_dir.name, "cfg.json")
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump({"minutes": 15}, f)
        self.assertEqual(parse_config_arg(f"@{cfg_file}"), {"minutes": 15})
        args, cfg = parse_cli_args(
            [
                "--email",
                "a@b.com",
                "--world",
                "s301",
                "--task",
                "alertAttacks",
                "--config",
                "{city_name: My",
                "Polis,",
                "minutes: 20}",
            ],
            raw_cmdline=(
                'ikabot --email a@b.com --world s301 --task alertAttacks '
                '--config "{"city_name": "My Polis", "minutes": 20}"'
            ),
        )
        self.assertEqual(args.task, "alertAttacks")
        self.assertEqual(cfg, {"city_name": "My Polis", "minutes": 20})

    def test_validate_task_config(self):
        @task("ipc_dummy_task")
        def dummy(session, minutes, optional_flag=True):
            pass

        name, fn = _resolve_task("ipc_dummy_task")
        self.assertEqual(name, "ipc_dummy_task")
        self.assertEqual(
            _validate_task_config(name, fn, {"minutes": 10, "session": "ignored"}),
            {"minutes": 10},
        )
        with self.assertRaises(ValueError):
            _validate_task_config(name, fn, {})
        with self.assertRaises(ValueError):
            _validate_task_config(name, fn, {"minutes": 10, "bogus": 1})

    @patch("ikabot.helpers.ipc.updateProcessList")
    @patch("ikabot.helpers.ipc.multiprocessing.Process")
    def test_ipc_server_roundtrip_and_start_task(self, mock_proc_cls, mock_update_plist):
        @task("ipc_roundtrip_task")
        def rt_task(session, minutes):
            pass

        fake_proc = MagicMock()
        fake_proc.pid = 54321
        mock_proc_cls.return_value = fake_proc

        fake_session = MagicMock()
        fake_session.logged = True
        fake_session.mail = "myemail@gmail.com"
        fake_session.mundo = "301"
        fake_session.servidor = "en"
        fake_session.username = "PlayerOne"

        server = IPCServer(default_session=fake_session).start()
        try:
            self.assertTrue(ping_ipc_server())
            resp = send_ipc_request(
                {
                    "action": "start_task",
                    "email": "myemail@gmail.com",
                    "world": "s301",
                    "task": "ipc_roundtrip_task",
                    "config": {"minutes": 25},
                }
            )
            self.assertEqual(resp["status"], "ok")
            self.assertEqual(resp["pid"], 54321)
            self.assertEqual(resp["task"], "ipc_roundtrip_task")
            self.assertEqual(resp["world"], "s301-en")
            fake_proc.start.assert_called_once()
            saved_entry = mock_update_plist.call_args.kwargs["programprocesslist"][0]
            self.assertEqual(saved_entry["config"], {"minutes": 25})
        finally:
            server.stop()
        self.assertFalse(ping_ipc_server())

    @patch("ikabot.function.killTasks.banner")
    @patch("ikabot.function.killTasks.enter")
    @patch("ikabot.function.killTasks.updateProcessList")
    def test_kill_tasks_view_config(self, mock_update_plist, _mock_enter, _mock_banner):
        mock_update_plist.return_value = [
            {
                "pid": 9999,
                "action": "alertAttacks",
                "date": 1700000000,
                "status": "running",
                "config": {"minutes": 20},
            }
        ]
        session = MagicMock()
        event = multiprocessing.Event()
        # Enter 'c' to view config, '1' to select first task, then '0' to exit killTasks
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            killTasks(session, event, None, ["c", 1, 0])
        out = buf.getvalue()
        self.assertIn('"minutes": 20', out)
        self.assertIn("alertAttacks", out)
        self.assertTrue(event.is_set())


if __name__ == "__main__":
    unittest.main()
