import logging

# Log to console
logger = logging.getLogger("rcbops.qa")
console_handler = logging.StreamHandler()
format = '%(asctime)s %(name)s %(levelname)s: %(message)s'
formatter = logging.Formatter(format)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def set_log_level(level):
    log_level = getattr(logging, level, logging.INFO)
    logger.setLevel(log_level)


def log_to_file(file):
    fh = logging.FileHandler(file)
    fh.setFormatter(console_handler.formatter)
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)
