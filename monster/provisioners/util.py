import logging
import sys

from monster.util import module_classes
from monster.provisioners import *

logger = logging.getLogger(__name__)


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
        logger.error("Provisioner not found: {0}".format(provisioner,
                                                         exc_info=True))
        exit(1)
    return module_classes(identifier)[provisioner]()
