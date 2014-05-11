"""
Module to test High Availability in RPC
"""
import logging
import os
import sys
import socket

from time import sleep
from subprocess import call
import novaclient.v1_1.client as nova_
import neutronclient.v2_0.client as neutron_

from monster.utils.color import Color
from monster.tests.test import Test
from monster.tests.util import xunit_merge

logger = logging.getLogger(__name__)


class Creds(object):
    """Openstack cred object."""
    def __init__(self, user, password, url):
        self.user = user
        self.password = password
        self.url = url


class Build(object):
    """Builds state to be verified after failover."""
    def __init__(self, server, network_id, subnet_id, name, iface_port, image,
                 flavor):
        self.server = server
        self.name = name
        self.image = image
        self.flavor = flavor
        self.iface_port = iface_port
        self.network_id = network_id
        self.subnet_id = subnet_id
        self.ip_info = None
        self.router_id = None

    def destroy(self, nova, neutron, progress, node1, node2):
        """Cleans up build state from OpenStack."""
#float     neutron floatingip-delete [floatingip-id]
#instance  nova delete [instance-id]
#iface     neutron router-interface-delete [router-id] [subnet-id]
#router    neutron router-delete [router-id]
#subnet    neutron subnet-delete [subnet-id]
#network   neutron net-delete [network-id]
        logger.info('Cleaning up instance and network clutter...')

        logger.debug('Deleting floating IP')
        progress.update("Progress")
        deleted = False
        while not deleted:
            try:
                neutron.delete_floatingip(self.ip_info['id'])
                deleted = True
            except:
                deleted = False

        logger.debug('Deleting server {0}'.format(self.name))
        progress.update("Progress")
        deleted = False
        while not deleted:
            try:
                # Run server deletion command
                logger.debug("Attempting server deletion")
                progress.update("Progress")
                nova.servers.delete(self.server)

            except:
                deleted = False

            max_tries = 60
            current_try = 1
            # If "No server" is not found in the return, then the server
            # has not yet been deleted...
            deleted = True
            really_deleted = False
            while not really_deleted:
                try:
                    nova.servers.get(self.server)
                    if current_try > max_tries:
                        # Force kill RabbitMQ server and start it back up
                        logger.error(Color.red("Server deletion is hung"))
                        progress.update("Progress")
                        self.kill_rabbit(node1, node2)
                        deleted = False
                        break

                    logger.warning(Color.yellow("Deleting server: {0}".format(
                        current_try)))
                    progress.update("Progress")
                    sleep(1)
                    current_try += 1
                except:
                    logger.debug(Color.green("Server deleted."))
                    really_deleted = True
                    deleted = True

        logger.debug('Deleting router interface')
        progress.update("Progress")
        deleted = False
        while not deleted:
            try:
                neutron.remove_interface_router(self.router_id,
                                                {"subnet_id": self.subnet_id})
                deleted = True
            except:
                deleted = False

        logger.debug("Deleting router")
        progress.update("Progress")
        deleted = False
        while not deleted:
            try:
                neutron.delete_router(self.router_id)
                deleted = True
            except:
                deleted = False

        logger.debug("Deleting subnet")
        progress.update("Progress")
        deleted = False
        while not deleted:
            try:
                neutron.delete_subnet(self.subnet_id)
                deleted = True
            except:
                deleted = False

        logger.debug("Deleting network")
        progress.update("Progress")
        deleted = False
        while not deleted:
            try:
                neutron.delete_network(self.network_id)
                deleted = True
            except:
                deleted = False


