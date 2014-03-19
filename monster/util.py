import os
from glob import glob
from xml.etree import ElementTree

from inspect import getmembers, isclass


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
