#!/bin/bash

set -x

if [[ $2 ]]; then
    $neutron = $2
else
    $neutron = "neutron"
fi

destroy() {
    for i in `$neutron floatingip-list | awk '{print $neutron}'`; do $neutron floatingip-delete $i; done
    for i in `$neutron port-list | awk '{print $neutron}'`; do $neutron port-delete $i; done
    for i in `$neutron router-list | awk '{print $neutron}'`; do $neutron router-delete $i; done
    for i in `nova list | awk '{print $neutron}'`; do nova delete $i; done
    for i in `$neutron net-list | awk '{print $neutron}'`; do $neutron net-delete $i; done
}

if [[ $1 == "destroy" ]]; then
    destroy
    exit 0
fi

nova keypair-add key
cinder type-create Backup

for i in `$neutron security-group-list | awk '/default/ {print $neutron}'`; do $neutron security-group-rule-create --protocol tcp --port-range-min 22 --port-range-max 22 --direction ingress $i; done
for i in `$neutron security-group-list | awk '/default/ {print $neutron}'`; do $neutron security-group-rule-create --protocol icmp --direction ingress $i; done

flatnetid=`$neutron net-create ENV01-FLAT --provider:network_type=flat --provider:physical_network=ph-vmnet | grep -w id | awk '{print $4}'`
$neutron subnet-create ENV01-FLAT 10.127.100.0/24 --name ENV01-FLAT-SUBNET --no-gateway --host-route destination=0.0.0.0/0,nexthop=10.127.100.1 --allocation-pool start=10.127.100.128,end=10.127.100.159 --dns-nameservers list=true 8.8.8.8 8.8.4.4

nova boot --flavor 2 --image precise-image --security-groups default --key-name key --nic net-id=$flatnetid flattest

vlan_provider() {
    vlannetid=`$neutron net-create ENV01-VLAN --provider:network_type=vlan --provider:physical_network=ph-vmnet --provider:segmentation_id=867 | grep -w id | awk '{print $4}'`
    $neutron subnet-create ENV01-VLAN 10.127.102.0/24 --name ENV01-VLAN-SUBNET --gateway 10.127.102.1 --allocation-pool start=10.127.102.128,end=10.127.102.159
    $neutron net-update $vlannetid --router:external=true
    grenetid=`$neutron net-create ENV01-GRE --provider:network_type=gre --provider:segmentation_id=1 | grep -w id | awk '{print $4}'`
    gresubid=`$neutron subnet-create ENV01-GRE 192.168.105/24 --name ENV01-GRE-SUBNET --dns-nameservers list=true 8.8.8.8 8.8.4.4 | grep -w id | awk '{print $4}'`

    $neutron router-create ENV01-RTR
    $neutron router-gateway-set ENV01-RTR $vlannetid
    $neutron router-interface-add ENV01-RTR $gresubid

    greinstanceid=`nova boot --flavor 2 --image precise-image --security-groups default --key-name key --nic net-id=$grenetid gretest | grep -w id | awk '{print $4}'`

    floatingipid=`$neutron floatingip-create $vlannetid | grep -w id | awk '{print $4}'`
    greinstanceportid=$(for i in `$neutron port-list | awk '/:/ {print $neutron}'`; do $neutron port-show $i | grep -q $greinstanceid && $neutron port-show $i | grep -w id | awk '{print $4}' ; done)
    $neutron floatingip-associate $floatingipid $greinstanceportid
}

vlan_tenant() {
    vlannetid=`$neutron net-create ENV01-VLAN --provider:network_type=vlan --provider:physical_network=ph-vmnet --provider:segmentation_id=867 | grep -w id | awk '{print $4}'`
    $neutron subnet-create ENV01-VLAN 10.127.102.0/24 --name ENV01-VLAN-SUBNET --no-gateway --host-route destination=0.0.0.0/0,nexthop=10.127.102.1 --allocation-pool start=10.127.102.128,end=10.127.102.159 --dns-nameservers list=true 8.8.8.8 8.8.4.4
    nova boot --flavor 2 --image precise-image --security-groups default --key-name key --nic net-id=$vlannetid vlantest
}

if [[ $1 == "provider" ]]; then
    vlan_provider
elif [[ $1 == "tenant" ]]; then
    vlan_tenant
fi

