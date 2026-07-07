import logging
import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.helpers.logging import SecretsFilter


def _redact(message):
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg=message, args=None, exc_info=None,
    )
    SecretsFilter().filter(record)
    return record.getMessage()


class TestSecretsFilter(unittest.TestCase):

    def test_cookie_header_redacted(self):
        msg = "'Cookie': 'ikariam=abc123secret; PHPSESSID=deadbeef42'"
        redacted = _redact(msg)
        self.assertNotIn("abc123secret", redacted)
        self.assertNotIn("deadbeef42", redacted)
        self.assertIn("<REDACTED>", redacted)

    def test_gf_token_redacted(self):
        msg = "{'gf-token-production': 'eyJhbGciOiJIUzI1NiJ9.secret.token'}"
        redacted = _redact(msg)
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", redacted)

    def test_authorization_bearer_redacted(self):
        msg = "'Authorization': 'Bearer eyJhbGciOiJIUzI1NiJ9.abc.def'"
        redacted = _redact(msg)
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9.abc.def", redacted)

    def test_blackbox_redacted(self):
        msg = "'blackbox': 'tra:JVqmZ0aBcDeFgHiJkLmNoPqRsTuVwXyZ01234567'"
        redacted = _redact(msg)
        self.assertNotIn("JVqmZ0aBcDeFgHiJkLmNoPqRsTuVwXyZ01234567", redacted)

    def test_password_redacted(self):
        msg = '"password": "hunter2!!"'
        redacted = _redact(msg)
        self.assertNotIn("hunter2", redacted)

    def test_normal_message_untouched(self):
        msg = "Donated 5000 wood in city 1234"
        self.assertEqual(_redact(msg), msg)

    def test_message_with_args_untouched(self):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname=__file__, lineno=1,
            msg="Donated %s wood in city %s", args=(5000, 1234), exc_info=None,
        )
        SecretsFilter().filter(record)
        self.assertEqual(record.getMessage(), "Donated 5000 wood in city 1234")


if __name__ == '__main__':
    unittest.main()
