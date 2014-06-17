import logging

import monster.provisioners.openstack.provisioner as openstack
import monster.provisioners.rackspace.provisioner as rackspace
import monster.provisioners.razor.provisioner as razor
import monster.provisioners.razor2.provisioner as razor2

logger = logging.getLogger(__name__)


def get_provisioner(provisioner_name):
    """Returns an instance of the correct provisioner class.
    :type provisioner_name: str
    :rtype: monster.provisioners.base.Provisioner
    """
    provisioner_dict = {'openstack': openstack.Provisioner,
                        'rackspace': rackspace.Provisioner,
                        'razor': razor.Provisioner,
                        'razor2': razor2.Provisioner}
    try:
        return provisioner_dict[provisioner_name]()
    except KeyError:
        logger.critical("Provisioner {} not found.".format(provisioner_name))
