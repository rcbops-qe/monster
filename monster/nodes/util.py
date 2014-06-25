import logging
import time
import chef
import monster.active as active


logger = logging.getLogger(__name__)


def node_search(query, environment=None, tries=10):
    """Performs a node search query on the chef server.
    :param query: search query to request
    :type query: string
    :param environment: Environment the query should be
    :type environment: monster.environments.chef.environment.Environment
    :rtype: Iterator (chef.Node)
    """
    if environment:
        api = environment.local_api
    else:
        try:
            api = chef.autoconfigure(
                active.config['secrets']['chef']['knife'])
            logger.debug("Using knife.rb found at {}".format(
                active.config['secrets']['chef']['knife']))
        except KeyError:
            api = chef.autoconfigure()

    search = None
    while not search and tries > 0:
        search = chef.Search("node", api=api).query(query)
        time.sleep(10)
        tries -= 1
    return (n.object for n in search)


class OS(object):
    def mkswap_cmds(self, size):
        """Command to make a swap file of a given size on the OS.
        :param size: Size of swap file in GBs
        :type size: int
        """
        size_b = 1048576 * size
        return [
            "dd if=/dev/zero of=/mnt/swap bs=1024 count={size_b}"
            .format(size_b=size_b),
            "mkswap /mnt/swap",
            "sed 's/vm.swappiness.*$/vm.swappiness=25/g' /etc/sysctl.conf "
            "> /etc/sysctl.conf",
            "sysctl vm.swappiness=30",
            "swapon /mnt/swap",
            "echo '/mnt/swap swap swap defaults 0 0' >> /etc/fstab"
        ]


class DebianOS(OS):
    def __repr__(self):
        return 'debian/ubuntu'

    def check_package_cmd(self, package):
        return "dpkg -l | grep {0}".format(package)

    def update_dist_cmd(self, dist_upgrade=False):
        if dist_upgrade:
            return 'apt-get update -y; apt-get dist-upgrade -y'
        else:
            return 'apt-get update -y; apt-get upgrade -y'

    def install_package_cmd(self, package):
        return 'apt-get install -y {0}'.format(package)

    remove_chef_cmd = "apt-get remove --purge -y chef; rm -rf /etc/chef"
    initial_update_cmds = [
        "DEBIAN_FRONTEND=noninteractive apt-get update -y",
        "DEBIAN_FRONTEND=noninteractive apt-get upgrade -y",
        "DEBIAN_FRONTEND=noninteractive apt-get install "
        "openssh-client git curl -y"]


class RHEL(OS):
    def __repr__(self):
        return 'rhel/centos'

    def check_package_cmd(self, package):
        return "rpm -a | grep {0}".format(package)

    def update_dist_cmd(self, dist_upgrade=False):
        return 'yum update -y'

    def install_package_cmd(self, package):
        return 'yum install -y {0}'.format(package)

    remove_chef_cmd = "yum remove -y chef; rm -rf /etc/chef /var/chef"
    initial_update_cmds = [
        "yum update -y",
        "yum upgrade -y",
        "yum install openssh-clients git curl -y",
        "wget http://dl.fedoraproject.org/pub/epel/6/x86_64/"
        "epel-release-6-8.noarch.rpm",
        "wget http://rpms.famillecollet.com/enterprise/remi-release-6.rpm",
        "sudo rpm -Uvh remi-release-6*.rpm epel-release-6*.rpm",
        "/sbin/iptables -F",
        "/etc/init.d/iptables save",
        "/sbin/iptables -L"]


def get_os(os_name):
    """Given the name of an OS, returns an object that is capable of
    providing OS specific command-line commands for many useful
    functionalities, such as package upgrades."""
    if os_name in ['ubuntu']:
        return DebianOS()
    elif os_name in ['rhel', 'centos']:
        return RHEL()
    else:
        logger.exception("OS not supported at this time!")
