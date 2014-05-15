import logging
from time import sleep

import monster.active as actv
from monster.upgrades.upgrade import Upgrade

logger = logging.getLogger(__name__)


class FourOneThree(Upgrade):
    """
    4.1.3 Upgrade Procedures
    """

    def __init__(self, deployment):
        super(FourOneThree, self).__init__(deployment)

    def upgrade(self, rc=False):
        """
        Upgrades the deployment (very chefy, rcbopsy)
        """

        if rc:
            upgrade_branch = "v4.1.3rc"
        else:
            upgrade_branch = "v4.1.3"

        supported = actv.config['upgrade']['supported'][self.deployment.branch]
        if upgrade_branch not in supported:
            logger.error("{0} to {1} upgarde not supported".format(
                self.deployment.branch,
                upgrade_branch
            ))
            raise NotImplementedError

        # load override attrs from env
        override = self.deployment.override_attrs

        # set the deploy branch to the upgrade branch
        self.deployment.branch = upgrade_branch
        override['deployment']['branch'] = upgrade_branch
        self.deployment.environment.save()

        # Gather all the nodes of the deployment
        chef_server = next(self.deployment.search_role('chefserver'))
        controllers = list(self.deployment.search_role('controller'))
        computes = list(self.deployment.search_role('compute'))

        # upgrade the chef server
        chef_server.upgrade()
        controller1 = controllers[0]

        # save image upload value
        try:
            image_upload = override['glance']['image_upload']
            override['glance']['image_upload'] = False
            override['osops']['do_package_upgrades'] = True
            self.deployment.environment.save()
        except KeyError:
            pass

        if self.deployment.has_feature('highavailability'):
            controller2 = controllers[1]
            stop = actv.config['upgrade']['commands']['stop-services']
            start = actv.config['upgrade']['commands']['start-services']

            # Sleep for vips to move
            controller2.run_cmd(stop)
            sleep(30)

            # Upgrade
            controller1.upgrade(times=2, accept_failure=True)
            controller1.run_cmd("service keepalived restart")
            controller1.upgrade()
            controller2.upgrade()
            controller1.upgrade()

            # Codeing around issue
            # https://github.com/rcbops/chef-cookbooks/issues/791
            controller1.run_cmd('monit reload')

            # sleep for monit
            sleep(30)

            #restart services
            controller1.run_cmd("service haproxy restart", attempts=2)
            controller1.run_cmd("monit restart rpcdaemon", attempts=5)

            # restart services of controller2
            controller2.run_cmd(start, attempts=5)
        else:
            controller1.upgrade()

        # run the computes
        for compute in computes:
            compute.upgrade(times=2)

        # restore value of image upload
        if image_upload:
            override['glance']['image_upload'] = image_upload
            override['osops']['do_package_upgrades'] = False
            self.deployment.environment.save()

        # Fix OVS as per issue
        # https://github.com/rcbops/chef-cookbooks/issues/758
        if self.deployment.has_feature('neutron'):
            if self.deployment.has_feature('highavailability'):

                # Fix ovs
                self.ovs_fix(controller1)

                # Sleep 10 seconds to allow vips to move
                sleep(10)

                # Fix controller 2 ovs
                self.ovs_fix(controller2)

                # sleep
                sleep(10)
            else:
                self.ovs_fix(controller1)
                sleep(10)

            for compute in computes:
                self.ovs_fix(compute)

    def ovs_fix(self, node):
        """
        This is code to work around the ovs package upgrade issue
        : param node : Monter node object
        : type node : Node
        """

        # STEPS
        # 1. apt-get update; apt-get upgrade -y
        # 2. service networking stop
        # 3. /usr/share/openvswitch/scripts/ovs-ctl force-reload-kmod
        # 4. service networking start
        # 5. service keepalived restart

        node.update_packages()
        commands = ['/usr/share/openvswitch/scripts/ovs-ctl force-reload-kmod']

        if self.deployment.has_feature('highavailability'):
            if 'controller' in node.name:
                commands.append('service keepalived restart')

        node.run_cmd(';'.join(commands))
