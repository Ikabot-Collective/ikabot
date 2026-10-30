#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import ast
import ctypes
import importlib
import importlib.util
import inspect
import json
import multiprocessing
import os
import secrets
import socket
import sys
import threading
import time

import psutil

from ikabot import config
from ikabot.helpers.decorators import _TASK_REGISTRY
from ikabot.helpers.logging import getLogger, setLoggedInPlayer
from ikabot.helpers.process import set_child_mode, updateProcessList
from ikabot.helpers.sessionStorage import (
    get_global_config_path,
    get_home_dir,
    get_ikabot_dir,
    init_storage,
    read_json_file,
    write_json_file,
)
from ikabot.web.session import Session, parse_world_spec

logger = getLogger(__name__)

_CLI_FLAGS = (
    "--task",
    "--email",
    "--world",
    "--player",
    "--config",
    "--batch",
    "--server",
    "--help",
    "-h",
)
_BATCH_ENTRY_KEYS = ("task", "config", "email", "world", "server", "player")
_MAX_IPC_MSG_BYTES = 16 * 1024 * 1024
_TASK_STARTUP_TIMEOUT = 60.0
_LOCAL_SERVER = None
_LOCAL_SERVER_LOCK = threading.Lock()


def get_ipc_file_path():
    """Return path to ~/.ikabot/ipc.json."""
    return os.path.join(get_ikabot_dir(), "ipc.json")


def get_ipc_lock_path():
    """Return path to ~/.ikabot/ipc.lock."""
    return os.path.join(get_ikabot_dir(), "ipc.lock")


def get_tasks_dir():
    """Return path to ~/.ikabot/tasks (saved --batch files)."""
    return os.path.join(get_ikabot_dir(), "tasks")


def is_cli_invocation(argv):
    """Return True if argv uses CLI flags (--task, --email, --world, --config, etc.)
    rather than interactive mode or legacy positional predetermined_input.
    """
    for arg in argv[1:]:
        if arg in _CLI_FLAGS:
            return True
        for flag in _CLI_FLAGS:
            if flag.startswith("--") and arg.startswith(flag + "="):
                return True
    return False


class _StartupLock:
    """Cross-process lock file in ~/.ikabot/ipc.lock to prevent race conditions
    when multiple CLI processes check/start the IPC server simultaneously.
    """

    def __init__(self, timeout=5.0):
        self.timeout = timeout
        self.path = get_ipc_lock_path()
        self.acquired = False

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        deadline = time.time() + self.timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, str(os.getpid()).encode("utf-8"))
                finally:
                    os.close(fd)
                self.acquired = True
                return self
            except FileExistsError:
                try:
                    with open(self.path, "r", encoding="utf-8") as f:
                        holder_pid = int(f.read().strip() or "0")
                    stale_age = time.time() - os.path.getmtime(self.path) > 15.0
                    if (holder_pid and not psutil.pid_exists(holder_pid)) or stale_age:
                        os.remove(self.path)
                        continue
                except Exception:
                    pass
                if time.time() >= deadline:
                    return self
                time.sleep(0.05)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.acquired:
            try:
                os.remove(self.path)
            except OSError:
                pass


def _extract_windows_raw_config(raw_cmdline=None):
    """Recover lossless JSON after --config from Windows GetCommandLineW() when
    PowerShell 5.1 strips inner double quotes before building sys.argv.
    """
    if raw_cmdline is None:
        if not config.isWindows:
            return None
        try:
            ctypes.windll.kernel32.GetCommandLineW.restype = ctypes.c_wchar_p
            raw_cmdline = ctypes.windll.kernel32.GetCommandLineW()
        except Exception:
            return None
    if not raw_cmdline:
        return None
    idx = raw_cmdline.rfind("--config")
    if idx == -1:
        return None
    brace_idx = raw_cmdline.find("{", idx)
    if brace_idx == -1:
        return None
    obj, _ = json.JSONDecoder().raw_decode(raw_cmdline[brace_idx:])
    return obj if isinstance(obj, dict) else None


