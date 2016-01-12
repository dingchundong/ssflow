# coding: utf8

import re
import requests
from common import *


def geewan(nodes, config_section=None, **kwargs):
    '''kwargs: hostname, password, timeout'''
    '''Warning: All old ss nodes in the router will be deleted'''
    '''警告: 部署时将删除路由器中所有旧SS节点'''

    if config_section is None:
        config_section = 'geewan'
    kwargs = kwargs or get_config(config_section)

    kwargs['timeout'] = int(kwargs['timeout'])

    def url(interface):
        return 'http://{h}/cgi-bin/luci/;stok={s}/api/net_accel/{i}'.format(
            h=kwargs['hostname'],
            s=stok,
            i=interface)

    log.info('Logging in Geewan router...')

    session = requests.session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    r = session.post(
        'http://{}/cgi-bin/luci'.format(kwargs['hostname']),
        dict(username='admin', password=kwargs['password']))
    r.raise_for_status()

    m = re.search(';stok=([\da-f]{32,})/', r.content)
    stok = m.group(1)

    log.info('Getting old nodes...')
    r = session.get(url('get_custom_account_list'))
    r.raise_for_status()

    for i in r.json()['accounts']:
        if i['type'] == 'ss':
            log.info('Deleting old node "{}"'.format(i['alias']))
            r = session.get(
                url('del_other_account') + '?id={}'.format(i['id']))
            r.raise_for_status()

    for n in nodes:
        log.info('Deploying new node "{}"'.format(n.test_result()))
        r = session.post(
            url('set_other_account'),
            dict(
                type='ss',
                alias=n.test_result(),
                server=n.ip_or_host(),
                server_port=n.port,
                method=n.method,
                password=n.password,
                timeout=kwargs['timeout']
            ))
        r.raise_for_status()
