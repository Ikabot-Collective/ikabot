#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""Connections to Ikariam opened in advance.

Ikariam closes the connection after every answer, so each request has to open a new one
(DNS, TCP and TLS, around 100 ms). It does not close a connection that nobody uses for
several seconds though (it keeps it for about 19 s), so a few connections are kept ready and
a request takes one of them instead of opening its own.
"""

import logging
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool
from urllib3.util.wait import wait_for_read

logger = logging.getLogger(__name__)

# Ikariam was seen keeping an idle connection for 19 seconds and closing it at 20. A connection is
# renewed before it waited for this long
WARM_MAX_AGE = 8
# a connection which waited for longer than this is not used, whatever its age looked like
WARM_MAX_USE_AGE = 12
# nothing is opened in advance when no request came in the last seconds
WARM_ACTIVE_WINDOW = 30


def mark(conn):
    """Notes when a connection started to wait. Two clocks are kept: the monotonic one may not count
    the time the computer sleeps, and the wall clock can be changed"""
    conn._ikabot_ts = time.monotonic()
    conn._ikabot_wall = time.time()


def idle_time(conn, now=None):
    """Seconds a connection has been waiting in the pool, 0 for one which never waited"""
    started = getattr(conn, "_ikabot_ts", None)
    if started is None:
        return 0.0
    idle = (time.monotonic() if now is None else now) - started
    wall = getattr(conn, "_ikabot_wall", None)
    if wall is not None:
        idle = max(idle, time.time() - wall)
    return idle


def drain(sock):
    """Reads what is waiting on the socket without blocking. Returns True when there was only
    TLS records (session tickets), which leave the connection open"""
    timeout = sock.gettimeout()
    sock.setblocking(False)
    try:
        sock.recv(1)
    except (ssl.SSLWantReadError, BlockingIOError):
        return True
    except OSError:
        return False
    finally:
        sock.settimeout(timeout)
    # the server closed the connection, or sent something it should not have
    return False


class WarmHTTPSConnection(HTTPSConnection):
    @property
    def is_connected(self):
        # urllib3 asks this before it uses a connection which was waiting in the pool. The TLS session
        # tickets can arrive late, which makes the socket readable and the connection look closed
        if self.sock is None:
            return False
        if not wait_for_read(self.sock, timeout=0.0):
            return True
        return drain(self.sock)


class WarmHTTPSConnectionPool(HTTPSConnectionPool):
    """The pool is a stack: the last connection put in it is the first one used.
    A closed connection goes to the bottom, so the ones opened in advance are used first
    """

    ConnectionCls = WarmHTTPSConnection

    def _get_conn(self, timeout=None):
        conn = super()._get_conn(timeout)
        # Ikariam closes a connection which waited for about 20 s, and after the computer slept the
        # connection can look younger than it is. Closed here, urllib3 reconnects it when it is used
        if conn.sock is not None and idle_time(conn) > WARM_MAX_USE_AGE:
            conn.close()
        return conn

    def _put_conn(self, conn):
        if conn is None or conn.sock is None:
            # the pool is None once it was closed
            if self.pool is not None:
                with self.pool.mutex:
                    if len(self.pool.queue) < self.pool.maxsize:
                        self.pool.queue.insert(0, None)
            return
        # the wait of a connection which was kept open starts now
        mark(conn)
        super()._put_conn(conn)


class WarmAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {
            **self.poolmanager.pool_classes_by_scheme,
            "https": WarmHTTPSConnectionPool,
        }


def rebalance(pool, max_age=WARM_MAX_AGE, now=None):
    """Closes the connections of the pool which waited for more than max_age seconds and
    puts the others at the end, where they are used first
    Returns
    -------
    kept : int
        number of connections ready to be used
    """
    now = time.monotonic() if now is None else now
    kept, dropped, empty = [], [], 0
    with pool.pool.mutex:
        queue = pool.pool.queue
        for conn in queue:
            if conn is None or conn.sock is None:
                empty += 1
            elif idle_time(conn, now) > max_age:
                dropped.append(conn)
                empty += 1
            else:
                kept.append(conn)
        # urllib3 1.26 keeps the connections in a deque, 2.x in a list
        queue.clear()
        queue.extend([None] * empty + kept)
    for conn in dropped:
        conn.close()
    return len(kept)


def settle(conn, timeout=0.15):
    """Waits for what the server sends right after the TLS handshake (session tickets), and reads it.
    Left unread, it makes a connection look closed. WarmHTTPSConnection reads it as well, this
    only saves that work to the first request.
    Returns False when the connection is closed or has unexpected data"""
    conn.sock.settimeout(timeout)
    try:
        conn.sock.recv(1)
    except (TimeoutError, socket.timeout, ssl.SSLWantReadError):
        conn.sock.settimeout(conn.timeout)
        return True
    except OSError:
        return False
    return False


def add_connection(pool, conn):
    """Puts an open connection in the pool, returns False when there is no room for it"""
    with pool.pool.mutex:
        queue = pool.pool.queue
        if queue and queue[0] is None:
            del queue[0]
            queue.append(conn)
            return True
    return False


class ConnectionWarmer:
    """Keeps `target` connections ready while requests are coming in"""

    def __init__(
        self,
        get_session,
        get_url,
        get_verify,
        target=6,
        max_age=WARM_MAX_AGE,
        active_window=WARM_ACTIVE_WINDOW,
    ):
        self.get_session = get_session
        self.get_url = get_url
        self.get_verify = get_verify
        self.target = target
        self.max_age = max_age
        self.active_window = active_window
        self._last_touch = 0.0
        self._failed = False

    def touch(self):
        """Tells that a request is being sent"""
        self._last_touch = time.monotonic()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def is_active(self):
        return time.monotonic() - self._last_touch <= self.active_window

    def _run(self):
        while True:
            # wait longer after a failure, so a network problem is not hammered, and when idle
            time.sleep(5 if self._failed else 0.2 if self.is_active() else 1)
            self._failed = False
            try:
                self.warm_once()
            except Exception:
                logger.debug("Could not open connections in advance", exc_info=True)
                self._failed = True

    def warm_once(self):
        """Opens the missing connections. Returns how many were opened"""
        if not self.is_active():
            return 0
        session = self.get_session()
        parts = urlsplit(self.get_url())
        url = f"{parts.scheme}://{parts.netloc}/"
        # requests also uses the proxies of the environment (HTTPS_PROXY...), and NO_PROXY, not only
        # session.proxies. Connections opened directly would never be used when a proxy applies
        proxies = session.merge_environment_settings(url, {}, None, None, None)[
            "proxies"
        ]
        adapter = session.get_adapter(url)
        # requests older than 2.32 can't tell which pool a request will use
        if not isinstance(adapter, WarmAdapter) or not hasattr(
            adapter, "get_connection_with_tls_context"
        ):
            return 0
        verify = self.get_verify()
        request = requests.Request("GET", url).prepare()
        # the pool of direct connections, which requests uses when no proxy applies
        pool = adapter.get_connection_with_tls_context(
            request, verify=verify, proxies={}
        )
        adapter.cert_verify(pool, request.url, verify, None)
        if pool.pool is None:
            return 0
        if requests.utils.select_proxy(url, proxies):
            # the ones opened before the proxy was set would never be used
            rebalance(pool, max_age=-1)
            return 0

        missing = self.target - rebalance(pool, self.max_age)
        opened = []

        def open_connection():
            try:
                conn = pool._new_conn()
                conn.timeout = 10
                start = time.monotonic()
                conn.connect()
                # the tickets come about one round trip after the handshake, which took two
                if not settle(conn, min(1.0, max(0.15, time.monotonic() - start))):
                    conn.close()
                    return
                mark(conn)
                if add_connection(pool, conn):
                    opened.append(conn)
                else:
                    conn.close()
            except Exception:
                logger.debug("Could not open a connection in advance", exc_info=True)
                self._failed = True

        threads = [
            threading.Thread(target=open_connection) for _ in range(max(0, missing))
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return len(opened)