def _read_arg_file(text, opening):
    """Return the contents of @file / bare file path arguments, or text unchanged."""
    if text.startswith("@"):
        filepath = text[1:].strip()
        if not os.path.isfile(filepath):
            raise ValueError(f"File not found: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    if not text.startswith(opening) and os.path.isfile(text):
        with open(text, "r", encoding="utf-8") as f:
            return f.read().strip()
    return text


def parse_config_arg(config_str, raw_cmdline=None):
    """Parse --config value from JSON string, Python dict literal, @file.json,
    or Windows raw command line fallback.
    """
    if config_str is None or str(config_str).strip() == "":
        return {}
    text = _read_arg_file(str(config_str).strip(), "{")

    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("--config must decode to a JSON object/dictionary.")
        return parsed
    except json.JSONDecodeError:
        pass

    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    try:
        recovered = _extract_windows_raw_config(raw_cmdline=raw_cmdline)
        if isinstance(recovered, dict):
            return recovered
    except Exception:
        pass

    raise ValueError(
        f"Invalid --config dictionary: {config_str!r}. Pass a valid JSON object (e.g. '{{\"minutes\": 20}}')."
    )


def parse_batch_arg(batch_str, overrides=None):
    """Parse --batch value (JSON list of task entries, a single entry, or @file.json)
    into a list of start_task requests. email/world/server/player given in ``overrides``
    (the CLI flags) replace the entries' own values; the others are kept.
    """
    if batch_str is None or str(batch_str).strip() == "":
        raise ValueError("--batch cannot be empty.")
    text = _read_arg_file(str(batch_str).strip(), "[")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid --batch JSON: {exc}")
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("--batch must be a non-empty JSON list of task entries.")

    overrides = overrides or {}
    requests = []
    for idx, entry in enumerate(parsed, start=1):
        if not isinstance(entry, dict) or not entry.get("task"):
            raise ValueError(f"Batch entry {idx} must be an object with a 'task' key.")
        unknown = [k for k in entry if k not in _BATCH_ENTRY_KEYS]
        if unknown:
            raise ValueError(
                f"Batch entry {idx} has unknown key(s) {unknown}. Expected: {list(_BATCH_ENTRY_KEYS)}"
            )
        task_config = entry.get("config") or {}
        if not isinstance(task_config, dict):
            raise ValueError(f"Batch entry {idx}: 'config' must be an object.")
        request = {"action": "start_task", "task": entry["task"], "config": task_config}
        for key in ("email", "world", "server", "player"):
            request[key] = overrides.get(key) or entry.get(key)
        requests.append(request)
    return requests


def build_batch_entry(session, process):
    """Build a --batch entry that relaunches a running task (processList row) on this session's account."""
    entry = {
        "task": process["action"],
        "world": f"s{session.mundo}-{session.servidor}",
        "player": session.username,
        "config": process["config"],
    }
    if getattr(session, "mail", ""):
        entry = {"email": session.mail, **entry}
    return entry


def _write_tasks_file(session, name, data):
    """Write ``data`` to ~/.ikabot/tasks/<player>_s<world>-<lang>_<name>.json and return the path."""
    stem = f"{session.username}_s{session.mundo}-{session.servidor}_{name}"
    stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)
    path = os.path.join(get_tasks_dir(), stem + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def save_task_config(session, process):
    """Write one running task's config as a --config file (see build_task_command).
    Returns the path, or None if the task has no config.
    """
    if process.get("config") is None:
        return None
    return _write_tasks_file(session, process["action"], process["config"])


def build_task_command(session, process, config_path):
    """Return the `ikabot --task=... --config=@...` command that relaunches ``process``."""
    entry = build_batch_entry(session, process)
    args = []
    if entry.get("email"):
        args.append(f'--email="{entry["email"]}"')
    args += [
        f'--world={entry["world"]}',
        f'--player="{entry["player"]}"',
        f'--task={entry["task"]}',
        f'--config="@{config_path}"',
    ]
    return "ikabot " + " ".join(args)


def save_batch_file(session, processes, name):
    """Write the configs of ``processes`` to ~/.ikabot/tasks/<player>_s<world>-<lang>_<name>.json
    as a --batch file. Rows without a config are skipped.
    Returns (path, saved_count, skipped_actions).
    """
    entries = [build_batch_entry(session, p) for p in processes if p.get("config") is not None]
    skipped = [p["action"] for p in processes if p.get("config") is None]
    if not entries:
        return None, 0, skipped
    return _write_tasks_file(session, name, entries), len(entries), skipped


def _lookup_registry(task_name):
    if task_name in _TASK_REGISTRY:
        return task_name, _TASK_REGISTRY[task_name]
    low = task_name.lower()
    for reg_name, func in _TASK_REGISTRY.items():
        if reg_name.lower() == low:
            return reg_name, func
    return None, None


def _resolve_task(task_name):
    """Locate (canonical_name, task_func) for a @task-decorated ikabot module."""
    if not task_name or not str(task_name).strip():
        raise ValueError("Task name (--task) cannot be empty.")
    name = str(task_name).strip()

    found_name, found_func = _lookup_registry(name)
    if found_func is not None:
        return found_name, found_func

    func_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "function")
    if os.path.isdir(func_dir):
        for fname in os.listdir(func_dir):
            if not fname.endswith(".py") or fname.startswith("__"):
                continue
            mod_stem = fname[:-3]
            if mod_stem.lower() == name.lower():
                importlib.import_module(f"ikabot.function.{mod_stem}")
                found_name, found_func = _lookup_registry(name)
                if found_func is not None:
                    return found_name, found_func

    custom_paths = read_json_file(get_global_config_path(), {}).get("customModules", [])
    for cpath in custom_paths:
        if not isinstance(cpath, str) or not os.path.isfile(cpath):
            continue
        cstem = os.path.splitext(os.path.basename(cpath))[0]
        if cstem.lower() == name.lower():
            spec = importlib.util.spec_from_file_location(cstem, cpath)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            found_name, found_func = _lookup_registry(name)
            if found_func is not None:
                return found_name, found_func

    # Populate full registry so the error lists all available tasks
    if os.path.isdir(func_dir):
        for fname in sorted(os.listdir(func_dir)):
            if not fname.endswith(".py") or fname.startswith("__"):
                continue
            try:
                importlib.import_module(f"ikabot.function.{fname[:-3]}")
            except Exception:
                pass

    found_name, found_func = _lookup_registry(name)
    if found_func is not None:
        return found_name, found_func

    available = ", ".join(sorted(_TASK_REGISTRY.keys()))
    raise ValueError(
        f"Unknown background task '{name}'. Available tasks: {available}"
    )