class HATest(Test):
    """
    HA Openstack tests
    """
    def __init__(self, deployment, progress):
        super(HATest, self).__init__(deployment)
        self.iterations = 1
        self.progress = progress
        self.current_iteration = 0
        controllers = list(self.deployment.search_role("controller"))
        self.controller1 = controllers[0]
        self.controller2 = controllers[1]
        # get creds
        creds = self.gather_creds(deployment)

        # Setup clients
        self.nova = nova_.Client(username=creds.user,
                                 api_key=creds.password,
                                 project_id=creds.user,
                                 auth_url=creds.url)
        self.neutron = neutron_.Client(auth_url=creds.url,
                                       username=creds.user,
                                       password=creds.password,
                                       tenant_name=creds.user)
        self.rabbit = deployment.rabbitmq_mgmt_client

    @property
    def name(self):
        return "High Availability tests"

    def gather_creds(self, deployment):
        """
        Creates cred object based off deployment
        """
        keystone = deployment.override_attrs['keystone']
        user = keystone['admin_user']
        users = keystone['users']
        password = users[user]['password']
        url = self.controller1['keystone']['adminURL']
        creds = Creds(user, password, url)
        return creds

    def instance_cmd(self, server_id, net_id, cmd):
        """
        Logs into instance using net namespace
        """
        namespace = "qdhcpd-{0}".format(net_id)
        server = self.nova.servers.get(server_id)
        server_ip = server['server']['ipaddress']
        icmd = ("ip netns exec {0} bash; "
                "ssh -o UseprKnownHostsFile=/dev/null "
                "-o StrictHostKeyChecking=no "
                "-i ~/.ssh/testkey {1}; "
                "{2}").format(namespace, server_ip, cmd)
        server.run_cmd(icmd)

    def create_network(self, network_name, router_external=False, shared=True):
        """
        Creates a neutron network
        """
        logger.debug("Creating network: {0}".format(network_name))
        new_net = {"network": {"name": network_name,
                               "router:external": router_external,
                               "shared": shared}}
        net = self.neutron.create_network(new_net)
        network_id = net['network']['id']
        logger.debug("Network ({0}) created".format(network_id))
        return network_id

    def create_subnet(self, subnet_name, network_id, subnet_cidr, pnet=False):
        """
        Creates a neutron subnet
        """
        logger.debug("Creating subnetwork: {0}".format(subnet_name))
        if pnet:
            new_subnet = {"subnet": {
                "name": subnet_name, "network_id": network_id,
                "cidr": subnet_cidr, "ip_version": "4", "gateway_ip": None,
                "allocation_pools": [{'end': '192.168.4.128',
                                      'start': '192.168.4.64'}],
                "host_routes": [{'destination': '0.0.0.0/0',
                                 'nexthop': '192.168.4.54'}]}}
        else:
            new_subnet = {"subnet": {
                "name": subnet_name, "network_id": network_id,
                "cidr": subnet_cidr, "ip_version": "4"}}
        subnet = self.neutron.create_subnet(new_subnet)
        subnet_id = subnet['subnet']['id']
        logger.debug("Subnet ({0}) created".format(subnet_id))
        return subnet_id

    def create_router(self, router_name, admin_state_up=True):
        """
        Creates a neutron router
        """
        logger.debug("Creating router: {0}".format(router_name))
        new_router = {"router": {
                      "name": router_name,
                      "admin_state_up": admin_state_up}}
        router = self.neutron.create_router(new_router)
        router_id = router['router']['id']
        logger.debug("Router ({0}) created".format(router_id))
        return router_id

    def add_router_interface(self, router_id, subnet_id):
        """
        Adds an interface to a given router
        """
        logger.debug('Creating router interface')
        subnet_iface = {"subnet_id": subnet_id}
        iface = self.neutron.add_interface_router(router_id, subnet_iface)
        iface_port = iface['port_id']
        logger.debug("Interface port: {0}".format(iface_port))
        return iface_port

    def keepalived_fail(self, node):
        """
        Simulates failure with keepalived
        """
        node.run_cmd("service keepalived stop")

    def keepalived_restore(self, node):
        """
        Simulates failback with keepalived
        """
        node.run_cmd("service keepalived start")

    def move_vips_from(self, node_up):
        """
        Moves vips from controller using keepalived
        """
        logger.info('Restarting keepalived...')
        self.keepalived_fail(node_up)
        sleep(5)
        self.keepalived_restore(node_up)
        sleep(10)

    def fail_node(self, node):
        """
        Failover a node
        """
        logger.info('Powering off node...')
        node.power_off()

    def restore_node(self, node):
        """
        Restore a node
        """
        logger.info('Powering on node...')
        rebootable = False
        # In casae node is not in bootable state
        while not rebootable:
            try:
                node.power_on()
                rebootable = True
            except:
                logger.warning(Color.yellow("Unable to boot: {0}".format(
                    node.name
                )))
                sleep(5)

    def failover(self, progress, node_up, node_down, attempts=4):
        """
        Move vips on to first controller and fail it
        """
        progress.set_stages("Progress", 7)
        progress.update("Progress", 0)

        logger.info("Entering Failover Stage: {0}".format(node_down.name))

        def check_repl_status(node):
            status = node.run_cmd(
                "mysql -e 'show slave status\G' | "
                "grep 'Seconds_Behind_Master' | "
                "awk '{print $2}'"
            )['return'].rstrip()
            logger.debug("{0} status: {1}".format(node.name, status))
            return status

        progress.update("Progress")
        for node in [node_down, node_up]:
            logger.debug("Checking replication status: {0}".format(
                node.name
            ))
            for attempt in range(attempts):
                status = check_repl_status(node)
                if status is "0":
                    logger.debug("Replication complete.")
                    progress.update("Progress")
                    break
                else:
                    logger.debug("Replication incomplete; retrying.")
                    sleep(2)

        for i in range(5):
            progress.update("Progress", 1)

        self.move_vips_from(node_up)
        progress.update("Progress", 1)
        logger.debug('Powering down node')
        progress.update("Progress")
        self.fail_node(node_down)
        progress.update("Progress", 1)

    def failback(self, node_down, progress):
        """
        Unfails a node
        """
        progress.set_stages("Progress", 2)
        progress.update("Progress", 0)

        logger.info("Performing Failback operation...")
        self.restore_node(node_down)
        progress.update("Progress", 1)
        count = 1
        while not self.is_online(node_down.ipaddress):
            progress.update("Progress")
            logger.debug("Waiting for {0} to boot - s:{1}".format(
                node_down.name,
                count
            ))
            sleep(1)
            count += 1
        progress.update("Progress", 1)

    def is_online(self, ip):
        """
        Returns true if a connection can be made with ssh
        """
        logger.info("Checking if {0} is online".format(ip))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(2)
            s.connect((ip, 22))
            s.close()
        except socket.error:
            logger.debug('There was a socket error')
            return False
        logger.debug("{0} is online".format(ip))
        return True

    def build(self, server_name, server_image, server_flavor, network_name,
              subnet_name, router_name, cidr, progress, zone):
        """
        Builds state in OpenStack (net, server)
        """
        progress.set_stages("Progress", 14)
        progress.update("Progress", 0)

        logger.info("Configuring network and building instance...")

        network_id = self.create_network(network_name)
        progress.update("Progress", 1)

        subnet_id = self.create_subnet(subnet_name, network_id, cidr)
        progress.update("Progress", 1)

        router_id = self.create_router(router_name)
        progress.update("Progress", 1)

        iface_port = self.add_router_interface(router_id, subnet_id)
        progress.update("Progress", 1)
