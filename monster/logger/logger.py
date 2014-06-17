import logging
import logging.handlers
import os
import sys

import os.path as path


LOG_DIR = path.join(path.dirname(path.dirname(__file__)), '../../logs')
if not path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


# https://github.com/cloudnull/turbolift/blob/master/turbolift/logger/logger.py
class Logger(object):

    def __init__(self, log_level="DEBUG",
                 log_file=path.join(LOG_DIR, "monster.log")):
        self.log_level = log_level
        self.log_file = log_file

    def logger_setup(self):
        logger = logging.getLogger("monster")

        avail_level = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'CRITICAL': logging.CRITICAL,
            'WARN': logging.WARN,
            'ERROR': logging.ERROR
        }

        _log_level = self.log_level.upper()
        if _log_level in avail_level:
            lvl = avail_level[_log_level]
            formatter = logging.Formatter(
                "%(asctime)-15s %(name)-36s %(levelname)-9s %(message)s"
            )
            logger.setLevel(lvl)

        if self.log_file:
            file_handler = logging.handlers.RotatingFileHandler(
                self.log_file,
                maxBytes=150000000,
                backupCount=5
            )
            file_handler.setLevel(avail_level['DEBUG'])
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler(stream=sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        return logger