def _validate_task_config(task_name, task_func, config_dict):
    """Validate config_dict against the @task function's parameter signature."""
    if not isinstance(config_dict, dict):
        raise ValueError("--config must be a dictionary.")
    raw = {k: v for k, v in config_dict.items() if k != "session"}
    clean = json.loads(json.dumps(raw, default=list))

    target = getattr(task_func, "__wrapped__", task_func)
    sig = inspect.signature(target)
    accepts_var_kw = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )

    required = [
        pname
        for pname, p in sig.parameters.items()
        if pname != "session"
        and p.default is inspect.Parameter.empty
        and p.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    ]
    missing = [pname for pname in required if pname not in clean]
    if missing:
        raise ValueError(
            f"Missing required config parameter(s) for task '{task_name}': {missing}"
        )

    if not accepts_var_kw:
        allowed = {pname for pname in sig.parameters if pname != "session"}
        unknown = [k for k in clean if k not in allowed]
        if unknown:
            raise ValueError(
                f"Unknown config parameter(s) for task '{task_name}': {unknown}. Expected: {sorted(allowed)}"
            )

    return clean


def _run_ipc_task(task_name, session, task_config, started=None):
    """Child-process entry point for tasks launched via CLI/IPC."""
    if started is not None:
        # arguments are unpickled by now: the launching process may exit
        started.set()
    try:
        sys.stdin = open(os.devnull, "r")
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")
    except Exception:
        pass

    setLoggedInPlayer(getattr(session, "username", ""))
    set_child_mode(session)
    _, task_func = _resolve_task(task_name)
    try:
        task_func(session=session, **task_config)
    except Exception:
        logger.error("Unhandled exception in IPC task %s", task_name, exc_info=True)
        raise


def _send_json_line(sock, payload):
    data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    sock.sendall(data)


