"""
This module will set up proper ikabot logging when imported.
"""

import logging
import logging.handlers
import os

from ikabot.config import LOGS_DIRECTORY_FILE, DEFAULT_LOG_LEVEL

UNKNOWN_PLAYER = "unknown"
# the name is kept in the environment so that the background tasks inherit it: they are
# spawned (not forked) on Windows and macOS, which re-imports this module from scratch
PLAYER_ENV_VAR = "IKABOT_PLAYER"

class PlayerNameFilter(logging.Filter):
    """Adds the name of the logged in player to every record, so that logs written by
    several accounts running at the same time can be told apart. The name is unknown
    until the login finishes, so records written before that are marked as such"""

    def filter(self, record):
        record.player = os.environ.get(PLAYER_ENV_VAR) or UNKNOWN_PLAYER
        return True

# TODO wrap logging functions to remove cookies from logs, or add a filter
class IkabotLogger(logging.Logger):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
logging.setLoggerClass(IkabotLogger)    

# Create custom file logger
rotatingFileHandler = logging.handlers.RotatingFileHandler(
                filename=LOGS_DIRECTORY_FILE,
                maxBytes=10 * 1024 * 1024, #max logfile size is 10 MB
                backupCount=10, # max number of log files is 10
                    )
rotatingFileHandler.addFilter(PlayerNameFilter())
logConfig = {
    'format': '%(asctime)s - %(player)s - %(name)s - %(levelname)s - %(message)s',
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

def setLoggedInPlayer(username: str) -> None:
    """Sets the player name that will be written in every log record from now on, in this
    process and in every background task started after this call
    Parameters
    ----------
    username : str
        name of the logged in player
    """
    os.environ[PLAYER_ENV_VAR] = username if username else UNKNOWN_PLAYER