#-----------------------------------------------------------------------------
#
#-----------------------------------------------------------------------------
        pnet = False
        provider_net_id = ""
        for net in self.neutron.list_networks()['networks']:
            progress.update("Progress")
            #if net['name'] == "PROVIDER_NET":
            if net['name'] == "ENV01-VLAN" or net['name'] == "PROVIDER_NET":
                pnet = True
                provider_net_id = net['id']
                break
        progress.update("Progress", 1)
        if not pnet:
            logger.debug("Creating PROVIDER_NET")
            provider_net_id = self.create_network("PROVIDER_NET",
                                                  router_external=True,
                                                  shared=False)
            logger.debug("PROVIDER_NET created: {0}".format(provider_net_id))

            logger.debug("Creating PROVIDER_SUBNET")
            provider_subnet_id = self.create_subnet("PROVIDER_SUBNET",
                                                    provider_net_id,
                                                    "192.168.4.0/24",
                                                    pnet=True)
            logger.debug("PROVIDER_SUBNET created: {0}".format(
                provider_subnet_id
            ))
        progress.update("Progress", 1)

        self.neutron.add_gateway_router(router_id,
                                        body={"network_id": provider_net_id})
        progress.update("Progress", 1)
#-----------------------------------------------------------------------------
#
#-----------------------------------------------------------------------------
        networks = [{"net-id": network_id}]
        logger.debug("Building server with above network configuration")
        server = False

        ##########################
        # Build Instance - START
        ##########################
        build_status = "BUILD"
        while build_status != "ACTIVE":
            while not server:
                progress.update("Progress")
                try:
                    logger.debug("Executing server creation command")
                    server = self.nova.servers.create(server_name,
                                                      server_image,
                                                      server_flavor,
                                                      nics=networks,
                                                      availability_zone=zone)
                    logger.debug("Server creation command executed")
                except:
                    server = False
                    logger.debug("Server creation command failed.")
                    sleep(1)
            progress.update("Progress", 1)

            while build_status == "BUILD":
                try:
                    build_status = self.nova.servers.get(server.id).status
                except:
                    logger.error("Failed to communicate with Nova!")
                    continue
            progress.update("Progress", 1)
            if build_status == "ACTIVE":
                logger.debug("Server ({0}) status is now ACTIVE!".format(
                    server_name
                ))
            elif build_status == "ERROR":
                logger.error("Server ({0}) entered ERROR status!".format(
                    server_name
                ))
                #assert (build_status == "ACTIVE"),
                #        "Server failed to initialize!"
                server.delete()
                progress.update("Progress", -2)
            else:
                logger.warning("Server in unrecognized state: {1}".format(
                    server_name,
                    build_status
                ))
                assert (build_status == "ACTIVE"), ("Server is in an "
                                                    "unrecognized state!")
        ##########################
        # Build Instance - END
        ##########################

        progress.update("Progress", 1)
        build = Build(server, network_id, subnet_id, server_name, iface_port,
                      server_image, server_flavor)
        progress.update("Progress", 1)
