import json
from subprocess import check_call
from novaclient.v1_1 import client as nova_client
from neutronclient.v2_0.client import Client as neutron_client

user = "${USER}"
password = "${PASSWORD}"
url = "${URL}"
is_neutron = $IS_NEUTRON

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


def get_images():
    image_ids = (i.id for i in nova.images.list())
    try:
        image_id1 = next(image_ids)
    except StopIteration:
        # No images
        exit(1)
    try:
        image_id2 = next(image_ids)
    except StopIteration:
        # Only one image
        image_id2 = image_id1
    return (image_id1, image_id2)


def create_network():
    new_net = {"network": {"name": "test_net", "shared": True}}
    net = neutron.create_network(new_net)
    return net['network']['id']


def create_subnet(network_id):
    new_subnet = {"subnet": {
        "name": "test_subnet", "network_id": network_id,
        "cidr": "172.0.100.0/24", "ip_version": "4"}}
    subnet = neutron.create_subnet(new_subnet)
    return subnet['subnet']['id']


def create_router():
    new_router = {"router": {
        "name": "testrouter",
        "admin_state_up": True}}
    router = neutron.create_router(new_router)
    return router['router']['id']


def attach_router(router_id, subnet_id):
    new_router_interface = {"subnet_id": subnet_id}
    neutron.add_interface_router(router_id, new_router_interface)


def create_security_group():
    new_security_group = {"security_group": {
        "name": "web",
        "description": "http and ssh"}}
    security_group = neutron.create_security_group(new_security_group)
    return security_group['security_group']['id']


def create_security_group_rule(security_group_id):
    all_rule = {"security_group_rule": {
        "direction": "ingress",
        "security_group_id": security_group_id,
        "ethertype": "IPv4",
        "protocol": "TCP",
        "port_range_min": "0",
        "port_range_max": "65535"}}
    neutron.create_security_group_rule(all_rule)


def create_key():
    create_key = ("mkdir -p ~/.ssh; "
                  "nova keypair-add testkey > ~/.ssh/testkey; "
                  "chmod 600 ~/.ssh/testkey")
    run_cmd(create_key)


def prepare_tempest():
    data = {}
    image_id1, image_id2 = get_images()
    data['image_id1'] = image_id1
    data['image_id2'] = image_id2
    if is_neutron:
        network_id = create_network()
        # subnet_id = create_subnet(network_id)
        router_id = create_router()
        # attach_router(router_id, subnet_id)
    print json.dumps(data)

    # Not required for tempest
    # security_group_id = create_security_group()
    # create_security_group_rule(security_group_id)

if __name__ == "__main__":
    prepare_tempest()
