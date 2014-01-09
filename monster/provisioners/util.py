import sys
import types
from monster.provisioners import *
from monster.util import module_classes

def get_provisioner(provisioner):
    """
    This will return an instance of the correct provisoner class
    :param provisioner: The name of the provisoner
    :type provisioner: String
    :rtype: object
    """

    try:
        identifier = getattr(sys.modules['monster'].provisioners, provisioner)
    except AttributeError:
        raise NameError("{0} doesn't exist.".format(provisioner))

    return module_classes(identifier)[provisioner]