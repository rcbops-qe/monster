""" A Deployment Features
"""

import os
import json
import time
import requests
from string import Template
from itertools import chain, ifilter
from novaclient.v1_1 import client

from monster.features.feature import Feature
from monster.features.node_features import Tempest as NodeTempest
from monster import util


class Deployment(Feature):
    """ Represents a feature across a deployment
    """

    def __init__(self, deployment, rpcs_feature):
        self.rpcs_feature = rpcs_feature
        self.deployment = deployment

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        pass

    def pre_configure(self):
        pass

    def apply_feature(self):
        pass

    def post_configure(self):
        pass

#############################################################################
############################ OpenStack Features #############################
#############################################################################


class Neutron(Deployment):
    """ Represents a neutron network cluster
    """

    def __init__(self, deployment, rpcs_feature):
        super(Neutron, self).__init__(deployment, rpcs_feature)
        self.environment = util.config['environments'][str(self)][rpcs_feature]
        self.provider = rpcs_feature

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(self.provider,
                                                      self.environment)
        self._fix_nova_environment()

    def post_configure(self, auto=False):
        """ Runs cluster post configure commands
        """
        if self.deployment.os_name in ['centos', 'rhel']:
            # This is no longer needed. i think
            #self._reboot_cluster()
            pass

        # Grab the config to auto build or not
        auto_build = auto or \
            util.config[str(self)]['auto_build_subnets']
        self._build_subnets(auto_build)

    def _fix_nova_environment(self):
        # When enabling neutron, have to update the env var correctly
        env = self.deployment.environment
        neutron_network = {'provider': self.provider}
        if 'networks' in env.override_attributes['nova']:
            del env.override_attributes['nova']['networks']
            env.override_attributes['nova']['network'] = neutron_network

        # update the vip to correct api name and vip value
        if self.deployment.feature_in("highavailability"):
            api_name = '{0}-api'.format(self.provider)
            api_vip = util.config[str(self)][self.deployment.os_name]['vip']
            env.override_attributes['vips'][api_name] = api_vip
        env.save()

    def _reboot_cluster(self):

        # reboot the deployment
        self.deployment.reboot_deployment()

        # Sleep for 20 seconds to let the deployment reboot
        time.sleep(20)

        # Keep sleeping till the deployment comes back
        # Max at 8 minutes
        sleep_in_minutes = 5
        total_sleep_time = 0
        while not self.deployment.is_online():
            print "## Current Deployment is Offline ##"
            print "## Sleeping for {0} minutes ##".format(
                str(sleep_in_minutes))
            time.sleep(sleep_in_minutes * 60)
            total_sleep_time += sleep_in_minutes
            sleep_in_minutes -= 1

            # if we run out of time to wait, exit
            if sleep_in_minutes == 0:
                error = ("## -- Failed to reboot deployment"
                         "after {0} minutes -- ##".format(total_sleep_time))
                raise Exception(error)

    def _build_subnets(self, auto=False):
        """ Will print out or build the subnets
        """

        util.logger.info("### Beginning of Networking Block ###")

        network_bridge_device = util.config[str(self)][
            self.deployment.os_name]['network_bridge_device']
        controllers = self.deployment.search_role('controller')
        computes = self.deployment.search_role('compute')

        commands = ['ip a f {0}'.format(network_bridge_device),
                    'ovs-vsctl add-port br-{0} {0}'.format(
                        network_bridge_device)]
        command = "; ".join(commands)

        if auto:
            util.logger.info("### Building OVS Bridge and "
                             "Ports on network nodes ###")
            for controller in controllers:
                controller.run_cmd(command)
                for compute in computes:
                    compute.run_cmd(command)
        else:
            util.logger.info("### To build the OVS network bridge "
                             "log onto your controllers and computes"
                             " and run the following command: ###")
            util.logger.info(command)

        commands = ["source openrc admin",
                    "{0} net-create nettest".format(
                        self.rpcs_feature, network_bridge_device),
                    ("{0} subnet-create --name testnet "
                     "--no-gateway nettest 172.0.0.0/8".format(
                         self.rpcs_feature))]
        command = "; ".join(commands)

        if auto:
            util.logger.info("Adding Neutron Network")
            for controller in controllers:
                util.logger.info(
                    "Attempting to setup network on {0}".format(
                        controller.name))

                network_run = controller.run_cmd(command)
                if network_run['success']:
                    util.logger.info("Network setup succedded")
                    break
                else:
                    util.logger.info(
                        "Failed to setup network on {0}".format(
                            controller.name))

            if not network_run['success']:
                util.logger.info("## Failed to setup networks, "
                                 "please check logs ##")
        else:
            util.logger.info("### To Add Neutron Network log onto the active "
                             "controller and run the following commands: ###")
            for command in commands:
                util.logger.info(command)

        util.logger.info("### End of Networking Block ###")


