#
# Copyright (c) 2016-2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from ceph_manager import exception
from ceph_manager.i18n import _LI
# noinspection PyUnresolvedReferences
from oslo_log import log as logging


LOG = logging.getLogger(__name__)


def osd_pool_exists(ceph_api, pool_name):
    response, body = ceph_api.osd_pool_get(
        pool_name, "pg_num", body='json')
    if response.ok:
        return True
    return False


def osd_pool_create(ceph_api, pool_name, pg_num, pgp_num):
    # ruleset 0: is the default ruleset if no crushmap is loaded or
    # the ruleset for the backing tier if loaded:
    # Name: storage_tier_ruleset
    ruleset = 0
    response, body = ceph_api.osd_pool_create(
        pool_name, pg_num, pgp_num, pool_type="replicated",
        ruleset=ruleset, body='json')
    if response.ok:
        LOG.info(_LI("Created OSD pool: "
                     "pool_name={}, pg_num={}, pgp_num={}, "
                     "pool_type=replicated, ruleset={}").format(
            pool_name, pg_num, pgp_num, ruleset))
    else:
        e = exception.CephPoolCreateFailure(
            name=pool_name, reason=response.reason)
        LOG.error(e)
        raise e

    # Explicitly assign the ruleset to the pool on creation since it is
    # ignored in the create call
    response, body = ceph_api.osd_set_pool_param(
        pool_name, "crush_ruleset", ruleset, body='json')
    if response.ok:
        LOG.info(_LI("Assigned crush ruleset to OS pool: "
                     "pool_name={}, ruleset={}").format(
            pool_name, ruleset))
    else:
        e = exception.CephPoolRulesetFailure(
            name=pool_name, reason=response.reason)
        LOG.error(e)
        ceph_api.osd_pool_delete(
            pool_name, pool_name,
            sure='--yes-i-really-really-mean-it',
            body='json')
        raise e


def osd_pool_delete(ceph_api, pool_name):
    """Delete an osd pool

    :param pool_name:  pool name
    """
    response, body = ceph_api.osd_pool_delete(
        pool_name, pool_name,
        sure='--yes-i-really-really-mean-it',
        body='json')
    if response.ok:
        LOG.info(_LI("Deleted OSD pool {}").format(pool_name))
    else:
        e = exception.CephPoolDeleteFailure(
            name=pool_name, reason=response.reason)
        LOG.warn(e)
        raise e


def osd_set_pool_param(ceph_api, pool_name, param, value):
    response, body = ceph_api.osd_set_pool_param(
        pool_name, param, value,
        force=None, body='json')
    if response.ok:
        LOG.info('OSD set pool param: '
                 'pool={}, name={}, value={}'.format(
                     pool_name, param, value))
    else:
        raise exception.CephPoolSetParamFailure(
            pool_name=pool_name,
            param=param,
            value=str(value),
            reason=response.reason)
    return response, body


def osd_get_pool_param(ceph_api, pool_name, param):
    response, body = ceph_api.osd_get_pool_param(
        pool_name, param, body='json')
    if response.ok:
        LOG.debug('OSD get pool param: '
                  'pool={}, name={}, value={}'.format(
                      pool_name, param, body['output'][param]))
    else:
        raise exception.CephPoolGetParamFailure(
            pool_name=pool_name,
            param=param,
            reason=response.reason)
    return body['output'][param]
