""" A Deployment Features
"""
import logging
import requests
import sys

from monster.features.feature import Feature
from monster import util

logger = logging.getLogger(__name__)


class Deployment(Feature):
    """ Represents a feature across a deployment
    """

    def __init__(self, deployment, rpcs_feature):
        self.rpcs_feature = rpcs_feature
        self.deployment = deployment

    def __repr__(self):
        """
        Print out current instance
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

    def __init__(self, deployment, provider):
        """
        Create neutron feature in deployment

        :param deployment: The deployment to add neutron feature
        :type deployment: Object
        :param provider: feature provider (quantum/neutron)
        :type provider: String
        """

        super(Neutron, self).__init__(deployment, provider)

        # Grab correct environment based on the provider passed in the config
        self.environment = util.config['environments'][str(self)][provider]

        # Set the provider name in object (future use)
        self.provider = provider

    def update_environment(self):
        """
        Updates environment file to include feature
        """
        self.deployment.environment.add_override_attr(self.provider,
                                                      self.environment)

    def post_configure(self):
        """
        Runs cluster post configure commands
        """

        # Build OVS bridge for networking
        self._build_bridges()

        # Auto add default icmp and tcp sec rules
        #self._add_security_rules()

    def _add_security_rules(self):
        """
        Auto adds sec rules for ping and ssh
        """

        icmp_command = ("source openrc admin; "
                        "{0} security-group-rule-create "
                        "--protocol icmp "
                        "--direction ingress "
                        "default").format(self.provider)
        tcp_command = ("source openrc admin; "
                       "{0} security-group-rule-create "
                       "--protocol tcp "
                       "--port-range-min 22 "
                       "--port-range-max 22 "
                       "--direction ingress "
                       "default").format(self.provider)
        tcp_command2 = ("source openrc admin; "
                        "{0} security-group-rule-create "
                        "--protocol tcp "
                        "--port-range-min 8080 "
                        "--port-range-max 8080 "
                        "--direction ingress "
                        "default").format(self.provider)

        controller = next(self.deployment.search_role('controller'))
        logger.info("## Setting up ICMP security rule ##")
        controller.run_cmd(icmp_command)
        logger.info("## Setting up TCP security rule ##")
        controller.run_cmd(tcp_command)
        logger.info("## Setting up LBAAS testing security rule ##")
        controller.run_cmd(tcp_command2)

    def _build_bridges(self):
        """
        Build the subnets
        """

        logger.info("### Beginning of Networking Block ###")

        controllers = self.deployment.search_role('controller')
        computes = self.deployment.search_role('compute')

        logger.info("### Building OVS Bridge and Ports on network nodes ###")

        for controller in controllers:
            iface = controller.get_vmnet_iface()
            command = self.iface_bb_cmd(iface)
            logger.debug("Running {0} on {1}".format(command, controller))
            controller.run_cmd(command)

        # loop through computes and run
        for compute in computes:
            iface = compute.get_vmnet_iface()
            command = self.iface_bb_cmd(iface)
            logger.debug("Running {0} on {1}".format(command, compute))
            compute.run_cmd(command)

        logger.info("### End of Networking Block ###")

    def iface_bb_cmd(self, iface):
        logger.info("Using iface: {0}".format(iface))
        commands = ['ip a f {0}'.format(iface),
                    'ovs-vsctl add-port br-{0} {0}'.format(
                        iface)]
        command = "; ".join(commands)
        return command

    def clear_bridge_iface(self):
        """
        Clear the configured iface for neutron use
        """

        controllers = self.deployment.search_role('controller')
        computes = self.deployment.search_role('compute')

        for controller in controllers:
            iface = controller.get_vmnet_iface()
            cmd = self.iface_cb_cmd(iface)
            controller.run_cmd(cmd)

        for compute in computes:
            iface = compute.get_vmnet_iface()
            cmd = self.iface_cb_cmd(iface)
            compute.run_cmd(cmd)

    def iface_cb_cmd(self, iface):
        logger.info("Using iface: {0}".format(iface))
        cmd = "ip a f {0}".format(iface)
        return cmd


class Swift(Deployment):
    """ Represents a block storage cluster enabled by swift
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Swift, self).__init__(deployment, rpcs_feature)
        self.environment = util.config['environments'][str(self)][rpcs_feature]

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            str(self), self.environment)
        self._set_keystone_urls()
        self._fix_environment()

    def post_configure(self, auto=False):
        build_rings = auto or bool(util.config['swift']['auto_build_rings'])
        self._build_rings(build_rings)

    def _set_keystone_urls(self):
        """
        Gets the controllers ip and sets the url for the env accordingly
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
        """
        This is needed to make the environment for swift line up to the
        requirements from rpcs.
        """

        env = self.deployment.environment
        master_key = util.config['swift']['master_env_key']
        keystone = env.override_attributes['keystone']
        swift = env.override_attributes['swift'][master_key]
        swift['keystone'] = keystone

        logger.info("Matching environment: {0} to RPCS "
                    "swift requirements".format(env.name))

        env.del_override_attr('keystone')
        env.del_override_attr('swift')
        env.add_override_attr(master_key, swift)

        env.save()

    def _build_rings(self, auto=False):
        """
        This will either build the rings or print how to build the rings.

        :param auto: Whether or not to auto build the rings
        :type auto: Boolean
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
                logger.info(
                    "## Configuring Disks on Storage Node @ {0} ##".format(
                        storage_node.ipaddress))
                command = "; ".join(commands)
                storage_node.run_cmd(command)
            else:
                logger.info("## Info to setup drives for Swift ##")
                logger.info(
                    "## Log into root@{0} and run the following commands: "
                    "##".format(storage_node.ipaddress))
                for command in commands:
                    logger.info(command)

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
            logger.info(
                "## Setting up swift rings for deployment ##")
            command = "; ".join(commands)
            controller.run_cmd(command)
        else:
            logger.info("## Info to manually set up swift rings: ##")
            logger.info(
                "## Log into root@{0} and run the following commands: "
                "##".format(controller.ipaddress))
            for command in commands:
                logger.info(command)

        #####################################################################
        ############# Time to distribute the ring to all the boxes ##########
        #####################################################################

        command = "/usr/bin/swift-ring-minion-server -f -o"
        for proxy_node in proxy_nodes:
            if auto:
                logger.info(
                    "## Pulling swift ring down on proxy node @ {0}: "
                    "##".format(proxy_node.ipaddress))
                proxy_node.run_cmd(command)
            else:
                logger.info(
                    "## On node root@{0} run the following command: "
                    "##".format(proxy_node.ipaddress))
                logger.info(command)

        for storage_node in storage_nodes:
            if auto:
                logger.info(
                    "## Pulling swift ring down on storage node: {0} "
                    "##".format(storage_node.ipaddress))
                storage_node.run_cmd(command)
            else:
                logger.info(
                    "## On node root@{0} run the following command: "
                    "##".format(storage_node.ipaddress))
                logger.info(command)

        #####################################################################
        ############### Finalize by running chef on controler ###############
        #####################################################################

        if auto:
            logger.info("Finalizing install on all nodes")
            for proxy_node in proxy_nodes:
                proxy_node.run()
            for storage_node in storage_nodes:
                storage_node.run()
            controller.run()
        else:
            for proxy_node in proxy_nodes:
                logger.info("On node root@{0}, run: "
                            "chef client".format(proxy_node.ipaddress))
            for storage_node in storage_nodes:
                logger.info("On node root@{0}, run: "
                            "chef client".format(storage_node.ipaddress))
            logger.info("On node root@{0} run the following command: "
                        "chef-client ##".format(controller.ipaddress))

        logger.info("## Done setting up swift rings ##")


