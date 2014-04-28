import os
import logging
import logging.handlers
import subprocess
import sys

from glob import glob
from os.path import dirname, join
from xml.etree import ElementTree
from inspect import getmembers, isclass


# File logging setup
LOG_DIR = join(dirname(dirname(__file__)), 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


# https://github.com/cloudnull/turbolift/blob/master/turbolift/logger/logger.py
class Logger(object):

    def __init__(self, log_level="DEBUG",
                 log_file=join(LOG_DIR, "monster.log")):
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
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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


def get_file(ip, user, password, remote, local, remote_delete=False):
    cmd1 = 'sshpass -p {0} scp -q {1} {2}'.format(password, remote, local)
    subprocess.call(cmd1, shell=True)
    if remote_delete:
        cmd2 = ("sshpass -p {0} ssh -o UserKnownHostsFile=/dev/null "
                "-o StrictHostKeyChecking=no -o LogLevel=quiet -l {1} {2}"
                " 'rm *.xml;exit'".format(password, user, ip))
        subprocess.call(cmd2, shell=True)
