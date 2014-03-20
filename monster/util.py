import os
import sys
import logging
import traceback
from glob import glob
from xml.etree import ElementTree


from inspect import getmembers, isclass


console_handler = logging.StreamHandler()
config = None

# Log to console
def get_logger(name):
    logger = logging.getLogger(name)
    log_format = '%(asctime)s %(name)s %(levelname)s: %(message)s'
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


def set_log_level(logger, level):
    log_level = getattr(logging, level, logging.INFO)
    logger.setLevel(log_level)


def log_to_file(logger, path):
    log_file = logging.FileHandler(path)
    log_file.setFormatter(console_handler.formatter)
    log_file.setLevel(logging.DEBUG)
    logger.addHandler(log_file)


def error_exit(error_message=None):
    """
    Prints a stack track to the logger and exits gracefully.
    Takes an optional message parameter.
    """
    if error_message:
        logger.error(error_message)
    logger.error(traceback.print_exc())
    sys.exit(1)


def module_classes(module):
    return {k.lower(): v for (k, v) in
            getmembers(module, isclass)}


def xunit_merge(path="."):
    #print "Merging xunit files"
    files = glob(path + "/*.xml")
    tree = None
    attrs = ["failures", "tests", "errors", "skip"]
    for file in files:
        data = ElementTree.parse(file).getroot()
        for testcase in data.iter('testsuite'):
            if tree is None:
                tree = data
                insertion_point = tree
            else:
                for attr in attrs:
                    tree.attrib[attr] = str(int(tree.attrib[attr]) +
                                            int(data.attrib[attr]))
                insertion_point.extend(testcase)
    if tree is not None:
        with open("results.xunit", "w") as f:
            f.write(ElementTree.tostring(tree))
    [os.remove(file) for file in files]
