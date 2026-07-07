"""
This module will set up proper ikabot logging when imported.
"""

import logging
import logging.handlers
import re

from ikabot.config import LOGS_DIRECTORY_FILE, DEFAULT_LOG_LEVEL


class IkabotLogger(logging.Logger):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
logging.setLoggerClass(IkabotLogger)


class SecretsFilter(logging.Filter):
    """Redacts session cookies, auth tokens and passwords from log messages
    (request headers/cookies are logged at DEBUG level and would otherwise
    leak account access)."""

    _patterns = [
        re.compile(r"(gf-token-production['\"]?\s*[:=]\s*['\"]?)[^'\",;\s}]+"),
        re.compile(r"(ikariam=)[^'\",;\s}]+"),
        re.compile(r"(PHPSESSID=)[^'\",;\s}]+"),
        re.compile(r"(Authorization['\"]?\s*[:=]\s*['\"]?Bearer\s+)[^'\",;\s}]+"),
        re.compile(r"(blackbox['\"]?\s*[:=]\s*['\"]?)[A-Za-z0-9+/:_-]{20,}"),
        re.compile(r"(password['\"]?\s*[:=]\s*['\"]?)[^'\",;\s}]+", re.IGNORECASE),
    ]

    def filter(self, record):
        try:
            message = record.getMessage()
            redacted = message
            for pattern in self._patterns:
                redacted = pattern.sub(r"\g<1><REDACTED>", redacted)
            if redacted != message:
                record.msg = redacted
                record.args = None
        except Exception:
            pass  # a broken log record must never break the program
        return True


class SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler that survives rollover failures. Several ikabot
    processes write to the same log file; on Windows the rename during
    rollover then raises PermissionError (WinError 32). In that case just
    keep logging to the current file and try again later."""

    def doRollover(self):
        try:
            super().doRollover()
        except OSError:
            # another process holds the log file open; FileHandler.emit
            # reopens the stream automatically on the next record
            pass


# Create custom file logger
rotatingFileHandler = SafeRotatingFileHandler(
                filename=LOGS_DIRECTORY_FILE,
                maxBytes=10 * 1024 * 1024, #max logfile size is 10 MB
                backupCount=10, # max number of log files is 10
                delay=True, # don't hold the file open until something is logged
                    )
rotatingFileHandler.addFilter(SecretsFilter())
logConfig = {
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'level': DEFAULT_LOG_LEVEL,
    'force': True,
    'handlers': [rotatingFileHandler]
    }
logging.basicConfig(**logConfig)

# Make sure to set all loggers to propagate and clear their handlers (only use the root logger)
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).propagate = True
    logging.getLogger(name).handlers.clear()

def getLogger(name: str) -> IkabotLogger:
    """Convenience function to get a logger by name"""
    return logging.getLogger(name)