class Swift(Deployment):
    """ Represents a block storage cluster enabled by swift
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Swift, self).__init__(deployment, rpcs_feature)
        self.environment = util.config['environments'][str(self)][rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            str(self), self.environment)
        self._set_keystone_urls()
        self._fix_environment()

    def post_configure(self, auto=False):
        build_rings = auto or bool(util.config['swift']['auto_build_rings'])
        self._build_rings(build_rings)

    def _set_keystone_urls(self):
        """ Gets the controllers ip and sets the url for the env
        accordingly
        """
        proxy_ip = next(
            self.deployment.search_role('proxy')).ipaddress

        env = self.deployment.environment

        proxy_url = \
            "http://{0}:8080/v1/AUTH_%(tenant_id)s".format(proxy_ip)

        for item in env.override_attributes['keystone']:
            if 'url' in item:
                env.override_attributes['keystone'][item] = proxy_url

        env.save()

    def _fix_environment(self):
        """ This is needed to make the environment for swift line up to the
        requirements from rpcs.
        """

        env = self.deployment.environment
        master_key = util.config['swift']['master_env_key']
        keystone = env.override_attributes['keystone']
        swift = env.override_attributes['swift'][master_key]
        swift['keystone'] = keystone

        util.logger.info("Matching environment: {0} to RPCS "
                         "swift requirements".format(env.name))

        env.del_override_attr('keystone')
        env.del_override_attr('swift')
        env.add_override_attr(master_key, swift)

        env.save()

    def _build_rings(self, auto=False):
        """ This will either build the rings or
            print how to build the rings.
            @param auto Whether or not to auto build the rings
            @type auto Boolean
        """

        # Gather all the nodes
        controller = next(self.deployment.search_role('controller'))
        proxy_nodes = list(self.deployment.search_role('proxy'))
        storage_nodes = list(self.deployment.search_role('storage'))

        #####################################################################
        ################## Run chef on the controller node ##################
        #####################################################################

        controller.run()

        #####################################################################
        ####### Run through the storage nodes and set up the disks ##########
        #####################################################################

        # Build Swift Rings
        disk = util.config['swift']['disk']
        label = util.config['swift']['disk_label']
        for storage_node in storage_nodes:
            commands = ["/usr/local/bin/swift-partition.sh {0}".format(disk),
                        "/usr/local/bin/swift-format.sh {0}".format(label),
                        "mkdir -p /srv/node/{0}".format(label),
                        "mount -t xfs -o noatime,nodiratime,logbufs=8 "
                        "/dev/{0} /srv/node/{0}".format(label),
                        "chown -R swift:swift /srv/node"]
            if auto:
                util.logger.info(
                    "## Configuring Disks on Storage Node @ {0} ##".format(
                        storage_node.ipaddress))
                command = "; ".join(commands)
                storage_node.run_cmd(command)
            else:
                util.logger.info("## Info to setup drives for Swift ##")
                util.logger.info(
                    "## Log into root@{0} and run the following commands: "
                    "##".format(storage_node.ipaddress))
                for command in commands:
                    util.logger.info(command)

        ####################################################################
        ## Setup partitions on storage nodes, (must run as swiftops user) ##
        ####################################################################

        num_rings = util.config['swift']['num_rings']
        part_power = util.config['swift']['part_power']
        replicas = util.config['swift']['replicas']
        min_part_hours = util.config['swift']['min_part_hours']
        disk_weight = util.config['swift']['disk_weight']

        commands = ["su swiftops",
                    "swift-ring-builder object.builder create "
                    "{0} {1} {2}".format(part_power,
                                         replicas,
                                         min_part_hours),
                    "swift-ring-builder container.builder create "
                    "{0} {1} {2}".format(part_power,
                                         replicas,
                                         min_part_hours),
                    "swift-ring-builder account.builder create "
                    "{0} {1} {2}".format(part_power,
                                         replicas,
                                         min_part_hours)]

        # Determine how many storage nodes we have and add them
        builders = util.config['swift']['builders']

        for builder in builders:
            name = builder
            port = builders[builder]['port']

            for index, node in enumerate(storage_nodes):

                # if the current index of the node is % num_rings = 0,
                # reset num so we dont add anymore rings past num_rings
                if index % num_rings is 0:
                    num = 0

                # Add the line to command to build the object
                commands.append("swift-ring-builder {0}.builder add "
                                "z{1}-{2}:{3}/{4} {5}".format(name,
                                                              num + 1,
                                                              node.ipaddress,
                                                              port,
                                                              label,
                                                              disk_weight))
                num += 1

        # Finish the command list
        cmd_list = ["swift-ring-builder object.builder rebalance",
                    "swift-ring-builder container.builder rebalance",
                    "swift-ring-builder account.builder rebalance",
                    "sudo cp *.gz /etc/swift",
                    "sudo chown -R swift: /etc/swift"]
        commands.extend(cmd_list)

        if auto:
            util.logger.info(
                "## Setting up swift rings for deployment ##")
            command = "; ".join(commands)
            controller.run_cmd(command)
        else:
            util.logger.info("## Info to manually set up swift rings: ##")
            util.logger.info(
                "## Log into root@{0} and run the following commands: "
                "##".format(controller.ipaddress))
            for command in commands:
                util.logger.info(command)

        #####################################################################
        ############# Time to distribute the ring to all the boxes ##########
        #####################################################################

        command = "/usr/bin/swift-ring-minion-server -f -o"
        for proxy_node in proxy_nodes:
            if auto:
                util.logger.info(
                    "## Pulling swift ring down on proxy node @ {0}: "
                    "##".format(proxy_node.ipaddress))
                proxy_node.run_cmd(command)
            else:
                util.logger.info(
                    "## On node root@{0} run the following command: "
                    "##".format(proxy_node.ipaddress))
                util.logger.info(command)

        for storage_node in storage_nodes:
            if auto:
                util.logger.info(
                    "## Pulling swift ring down on storage node: {0} "
                    "##".format(storage_node.ipaddress))
                storage_node.run_cmd(command)
            else:
                util.logger.info(
                    "## On node root@{0} run the following command: "
                    "##".format(storage_node.ipaddress))
                util.logger.info(command)

        #####################################################################
        ############### Finalize by running chef on controler ###############
        #####################################################################

        if auto:
            util.logger.info("Finalizing install on all nodes")
            for proxy_node in proxy_nodes:
                proxy_node.run()
            for storage_node in storage_nodes:
                storage_node.run()
            controller.run()
        else:
            for proxy_node in proxy_nodes:
                util.logger.info("On node root@{0}, run the following command: "
                                 "chef client".format(proxy_node.ipaddress))
            for storage_node in storage_nodes:
                util.logger.info("On node root@{0}, run the following command: "
                                 "chef client".format(storage_node.ipaddress))
            util.logger.info(
                "On node root@{0} run the following command: chef-client "
                "##".format(controller.ipaddress))

        util.logger.info("## Done setting up swift rings ##")


class Glance(Deployment):
    """ Represents a glance with cloud files backend
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Glance, self).__init__(deployment, rpcs_feature)
        self.environment = util.config['environments'][str(self)][rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            str(self), self.environment)
        if self.rpcs_feature == 'cf':
            self._add_credentials()

    def _add_credentials(self):
        cf_secrets = util.config['secrets']['cloudfiles']
        user = cf_secrets['user']
        password = cf_secrets['password']

        # acquire tenant_id
        data = ('{{"auth": {{"passwordCredentials": {{"username": "{0}", '
                '"password": "{1}"}}}}}}'.format(user, password))
        head = {"content-type": "application/json"}
        auth_address = self.environment['api']['swift_store_auth_address']
        url = "{0}/tokens".format(auth_address)
        response = requests.post(url, data=data, headers=head, verify=False)
        try:
            services = json.loads(response._content)['access'][
                'serviceCatalog']
        except KeyError:
            raise Exception("Unable to authenticate with Endpoint")
        cloudfiles = next(s for s in services if s['type'] == "object-store")
        tenant_id = cloudfiles['endpoints'][0]['tenantId']

        # set api credentials in environment
        api = self.environment['api']
        api['swift_store_user'] = "{0}:{1}".format(tenant_id, user)
        api['swift_store_key'] = password


