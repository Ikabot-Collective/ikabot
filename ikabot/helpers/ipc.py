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

_CLI_FLAGS = ("--task", "--email", "--world", "--config", "--server", "--help", "-h")
_MAX_IPC_MSG_BYTES = 16 * 1024 * 1024
_LOCAL_SERVER = None
_LOCAL_SERVER_LOCK = threading.Lock()


def get_ipc_file_path():
    """Return path to ~/.ikabot/ipc.json."""
    return os.path.join(get_ikabot_dir(), "ipc.json")


def get_ipc_lock_path():
    """Return path to ~/.ikabot/ipc.lock."""
    return os.path.join(get_ikabot_dir(), "ipc.lock")


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


def parse_config_arg(config_str, raw_cmdline=None):
    """Parse --config value from JSON string, Python dict literal, @file.json,
    or Windows raw command line fallback.
    """
    if config_str is None or str(config_str).strip() == "":
        return {}
    text = str(config_str).strip()

    if text.startswith("@"):
        filepath = text[1:].strip()
        if not os.path.isfile(filepath):
            raise ValueError(f"Config file not found: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read().strip()
    elif not text.startswith("{") and os.path.isfile(text):
        with open(text, "r", encoding="utf-8") as f:
            text = f.read().strip()

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


def _run_ipc_task(task_name, session, task_config):
    """Child-process entry point for tasks launched via CLI/IPC."""
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
            threading.Thread(
                target=self._handle_client, args=(conn,), daemon=True
            ).start()

    def _handle_client(self, conn):
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

    def _session_matches(self, sess, email, world, server):
        if sess is None or not getattr(sess, "logged", False):
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

    def _get_or_create_session(self, email, world, server):
        matches = [
            sess
            for sess in self._sessions
            if self._session_matches(sess, email, world, server)
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                "Multiple active sessions match; please specify --email and --world."
            )
        sess = Session.from_saved(mail=email, world=world, server=server)
        self._sessions.append(sess)
        return sess

    def handle_request(self, request):
        action = request.get("action")
        if action == "ping":
            return {"status": "ok", "pid": os.getpid()}

        with self._count_lock:
            self._active_requests += 1
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
        finally:
            with self._count_lock:
                self._active_requests -= 1

    def _start_task(self, request):
        task_name = request.get("task")
        config_dict = request.get("config") or {}
        email = request.get("email")
        world = request.get("world")
        server = request.get("server")

        canonical_name, task_func = _resolve_task(task_name)
        clean_config = _validate_task_config(canonical_name, task_func, config_dict)
        session = self._get_or_create_session(email, world, server)

        proc = multiprocessing.Process(
            target=_run_ipc_task,
            args=(canonical_name, session, clean_config),
            name=canonical_name,
        )
        proc.start()

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
        "--task", required=True, help="Name of the @task module (e.g. alertAttacks)"
    )
    parser.add_argument(
        "--config",
        default="{}",
        help="JSON config dict for the task (or @path/to/config.json)",
    )
    return parser


def parse_cli_args(argv, raw_cmdline=None):
    parser = build_cli_parser()
    args, extras = parser.parse_known_args(argv)
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


def run_cli_task(argv):
    """Entry point for CLI task queries (`ikabot --email=... --world=... --task=... --config=...`)."""
    if "-h" in argv or "--help" in argv:
        parser = build_cli_parser()
        parser.print_help()
        return

    try:
        args, config_dict = parse_cli_args(argv)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), flush=True)
        sys.exit(1)

    os.chdir(get_home_dir())
    init_storage()

    request = {
        "action": "start_task",
        "email": args.email,
        "world": args.world,
        "server": args.server,
        "task": args.task,
        "config": config_dict,
    }

    local_server = None
    with _StartupLock():
        if not ping_ipc_server():
            local_server = IPCServer().start()

    if local_server is None:
        response = send_ipc_request(request)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
            sys.exit(0 if response.get("status") == "ok" else 1)
        # Existing server exited right after ping; claim IPC server locally
        with _StartupLock():
            if not ping_ipc_server():
                local_server = IPCServer().start()
        if local_server is None:
            response = send_ipc_request(request) or {
                "status": "error",
                "error": "Failed to communicate with running ikabot IPC server.",
            }
            print(json.dumps(response, ensure_ascii=False), flush=True)
            sys.exit(0 if response.get("status") == "ok" else 1)

    response = local_server.handle_request(request)
    print(json.dumps(response, ensure_ascii=False), flush=True)
    if response.get("status") != "ok":
        local_server.stop()
        sys.exit(1)

    try:
        while multiprocessing.active_children() or local_server.has_active_requests:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        local_server.stop()
