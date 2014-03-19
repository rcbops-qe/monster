import logging


class Logger(object):
    def __init__(self, name):
        # Log to console
        self.logger = logging.getLogger(name)
        self.console_handler = logging.StreamHandler()
        self.log_format = '%(asctime)s %(name)s %(levelname)s: %(message)s'
        self.formatter = logging.Formatter(self.log_format)
        self.console_handler.setFormatter(self.formatter)
        self.logger.addHandler(self.console_handler)
        #config = None

    def set_log_level(self, level):
        log_level = getattr(logging, level, logging.INFO)
        self.logger.setLevel(log_level)

    def log_to_file(self, path):
        log_file = logging.FileHandler(path)
        log_file.setFormatter(self.console_handler.formatter)
        log_file.setLevel(logging.DEBUG)
        self.logger.addHandler(log_file)