class Keystone(Deployment):
    """ Represents the keystone feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Keystone, self).__init__(deployment, rpcs_feature)
        self.environment = util.config['environments'][str(self)][rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            str(self), self.environment)


class Nova(Deployment):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Nova, self).__init__(deployment, rpcs_feature)
        self.environment = util.config['environments'][str(self)][
            self.deployment.provisioner.short_name()]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            str(self), self.environment)
        bridge_dev = None
        if self.deployment.provisioner.short_name() == 'openstack':
            bridge_dev = 'eth1'
        elif self.deployment.os_name in ['centos', 'rhel']:
            bridge_dev = 'em1'
        if bridge_dev:
            env = self.deployment.environment

            util.logger.info("Setting bridge_dev to {0}".format(bridge_dev))
            env.override_attributes['nova']['networks']['public'][
                'bridge_dev'] = bridge_dev

            self.deployment.environment.save()


class Horizon(Deployment):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Horizon, self).__init__(deployment, rpcs_feature)
        self.environment = util.config['environments'][str(self)][rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            str(self), self.environment)


class Cinder(Deployment):
    """ Represents the Cinder feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Cinder, self).__init__(deployment, rpcs_feature)
        self.environment = util.config['environments'][str(self)][rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            str(self), self.environment)


#############################################################################
############### Rackspace Private Cloud Software Features ###################
#############################################################################