def _recv_json_line(sock):
    buf = bytearray()
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf.extend(chunk)
        if b"\n" in chunk:
            break
        if len(buf) > _MAX_IPC_MSG_BYTES:
            raise ValueError("IPC message exceeded maximum size.")
    if not buf:
        raise EOFError("Empty IPC message.")
    line = bytes(buf).split(b"\n", 1)[0]
    return json.loads(line.decode("utf-8"))


class IPCServer:
    """Loopback socket server stored in ~/.ikabot/ipc.json so external CLI calls
    can add background tasks to an already-running ikabot main process.
    """

    def __init__(self, default_session=None):
        self._sock = None
        self.port = None
        self.authkey = secrets.token_hex(32)
        self._lock = threading.Lock()
        self._count_lock = threading.Lock()
        self._active_requests = 0
        self._running = False
        self._sessions = [default_session] if default_session is not None else []
        self._thread = None

    @property
    def has_active_requests(self):
        with self._count_lock:
            return self._active_requests > 0

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        sock.listen(16)
        self._sock = sock
        self.port = sock.getsockname()[1]
        self._running = True

        ipc_path = get_ipc_file_path()
        write_json_file(
            ipc_path,
            {
                "pid": os.getpid(),
                "host": "127.0.0.1",
                "port": self.port,
                "authkey": self.authkey,
            },
        )
        try:
            os.chmod(ipc_path, 0o600)
        except OSError:
            pass

        self._thread = threading.Thread(
            target=self._accept_loop, name="ikabot-ipc-server", daemon=True
        )
        self._thread.start()
        return self

    def stop(self):
        self._running = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        ipc_path = get_ipc_file_path()
        try:
            info = read_json_file(ipc_path, {})
            if info.get("pid") == os.getpid() and os.path.exists(ipc_path):
                os.remove(ipc_path)
        except OSError:
            pass

    def _accept_loop(self):
        while self._running and self._sock is not None:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                break
            # counted from accept() on, so stopping the server can wait for it
            with self._count_lock:
                self._active_requests += 1
            threading.Thread(
                target=self._handle_client, args=(conn,), daemon=True
            ).start()

    def _handle_client(self, conn):
        try:
            self._serve_connection(conn)
        finally:
            with self._count_lock:
                self._active_requests -= 1

    def _serve_connection(self, conn):
        with conn:
            conn.settimeout(30.0)
            try:
                msg = _recv_json_line(conn)
                if not isinstance(msg, dict) or not secrets.compare_digest(
                    str(msg.get("authkey", "")), self.authkey
                ):
                    _send_json_line(
                        conn, {"status": "error", "error": "Unauthorized IPC request."}
                    )
                    return
                resp = self.handle_request(msg)
                _send_json_line(conn, resp)
            except Exception as exc:
                try:
                    _send_json_line(conn, {"status": "error", "error": str(exc)})
                except Exception:
                    pass

    def _session_matches(self, sess, email, world, server, player=None):
        if sess is None or not getattr(sess, "logged", False):
            return False
        if player and str(player).strip():
            sess_player = (getattr(sess, "username", None) or "").strip().lower()
            if sess_player != str(player).strip().lower():
                return False
        sess_mail = (getattr(sess, "mail", None) or "").strip().lower()
        if email and str(email).strip() and str(email).strip() != "default_user":
            if sess_mail != str(email).strip().lower():
                return False
        elif email == "default_user":
            if sess_mail != "":
                return False

        want_mundo, want_servidor, raw_world = parse_world_spec(world, server)
        if not raw_world and want_servidor is None:
            return True
        if want_mundo is not None:
            if str(getattr(sess, "mundo", "")) != want_mundo:
                return False
            if want_servidor is not None:
                s_srv = (getattr(sess, "servidor", "") or "").lower()
                l_srv = (getattr(sess, "login_servidor", "") or "").lower()
                if want_servidor not in (s_srv, l_srv):
                    return False
            return True
        if raw_world:
            if (getattr(sess, "word", "") or "").strip().lower() != raw_world.lower():
                return False
            if want_servidor is not None:
                s_srv = (getattr(sess, "servidor", "") or "").lower()
                l_srv = (getattr(sess, "login_servidor", "") or "").lower()
                if want_servidor not in (s_srv, l_srv):
                    return False
        return True

    def _get_or_create_session(self, email, world, server, player=None):
        matches = [
            sess
            for sess in self._sessions
            if self._session_matches(sess, email, world, server, player)
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                "Multiple active sessions match; please specify --email, --world and/or --player."
            )
        sess = Session.from_saved(mail=email, world=world, server=server, player=player)
        self._sessions.append(sess)
        return sess

    def handle_request(self, request):
        action = request.get("action")
        if action == "ping":
            return {"status": "ok", "pid": os.getpid()}

        try:
            with self._lock:
                if action == "start_task":
                    return self._start_task(request)
                return {"status": "error", "error": f"Unknown IPC action: {action!r}"}
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            logger.error("IPC request failed", exc_info=True)
            return {"status": "error", "error": str(exc)}

    def _start_task(self, request):
        task_name = request.get("task")
        config_dict = request.get("config") or {}
        email = request.get("email")
        world = request.get("world")
        server = request.get("server")
        player = request.get("player")

        canonical_name, task_func = _resolve_task(task_name)
        clean_config = _validate_task_config(canonical_name, task_func, config_dict)
        session = self._get_or_create_session(email, world, server, player)

        started = multiprocessing.Event()
        proc = multiprocessing.Process(
            target=_run_ipc_task,
            args=(canonical_name, session, clean_config, started),
            name=canonical_name,
        )
        proc.start()
        # A spawned child reads its arguments through a handle owned by this process,
        # so wait for it before answering: a CLI launcher exits right after the answer.
        if not started.wait(timeout=_TASK_STARTUP_TIMEOUT) and not proc.is_alive():
            raise RuntimeError(
                f"Task '{canonical_name}' exited during startup (exit code {proc.exitcode})."
            )

        entry = {
            "pid": proc.pid,
            "action": canonical_name,
            "date": time.time(),
            "status": "started",
            "config": clean_config,
        }
        updateProcessList(session, programprocesslist=[entry])

        return {
            "status": "ok",
            "pid": proc.pid,
            "task": canonical_name,
            "email": session.mail,
            "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username,
            "host_pid": os.getpid(),
        }


