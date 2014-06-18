import logging
import sys

import requests

import monster.features.deployment.base as deployment_
import monster.active as actv


logger = logging.getLogger(__name__)


#############################################################################
############################ OpenStack Features #############################
#############################################################################


class Neutron(deployment_.Feature):
    """Represents a Neutron network cluster."""

    def __init__(self, deployment, provider):
        """Create Neutron feature in deployment.

        :param deployment: The deployment to add neutron feature
        :type deployment: Object
        :param provider: feature provider (quantum/neutron)
        :type provider: String
        """
        super(Neutron, self).__init__(deployment, provider)
        self.env = actv.config['environments'][str(self)][provider]
        self.provider = provider

    def update_environment(self):
        """Updates environment file to include feature."""
        env = self.deployment.environment
        env.add_override_attr(self.provider, self.env)
        env.save()

    def post_configure(self):
        """Runs cluster post-configure commands."""

        # Build OVS bridge for networking
        self._build_bridges()

        # Auto add default ICMP and TCP security rules
        #self._add_security_rules()

    def _add_security_rules(self):
        """Auto adds security rules for ping and SSH."""

        controller = self.deployment.first_node_with_role('controller')

        logger.info("## Setting up ICMP security rule ##")
        controller.run_cmd(
            "source openrc admin; "
            "{provider} security-group-rule-create --protocol icmp "
            "--direction ingress default".format(provider=self.provider))

        logger.info("## Setting up TCP security rule ##")
        controller.run_cmd(
            "source openrc admin; "
            "{provider} security-group-rule-create --protocol tcp "
            "--port-range-min 22 --port-range-max 22 --direction ingress "
            "default".format(provider=self.provider))

        logger.info("## Setting up LBAAS testing security rule ##")
        controller.run_cmd(
            "source openrc admin; "
            "{provider} security-group-rule-create --protocol tcp "
            "--port-range-min 8080 --port-range-max 8080 --direction ingress "
            "default".format(provider=self.provider))

    def _build_bridges(self):
        """Builds the subnets."""

        logger.info("### Beginning of Networking Block ###")
        logger.info("### Building OVS Bridge and Ports on network nodes ###")

        for controller in self.deployment.controllers:
            command = self.iface_bb_cmd(controller.vmnet_iface)
            logger.debug("Running {0} on {1}".format(command, controller.name))
            try:
                controller.run_cmd(command, attempts=2)
            except Exception:
                logger.warning("Failed to build bridge on " + controller.name)

        for compute in self.deployment.computes:
            command = self.iface_bb_cmd(compute.vmnet_iface)
            logger.debug("Running {0} on {1}".format(command, compute.name))
            try:
                compute.run_cmd(command, attempts=2)
            except Exception:
                logger.warning("Failed to build bridge on " + compute.name)

        logger.info("### End of Networking Block ###")

    def iface_bb_cmd(self, iface):
        logger.info("Using iface: {0}".format(iface))
        return 'ip a f {0}; ovs-vsctl add-port br-{0} {0}'.format(iface)

    def clear_bridge_iface(self):
        """Clears configured interface for Neutron use."""

        for controller in self.deployment.controllers:
            iface = controller.vmnet_iface
            controller.run_cmd(self.iface_cb_cmd(iface))

        for compute in self.deployment.computes:
            iface = compute.vmnet_iface
            compute.run_cmd(self.iface_cb_cmd(iface))

    def iface_cb_cmd(self, iface):
        logger.info("Using iface: {}".format(iface))
        return "ip a f {}".format(iface)