#-----------------------------------------------------------------------------
#
#-----------------------------------------------------------------------------
        port_id = ""
        while not port_id:
            progress.update("Progress")
            logger.debug("Attempting to get a valid port id...")
            port_id = self.get_port_id(build)
        progress.update("Progress", 1)

        floating_ip = self.neutron.create_floatingip({"floatingip":
                                                     {"floating_network_id":
                                                      provider_net_id,
                                                      "port_id": port_id}})
        progress.update("Progress", 1)
        build.ip_info = floating_ip['floatingip']
        build.router_id = router_id
        progress.update("Progress", 1)
#-----------------------------------------------------------------------------
#
#-----------------------------------------------------------------------------
        return build

    def get_port_id(self, build):
        port_id = ""
        for port in self.neutron.list_ports()['ports']:
            if port['device_id'] == build.server.id:
                return port['id']
        return port_id

    def wait_service(self, service, node, retry=10):
        service_up = False
        while not service_up:
            logger.debug("Checking {0} on {1}".format(service, node.name))
            service_up = node.run_cmd("pgrep -fl {0}".format(
                                      service))['return'].rstrip()
            if not service_up:
                logger.debug("{0} is not running on {1}".format(
                    service, node.name))
                retry -= 1
                #==============================================
                # Manually restart service if retries exceeded
                #==============================================
                #if retry == 0:
                #    logger.warning("Manually starting {0}".format(
                #        service))
                #    node.run_cmd("service {0} start".format(service))
                sleep(1)
        logger.debug("{0} is up on {1}!".format(service, node.name))

    def verify(self, builds, progress, node_up, node_down=None):
        """
        Verifies state persistence
        """
        logger.info("Verifying cluster integrity...")
        progress.set_stages("Progress", 14)
        progress.update("Progress", 0)

        # Verify that node_up IS INDEED up... (yes it's necessary)
        while not self.is_online(node_up.ipaddress):
            sleep(1)

        # Checks if RS Cloud libvirt issue has been resolved
        computes_reporting = False
        while not computes_reporting:
            logger.debug("Checking if compute nodes are checked in")
            progress.update("Progress")
            libvirt = node_up.run_cmd(";".join(["source openrc",
                                     ("nova service-list | "
                                      "grep 'nova-compute' "
                                      "| awk '{print $10}'")]))['return']
            if "down" in libvirt:
                logger.warning(Color.yellow("Compute nodes are unchecked"))
                continue
            elif "up" in libvirt:
                logger.debug(Color.green("Compute nodes are checked in."))
                computes_reporting = True
        progress.update("Progress", 1)

        # Check RPCS services (ha_proxy, keepalived, rpc daemon)
        services = ['haproxy', 'keepalived', 'rpcdaemon']
        for service in services:
            self.wait_service(service, node_up)
            progress.update("Progress", 1)

        if node_down:
            for service in services:
                self.wait_service(service, node_down)
                progress.update("Progress", 1)
        else:
            progress.update("Progress", 3)

        # Check that the VIPS moved over to node_up
        logger.debug("Checking for vips on {0}".format(node_up.name))
        exec_vips = node_up.run_cmd("ip netns exec vips ip a")['return']
        progress.update("Progress", 1)
        exec_vips_down = " "
        if node_down:
            logger.debug("Checking for vips on {0}".format(
                node_down.name))
            exec_vips_down = node_down.run_cmd("ip netns exec vips ip a")[
                'return']
        progress.update("Progress", 1)

        vips = self.deployment.override_attrs['vips']['config'].keys()
        progress.update("Progress", 1)
        for vip in vips:
            logger.debug("VIP: {0}".format(vip))
            logger.debug("Verifying VIP namespace.")
            # Checks if the vips are absent from both controllers
            while (vip not in exec_vips) and (vip not in exec_vips_down):
                sleep(1)
                exec_vips = node_up.run_cmd("ip netns exec vips "
                                            "ip a")['return']
                if node_down:
                    exec_vips_down = node_down.run_cmd("ip netns exec vips "
                                                       "ip a")['return']
            # Verifies that the vips do not reside on both servers
            if (vip in exec_vips) and (vip in exec_vips_down):
                assert vip not in exec_vips, ("{0} vip found on both "
                                              "controllers").format(vip)
            # Checks for the vips on node_up controller
            elif vip in exec_vips:
                logger.debug("{0} vip found in {1}...".format(
                    vip, node_up.name))
            # Checks for the vips on the node_down controller
            else:
                logger.debug("{0} vip found on {1}...".format(
                    vip, node_down.name))
        progress.update("Progress", 1)

