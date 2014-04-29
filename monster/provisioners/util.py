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
    if provisioner_name == 'openstack':
        return openstack.Provisioner()
    elif provisioner_name == 'rackspace':
        return rackspace.Provisioner()
    elif provisioner_name == 'razor':
        return razor.Provisioner()
    elif provisioner_name == 'razor2':
        return razor2.Provisioner()
    else:
        logger.critical("Provisioner {} not found.".format(provisioner_name))