class Swift(deployment_.Feature):
    """Represents a Block Storage cluster enabled by Swift."""

    def __init__(self, deployment, rpcs_feature='default'):
        super(Swift, self).__init__(deployment, rpcs_feature)
        self.environment = actv.config['environments'][str(self)][rpcs_feature]

    def update_environment(self):
        env = self.deployment.environment
        env.add_override_attr(str(self), self.environment)
        self._set_keystone_urls()
        self._fix_environment()
        env.save()

    def post_configure(self, auto=False):
        build_rings = auto or \
            bool(actv.config['swift']['auto_build_rings'])
        self._build_rings(build_rings)

    def _set_keystone_urls(self):
        """Gets the controller's IP and sets the url for the env."""
        proxy_ip = self.deployment.first_node_with_role('proxy').ipaddress
        proxy_url = "http://{}:8080/v1/AUTH_%(tenant_id)s".format(proxy_ip)

        env = self.deployment.environment
        for item in env.override_attrs['keystone']:
            if 'url' in item:
                env.override_attrs['keystone'][item] = proxy_url
        env.save()

    def _fix_environment(self):
        """This is needed to make the environment for Swift line up to the
        requirements from Rackspace Private Cloud Software.
        """

        env = self.deployment.environment
        master_key = actv.config['swift']['master_env_key']
        keystone = env.override_attrs['keystone']
        swift = env.override_attrs['swift'][master_key]
        swift['keystone'] = keystone

        logger.info("Matching environment: {} to RPCS swift requirements"
                    .format(env.name))

        env.del_override_attr('keystone')
        env.del_override_attr('swift')
        env.add_override_attr(master_key, swift)
        env.save()

    def _build_rings(self, auto=False):
        """This will either build the rings or print how to build the rings.

        :param auto: Whether or not to auto build the rings
        :type auto: bool
        """

        # Gather all the nodes
        controller = self.deployment.first_node_with_role('controller')
        proxy_nodes = self.deployment.nodes_with_role('proxy')
        storage_nodes = self.deployment.nodes_with_role('storage')

        #####################################################################
        ################## Run chef on the controller node ##################
        #####################################################################

        controller.run()

        #####################################################################
        ####### Run through the storage nodes and set up the disks ##########
        #####################################################################

        # Build Swift Rings
        disk = actv.config['swift']['disk']
        label = actv.config['swift']['disk_label']
        for storage_node in storage_nodes:
            commands = ("/usr/local/bin/swift-partition.sh {disk}; "
                        "/usr/local/bin/swift-format.sh {label}; "
                        "mkdir -p /srv/node/{label}; "
                        "mount -t xfs -o noatime,nodiratime,logbufs=8 "
                        "/dev/{label} /srv/node/{label}; "
                        "chown -R swift:swift /srv/node"
                        .format(label=label, disk=disk))
            if auto:
                logger.info(
                    "## Configuring Disks on Storage Node @ {0} ##".format(
                        storage_node.ipaddress))
                command = "; ".join(commands)
                storage_node.run_cmd(command)
            else:
                logger.info("## Info to setup drives for Swift ##")
                logger.info("## Log into root@{ip} and run the following "
                            "commands: ##".format(ip=storage_node.ipaddress))
                for command in commands:
                    logger.info(command)

        ####################################################################
        ## Setup partitions on storage nodes, (must run as swiftops user) ##
        ####################################################################

        num_rings = actv.config['swift']['num_rings']
        part_power = actv.config['swift']['part_power']
        replicas = actv.config['swift']['replicas']
        min_part_hours = actv.config['swift']['min_part_hours']
        disk_weight = actv.config['swift']['disk_weight']

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

        builders = actv.config['swift']['builders']
        for builder in builders:
            name = builder
            port = builders[builder]['port']

            for index, node in enumerate(storage_nodes):

                # if the current index of the node is % num_rings = 0,
                # reset num so we don't add anymore rings past num_rings
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
        command = "; ".join(commands)

        if auto:
            logger.info(
                "## Setting up swift rings for deployment ##")
            command = "; ".join(commands)
            controller.run_cmd(command)
        else:
            logger.info("## Info to manually set up swift rings: ##")
            logger.info(
                "## Log into root@{host} and run: {cmd}"
                .format(host=controller.ipaddress, cmd=command))

        #####################################################################
        ############# Time to distribute the ring to all the boxes ##########
        #####################################################################

        command = "/usr/bin/swift-ring-minion-server -f -o"
        for proxy_node in proxy_nodes:
            if auto:
                logger.info(
                    "## Pulling swift ring down on proxy node {host} ##"
                    .format(host=proxy_node.ipaddress))
                proxy_node.run_cmd(command)
            else:
                logger.info("## On node {0} run: {cmd}"
                            .format(host=proxy_node.ipaddress, cmd=command))

        for storage_node in storage_nodes:
            if auto:
                logger.info(
                    "## Pulling swift ring down on storage node: {host} ##"
                    .format(host=storage_node.ipaddress))
                storage_node.run_cmd(command)
            else:
                logger.info("## On node {host} run: {cmd}"
                            .format(host=storage_node.ipaddress, cmd=command))

        #####################################################################
        ############### Finalize by running chef on controller ##############
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
                logger.info("On node {host}, run: chef client"
                            .format(host=proxy_node.ipaddress))
            for storage_node in storage_nodes:
                logger.info("On node {host}, run: chef client"
                            .format(host=storage_node.ipaddress))
            logger.info("On node {host} run: chef-client"
                        .format(host=controller.ipaddress))

        logger.info("## Done setting up swift rings ##")