def send_ipc_request(request, connect_timeout=1.5, read_timeout=120.0):
    """Send a request dict to the running ikabot IPC server if one exists.
    Returns the decoded response dict, or None if no live server is reachable.
    """
    ipc_path = get_ipc_file_path()
    info = read_json_file(ipc_path, None)
    if not isinstance(info, dict):
        return None
    pid = info.get("pid")
    host = info.get("host") or "127.0.0.1"
    port = info.get("port")
    authkey = info.get("authkey")
    if not pid or not port or not authkey or not psutil.pid_exists(int(pid)):
        return None

    try:
        with socket.create_connection((host, int(port)), timeout=connect_timeout) as sock:
            sock.settimeout(read_timeout)
            payload = dict(request)
            payload["authkey"] = authkey
            _send_json_line(sock, payload)
            return _recv_json_line(sock)
    except OSError:
        return None
    except EOFError:
        return None


def ping_ipc_server():
    """Return True if a live ikabot IPC server responds on ~/.ikabot/ipc.json."""
    resp = send_ipc_request({"action": "ping"}, connect_timeout=1.0, read_timeout=2.0)
    return isinstance(resp, dict) and resp.get("status") == "ok"


def ensure_ipc_server(default_session=None):
    """Ensure an IPC server is running in this interactive ikabot process if no
    other ikabot main process on the system already owns ~/.ikabot/ipc.json.
    """
    global _LOCAL_SERVER
    with _LOCAL_SERVER_LOCK:
        if _LOCAL_SERVER is not None:
            if default_session is not None and default_session not in _LOCAL_SERVER._sessions:
                _LOCAL_SERVER._sessions.insert(0, default_session)
            return _LOCAL_SERVER
        with _StartupLock():
            if ping_ipc_server():
                return None
            _LOCAL_SERVER = IPCServer(default_session=default_session).start()
            return _LOCAL_SERVER