###########################################################################
#       IP NETNS NEEDS TO CONTAIN NEUTRON NET-LIST?
#       ip_netns_value = node_up.run_cmd("ip netns")['return'].rstrip()
###########################################################################

        # Check networks rescheduled
        for build in builds:
            logger.debug("Checking DHCP on {0}".format(build.name))
            self.wait_dhcp_agent_alive(build.network_id, progress)
        progress.update("Progress", 1)
#-----------------------------------------------------------------
        # Check connectivity to builds
        logger.info("Checking connectivity to builds...")
        for build in builds:
            logger.debug("Skipping connectivity test: {0}".format(build.name))
        #    while not self.is_online(build.ip_info['floating_ip_address']):
        #        logger.debug("Build {0} with IP {1} IS NOT "
        #                          "responding...".
        #                          format(build.name,
        #                                 build.ip_info[
        #                                     'floating_ip_address']))
        #        progress.update("Progress")
        #    logger.debug("Build {0} with IP {1} IS responding...".
        #                      format(build.name,
        #                             build.ip_info['floating_ip_address']))
            progress.update("Progress")
#-----------------------------------------------------------------

###########################################################################
        # Check MySQL replication isn't broken and Controller2 is master.
        #CAM
###########################################################################

        # Check rabbitmq
        self.test_rabbit_status(progress, node_up, node_down)
        progress.update("Progress", 1)

###########################################################################
        # Check if all the configured Openstack Services are functional.
        # Run tempest based on the features enabled.
        #SELECTIVE TEMPEST RUN