class Glance(deployment_.Feature):
    """Represents a Glance with CloudFiles backend."""

    def __init__(self, deployment, rpcs_feature='default'):
        super(Glance, self).__init__(deployment, rpcs_feature)
        self.environment = actv.config['environments'][str(self)][rpcs_feature]

    def update_environment(self):
        env = self.deployment.environment
        env.add_override_attr(str(self), self.environment)
        if self.rpcs_feature == 'cf':
            self._add_credentials()
        env.save()

    def _add_credentials(self):
        cf_secrets = actv.config['secrets']['cloudfiles']
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
            logger.info("Response for glance files has no key: serviceCatalog")
            sys.exit(1)

        cloudfiles = next(s for s in services if s['type'] == "object-store")
        tenant_id = cloudfiles['endpoints'][0]['tenantId']

        api = self.environment['api']
        api['swift_store_user'] = "{0}:{1}".format(tenant_id, user)
        api['swift_store_key'] = password


class Keystone(deployment_.Feature):
    """Represents the Keystone feature."""

    def __init__(self, deployment, rpcs_feature='default'):
        super(Keystone, self).__init__(deployment, rpcs_feature)
        self.environment = actv.config['environments'][str(self)][rpcs_feature]

    def update_environment(self):
        env = self.deployment.environment
        env.add_override_attr(str(self), self.environment)

        # Check to see if we need to add the secret info to
        # connect to AD/LDAP
        if 'actived' in self.rpcs_feature or 'openldap' in self.rpcs_feature:
            # grab values from secrets file
            url = actv.config['secrets'][self.rpcs_feature]['url']
            user = actv.config['secrets'][self.rpcs_feature]['user']
            password = actv.config['secrets'][self.rpcs_feature]['password']
            users = actv.config['secrets'][self.rpcs_feature]['users']

            env.override_attrs['keystone']['ldap']['url'] = url
            env.override_attrs['keystone']['ldap']['user'] = user
            env.override_attrs['keystone']['ldap']['password'] = password
            env.override_attrs['keystone']['users'] = users
            env.save()

    def pre_configure(self):

        env = self.deployment.environment

        # Check to see if we need to add the secret info to
        # connect to AD/LDAP
        if 'actived' in self.rpcs_feature or 'openldap' in self.rpcs_feature:

            # Add the service user passwords
            for user, value in actv.config['secrets'][
                    self.rpcs_feature].items():
                if self.deployment.has_feature(user):
                    env.override_attrs[user]['service_pass'] = \
                        value['service_pass']
            env.save()


class Nova(deployment_.Feature):
    """Represents the Monitoring feature."""

    def __init__(self, deployment, rpcs_feature='default'):
        """Decides nova block.
        nova-networks: when neutron or quantum is not a deployment feature
        neutron: when neutron is a deployment feature
        quantum: when quantum is neutron's rpcs feature
        """
        super(Nova, self).__init__(deployment, rpcs_feature)

    def get_net_choice(self):
        """Determines network choice."""
        if self.deployment.has_feature('neutron'):
            for feature in self.deployment.features:
                if feature.__class__.__name__ == 'Neutron':
                    return feature.rpcs_feature
        else:
            return "default"

    def update_environment(self):
        net_choice = self.get_net_choice()
        self.environment = actv.config['environments'][str(self)][net_choice]
        env = self.deployment.environment
        env.add_override_attr(str(self), self.environment)
        env.save()


class Horizon(deployment_.Feature):
    """Represents the Dashboard feature."""

    def __init__(self, deployment, rpcs_feature='default'):
        super(Horizon, self).__init__(deployment, rpcs_feature)
        self.environment = actv.config['environments'][str(self)][rpcs_feature]

    def update_environment(self):
        env = self.deployment.environment
        env.add_override_attr(str(self), self.environment)
        env.save()


class Cinder(deployment_.Feature):
    """Represents the Cinder feature."""

    def __init__(self, deployment, rpcs_feature='default'):
        super(Cinder, self).__init__(deployment, rpcs_feature)
        self.environment = actv.config['environments'][str(self)][rpcs_feature]

    def post_configure(self):
        for compute in self.deployment.computes:
            compute.run()

    def update_environment(self):
        env = self.deployment.environment
        env.add_override_attr(str(self), self.environment)
        env.save()


