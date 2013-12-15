#!/usr/bin/env bash
set -e

# Go to root Home
pushd /root

# Set the full path to the MYSQL commands
MYSQLDUMP=$(which mysqldump)
MYSQL=$(which mysql)

# return a list of databases to backup
DB_NAMES=$(${MYSQL} -Bse "show databases;" | grep -v -e "schema" -e "mysql")

# Set the backup directory
DB_BACKUP_DIR=${DB_BACKUP_DIR:-"database_backups"}

# Make the database backup dir if not found
if [ ! -d "${DB_BACKUP_DIR}" ];then
    mkdir -p "${DB_BACKUP_DIR}"
fi

# Go to the Database Backup Dir
pushd ${DB_BACKUP_DIR}

# Backup all databases individually
for db in ${DB_NAMES};do
    ${MYSQLDUMP} ${db} > ${db}.sql
done

popd
popd

exit 0
