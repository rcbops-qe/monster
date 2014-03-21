import os
import logging
from glob import glob
from xml.etree import ElementTree

from inspect import getmembers, isclass


class Logger(object):
    def __init__(self, name):
        # Log to console
        logger = logging.getLogger(name)
        self.console_handler = logging.StreamHandler()
        log_format = '%(asctime)s %(name)s %(levelname)s: %(message)s'
        formatter = logging.Formatter(log_format)
        self.console_handler.setFormatter(formatter)
        logger.addHandler(self.console_handler)
        self.logger = logger
        self.critical = logger.critical
        self.error = logger.error
        self.warning = logger.warning
        self.info = logger.info
        self.debug = logger.debug

    def set_log_level(self, level):
        log_level = getattr(logging, level, logging.INFO)
        self.logger.setLevel(log_level)

    def log_to_file(self, path):
        log_file = logging.FileHandler(path)
        log_file.setFormatter(self.console_handler.formatter)
        log_file.setLevel(logging.DEBUG)
        self.logger.addHandler(log_file)


def module_classes(module):
    return {k.lower(): v for (k, v) in
            getmembers(module, isclass)}


def xunit_merge(path="."):
    print "Merging xunit files"
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
