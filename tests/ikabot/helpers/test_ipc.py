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
    _dispatch_request,
    _resolve_task,
    _validate_task_config,
    build_batch_entry,
    is_cli_invocation,
    parse_batch_arg,
    parse_cli_args,
    parse_config_arg,
    ping_ipc_server,
    run_cli_task,
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

    @staticmethod
    def _started_process(fake_proc):
        """multiprocessing.Process stand-in whose child reports it started right away."""
        def factory(*args, **kwargs):
            kwargs["args"][3].set()
            return fake_proc
        return factory

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
        mock_proc_cls.side_effect = self._started_process(fake_proc)

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
        # Enter 'c' to view config, '1' to select first task, '' to go back without saving, then '0' to exit killTasks
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            killTasks(session, event, None, ["c", 1, "", 0])
        out = buf.getvalue()
        self.assertIn('"minutes": 20', out)
        self.assertIn("alertAttacks", out)
        self.assertTrue(event.is_set())
        self.assertFalse(os.path.exists(os.path.join(self.ika_dir, "tasks")))

    def _player_session(self):
        session = MagicMock()
        session.mail = ""
        session.username = "PlayerOne"
        session.mundo = "74"
        session.servidor = "es"
        return session

    @patch("ikabot.function.killTasks.banner")
    @patch("ikabot.function.killTasks.enter")
    @patch("ikabot.function.killTasks.updateProcessList")
    def test_kill_tasks_save_one_and_all(self, mock_update_plist, _mock_enter, _mock_banner):
        mock_update_plist.return_value = [
            {"pid": 1, "action": "alertAttacks", "date": 1700000000, "status": "running", "config": {"minutes": 20}},
            {"pid": 2, "action": "webServer", "date": 1700000000, "status": "running",
             "config": {"port": "43280", "local_network_ip": "10.0.0.2"}},
            {"pid": 3, "action": "oldTask", "date": 1700000000, "status": "running"},
        ]
        session = self._player_session()
        tasks_dir = os.path.join(self.ika_dir, "tasks")
        one_path = os.path.join(tasks_dir, "PlayerOne_s74-es_webServer.json")
        all_path = os.path.join(tasks_dir, "PlayerOne_s74-es_all.json")
        with patch("sys.stdout", io.StringIO()) as out:
            # save the webServer config, then save all, then exit
            killTasks(session, multiprocessing.Event(), None, ["c", 2, "s", "a", 0])
        shown = out.getvalue()

        # a single task is saved as a plain --config file and relaunched with --task
        self.assertIn(
            f'ikabot --world=s74-es --player="PlayerOne" --task=webServer --config="@{one_path}"',
            shown,
        )
        self.assertEqual(
            parse_config_arg("@" + one_path),
            {"port": "43280", "local_network_ip": "10.0.0.2"},
        )
        # all tasks are saved as a --batch file
        self.assertIn(f'ikabot --batch="@{all_path}"', shown)
        with open(all_path, encoding="utf-8") as f:
            saved_all = json.load(f)
        self.assertEqual([e["task"] for e in saved_all], ["alertAttacks", "webServer"])
        # the saved file is a valid --batch file
        requests = parse_batch_arg("@" + os.path.join(tasks_dir, "PlayerOne_s74-es_all.json"))
        self.assertEqual(requests[0]["player"], "PlayerOne")
        self.assertEqual(requests[0]["world"], "s74-es")
        self.assertEqual(requests[0]["config"], {"minutes": 20})

    def test_build_batch_entry_includes_email(self):
        session = self._player_session()
        session.mail = "a@b.com"
        entry = build_batch_entry(session, {"action": "alertAttacks", "config": {"minutes": 5}})
        self.assertEqual(entry["email"], "a@b.com")
        self.assertEqual(entry["task"], "alertAttacks")

    def test_parse_batch_arg(self):
        batch = (
            '[{"task": "alertAttacks", "config": {"minutes": 20}},'
            ' {"task": "webServer", "world": "s74-es", "player": "PlayerTwo"}]'
        )
        requests = parse_batch_arg(batch)
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0]["action"], "start_task")
        self.assertIsNone(requests[0]["player"])
        self.assertEqual(requests[1]["player"], "PlayerTwo")
        self.assertEqual(requests[1]["world"], "s74-es")
        self.assertEqual(requests[1]["config"], {})
        # flags given on the command line win over the file, the rest is kept
        overrides = {"email": None, "world": None, "server": None, "player": "PlayerOne"}
        requests = parse_batch_arg(batch, overrides=overrides)
        self.assertEqual([r["player"] for r in requests], ["PlayerOne", "PlayerOne"])
        self.assertEqual(requests[1]["world"], "s74-es")
        # a single entry object is accepted too
        self.assertEqual(len(parse_batch_arg('{"task": "alertAttacks"}')), 1)
        for bad in ("[]", '[{"config": {}}]', '[{"task": "x", "bogus": 1}]',
                    '[{"task": "x", "config": [1]}]', "not json"):
            with self.assertRaises(ValueError):
                parse_batch_arg(bad)

    def test_parse_cli_args_task_or_batch(self):
        args, cfg = parse_cli_args(["--batch", "[]", "--player", "PlayerOne"])
        self.assertEqual(args.batch, "[]")
        self.assertEqual(args.player, "PlayerOne")
        self.assertEqual(cfg, {})
        with self.assertRaises(ValueError):
            parse_cli_args(["--world", "s74"])
        with self.assertRaises(ValueError):
            parse_cli_args(["--batch", "[]", "--task", "alertAttacks"])
        self.assertTrue(is_cli_invocation(["ikabot", "--batch=@tasks.json"]))

    def test_session_matches_player(self):
        server = IPCServer()
        sess = MagicMock()
        sess.logged = True
        sess.mail = ""
        sess.username = "PlayerOne"
        sess.mundo = "74"
        sess.servidor = "es"
        sess.login_servidor = "es"
        self.assertTrue(server._session_matches(sess, None, "s74-es", None, "playerone"))
        self.assertFalse(server._session_matches(sess, None, "s74-es", None, "PlayerTwo"))
        self.assertTrue(server._session_matches(sess, None, None, None, None))

    @patch("ikabot.helpers.ipc.Session.from_saved")
    @patch("ikabot.helpers.ipc.updateProcessList")
    @patch("ikabot.helpers.ipc.multiprocessing.Process")
    def test_batch_dispatch_through_running_server(self, mock_proc_cls, _mock_update_plist, mock_from_saved):
        @task("ipc_batch_task")
        def batch_task(session, minutes):
            pass

        mock_proc_cls.side_effect = self._started_process(MagicMock(pid=777))
        menu_session = MagicMock(logged=True, mail="", username="PlayerOne", mundo="74", servidor="es")
        other_session = MagicMock(logged=True, mail="", username="PlayerTwo", mundo="74", servidor="es")
        mock_from_saved.return_value = other_session

        server = IPCServer(default_session=menu_session).start()
        try:
            requests = parse_batch_arg(
                '[{"task": "ipc_batch_task", "config": {"minutes": 1}},'
                ' {"task": "ipc_batch_task", "config": {"minutes": 2}, "player": "PlayerTwo"}]'
            )
            responses = []
            local_server = None
            for request in requests:
                response, local_server = _dispatch_request(request, local_server)
                responses.append(response)
            self.assertIsNone(local_server)
            self.assertEqual([r["status"] for r in responses], ["ok", "ok"])
            self.assertEqual([r["username"] for r in responses], ["PlayerOne", "PlayerTwo"])
            self.assertEqual(mock_from_saved.call_args.kwargs["player"], "PlayerTwo")
        finally:
            server.stop()

    @patch("ikabot.helpers.ipc._TASK_STARTUP_TIMEOUT", 0.1)
    @patch("ikabot.helpers.ipc.updateProcessList")
    @patch("ikabot.helpers.ipc.multiprocessing.Process")
    def test_task_dying_during_startup_is_an_error(self, mock_proc_cls, _mock_update_plist):
        @task("ipc_dying_task")
        def dying_task(session):
            pass

        mock_proc_cls.return_value = MagicMock(pid=1, exitcode=1, **{"is_alive.return_value": False})
        menu_session = MagicMock(logged=True, mail="", username="PlayerOne", mundo="74", servidor="es")
        resp = IPCServer(default_session=menu_session).handle_request(
            {"action": "start_task", "task": "ipc_dying_task", "config": {}}
        )
        self.assertEqual(resp["status"], "error")
        self.assertIn("exited during startup", resp["error"])

    @patch("ikabot.helpers.ipc.init_storage")
    @patch("ikabot.helpers.ipc.os.chdir")
    @patch("ikabot.helpers.ipc.os._exit", side_effect=SystemExit)
    @patch("ikabot.helpers.ipc.IPCServer.handle_request", return_value={"status": "ok", "pid": 1})
    def test_cli_returns_right_after_launching(self, _mock_handle, mock_exit, _mock_chdir, _mock_init):
        with patch("sys.stdout", io.StringIO()) as out:
            with self.assertRaises(SystemExit):
                run_cli_task(["--task", "alertAttacks", "--config", '{"minutes": 20}'])
        # exits at once (leaving the tasks running) instead of waiting for them
        mock_exit.assert_called_once_with(0)
        self.assertEqual(json.loads(out.getvalue())["status"], "ok")
        self.assertFalse(ping_ipc_server())


if __name__ == "__main__":
    unittest.main()