def stop_ipc_server():
    """Stop this process's IPC server if one was started."""
    global _LOCAL_SERVER
    with _LOCAL_SERVER_LOCK:
        if _LOCAL_SERVER is not None:
            _LOCAL_SERVER.stop()
            _LOCAL_SERVER = None


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def build_cli_parser():
    parser = _JsonArgumentParser(
        prog="ikabot",
        description="Start ikabot background tasks via CLI / IPC.",
    )
    parser.add_argument("--email", default=None, help="Saved account email address")
    parser.add_argument(
        "--world",
        default=None,
        help="Target world (e.g. s301, 301, s301-en, or world name)",
    )
    parser.add_argument(
        "--server",
        default=None,
        help="Optional server language disambiguator (e.g. en, de)",
    )
    parser.add_argument(
        "--player",
        default=None,
        help="In-game player name, needed when the lobby has several accounts on the same world",
    )
    parser.add_argument(
        "--task", default=None, help="Name of the @task module (e.g. alertAttacks)"
    )
    parser.add_argument(
        "--config",
        default=None,
        help="JSON config dict for the task (or @path/to/config.json)",
    )
    parser.add_argument(
        "--batch",
        default=None,
        help='JSON list of tasks to start, e.g. [{"task": "alertAttacks", "config": {"minutes": 20}}] '
        "(or @path/to/tasks.json). Entries may set email/world/server/player; "
        "those flags, when given on the command line, override them for every entry.",
    )
    return parser


def _check_task_or_batch(parser, args):
    if args.batch is not None:
        if args.task is not None or args.config is not None:
            parser.error("--batch cannot be combined with --task or --config.")
    elif not args.task:
        parser.error("one of the arguments --task or --batch is required")


def parse_cli_args(argv, raw_cmdline=None):
    parser = build_cli_parser()
    args, extras = parser.parse_known_args(argv)
    _check_task_or_batch(parser, args)
    if not extras:
        return args, parse_config_arg(args.config, raw_cmdline=raw_cmdline)

    if not any(e.startswith("-") for e in extras):
        try:
            recovered = _extract_windows_raw_config(raw_cmdline=raw_cmdline)
            if isinstance(recovered, dict):
                return args, recovered
        except Exception:
            pass

    parser.error(f"unrecognized arguments: {' '.join(extras)}")


def _dispatch_request(request, local_server):
    """Send one request to the running IPC server, or handle it in this process.
    Returns (response, local_server); local_server is set once this process owns the IPC server.
    """
    if local_server is not None:
        return local_server.handle_request(request), local_server
    response = send_ipc_request(request)
    if response is not None:
        return response, None
    # Existing server exited right after ping; claim IPC server locally
    with _StartupLock():
        if not ping_ipc_server():
            local_server = IPCServer().start()
    if local_server is not None:
        return local_server.handle_request(request), local_server
    response = send_ipc_request(request) or {
        "status": "error",
        "error": "Failed to communicate with running ikabot IPC server.",
    }
    return response, None


def run_cli_task(argv):
    """Entry point for CLI task queries (`ikabot --email=... --world=... --task=... --config=...`
    or `ikabot --batch=@tasks.json`)."""
    if "-h" in argv or "--help" in argv:
        parser = build_cli_parser()
        parser.print_help()
        return

    try:
        args, config_dict = parse_cli_args(argv)
        account_flags = {
            "email": args.email,
            "world": args.world,
            "server": args.server,
            "player": args.player,
        }
        if args.batch is not None:
            requests = parse_batch_arg(args.batch, overrides=account_flags)
        else:
            requests = [
                dict(account_flags, action="start_task", task=args.task, config=config_dict)
            ]
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), flush=True)
        sys.exit(1)

    os.chdir(get_home_dir())
    init_storage()

    local_server = None
    with _StartupLock():
        if not ping_ipc_server():
            local_server = IPCServer().start()

    responses = []
    for request in requests:
        response, local_server = _dispatch_request(request, local_server)
        responses.append(response)

    output = responses if args.batch is not None else responses[0]
    print(json.dumps(output, ensure_ascii=False), flush=True)
    all_ok = all(r.get("status") == "ok" for r in responses)

    if local_server is not None:
        local_server.stop()
        # let requests from other CLI calls that reached us finish
        while local_server.has_active_requests:
            time.sleep(0.2)

    # Like the menu's exit, return the shell and leave the tasks running in the
    # background. os._exit skips multiprocessing's atexit hook, which would wait for them.
    os._exit(0 if all_ok else 1)
