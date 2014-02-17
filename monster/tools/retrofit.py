"""
Tool to retrofit a install
"""

from monster import util


class Retrofit(object):

    def __init__(self, deployment):
        self.deployment = deployment
        self.controllers = self.deployment.search_role('controller')
        self.computes = self.deployment.search_role('compute')

    def install(self, branch):
        """
        Installs the retrofit tool on the nodes
        """

        # Check for support
        self._check_os()
        self._check_neutron()

        for controller in self.controllers:
            self._install_repo(controller, branch)

        for compute in self.computes:
            self._install_repo(compute, branch)

    def bootstrap(self, iface, lx_bridge, ovs_bridge):
        """
        Bootstraps a node with retrofit
        """

        # bootstrap cmd
        bstrap_cmds = ['cd /opt/retrofit',
                       './retrofit.py bootstrap -i {0} -l {1} -o {2}'.format(
                           iface, lx_bridge, ovs_bridge)]

        bstrap_cmd = "; ".join(bstrap_cmds)

        for controller in self.controllers:
            controller.run_cmd(bstrap_cmd)

        for compute in self.computes:
            compute.run_cmd(bstrap_cmd)

    def convert(self, iface, lx_bridge, ovs_bridge):
        raise NotImplementedError()

    def revert(self, iface, lx_bridge, ovs_bridge):
        raise NotImplementedError()

    def _install_repo(self, node, branch='master'):
        """
        Installs the retrofit repository
        """

        retro_git = util.config['rcbops'][str(self)]['git']['url']
        branches = util.config['rcbops'][str(self)]['git']['branches']

        if branch not in branches:
            error = "{0} not a supported branch in retrofit"
            util.logger.info(error)
            raise Exception(error)

        # clone repo
        clone_cmds = ['cd /opt',
                      'rm -rf retrofit',
                      'git clone -b {0} {1}'.format(branch, retro_git)]

        clone_cmd = "; ".join(clone_cmds)

        node.run_cmd(clone_cmd)

    def _check_neutron(self):
        """
        Check to make sure neutron is in the deployment
        """

        if not self.deployment.feature_in('neutron'):
            error = "This build doesnt have Neutron/Quantum, cannot Retrofit"
            util.logger.info(error)
            raise Exception(error)

    def _check_os(self):
        """
        Checks to see if os is supported
        """

        supported = util.config['rcbops'][str(self)]['supported']['os']

        if not self.deployment.os_name in supported:
            error = "{0} is not a retrofit supported OS".format(
                self.deployment.os_name)
            util.logger.info(error)
            raise NotImplementedError(error)