###########################################################################

        ###################################################################
        # Verifies that the compute nodes are able to report
        ###################################################################
        nova_status = "down"
        while "down" in nova_status:
            logger.debug("Checking if nova is up on compute")
            progress.update("Progress")
            nova_status = node_up.run_cmd(";".join(["source openrc", "nova "
                                                    "service-list | grep "
                                                    "compute | awk '{print "
                                                    "$10}'"
                                                    ""]))['return'].rstrip()
            if "down" in nova_status:
                logger.warning(Color.yellow(
                    "At least one compute node isn't properly reporting"))
            else:
                logger.debug("All compute nodes are properly reporting")
        progress.update("Progress", 1)

    def wait_dhcp_agent_alive(self, net, progress, wait=240):
        """
        Waits until dhcp agent for net is alive
        """
        count = 0
        neutron_up = False
        while not neutron_up:
            try:
                dhcp_stat = self.neutron.list_dhcp_agent_hosting_networks(net)
                neutron_up = True
            except:
                logger.warning("Neutron is not up yet")
        in_time = lambda x: wait > x

        while not dhcp_stat['agents'] and in_time(count):
            logger.debug("Waiting for agents to populate {0}".format(
                count))
            progress.update("Progress")
            sleep(1)
            count += 1
            dhcp_stat = self.neutron.list_dhcp_agent_hosting_networks(net)
        assert in_time(count), "Agents failed to populate in time"

        alive = False
        while not alive and in_time(count):
            logger.debug("Waiting for agents to arise {0}".format(
                count))
            progress.update("Progress")
            sleep(1)
            count += 1
            dhcp_stat = self.neutron.list_dhcp_agent_hosting_networks(net)
            try:
                alive = dhcp_stat['agents'][0]['alive']
            except IndexError:
                logger.warning("Failed to retrieve alive DCHP agent.")
                alive = False
                continue
        assert in_time(count), "Agents failed to rise in time"
        logger.debug("DHCP is alive")

    def run_tests(self):
        """
        Run ha tests
        """
        #-------------------#
        # Preparation Begin #
        #-------------------#
        #branch = TempestQuantum.tempest_branch(self.deployment.branch)
        #if "grizzly" in branch:
        #    tempest = TempestQuantum(self.deployment)
        #else:
        #    tempest = TempestNeutron(self.deployment)
        images = self.nova.images.list()
        server_image = next(i for i in images if "cirros" in i.name)
        flavors = self.nova.flavors.list()
        server_flavor = next(f for f in flavors if "tiny" in f.name)
        #-----------------#
        # Preparation End #
        #-----------------#

        max_waves = 2

        iterations = self.iterations
        build_stages = 4 + (len(self.nova.hypervisors.list()) * 2 * max_waves)
        verify_stages = 5
        failover_stages = 2
        failback_stages = 2
        progress_stages = 100

        bars = [{'name': 'Iteration', 'current': self.current_iteration,
                 'total': iterations, 'size': 100},
                {'name': 'Build', 'current': 0,
                 'total': build_stages, 'size': 100},
                {'name': 'Verify', 'current': 0,
                 'total': verify_stages, 'size': 100},
                {'name': 'Failover', 'current': 0,
                 'total': failover_stages, 'size': 100},
                {'name': 'Failback', 'current': 0,
                 'total': failback_stages, 'size': 100},
                {'name': 'Progress', 'current': 0,
                 'total': progress_stages, 'size': 100}]
        progress = Progress(bars, self.progress)

        builds = []

        node_up = self.controller1
        node_down = self.controller2

        stage = 0
        wave = 0
        while wave < max_waves:
            wave += 1
            #os.system('clear')
            progress.display("Verify")
            self.verify(builds, progress, node_up, node_down)
            progress.advance("Verify")
            #os.system('clear')

            progress.display("Build")
            hyp_name = None
            build = self.build("testbuild{0}".format(stage),
                               server_image, server_flavor,
                               "testnetwork{0}".format(stage),
                               "testsubnet{0}".format(stage),
                               "testrouter{0}".format(stage),
                               "172.32.{0}.0/24".format(stage),
                               progress,
                               hyp_name)
            stage += 1
            builds.append(build)
            progress.advance("Build")

            for hypervisor in self.nova.hypervisors.list():
                hyp_name = hypervisor.hypervisor_hostname
                build = self.build("testbuild{0}".format(stage),
                                   server_image, server_flavor,
                                   "testnetwork{0}".format(stage),
                                   "testsubnet{0}".format(stage),
                                   "testrouter{0}".format(stage),
                                   "172.32.{0}.0/24".format(stage),
                                   progress,
                                   "nova:{0}".format(hyp_name))
                stage += 1
                builds.append(build)
                progress.advance("Build")

            progress.display("Failover")
            self.failover(progress, node_up, node_down)
            progress.advance("Failover")

            progress.display("Verify")
            self.verify(builds, progress, node_up)
            progress.advance("Verify")

            progress.display("Build")
            hyp_name = None
            build = self.build("testbuild{0}".format(stage),
                               server_image, server_flavor,
                               "testnetwork{0}".format(stage),
                               "testsubnet{0}".format(stage),
                               "testrouter{0}".format(stage),
                               "172.32.{0}.0/24".format(stage),
                               progress,
                               hyp_name)
            stage += 1
            builds.append(build)
            progress.advance("Build")

            for hypervisor in self.nova.hypervisors.list():
                hyp_name = hypervisor.hypervisor_hostname
                build = self.build("testbuild{0}".format(stage),
                                   server_image, server_flavor,
                                   "testnetwork{0}".format(stage),
                                   "testsubnet{0}".format(stage),
                                   "testrouter{0}".format(stage),
                                   "172.32.{0}.0/24".format(stage),
                                   progress,
                                   "nova:{0}".format(hyp_name))
                stage += 1
                builds.append(build)
                progress.advance("Build")

            progress.display("Failback")
            self.failback(node_down, progress)
            progress.advance("Failback")

            node_temp = node_up
            node_up = node_down
            node_down = node_temp

        progress.display("Verify")
        self.verify(builds, progress, node_up, node_down)
        progress.advance("Verify")

        progress.display("Iteration")

        for build in builds:
            build.destroy(self.nova, self.neutron, progress, node_up,
                          node_down)

        progress.advance("Iteration")
        progress.display("Iteration")
        self.current_iteration += 1
        #tempest.test_node = node_up
        #tempest.test()

    def kill_rabbit(self, node1, node2=None):
        logger.warning(Color.yellow("Remidiation: Hard restarting RabbitMQ"))
        node1.run_cmd(";".join([
            "for i in `ps aux | grep [r]abbitmq | ",
            "awk '{print $2}'`",
            "do kill -9 $i", "done",
            "service rabbitmq-server start"
        ]))
        if node2:
            node2.run_cmd(";".join([
                "for i in `ps aux | grep [r]abbitmq | ",
                "awk '{print $2}'`",
                "do kill -9 $i",
                "done",
                "service rabbitmq-server start"
            ]))

    def test_rabbit_status(self, progress, node1, node2=None):
        """
        Assures rabbit is alive
        """
        status = False
        cycle = 1
        max_cycle = 120
        while not status:
            logger.debug("Testing if RabbitMQ is alive: {0}".format(cycle))
            progress.update("Progress")
            try:
                status = self.rabbit.is_alive()
                logger.debug("RabbitMQ is alive")
            except:
                status = False
                cycle += 1
                if cycle > max_cycle:
                    self.kill_rabbit(node1, node2)
                    cycle = 1
                sleep(1)

    def test_list_queues(self):
        """
        Assures rabbit can list queues
        """
        queues = self.rabbit.list_queues()
        assert queues is not None, "queues empty"

    def collect_results(self):
        """
        Collect report and merge tests
        """
        xunit_merge()

    def test(self, iterations):
        self.iterations = iterations
        self.run_tests()
        self.collect_results()

