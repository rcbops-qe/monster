#!/usr/bin/env bash
set -e

pushd /root

MYSQLDUMP=$(which mysqldump)
MYSQL=$(which mysql)
DATABASE_BACKUP_DIR=${DATABASE_BACKUP_DIR:-"database_backups"}

NEUTRON_SERVICE=$(ls /etc/init.d/ | grep -E neutron-server)

if [ ! -f "${DATABASE_BACKUP_DIR}/quantum.sql" ];then
    echo "The Quantum Database File was not found."
    exit 0
fi

if [ "$(service ${NEUTRON_SERVICE} status | grep 'start/running')" ];then
    service ${NEUTRON_SERVICE} stop;
fi

# Drop the current Quantum Database
${MYSQL} -e "drop database quantum"

# Recreate the Quantum Database
${MYSQL} -e "create database quantum"

# ReImport the Quantum Database
pushd ${DATABASE_BACKUP_DIR}
${MYSQL} -o quantum < quantum.sql
popd

# STAMP THE QUANTUM DB AS GRIZZLY. THIS IS A MUST DO!
neutron-db-manage --config-file /etc/neutron/neutron.conf \
                  --config-file /etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini \
                  stamp grizzly

# Upgrade Neutron Database to havana
neutron-db-manage --config-file /etc/neutron/neutron.conf \
                  --config-file /etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini \
                  upgrade havana

# Start Neutron Service
if [ "$(service ${NEUTRON_SERVICE} status | grep 'stop/waiting')" ];then
    service ${NEUTRON_SERVICE} stop;
fi

popd
