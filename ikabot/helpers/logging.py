"""
This module will set up proper ikabot logging when imported.
"""

import logging
import logging.handlers

from ikabot.config import LOGS_DIRECTORY_FILE, DEFAULT_LOG_LEVEL

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