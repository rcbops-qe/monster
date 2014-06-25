import logging

from time import sleep

import monster.active as actv
from monster.upgrades.upgrade import Upgrade

logger = logging.getLogger(__name__)


class FourTwoThree(Upgrade):
    """
    4.2.3 Upgrade Procedures
    """

    def __init__(self, deployment):
        super(FourTwoThree, self).__init__(deployment)

    def upgrade(self, rc=False):
        """
        Upgrades the deployment (very chefy, rcbopsy)
        """

        current_branch = self.deployment.branch

        if rc:
            upgrade_branch = "v4.2.3rc"
        else:
            upgrade_branch = "v4.2.3"

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

        # prepare the upgrade
        if "4.1" in current_branch:
            if self.deployment.os_name == "ubuntu":
                self.pre_upgrade()
            self.mungerate()

        # Gather all the nodes of the deployment
        chef_server, controllers, computes = self.deployment_nodes()
        controller1 = self.deployment.controller(1)

        # upgrade chef
        chef_server.upgrade()

        # change environment flags for upgrade
        try:
            image_upload = override['glance']['image_upload']
            override['glance']['image_upload'] = False
            override['osops']['do_package_upgrades'] = True
            self.deployment.environment.save()
        except KeyError:
            pass

        # Upgrade nodes
        if self.deployment.feature_in('highavailability'):
            controller2 = self.deployment.controller(2)
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

            # sleep for monit
            sleep(30)

            #restart services
            controller1.run_cmd("service haproxy restart", attempts=2)
            controller1.run_cmd("monit restart rpcdaemon", attempts=5)

            # restart services of controller2
            controller2.run_cmd(start, attempts=5)
        else:
            controller1.upgrade()

        if "4.1" in current_branch:
            # restore quantum db
            restore_db = actv.config['upgrade']['commands']['restore-db']
            controller1.run_cmd(restore_db)

        # restore value of image upload
        if image_upload:
            override['glance']['image_upload'] = image_upload
            override['osops']['do_package_upgrades'] = False
            self.deployment.environment.save()

        # run the computes
        for compute in computes:
            compute.upgrade(times=2)

        # post upgrade
        if "4.1" in current_branch:
            if self.deployment.os_name == "ubuntu":
                self.post_upgrade()
