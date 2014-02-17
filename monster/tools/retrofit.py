"""
Tool to retrofit a install
"""

from monster import util


class Retrofit(object):

    def __init__(self, deployment):
        self.deployment = deployment

    def install(self, branch='master'):
        """
        Installs the retrofit tool on the nodes
        """

        # Check for support
        self._check_os()
        self._check_neutron()

        # Load Nodes
        controllers = self.deployment.search_role('controller')
        computes = self.deployment.search_role('compute')

        # Retrofit Controllers
        for controller in controllers:
            self._install_repo(controller, branch)
            self.bootstrap(controller)

        # Retrofit Computes
        for compute in computes:
            self._install_repo(compute, branch)
            self.bootstrap(compute)

    def bootstrap(self, node, iface, lx_bridge, ovs_bridge):
        """
        Bootstraps a node with retrofit
        """

        # run bootstrap retrofit
        retro_cmds = ['cd /opt/retrofit',
                      './retrofit.py bootstrap -i {0} -l {1} -o {2}'.format(
                          iface, lx_bridge, ovs_bridge)]

        retro_cmd = "; ".join(retro_cmds)
        util.logger.debug("Running {0} on {1}".format(retro_cmd, self.name))
        node.run_cmd(retro_cmd)

    def convert(self, node):
        raise NotImplementedError()

    def revert(self, node):
        raise NotImplementedError()

    def _install_repo(self, node, branch):
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