class Ceilometer(deployment_.Feature):
    """Represents the Ceilometer feature."""

    def __init__(self, deployment, rpcs_feature='default'):
        super(Ceilometer, self).__init__(deployment, rpcs_feature)
        self.environment = actv.config['environments'][str(self)][rpcs_feature]

    def update_environment(self):
        env = self.deployment.environment
        env.add_override_attr(str(self), self.environment)
        env.save()


#############################################################################
############### Rackspace Private Cloud Software Features ###################
#############################################################################


class RPCS(deployment_.Feature):
    """Represents a Rackspace Private Cloud Software deployment_.Feature."""

    def __init__(self, deployment, rpcs_feature, name):
        super(RPCS, self).__init__(deployment, rpcs_feature)
        self.name = name

    def update_environment(self):
        pass


class Monitoring(RPCS):
    """Represents a Monitoring feature."""

    def __init__(self, deployment, rpcs_feature='default'):
        super(Monitoring, self).__init__(deployment, rpcs_feature, str(self))
        self.environment = actv.config['environments'][self.name][rpcs_feature]

    def update_environment(self):
        env = self.deployment.environment
        env.add_override_attr(self.name, self.environment)
        env.save()


class MySql(RPCS):
    """Represents a MySQL feature."""

    def __init__(self, deployment, rpcs_feature='default'):
        super(MySql, self).__init__(deployment, rpcs_feature, str(self))
        self.environment = actv.config['environments'][self.name][rpcs_feature]

    def update_environment(self):
        env = self.deployment.environment
        env.add_override_attr(self.name, self.environment)
        env.save()


class OsOps(RPCS):
    """Represents an OpenStack Ops feature."""

    def __init__(self, deployment, rpcs_feature='default'):
        super(OsOps, self).__init__(deployment, rpcs_feature, str(self))
        self.environment = actv.config['environments'][self.name][rpcs_feature]

    def update_environment(self):
        env = self.deployment.environment
        env.add_override_attr(self.name, self.environment)
        env.save()


class DeveloperMode(RPCS):
    """Represents developer mode feature."""

    def __init__(self, deployment, rpcs_feature='default'):
        super(DeveloperMode, self).__init__(deployment,
                                            rpcs_feature, 'developer_mode')
        self.environment = actv.config['environments'][self.name][rpcs_feature]

    def update_environment(self):
        env = self.deployment.environment
        env.add_override_attr(self.name, self.environment)
        env.save()


class OsOpsNetworks(RPCS):
    """Represents OpenStack Ops Networking feature."""

    def __init__(self, deployment, rpcs_feature='default'):
        super(OsOpsNetworks, self).__init__(deployment,
                                            rpcs_feature, 'osops_networks')
        self.environment = actv.config['environments'][self.name]

    def update_environment(self):
        env = self.deployment.environment
        env.add_override_attr(self.name, self.environment)
        env.save()


class HighAvailability(RPCS):
    """Represents a 'Highly Available' cluster."""

    def __init__(self, deployment, rpcs_feature):
        super(HighAvailability, self).__init__(deployment,
                                               rpcs_feature, 'vips')
        self.environment = actv.config['environments'][self.name]

    def update_environment(self):
        env = self.deployment.environment
        env.add_override_attr(self.name, self.environment)
        env.save()


class OpenLDAP(RPCS):
    """Represents a keystone with an OpenLDAP backend."""

    def __init__(self, deployment, rpcs_feature):
        super(OpenLDAP, self).__init__(deployment, rpcs_feature, str(self))
        self.environment = actv.config['environments'][self.name]

    def update_environment(self):
        env = self.deployment.environment
        env.add_override_attr(self.name, self.environment)

        ldap_server = self.deployment.first_node_with_role('openldap')
        password = actv.config['ldap']['pass']
        ip = ldap_server.ipaddress

        env.override_attrs['keystone']['ldap']['url'] = "ldap://{0}".format(ip)
        env.override_attrs['keystone']['ldap']['password'] = password
        env.save()


class Openssh(RPCS):
    """Configures OpenSSH."""

    def __init__(self, deployment, rpcs_feature):
        super(Openssh, self).__init__(deployment, rpcs_feature, str(self))
        self.environment = actv.config['environments'][self.name]

    def update_environment(self):
        env = self.deployment.environment
        env.add_override_attr(self.name, self.environment)
        env.save()
