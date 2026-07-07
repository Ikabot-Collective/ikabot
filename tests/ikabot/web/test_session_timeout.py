import unittest
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.web.session import (
    DEFAULT_REQUEST_TIMEOUT,
    TimeoutHTTPAdapter,
    newRequestsSession,
)


class TestTimeoutAdapter(unittest.TestCase):

    def test_new_session_mounts_timeout_adapter(self):
        s = newRequestsSession()
        self.assertIsInstance(s.get_adapter('https://example.com'), TimeoutHTTPAdapter)
        self.assertIsInstance(s.get_adapter('http://example.com'), TimeoutHTTPAdapter)

    @patch('requests.adapters.HTTPAdapter.send')
    def test_default_timeout_applied(self, mock_send):
        adapter = TimeoutHTTPAdapter()
        adapter.send(Mock())
        self.assertEqual(mock_send.call_args.kwargs['timeout'], DEFAULT_REQUEST_TIMEOUT)

    @patch('requests.adapters.HTTPAdapter.send')
    def test_explicit_timeout_not_overridden(self, mock_send):
        adapter = TimeoutHTTPAdapter()
        adapter.send(Mock(), timeout=300)
        self.assertEqual(mock_send.call_args.kwargs['timeout'], 300)


if __name__ == '__main__':
    unittest.main()
