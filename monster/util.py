import os
import logging
import subprocess
from glob import glob
from string import Template
from xml.etree import ElementTree
from inspect import getmembers, isclass


# Gets RPC-QE logger
name = 'Monster'
time_cmd = subprocess.Popen(['date', '+%F_%T'],
                            stdout=subprocess.PIPE)
time = time_cmd.stdout.read().rstrip()
logger = logging.getLogger(name)

# Console logging setup
console_handler = logging.StreamHandler()
console_format = '%(asctime)s %(name)s %(levelname)s %(module)s: %(message)s'
console_formatter = logging.Formatter(console_format)
console_handler.setFormatter(console_formatter)

# File logging setup

if not os.path.exists('logs'):
    os.makedirs('logs')

file_handler = logging.FileHandler("logs/{0}-{1}.log".format(name, time))
file_format = '%(asctime)s %(name)s %(levelname)s %(module)s: %(message)s'
file_formatter = logging.Formatter(file_format)
file_handler.setFormatter(file_formatter)

critical = logger.critical
error = logger.error
warning = logger.warning
info = logger.info
debug = logger.debug

# Sets logging level to the file
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


def set_log_level(level):
    log_level = getattr(logging, level, logging.DEBUG)
    # Sets logging level to the console
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)


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


def template_file(source, destination=None, args=None):
    with open(source) as f:
        template = Template(f.read()).substitute(args)
        logger.debug("Templated:{0}". format(template))

    if not destination:
        destination = "{0}.templated".format(source)
    with open(destination, 'w') as f:
        f.write(template)
        logger.debug("Writing template to:{0}".format(destination))
