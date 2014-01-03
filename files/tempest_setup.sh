#!/bin/bash
# create network
NET_ID=$(neutron net-create net1 | grep id | head -n +1 | awk '{print $4}')

# create subnet
SUBNET_ID=$(neutron subnet-create --name subnet1 $NET_ID 10.0.100.0/24 | grep id | tail -n +2 | head -n +1 | awk '{print $4}')

# create router
ROUTER_ID=$(neutron router-create router1 | grep id | head -n +1 | awk '{print $4}')

# connect router
neutron router-interface-add $ROUTER_ID $SUBNET_ID

# create security group
SECURITY_GROUP_ID=$(neutron security-group-create web | grep id | head -n +1 | awk '{print $4}')
neutron security-group-rule-create --direction ingress --protocol TCP --port-range-min 80 --port-range-max 80 $SECURITY_GROUP_ID
neutron security-group-rule-create --direction ingress --protocol TCP --port-range-min 22 --port-range-max 22 $SECURITY_GROUP_ID
neutron security-group-rule-create --protocol icmp --direction ingress $SECURITY_GROUP_ID

# create key
mkdir -p ~/.ssh; nova keypair-add key1 > ~/.ssh/mykey && chmod 600 ~/.ssh/mykey

# create instances
echo """echo 1 > index.html; nohup python -m SimpleHTTPServer 80 &""" > server.sh
chmod u+x server.sh
SERVER1_ID=$(nova boot --image precise-image --flavor 2 --key-name key1 --nic net-id=$NET_ID --security_groups $SECURITY_GROUP_ID server1 | grep id | head -n +1 | awk '{print $4}')
SERVER2_ID=$(nova boot --image precise-image --flavor 2 --key-name key1 --nic net-id=$NET_ID --security_groups $SECURITY_GROUP_ID server2 | grep id | head -n +1 | awk '{print $4}')
CLIENT_ID=$(nova boot --image precise-image --flavor 2 --key-name key1 --nic net-id=$NET_ID --security_groups $SECURITY_GROUP_ID client | grep id | head -n +1 | awk '{print $4}')

# setup loadbalancer
POOL_ID=$(neutron lb-pool-create --lb-method ROUND_ROBIN --name mypool --protocol HTTP --subnet-id $SUBNET_ID | grep id | head -n +1 | awk '{print $4}')
sleep 20
ADDRESS1=$(nova show $SERVER1_ID | grep net | awk '{print $5}')
ADDRESS2=$(nova show $SERVER2_ID | grep net | awk '{print $5}')
neutron lb-member-create --address $ADDRESS1 --protocol-port 80 $POOL_ID
neutron lb-member-create --address $ADDRESS2 --protocol-port 80 $POOL_ID
HEALTH_MONITOR_ID=$(neutron lb-healthmonitor-create --delay 3 --type HTTP --max-retries 3 --timeout 3 | grep id | head -n +1 | awk '{print $4}')
neutron lb-healthmonitor-associate $HEALTH_MONITOR_ID $POOL_ID
neutron lb-vip-create --name myvip --protocol-port 80 --protocol HTTP --subnet-id $SUBNET_ID $POOL_ID

# setup web servers
# ip netns exec qdhcp-$NET_ID ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i ~/.ssh/mykey $ADDRESS1
# ip netns exec qdhcp-$NET_ID
# ssh -i ~/.ssh/mykey $ADDRESS2
# echo 1 > index.html; nohup python -m SimpleHTTPServer 80 &

# test heat
IMAGE_ID=$(nova image-show precise-image | grep id | awk '{print $4}')
heat stack-create -u https://raw.github.com/openstack/heat-templates/master/hot/hello_world.yaml -P "KeyName=key1;ImageId=${IMAGE_ID};db_password=Password" mystack
