#!/bin/bash -e
#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
# This script is to update the docker registry credentials
#

USAGE="Usage: ${0##*/} <username> <password>"

get_password()
{
    read -s -p "Password of ${usr}: " pw
    echo
    read -s -p "Password of ${usr} (again): " pw2
    while [ "${pw}" != "${pw2}" ]; do
        echo
        echo "Incorrect input of password, please try again."
        read -s -p "Password of ${usr}: " pw
        echo
        read -s -p "Password of ${usr} (again): " pw2
    done
}

if [ $# -eq 0 ]; then
    read -p "Username: " usr
    get_password
elif [ $# -eq 1 ]; then
    usr=${1}
    get_password
elif [ $# -eq 2 ]; then
    usr=${1}
    pw=${2}
else
    echo Too many arguments.
    echo $USAGE
    echo
    exit
fi

NEW_CREDS="username:${usr} password:${pw}"

echo

source /etc/platform/openrc

for REGISTRY in docker-registry quay-registry elastic-registry gcr-registry \
    k8s-registry ghcr-registry; do
    echo -n "Updating" $REGISTRY "credentials ."
    SECRET_UUID=$(system service-parameter-list | fgrep $REGISTRY |\
        fgrep auth-secret | awk '{print $10}')
    if [ -z "$SECRET_UUID" ]; then
        echo "No $REGISTRY entry in service-parameters"
        echo
        continue
    fi

    SECRET_REF=$(openstack secret list | fgrep ${SECRET_UUID} |\
        awk '{print $2}')
    echo -n "."
    if [ -z "$SECRET_REF" ]; then
        echo "No $REGISTRY entry in openstack secret list"
    else
        SECRET_VALUE=$(openstack secret get ${SECRET_REF} --payload -f value)
        echo -n "."
        openstack secret delete ${SECRET_REF} > /dev/null
        echo -n "."
    fi

    NEW_SECRET_VALUE=$NEW_CREDS
    openstack secret store -n ${REGISTRY}-secret -p "${NEW_SECRET_VALUE}" \
        >/dev/null
    echo -n "."
    NEW_SECRET_REF=$(openstack secret list | fgrep ${REGISTRY}-secret |\
        awk '{print $2}')
    NEW_SECRET_UUID=$(echo "${NEW_SECRET_REF}" | awk -F/ '{print $6}')
    system service-parameter-modify docker $REGISTRY \
        auth-secret="${NEW_SECRET_UUID}" > /dev/null
    echo -n "."
    echo " done."

    echo -n "Validating $REGISTRY credentials updated to:  "
    SECRET_UUID=$(system service-parameter-list | fgrep $REGISTRY |\
        fgrep auth-secret | awk '{print $10}')
    if [ -z "$SECRET_UUID" ]; then
        continue
    fi
    SECRET_REF=$(openstack secret list | fgrep ${SECRET_UUID} | awk '{print $2}')
    SECRET_VALUE=$(openstack secret get ${SECRET_REF} --payload -f value)
    echo $SECRET_VALUE

    echo
done
