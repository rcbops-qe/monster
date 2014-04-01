import sys
import traceback
from monster.util import module_classes
from monster.provisioners import *
from monster import util


def get_provisioner(provisioner):
    """
    This will return an instance of the correct provisioner class
    :param provisioner: The name of the provisioner
    :type provisioner: String
    :rtype: object
    """

    try:
        identifier = getattr(sys.modules['monster'].provisioners, provisioner)
    except AttributeError:
        print(traceback.print_exc())
        util.logger.error("The provisioner \"{0}\" was not found."
                          .format(provisioner))
        exit(1)
    return module_classes(identifier)[provisioner]()
