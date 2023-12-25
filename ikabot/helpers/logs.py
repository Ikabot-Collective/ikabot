import logging
import os
from logging.handlers import TimedRotatingFileHandler

from ikabot import config
from ikabot.config import LOG_FILE, LOG_DIR


def __record_factory(old_factory, *args, **kwargs):
    record = old_factory(*args, **kwargs)
    record.player = ''
    record.customRequestId = ''
    record.customRequest = ''

    if len(config.infoUser) > 0:
        record.player = '[{}]'.format(config.infoUser)

    return record

def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        datefmt='%Y-%m-%dT%H:%M:%S',
        format='%(asctime)s.%(msecs)03d pid:%(process)-6s %(levelname)-5s %(filename)s %(player)s - %(message)s',
        handlers=[
            TimedRotatingFileHandler(
                filename=LOG_FILE,
                when='midnight',
            ),
        ]
    )

    __old_factory = logging.getLogRecordFactory()
    logging.setLogRecordFactory(
        lambda *args, **kwargs: __record_factory(__old_factory, *args, **kwargs)
    )
