from time import sleep

from monster import util
from monster.upgrades.upgrade import Upgrade


class FourOneFour(Upgrade):
    """
    4.1.4 Upgrade Procedures
    """

    def __init__(self, deployment):
        super(FourOneFour, self).__init__(deployment)

    def upgrade(self):
        """
        Upgrades the deployment (very chefy, rcbopsy)
        """

        supported = util.config['upgrade']['supported'][self.deployment.branch]
        if 'v4.1.4' not in supported:
            util.logger.error("{0} to {1} upgarde not supported".format(
                self.deployment.branch, 'v4.1.4'))
            raise NotImplementedError

        # Gather all the nodes of the deployment
        chef_server = next(self.deployment.search_role('chefserver'))
        controllers = list(self.deployment.search_role('controller'))
        computes = list(self.deployment.search_role('compute'))

        # upgrade the chef server
        self.deployment.branch = 'v4.1.4'
        chef_server.upgrade()
        controller1 = controllers[0]

        # save image upload value
        override = self.deployment.environment.override_attributes
        try:
            image_upload = override['glance']['image_upload']
            override['glance']['image_upload'] = False
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
        else:
            controller1.upgrade()

        if self.deployment.feature_in('highavailability'):
            controller1.run_cmd("service haproxy restart; "
                                "monit restart rpcdaemon")
            # restart services of controller2
            controller2.run_cmd(start)

        # restore value of image upload
        if image_upload:
            override['glance']['image_upload'] = image_upload
            self.deployment.environment.save()

        # run the computes
        for compute in computes:
            compute.upgrade
