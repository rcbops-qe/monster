import os
import logging
from glob import glob
from xml.etree import ElementTree

from inspect import getmembers, isclass


class Logger(object):
    def __init__(self, name):
        # Log to console
        self.logger = logging.getLogger(name)

        self.console_handler = logging.StreamHandler()
        console_format = '%(asctime)s %(module)s %(levelname)s: %(message)s'
        self.console_formatter = logging.Formatter(console_format)
        self.console_handler.setFormatter(self.console_formatter)


        self.file_handler = logging.FileHandler('log.log')
        file_format = '%(asctime)s %(module)s %(levelname)s: %(message)s'
        self.file_formatter = logging.Formatter(file_format)
        self.file_handler.setFormatter(self.file_formatter)


        self.critical = self.logger.critical
        self.error = self.logger.error
        self.warning = self.logger.warning
        self.info = self.logger.info
        self.debug = self.logger.debug

    def set_log_level(self, level=None):
        log_level = ""
        if self.logger.name == "compute":
            log_level = getattr(logging, level, logging.DEBUG)
        else:
            level = logging.getLogger("compute").handlers[0].level
            if level == 0:
                level = logging.getLogger("storage").level

            if level == 50:
                log_level = "CRITICAL"
            elif level == 40:
                log_level = "ERROR"
            elif level == 30:
                log_level = "WARNING"
            elif level == 20:
                log_level = "INFO"
            elif level == 10:
                log_level = "DEBUG"
        self.console_handler.setLevel(log_level)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.console_handler)
        self.logger.addHandler(self.file_handler)

        #self.logger.critical("This is a critical log")
        #self.logger.error("This is an error log")
        #self.logger.warning("This is a warning log")
        #self.logger.info("This is an info log")
        #self.logger.debug("This is a debug log")


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
