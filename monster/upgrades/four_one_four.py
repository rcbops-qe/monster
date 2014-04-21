import logging

from time import sleep

from monster import util
from monster.upgrades.upgrade import Upgrade

logger = logging.getLogger(__name__)


class FourOneFour(Upgrade):
    """
    4.1.4 Upgrade Procedures
    """

    def __init__(self, deployment):
        super(FourOneFour, self).__init__(deployment)

    def upgrade(self, rc=False):
        """
        Upgrades the deployment (very chefy, rcbopsy)
        """

        if rc:
            upgrade_branch = "v4.1.4rc"
        else:
            upgrade_branch = "v4.1.4"

        supported = util.config['upgrade']['supported'][self.deployment.branch]
        if upgrade_branch not in supported:
            logger.error("{0} to {1} upgrade not supported".format(
                self.deployment.branch,
                upgrade_branch
            ))
            raise NotImplementedError

        # load override attrs from env
        override = self.deployment.environment.override_attributes

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

        if self.deployment.feature_in('highavailability'):
            controller2 = controllers[1]
            stop = util.config['upgrade']['commands']['stop-services']
            start = util.config['upgrade']['commands']['start-services']

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

            # Restart Services
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
