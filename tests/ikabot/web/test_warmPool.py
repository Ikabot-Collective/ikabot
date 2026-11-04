import datetime
import http.server
import os
import queue
import socket
import ssl
import sys
import tempfile
import threading
import time
import unittest
import warnings
from types import SimpleNamespace

import requests

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
)

from ikabot.web.warmPool import (
    ConnectionWarmer,
    WarmAdapter,
    WarmHTTPSConnectionPool,
    add_connection,
    rebalance,
)


def fake_conn(open=True, ts=0.0):
    conn = SimpleNamespace(sock=object() if open else None, _ikabot_ts=ts, closed=False)
    conn.close = lambda: setattr(conn, "closed", True)
    return conn


def make_cert(folder):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = os.path.join(folder, "c.pem"), os.path.join(folder, "k.pem")
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(key_path, "wb") as f:
        f.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
    return cert_path, key_path


class TestPoolQueue(unittest.TestCase):
    def setUp(self):
        self.pool = WarmHTTPSConnectionPool("localhost", maxsize=4)

    def test_a_closed_connection_goes_to_the_bottom(self):
        warm = fake_conn(ts=1)
        self.pool.pool.queue[:] = [None, None, None, warm]
        taken = self.pool.pool.get()
        self.assertIs(taken, warm)
        self.pool._put_conn(fake_conn(open=False))
        self.assertIsNone(self.pool.pool.queue[0])
        self.assertEqual(len(self.pool.pool.queue), 4)

    def test_rebalance_drops_old_connections_and_puts_the_warm_ones_last(self):
        old, fresh = fake_conn(ts=0), fake_conn(ts=95)
        self.pool.pool.queue[:] = [fresh, None, old, fake_conn(open=False)]
        kept = rebalance(self.pool, max_age=8, now=100)
        self.assertEqual(kept, 1)
        self.assertTrue(old.closed)
        self.assertFalse(fresh.closed)
        self.assertEqual(self.pool.pool.queue, [None, None, None, fresh])

    def test_a_connection_returned_to_a_closed_pool_is_ignored(self):
        self.pool.close()
        self.pool._put_conn(fake_conn(open=False))
        conn = fake_conn()
        self.pool._put_conn(conn)
        self.assertTrue(conn.closed)

    def test_a_connection_is_not_added_to_a_full_pool(self):
        self.pool.pool.queue[:] = [fake_conn(ts=1)] * 4
        self.assertFalse(add_connection(self.pool, fake_conn()))

    def test_a_warm_connection_is_added_at_the_end(self):
        conn = fake_conn()
        self.pool.pool.queue[:] = [None, None, None, fake_conn(ts=1)]
        self.assertTrue(add_connection(self.pool, conn))
        self.assertIs(self.pool.pool.queue[-1], conn)
        self.assertEqual(len(self.pool.pool.queue), 4)


class Handler(http.server.BaseHTTPRequestHandler):
    # HTTP/1.0: the connection is closed after the answer, like Ikariam does
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


class CountingServer(http.server.ThreadingHTTPServer):
    accepted = 0

    def get_request(self):
        request = super().get_request()
        self.accepted += 1
        return request


