import logging


class Logger(object):
    def __init__(self, name):
        # Log to console
        logger = logging.getLogger(name)
        console_handler = logging.StreamHandler()
        log_format = '%(asctime)s %(name)s %(levelname)s: %(message)s'
        formatter = logging.Formatter(log_format)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        config = None

    def set_log_level(level):
        log_level = getattr(logging, level, logging.INFO)
        logger.setLevel(log_level)

    def log_to_file(path):
        log_file = logging.FileHandler(path)
        log_file.setFormatter(console_handler.formatter)
        log_file.setLevel(logging.DEBUG)
        logger.addHandler(log_file)
