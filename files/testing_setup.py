from subprocess import check_call
from novaclient.v1_1 import client as nova_client
from neutronclient.v2_0.client import Client as neutron_client

user = "admin"
password = "secrete"
url = "http://23.253.54.156:5000/v2.0"

data = {}

# Setup clients
nova = nova_client.Client(user, password, user, auth_url=url)
neutron = neutron_client(auth_url=url, username=user, password=password,
                         tenant_name=user)


def run_cmd(command):
    check_call(command, shell=True)


def instance_cmd(server_id, net_id, cmd):
    namespace = "qdhcpd-{0}".format(net_id)
    server = nova.servers.get(server_id)
    server_ip = server['server']['ipaddress']
    icmd = ("ip netns exec {0} bash; "
            "ssh -o UseprKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i ~/.ssh/testkey {1}; "
            "{2}").format(namespace, server_ip, cmd)
    run_cmd(icmd)

# Create network
new_net = {"network": {"name": "test_net", "shared": True}}
net = neutron.create_network(new_net)
net_id = net['network']['id']
data['net_id'] = net_id

# Create subnet
new_subnet = {"subnet": {
    "name": "test_subnet", "network_id": net_id,
    "cidr": "172.0.100.0/24", "ip_version": "4"}}
subnet = neutron.create_subnet(new_subnet)
subnet_id = subnet['subnet']['id']

# Create router
new_router = {"router": {
    "name": "testrouter",
    "admin_state_up": True}}
router = neutron.create_router(new_router)
router_id = router['router']['id']
data['router_id'] = router['router']['id']

# Hook up router to subnet
new_router_interface = {"subnet_id": subnet_id}
neutron.add_interface_router(router_id)

# Create security group
new_security_group = {"security_group": {
    "name": "web",
    "description": "http and ssh"}}
security_group = neutron.create_security_group(new_security_group)
security_group_id = security_group['security_group']['id']

all_rule = {"security_group_rule": {
    "direction": "ingress",
    "security_group_id": security_group_id,
    "ethertype": "IPv4",
    "protocol": "TCP",
    "port_range_min": "0",
    "port_range_max": "65535"}}
neutron.create_security_group_rule(all_rule)

# Create key
create_key = "mkdir -p ~/.ssh; nova keypair-add testkey > ~/.ssh/testkey; chmod 600 ~/.ssh/testkey"
run_cmd(create_key)
