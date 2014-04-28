import logging


logger = logging.getLogger(__name__)


class OS:
    def __init__(self, os_name):
        if os_name in ['ubuntu']:
            self.__class__ = DebianOS
        elif os_name in ['rhel', 'centos']:
            self.__class__ = RHEL
        else:
            logger.exception("OS not supported at this time!")

    def check_package(self, package):
        raise NotImplementedError()

    def install_package(self, package):
        raise NotImplementedError()

    def update_dist(self, dist_upgrade=False):
        raise NotImplementedError()


class DebianOS(OS):
    def check_package(self, package):
        return "dpkg -l | grep {0}".format(package)

    def update_dist(self, dist_upgrade=False):
        if dist_upgrade:
            return 'apt-get update; apt-get dist-upgrade -y'
        else:
            return 'apt-get update; apt-get upgrade -y'

    def install_package(self, package):
        return 'apt-get install -y {0}'.format(package)

    def remove_chef(self):
        return "apt-get remove --purge -y chef; rm -rf /etc/chef"


class RHEL(OS):
    def check_package(self, package):
        return "rpm -a | grep {0}".format(package)

    def update_dist(self, dist_upgrade=False):
        return 'yum update -y'

    def install_package(self, package):
        return 'yum install -y {0}'.format(package)

    def remove_chef(self):
        return "yum remove -y chef; rm -rf /etc/chef /var/chef"
