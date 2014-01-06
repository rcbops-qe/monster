"""
Base Feature
"""


class Feature(object):
    """ 
    Represents a OpenStack Feature
    """

    def __repr__(self):
        """ 
        Print out current instance
        :rtype: String
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def __str__(self):
        """ 
        Prints out class name
        :rtype: String
        """

        return self.__class__.__name__.lower()

    def update_environment(self):
        pass

    def pre_configure(self):
        pass

    def apply_feature(self):
        pass

    def post_configure(self):
        pass

    def destroy(self):
        pass

    def archive(self):
        pass


def remove_chef(node):
    """ 
    Removes chef from the given node
    
    :param node: Node object to remove chef from
    :type node: object
    :rtype: function
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
    """ 
    Installs given package

    :param package: package to install
    :type package: String
    :rtype: function
    """

    # Need to make this more machine agnostic (jwagner)
    if node.os_name == "precise":
        command = 'apt-get install -y {0}'.format(package)
    if node.os_name in ["centos", "rhel"]:
        command = 'yum install -y {0}'.format(package)

    return node.run_cmd(command)


def install_packages(node, packages):
    """
    Installs a list of packages

    :param packages: List of packages to install
    :type packages: List of Strings
    """

    for package in packages:
        install_package(node, package)


def install_ruby_gem(node, gem):
    """
    Installs a ruby gem

    :param gem: Ruby gem to install
    :type gem: String
    :rtype: function
    """

    command = ('source /usr/local/rvm/scripts/rvm; gem install '
               '--no-rdoc --no-ri {0}'.format(gem))

    return node.run_cmd(command)


def install_ruby_gems(node, gems):
    """
    Installs a list of ruby gems

    :param gems: List of gems to install
    :type gems: List of Strings
    """

    for gem in gems:
        install_ruby_gem(node, gem)
