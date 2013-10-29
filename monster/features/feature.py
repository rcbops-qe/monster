"""
Base Feature
"""


class Feature(object):
    """ Represents a OpenStack Feature
    """

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def __str__(self):
        return self.__class__.__name__

    def update_environment(self):
        pass

    def pre_configure(self):
        pass

    def apply_feature(self):
        pass

    def post_configure(self):
        pass


def remove_chef(node):
    """ Removes chef from the given node
    """

    if node.os_name == "precise":
        commands = ["apt-get remove --purge -y chef",
                    "rm -rf /etc/chef"]
    if node.os_name in ["centos", "rhel"]:
        commands = ["yum remove -y chef",
                    "rm -rf /etc/chef /var/chef"]

    command = "; ".join(commands)

    return node.run_cmd(command)

def install_package(node, package):

    # Need to make this more machine agnostic (jwagner)
    if node.os_name == "precise":
        command = 'apt-get install -y {0}'.format(package)
    if node.os_name in ["centos", "rhel"]:
        command = 'yum install -y {0}'.format(package)

    return node.run_cmd(command)

def install_packages(node, packages):

    for package in packages:
        install_package(node, package)

def install_ruby_gem(node, gem):

    command = 'source /usr/local/rvm/scripts/rvm; gem install --no-rdoc --no-ri {0}'.format(gem)

    return node.run_cmd(command)


def install_ruby_gems(node, gems):

    for gem in gems:
        install_ruby_gem(node, gem)
