for i in `neutron security-group-list | awk '/default/ {print $2}'`; do neutron security-group-rule-create --protocol tcp --port-range-min 22 --port-range-max 22 --direction ingress $i; done
for i in `neutron security-group-list | awk '/default/ {print $2}'`; do neutron security-group-rule-create --protocol icmp --direction ingress $i; done

neutron net-create ENV01-FLAT --provider:network_type=flat --provider:physical_network=ph-vmnet
neutron subnet-create ENV01-FLAT 10.127.100.0/24 --name ENV01-FLAT-SUBNET --no-gateway --host-route destination=0.0.0.0/0,nexthop=10.127.100.1 --allocation-pool start=10.127.100.128,end=10.127.100.159 --dns-nameservers list=true 8.8.8.8 8.8.4.4

nova boot --flavor 2 --image precise-image --security-groups default --key-name ctrl1admin --nic net-id=a68cb024-70ed-42d7-aed7-d592a1f3d931 jd-flat-test-1

neutron net-create ENV01-VLAN --provider:network_type=vlan --provider:physical_network=ph-vmnet --provider:segmentation_id=867
neutron subnet-create ENV01-VLAN 10.127.102.0/24 --name ENV01-VLAN-SUBNET --gateway 10.127.102.1 --allocation-pool start=10.127.102.128,end=10.127.102.159 --dns-nameservers list=true 8.8.8.8 8.8.4.4
neutron net-update $vlannet --router:external=true

neutron net-create ENV01-GRE --provider:network_type=gre --provider:segmentation_id=1
neutron subnet-create ENV01-GRE 192.168.105/24 --name ENV01-GRE-SUBNET --dns-nameservers list=true 8.8.8.8 8.8.4.4
neutron router-create ENV01-RTR
neutron router-gateway-set ENV01-RTR $vlannet
neutron router-interface-add ENV01-RTR $gresub
