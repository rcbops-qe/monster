import sys
import traceback
from monster.provisioners.provisioner import logger
from monster.util import module_classes
from monster.provisioners import *


def get_provisioner(provisioner_name):
    """
    This will return an instance of the correct provisioner class
    :param provisioner_name: The name of the provisioner
    :type provisioner_name: str
    :rtype: Provisioner
    """

    try:
        identifier = getattr(sys.modules['monster'].provisioners,
                             provisioner_name)
    except AttributeError:
        print(traceback.print_exc())
        logger.error("The provisioner \"{0}\" was not found."
                     .format(provisioner_name))
        exit(1)
    else:
        return module_classes(identifier)[provisioner_name]()