class RPCS(Deployment):
    """ Represents a Rackspace Private Cloud Software Feature
    """

    def __init__(self, deployment, rpcs_feature, name):
        super(RPCS, self).__init__(deployment, rpcs_feature)
        self.name = name

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        pass


class Monitoring(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Monitoring, self).__init__(deployment, rpcs_feature,
                                         str(self))
        self.environment = util.config['environments'][self.name][rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            str(self), self.environment)


class MySql(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(MySql, self).__init__(deployment, rpcs_feature,
                                    str(self))
        self.environment = util.config['environments'][self.name][rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)


class OsOps(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(OsOps, self).__init__(deployment, rpcs_feature,
                                    str(self))
        self.environment = util.config['environments'][self.name][rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)


class DeveloperMode(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(DeveloperMode, self).__init__(deployment, rpcs_feature,
                                            'developer_mode')
        self.environment = util.config['environments'][self.name][rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)


class OsOpsNetworks(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(OsOpsNetworks, self).__init__(deployment, rpcs_feature,
                                            'osops_networks')
        self.environment = util.config['environments'][self.name][
            self.deployment.provisioner.short_name()]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)


class HighAvailability(RPCS):
    """ Represents a highly available cluster
    """

    def __init__(self, deployment, rpcs_feature):
        super(HighAvailability, self).__init__(deployment, rpcs_feature,
                                               'vips')
        self.environment = util.config['environments'][self.name][
            deployment.os_name]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(self.name,
                                                      self.environment)


class OpenLDAP(RPCS):
    """ Represents a keystone with an openldap backend
    """

    def __init__(self, deployment, rpcs_feature):
        super(OpenLDAP, self).__init__(deployment, rpcs_feature,
                                       str(self))
        self.environment = util.config['environments'][self.name]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)

        ldap_server = self.deployment.search_role('openldap')
        password = util.config['ldap']['pass']
        ip = ldap_server.ipaddress
        env = self.deployment.environment

        # Override the attrs
        env.override_attributes['keystone']['ldap']['url'] = \
            "ldap://{0}".format(ip)
        env.override_attributes['keystone']['ldap']['password'] = password

        # Save the Environment
        self.node.deployment.environment.save()


class Openssh(RPCS):
    """ Configures ssh
    """

    def __init__(self, deployment, rpcs_feature):
        super(Openssh, self).__init__(deployment, rpcs_feature, str(self))
        self.environment = util.config['environments'][self.name]

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)


class Tempest(RPCS):

    def __init__(self, deployment, rpcs_feature):
        name = str(self)
        super(Tempest, self).__init__(deployment, rpcs_feature, name)
        self.path = "/tmp/%s.conf" % self.deployment.name
        self.tempest_config = dict(
            identity="", user1_user="", user1_password="", user1_tenant="",
            user2_user="", user2_password="", user2_tenant="", admin_user="",
            admin_password="", admin_tenant="", image_id1="", image_id2="",
            public_network_id="", public_router_id="", storage_protocol="",
            vendor_name="", glance_ip="", aws_access="", aws_secret="",
            horizon="", cinder_enabled="", neutron_enabled="",
            glance_enabled="", swift_enabled="", heat_enabled="", nova_ip=""
        )

    def tempest_configure(self):
        tempest = self.tempest_config
        override = self.deployment.environment.override_attributes
        controller = next(self.deployment.search_role("controller"))

        if "highavailability" in self.deployment.feature_names():
            #use vips
            vips = override['vips']
            tempest['identity'] = vips['keystone-service-api']
            tempest['glance_ip'] = vips['glance-api']
            tempest['horizon'] = vips['horizon-dash']
            tempest['nova_ip'] = vips['nova-api']
        else:
            # use controller1
            tempest['identity'] = controller.ipaddress
            tempest['glance_ip'] = controller.ipaddress
            tempest['horizon'] = controller.ipaddress
            tempest['nova_ip'] = controller.ipaddress

        ec2_creds = controller['credentials']['EC2']['admin']
        tempest['aws_access'] = ec2_creds['access']
        tempest['aws_secret'] = ec2_creds['secret']

        keystone = override['keystone']
        users = keystone['users']
        non_admin_users = (user for user in users.keys()
                           if "admin" not in users[user]['roles'].keys())
        user1 = next(non_admin_users)
        tempest['user1_user'] = user1
        tempest['user1_password'] = users[user1]['password']
        tempest['user1_tenant'] = users[user1]['roles']['Member'][0]
        user2 = next(non_admin_users, None)
        if user2:
            tempest['user2_user'] = user2
            tempest['user2_password'] = users[user2]['password']
            tempest['user2_tenant'] = users[user2]['roles']['Member'][0]
        admin_user = keystone['admin_user']
        tempest['admin_user'] = admin_user
        tempest['admin_password'] = users[admin_user][
            'password']
        tempest['admin_tenant'] = users[admin_user][
            'roles']['admin'][0]
        url = "http://{0}:5000/v2.0".format(tempest['glance_ip'])
        compute = client.Client(tempest['admin_user'],
                                tempest['admin_password'],
                                tempest['admin_tenant'],
                                url,
                                service_type="compute")
        image_ids = (i.id for i in compute.images.list())
        try:
            tempest['image_id1'] = next(image_ids)
        except StopIteration:
            util.logger.error("No glance images available")
            tempest['image_id1']
        try:
            tempest['image_id2'] = next(image_ids)
        except StopIteration:
            tempest['image_id2'] = tempest['image_id1']

        # tempest.public_network_id = None
        # tempest.public_router_id = None

        featured = lambda x: self.deployment.feature_in(x)
        tempest['cinder_enabled'] = False
        if featured('cinder'):
            tempest['cinder_enabled'] = True
            tempest['storage_protocol'] = override['cinder']['storage'][
                'provider']
            tempest['vendor_name'] = "Open Source"

        tempest['neutron_enabled'] = True if featured('neutron') else False
        tempest['glance_enabled'] = True if featured('glance') else False
        tempest['swift_enabled'] = True if featured('swift') else False
        tempest['heat_enabled'] = True if featured('orchestration') else False

    def pre_configure(self):
        controller = next(self.deployment.search_role("controller"))
        tempest_feature = NodeTempest(controller)
        env = self.deployment.environment
        env.override_attributes['glance']['image_upload'] = True
        env.save()
        controller.features.append(tempest_feature)

    def post_configure(self):
        controller = next(self.deployment.search_role("controller"))
        self.build_config()

        # Send config
        tempest_dir = util.config['tests']['tempest']['dir']
        rem_config_path = "{0}/etc/tempest.conf".format(tempest_dir)
        controller.run_cmd("rm {0}".format(rem_config_path))
        controller.scp_to(self.path, remote_path=rem_config_path)

        # run tests
        exclude = ['volume', 'resize', 'floating']
        self.test_from(controller, xunit=True, exclude=exclude)

    def build_config(self):
        self.tempest_configure()
        template_path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), os.pardir, os.pardir,
            "files/tempest.conf")

        with open(template_path) as f:
            template = Template(f.read()).substitute(
                self.tempest_config)

        with open(self.path, 'w') as w:
            util.logger.info("Writing tempest config:{0}".
                             format(self.path))
            util.logger.debug(template)
            w.write(template)

    def test_from(self, node, xunit=False, tags=None, exclude=None,
                  paths=None, config_path=None):
        """
        Runs tests from node
        @param xunit: Produce xunit report
        @type xunit: Boolean
        @param tags: Tags to pass the nosetests
        @type tags: list
        @param exclude: Expressions to exclude
        @param exclude: list
        @param paths: Paths to load tests from (compute, compute/servers...)
        @param paths: list
        """

        tempest_dir = util.config['tests']['tempest']['dir']
        checkout = "cd {0}; git checkout stable/havana".format(tempest_dir)
        node.run_cmd(checkout)

        xunit_file = "{0}.xml".format(node.name)
        xunit_flag = ''
        if xunit:
            xunit_flag = '--with-xunit --xunit-file=%s' % xunit_file

        tag_flag = "-a " + " -a ".join(tags) if tags else ""

        exclude_flag = "-e " + " -e ".join(exclude) if exclude else ''

        test_map = util.config['tests']['tempest']['test_map']
        if not paths:
            features = self.deployment.feature_names()
            paths = ifilter(None, set(
                chain(*ifilter(None, (
                    test_map.get(feature, None) for feature in features)))))
        path_args = " ".join(paths)
        config_arg = ""
        if config_path:
            config_arg = "-c {0}".format(config_path)
        venv_bin = ".venv/bin"
        tempest_command = (
            "source {0}/{6}/activate; "
            "python -u {0}/{6}/nosetests -w "
            "{0}/tempest/api {5} "
            "{1} {2} {3} {4}".format(tempest_dir, xunit_flag,
                                     tag_flag, path_args,
                                     exclude_flag, config_arg, venv_bin)
        )
        screen = [
            "screen -d -m -S tempest -t shell -s /bin/bash",
            "screen -S tempest -X screen -t tempest",
            "export NL=`echo -ne '\015'`",
            'screen -S tempest -p tempest -X stuff "{0}$NL"'.format(
                tempest_command)
        ]
        command = "; ".join(screen)
        node.run_cmd(command)
        # if xunit:
        #     node.scp_from(xunit_file, local_path=".")
        #     util.xunit_merge()
