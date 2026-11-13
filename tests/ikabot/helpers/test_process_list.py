import logging
import multiprocessing
import os
import time

import pytest

from ikabot.helpers.process import updateProcessList
from ikabot.helpers.sessionStorage import get_session_data, init_storage, set_session_data
from ikabot.web.session import Session


class FakeSession:
    mail = "test@example.com"
    username = "user"
    mundo = "1"
    servidor = "es"
    logger = logging.getLogger("test_process_list")

    def getSessionData(self):
        return get_session_data(self)

    def setSessionData(self, sessionData, shared=False, keep_process_list=True):
        set_session_data(self, sessionData, shared=shared, keep_process_list=keep_process_list)

    setStatus = Session.setStatus
    updateProcessEntry = Session.updateProcessEntry


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    init_storage()
    return FakeSession()


def row(pid, **extra):
    return dict({"pid": pid, "action": "task", "date": 0, "status": "started"}, **extra)


def test_stale_snapshot_does_not_drop_registered_processes(session):
    set_session_data(session, {"processList": [row(1), row(2)]})

    stale = {"processList": [row(1)], "actionRequestToken": "abc"}
    session.setSessionData(stale)

    data = session.getSessionData()
    assert [p["pid"] for p in data["processList"]] == [1, 2]
    assert data["actionRequestToken"] == "abc"


def test_keep_process_list_false_replaces_the_list(session):
    set_session_data(session, {"processList": [row(1), row(2)]})

    session.setSessionData({"processList": [row(1)]}, keep_process_list=False)

    assert [p["pid"] for p in session.getSessionData()["processList"]] == [1]


def test_update_process_entry_changes_only_that_row(session):
    set_session_data(session, {"processList": [row(1), row(2)]})

    session.updateProcessEntry(2, action="lcm_module")

    processes = {p["pid"]: p for p in session.getSessionData()["processList"]}
    assert processes[2]["action"] == "lcm_module"
    assert processes[1]["action"] == "task"


def test_set_status_updates_the_current_process_row(session):
    set_session_data(session, {"processList": [row(os.getpid()), row(1)]})

    session.setStatus("running")

    processes = {p["pid"]: p for p in session.getSessionData()["processList"]}
    assert processes[os.getpid()]["status"] == "running"
    assert processes[1]["status"] == "started"


def _register(start, stop):
    session = FakeSession()
    start.wait()
    updateProcessList(session, [row(os.getpid())])
    stop.wait()


def test_concurrent_registration_keeps_every_process(session):
    start, stop = multiprocessing.Event(), multiprocessing.Event()
    procs = [multiprocessing.Process(target=_register, args=(start, stop)) for _ in range(10)]
    [p.start() for p in procs]
    try:
        start.set()
        expected = {p.pid for p in procs}
        deadline = time.time() + 20
        listed = set()
        while time.time() < deadline:
            listed = {p["pid"] for p in updateProcessList(session)}
            if expected <= listed:
                break
            time.sleep(0.2)
        assert expected <= listed
    finally:
        stop.set()
        [p.join() for p in procs]
