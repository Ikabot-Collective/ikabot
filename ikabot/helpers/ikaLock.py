#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""Cross-platform inter-process locks used to serialize access to the .ikabot
session file and to the re-login procedure. Several ikabot processes (main
menu + every background task) read-modify-write the session file
concurrently; without a lock, updates get lost and readers can see
half-written content, which destroys the session data.

Stdlib only: msvcrt on Windows, fcntl elsewhere.
"""

import os
import threading
import time
from contextlib import contextmanager

from ikabot.config import ikaFile, isWindows

if isWindows:
    import msvcrt
else:
    import fcntl

_POLL_INTERVAL = 0.05  # seconds between non-blocking lock attempts


def _try_lock(fd):
    """Attempts to take a non-blocking exclusive lock. Returns True on success."""
    try:
        if isWindows:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(fd):
    if isWindows:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)


class InterProcessLock:
    """Exclusive inter-process lock on a companion file next to the .ikabot
    file. Reentrant within the same process, so callers can wrap a whole
    read-modify-write:

        with sessionFileLock():
            data = session.getSessionData()
            data["x"] = 1
            session.setSessionData(data)

    Raises TimeoutError if the lock cannot be taken within ``timeout`` seconds.
    """

    def __init__(self, suffix, timeout):
        self.suffix = suffix
        self.timeout = timeout
        self._thread_lock = threading.RLock()
        self._depth = 0
        self._fd = None

    @contextmanager
    def __call__(self):
        with self._thread_lock:
            if self._depth == 0:
                lock_path = ikaFile + self.suffix
                fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
                deadline = time.time() + self.timeout
                while not _try_lock(fd):
                    if time.time() > deadline:
                        os.close(fd)
                        raise TimeoutError(
                            "Could not lock {} within {} seconds; another ikabot "
                            "process seems stuck holding it".format(lock_path, self.timeout)
                        )
                    time.sleep(_POLL_INTERVAL)
                self._fd = fd
            self._depth += 1
            try:
                yield
            finally:
                self._depth -= 1
                if self._depth == 0:
                    try:
                        _unlock(self._fd)
                    finally:
                        os.close(self._fd)
                        self._fd = None


# serializes every read-modify-write of the .ikabot session file; held only
# for the duration of file operations, so the timeout is short
sessionFileLock = InterProcessLock(".lock", timeout=30)

# serializes the full re-login procedure so only one ikabot process at a time
# performs it (a full login can take minutes when the blackbox token API is
# slow, hence the long timeout). Lock ordering: loginLock is always taken
# BEFORE sessionFileLock, never while holding it.
loginLock = InterProcessLock(".login.lock", timeout=20 * 60)