class TestWarmer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cert, key = make_cert(cls.folder.name)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        cls.server = CountingServer(("127.0.0.1", 0), Handler)
        cls.server.socket = context.wrap_socket(cls.server.socket, server_side=True)
        cls.url = f"https://127.0.0.1:{cls.server.server_address[1]}/"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.folder.cleanup()

    def setUp(self):
        warnings.simplefilter("ignore")
        self.session = requests.Session()
        self.session.mount("https://", WarmAdapter(pool_connections=5, pool_maxsize=5))
        self.warmer = ConnectionWarmer(
            lambda: self.session,
            lambda: self.url + "index.php?",
            lambda: False,
            target=2,
        )
        self.start = self.server.accepted

    def accepted(self, expected=None):
        """Connections the server took since the test began. The server counts them a moment after the
        client is connected, so wait for `expected`, or for the count to stop moving"""
        deadline = time.monotonic() + 2
        last = None
        while time.monotonic() < deadline:
            count = self.server.accepted - self.start
            if expected is not None and count >= expected:
                break
            if expected is None and count == last:
                break
            last = count
            time.sleep(0.15)
        return self.server.accepted - self.start

    def test_nothing_is_opened_when_nobody_asks_for_anything(self):
        self.assertEqual(self.warmer.warm_once(), 0)
        self.assertEqual(self.accepted(), 0)

    def test_requests_use_the_connections_opened_in_advance(self):
        self.warmer.touch()
        self.assertEqual(self.warmer.warm_once(), 2)
        self.assertEqual(self.accepted(2), 2)
        for _ in range(2):
            self.assertEqual(self.session.get(self.url, verify=False).text, "ok")
        # both requests used a connection opened before them
        self.assertEqual(self.accepted(), 2)
        # no connection left, the third request opens its own
        self.assertEqual(self.session.get(self.url, verify=False).text, "ok")
        self.assertEqual(self.accepted(3), 3)

    def test_used_connections_are_replaced(self):
        self.warmer.touch()
        self.warmer.warm_once()
        self.session.get(self.url, verify=False)
        self.assertEqual(self.warmer.warm_once(), 1)
        self.assertEqual(self.warmer.warm_once(), 0)

    def test_nothing_is_opened_with_a_proxy(self):
        self.session.proxies["https"] = "http://127.0.0.1:9"
        self.warmer.touch()
        self.assertEqual(self.warmer.warm_once(), 0)
        self.assertEqual(self.accepted(), 0)


class DelayProxy:
    """Sends everything it receives after `delay` seconds, in both directions, like a far away server"""

    def __init__(self, target_port, delay):
        self.target_port = target_port
        self.delay = delay
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                client, _ = self.listener.accept()
            except OSError:
                return
            upstream = socket.create_connection(("127.0.0.1", self.target_port))
            for source, destination in ((client, upstream), (upstream, client)):
                pending = queue.Queue()
                threading.Thread(
                    target=self._read, args=(source, pending), daemon=True
                ).start()
                threading.Thread(
                    target=self._write, args=(destination, pending), daemon=True
                ).start()

    def _read(self, source, pending):
        while True:
            try:
                data = source.recv(65536)
            except OSError:
                data = b""
            pending.put((time.monotonic() + self.delay, data))
            if not data:
                return

    def _write(self, destination, pending):
        while True:
            due, data = pending.get()
            time.sleep(max(0, due - time.monotonic()))
            try:
                if data:
                    destination.sendall(data)
                else:
                    # a close() with unread data would reset the connection and the client would lose the answer
                    destination.shutdown(socket.SHUT_WR)
                    return
            except OSError:
                return

    def close(self):
        self.listener.close()


class TestFarAwayServer(unittest.TestCase):
    """The TLS 1.3 session tickets arrive about one round trip after the handshake. When the server is far
    away they come later than any fixed wait, and urllib3 throws away a connection it can read from
    """

    @classmethod
    def setUpClass(cls):
        TestWarmer.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        TestWarmer.tearDownClass.__func__(cls)

    def check(self, delay):
        proxy = DelayProxy(self.server.server_address[1], delay)
        self.addCleanup(proxy.close)
        url = f"https://127.0.0.1:{proxy.port}/"
        session = requests.Session()
        session.mount("https://", WarmAdapter(pool_connections=5, pool_maxsize=5))
        warmer = ConnectionWarmer(
            lambda: session, lambda: url + "index.php?", lambda: False, target=2
        )
        warnings.simplefilter("ignore")
        start = self.server.accepted
        warmer.touch()
        self.assertEqual(warmer.warm_once(), 2)
        # the tickets are on their way
        time.sleep(delay * 6)
        opened = self.server.accepted - start
        for _ in range(2):
            self.assertEqual(session.get(url, verify=False).text, "ok")
        time.sleep(0.3)
        self.assertEqual(
            self.server.accepted - start, opened, "a connection was opened again"
        )

    def test_a_server_at_100_ms(self):
        self.check(0.05)

    def test_a_server_at_250_ms(self):
        self.check(0.125)

    def test_a_server_at_500_ms(self):
        self.check(0.25)


if __name__ == "__main__":
    unittest.main()