class Glance(Deployment):
    """ Represents a glance with cloud files backend
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Glance, self).__init__(deployment, rpcs_feature)
        self.environment = util.config['environments'][str(self)][rpcs_feature]

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

        if not response.ok:
            logger.info("Unauthorized with provided credentials.")
            sys.exit(1)
        try:
            services = response.json()['access']['serviceCatalog']
        except KeyError:
            logger.info(
                "Response content for glance files has no key: serviceCatalog")
            sys.exit(1)

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

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            str(self), self.environment)

        # Check to see if we need to add the secret info to
        # connect to AD/ldap
        if 'actived' in self.rpcs_feature or 'openldap' in self.rpcs_feature:
            # grab values from secrets file
            url = util.config['secrets'][self.rpcs_feature]['url']
            user = util.config['secrets'][self.rpcs_feature]['user']
            password = util.config['secrets'][self.rpcs_feature]['password']
            users = util.config['secrets'][self.rpcs_feature]['users']

            # Grab environment
            env = self.deployment.environment

            # Override the attrs
            env.override_attributes['keystone']['ldap']['url'] = url
            env.override_attributes['keystone']['ldap']['user'] = user
            env.override_attributes['keystone']['ldap']['password'] = password
            env.override_attributes['keystone']['users'] = users

            # Save the Environment
            self.deployment.environment.save()

    def pre_configure(self):

        # Grab environment
        env = self.deployment.environment

        # Check to see if we need to add the secret info to
        # connect to AD/ldap
        if 'actived' in self.rpcs_feature or 'openldap' in self.rpcs_feature:

            # Add the service user passwords
            for user, value in util.config['secrets'][
                    self.rpcs_feature].items():
                if self.deployment.feature_in(user):
                    env.override_attributes[user]['service_pass'] = \
                        value['service_pass']
            self.deployment.environment.save()


class Nova(Deployment):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        """
        Decides nova block
        nova networks: when neutron or quantum is not a deployment feature
        neutron: when neutron is a deployment feature
        quantum: when quantum is neutron's rpcs feature
        """
        super(Nova, self).__init__(deployment, rpcs_feature)

    def get_net_choice(self):
        """
        determines network choice
        """
        if self.deployment.feature_in('neutron'):
            for feature in self.deployment.features:
                if feature.__class__.__name__ == 'Neutron':
                    return feature.rpcs_feature
        else:
            return "default"

    def update_environment(self):
        net_choice = self.get_net_choice()
        self.environment = util.config['environments'][str(self)][net_choice]
        self.deployment.environment.add_override_attr(
            str(self), self.environment)

        self.deployment.environment.save()


class Horizon(Deployment):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Horizon, self).__init__(deployment, rpcs_feature)
        self.environment = util.config['environments'][str(self)][rpcs_feature]

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            str(self), self.environment)


class Cinder(Deployment):
    """ Represents the Cinder feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Cinder, self).__init__(deployment, rpcs_feature)
        self.environment = util.config['environments'][str(self)][rpcs_feature]

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            str(self), self.environment)

    def post_configure(self):
        computes = self.deployment.search_role("compute")
        for compute in computes:
            compute.run()


class Ceilometer(Deployment):
    """ Represents the Ceilometer feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Ceilometer, self).__init__(deployment, rpcs_feature)
        self.environment = util.config['environments'][str(self)][rpcs_feature]

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

    def update_environment(self):
        pass


class Monitoring(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Monitoring, self).__init__(deployment, rpcs_feature,
                                         str(self))
        self.environment = util.config['environments'][self.name][rpcs_feature]

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

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)


class OsOpsNetworks(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(OsOpsNetworks, self).__init__(deployment, rpcs_feature,
                                            'osops_networks')
        self.environment = util.config['environments'][self.name]

    def update_environment(self):

        self.deployment.environment.add_override_attr(
            self.name, self.environment)


class HighAvailability(RPCS):
    """ Represents a highly available cluster
    """

    def __init__(self, deployment, rpcs_feature):
        super(HighAvailability, self).__init__(deployment, rpcs_feature,
                                               'vips')
        self.environment = util.config['environments'][self.name]

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
        self.deployment.environment.save()


class Openssh(RPCS):
    """ Configures OpenSSH
    """

    def __init__(self, deployment, rpcs_feature):
        super(Openssh, self).__init__(deployment, rpcs_feature, str(self))
        self.environment = util.config['environments'][self.name]

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)
