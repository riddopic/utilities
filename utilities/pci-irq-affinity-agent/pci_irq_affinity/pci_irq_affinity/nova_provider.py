#
# Copyright (c) 2019-2022 StarlingX.
#
# SPDX-License-Identifier: Apache-2.0
#

# vim: tabstop=4 shiftwidth=4 softtabstop=4

# All Rights Reserved.
#

""" Define NovaProvider class
This class wraps novaclient access interface and expose get_instance() and
get_instances() to other agent classes.
"""

import keyring
import os
import socket

from keystoneauth1 import loading
from keystoneauth1 import session
from novaclient import client

from pci_irq_affinity.config import CONF
from pci_irq_affinity import guest
from pci_irq_affinity import instance
from pci_irq_affinity.log import LOG


class NovaProvider(object):

    _instance = None

    def __init__(self):
        if self._init:
            return
        self._creds = self._get_keystone_creds()
        self._auth = self._get_auth(self._creds)
        self._cacert = self._get_cacert()
        self._hostname = self.get_hostname()
        self._conn = guest.connect_to_libvirt()
        self._init = True

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(NovaProvider, cls).__new__(cls)
            cls._instance.unset_init()
        return cls._instance

    def __del__(self):
        if self._conn:
            self._conn.close()

    def unset_init(self):
        self._init = False

    def get_hostname(self):
        return os.getenv("COMPUTE_HOSTNAME", default=socket.gethostname())

    def _get_keystone_creds(self):
        creds = {}
        openstack_options = CONF.openstack
        creds_options = ['username', 'password', 'user_domain_name', 'project_name',
                         'project_domain_name', 'keyring_service', 'auth_url']

        try:
            for option in creds_options:
                value = openstack_options[option]
                if value:
                    creds[option] = value

            if 'password' not in creds:
                creds['password'] = keyring.get_password(creds['keyring_service'],
                                                         creds['username'])
            creds.pop('keyring_service')

        except Exception as e:
            LOG.error("Could not get keystone creds configuration! Err=%s" % e)
            creds = None

        return creds

    def _get_auth(self, creds):
        if creds is not None:
            loader = loading.get_plugin_loader('password')
            auth = loader.load_from_options(**creds)
            return auth
        return None

    def _get_cacert(self):
        return CONF.openstack.cacert

    def get_nova(self):
        try:
            sess = session.Session(auth=self._auth, verify=self._cacert)
            nova = client.Client('2.1', session=sess)
            return nova
        except Exception as e:
            LOG.warning("Failed to connect to nova!")
            raise Exception("could not connect nova!")

    def get_instance(self, uuid):
        try:
            nova = self.get_nova()
            server = nova.servers.get(uuid)
            flavor_info = nova.flavors.get(server.flavor["id"])
            hostname = server.__dict__['OS-EXT-SRV-ATTR:host']
        except Exception as e:
            LOG.warning("Could not get instance=%s from Nova! error=%s" % (uuid, e))
            return None

        LOG.debug('GET VM:%s in node:%s' % (server.name, hostname))

        if hostname == self._hostname:
            inst = instance.instance(uuid, server.name, flavor_info.get_keys())
            # get numa topology and pci info from libvirt
            try:
                domain = guest.get_guest_domain_by_uuid(self._conn, uuid)
                if domain:
                    inst.update(domain)
            except Exception as e:
                LOG.warning("Failed to access libvirt! error=%s" % e)
            return inst
        else:
            LOG.debug('The VM is not in current host!')
            return None

    def get_instances(self, filters):
        instances = set()
        try:
            nova = self.get_nova()
            filters['host'] = self._hostname
            servers = nova.servers.list(detailed=True, search_opts=filters)
            flavors = nova.flavors.list()

            for server in servers:
                for flavor in flavors:
                    if flavor.id == server.flavor["id"]:
                        extra_spec = flavor.get_keys()
                        if 'hw:cpu_policy' in extra_spec \
                                and extra_spec['hw:cpu_policy'] == 'dedicated':
                            inst = instance.instance(server.id, server.name, extra_spec)
                            instances.update([inst])
            # get numa topology and pci info from libvirt
            if len(instances) > 0:
                for inst in instances:
                    domain = guest.get_guest_domain_by_uuid(self._conn, inst.uuid)
                    inst.update(domain)
        except Exception as e:
            LOG.warning("Failed to get instances info! error=%s" % e)

        return instances


def get_nova_client():
    return NovaProvider()
