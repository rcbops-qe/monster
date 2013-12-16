from novaclient.v1_1 import client as nova_client
from neutronclient.v2_0.client import Client as neutron_client

user = None
password = None
url = None

data = {}

# Setup clients
nova = nova_client.Client(user, password, user, auth_url=url)
neutron = neutron_client(auth_url=url, username=user, password=password,
                         tenant_name=user)

# Create network
new_net = {"network": {"name": "test_net", "shared": True}}
net = neutron.create_network(new_net)
net_id = net['network']['id']
data['net_id'] = net_id

# Create subnet
new_subnet = {"subnet": {
    "name": "test_subnet", "network_id": net_id,
    "cidr": "172.0.100.0/24", "ip_version": "4"}}
neutron.create_subnet(new_subnet)

# Create router
new_router = {"router": {
    "name": "testrouter", "network_id": net_id}}
router = neutron.create_router(new_router)
data['router_id'] = router['router']['id']

# Create security group
new_security_group = {"security_group": {
    "name": "web", "description": "http and ssh"}}
security_group = neutron.create_security_group(new_security_group)
security_group_id = security_group['security_group']['id']

all_rule = {"security_group_rule": {
    "direction": "ingress",
    "ethertype": "IPv4",
    "protocol": "TCP",
    "port_range_min": "0",
    "port_range_max": "65535"}}
neutron.create_security_group_rule(all_rule)

# Create