#        from threading import Thread

#        t1 = Thread(target=self.run_multiple, args=(self.controller1, 1, ))
#        t2 = Thread(target=self.run_multiple, args=(self.controller2, 2, ))

#        t1.start()
#        sleep(1)
#        t2.start()


#        t1.join()
#        print "t1 finished!"
#        t2.join()
#        print "t2 finished!"

#    def run_multiple(self, node, which):
#        print "Running command {0}!".format(which)
#        remote_cmd = ";".join(["for i in {0..10000}", "do echo $i", "done"])
#        env.user = node.user
#        env.host_string = node.ipaddress
#        env.password = env.passwords[env.host_string] = node.password
#        run(remote_cmd)

#from fabric.api import *
#from fabric.state import env

class Progress(object):
    def __init__(self, bars, progress):
        self.bars = bars
        self.current = None
        self.progress = progress

    def advance(self, bar_name, adv_amount=1):
        #logger.debug("Advancing {0}...".format(bar_name))
        if not self.progress:
            return
        for bar in self.bars:
            if bar['name'] == bar_name:
                bar['current'] += adv_amount

    def display(self, current_bar_name):
        if not self.progress:
            return
        #logger.debug('Flushing print buffer for status bar...')
        self.current = current_bar_name
        #for i in range(210):
        #    sys.stdout.write("\b")

        os.system('clear')
        for bar in self.bars:
            if bar['name'] == "Iteration":
                self.print_bar(bar, bar['size'], 1)
            elif bar['name'] == current_bar_name:
                self.print_bar(bar, bar['size'], 1)
            else:
                self.print_bar(bar, bar['size'], 0)
        sys.stdout.flush()
        call(["tail -n 50 logs/monster.log | ",
              "sed 's/^.*RPC-QE //' | ",
              "cut -c-118"], shell=True)

    def set_stages(self, bar_name, stages):
        if not self.progress:
            return
        for bar in self.bars:
            if bar['name'] == bar_name:
                bar['total'] = stages

    def update(self, bar_name, adv_amount=None):
        if not self.progress:
            return
        # Advances bar without changing current bar indicator
        # If value is 0, resets current progress position
        if adv_amount == 0:
            for bar in self.bars:
                if bar['name'] == bar_name:
                    bar['current'] = 0
        elif adv_amount:
            self.advance(bar_name, adv_amount)
        self.display(self.current)

    def print_bar(self, bar, size, curr):
        #logger.debug("Printing bar {0}...".format(bar['name']))
        #sys.stdout.write("   {0}:[".format(bar['name']))
        if len(bar['name']) < 8:
            sys.stdout.write("{0}:\t\t[".format(bar['name']))
        else:
            sys.stdout.write("{0}:\t[".format(bar['name']))
        self.set_color("bold")
        complete = (float(bar['current']) / int(bar['total'])) * size
        if bar['name'] == "Progress":
            self.set_color("green")
            for i in range(int(complete)):
                sys.stdout.write(">")
        else:
            self.set_color("blue")
            for i in range(int(complete)):
                sys.stdout.write("|")

        self.set_color("yellow")
        self.set_color("blink")
        work_on = 0
        if curr == 1:
            work_on = (float(1) / int(bar['total'])) * size
            for i in range(int(work_on)):
                if (size - complete) > 0:
                    sys.stdout.write("|")

        self.set_color("default")
        self.set_color("gray")
        remain = (size - int(complete) - int(work_on))
        if bar['name'] == "Progress":
            for i in range(remain):
                sys.stdout.write(">")
        else:
            for i in range(remain):
                sys.stdout.write("|")

        self.set_color("default")
        #sys.stdout.write("]   ")
        sys.stdout.write("]\n")

    def set_color(self, style):
        #logger.debug("Changing output color to {0}...".format(style))
        if style == "default":
            sys.stdout.write("\033[0m")
        elif style == "bold":
            sys.stdout.write("\033[1m")
        elif style == "blue":
            sys.stdout.write("\033[34m")
        elif style == "yellow":
            sys.stdout.write("\033[33m")
        elif style == "gray":
            sys.stdout.write("\033[90m")
        elif style == "green":
            sys.stdout.write("\033[92m")
        elif style == "blink":
            sys.stdout.write("\033[5m")
