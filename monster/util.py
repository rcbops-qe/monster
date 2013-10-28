import logging
from inspect import getmembers, isclass

# Log to console
logger = logging.getLogger("rcbops.qa")
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


def module_classes(module):
    return {k.lower(): v for (k, v) in
            getmembers(module, isclass)}
