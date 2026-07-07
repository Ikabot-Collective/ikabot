import multiprocessing
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.helpers.ikaLock import sessionFileLock


MAIL = "stress@test.com"
PASSWORD = "pw"
WORKERS = 4
WRITES = 8


class SessionStub:
    mail = MAIL
    padre = True
    username = "player"
    mundo = "1"
    servidor = "en"


def _stress_worker(tmpdir, worker_id, writes):
    """Each worker repeatedly merges its own key into the shared session data
    and re-reads the file. Any lost update or corrupted file raises."""
    os.chdir(tmpdir)
    from ikabot.helpers.aesCipher import AESCipher

    session = SessionStub()
    cipher = AESCipher(MAIL, PASSWORD)
    for i in range(writes):
        cipher.setSessionData(session, {"key_{}".format(worker_id): i}, shared=True)
        data = cipher.getSessionData(session)
        assert "shared" in data, "file corrupted or write lost"


def _lock_holder(tmpdir, locked_event, hold_seconds):
    os.chdir(tmpdir)
    from ikabot.helpers.ikaLock import sessionFileLock as lock

    with lock():
        locked_event.set()
        time.sleep(hold_seconds)


class TestSessionFileLock(unittest.TestCase):

    def setUp(self):
        self._old_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._old_cwd)
        self._tmp.cleanup()

    def test_lock_is_reentrant(self):
        with sessionFileLock():
            with sessionFileLock():
                pass  # nesting must not deadlock

    def test_lock_can_be_retaken_after_release(self):
        with sessionFileLock():
            pass
        with sessionFileLock():
            pass

    def test_timeout_when_other_process_holds_lock(self):
        locked = multiprocessing.Event()
        holder = multiprocessing.Process(
            target=_lock_holder, args=(self._tmp.name, locked, 10)
        )
        holder.start()
        try:
            self.assertTrue(locked.wait(30), "lock holder process failed to start")
            with patch.object(sessionFileLock, 'timeout', 0.5):
                with self.assertRaises(TimeoutError):
                    with sessionFileLock():
                        pass
        finally:
            holder.terminate()
            holder.join()


class TestConcurrentSessionData(unittest.TestCase):
    """The regression test for the .ikabot corruption / lost-update bug:
    several processes hammering setSessionData concurrently must never
    corrupt the file nor lose each other's writes."""

    def test_parallel_writers_lose_nothing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            processes = [
                multiprocessing.Process(
                    target=_stress_worker, args=(tmpdir, worker_id, WRITES)
                )
                for worker_id in range(WORKERS)
            ]
            for p in processes:
                p.start()
            for p in processes:
                p.join(120)
                self.assertEqual(p.exitcode, 0, "worker crashed (corruption or lost write)")

            # verify every worker's final write survived
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                from ikabot.helpers.aesCipher import AESCipher
                cipher = AESCipher(MAIL, PASSWORD)
                data = cipher.getSessionData(SessionStub())
                for worker_id in range(WORKERS):
                    key = "key_{}".format(worker_id)
                    self.assertEqual(
                        data["shared"].get(key), WRITES - 1,
                        "lost update for worker {}".format(worker_id),
                    )
            finally:
                os.chdir(old_cwd)


if __name__ == '__main__':
    unittest.main()
