# coding: utf8

import re
import webbrowser
import requests
from common import log, ConfigBased


class GeeWan(ConfigBased):

    def __init__(self, section=None, **config):
        super(GeeWan, self).__init__(section, ints=['timeout'], **config)

        log.info('Logging in Geewan router...')

        self.session = requests.session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

        r = self.session.post(
            'http://{}/cgi-bin/luci'.format(self.config['hostname']),
            dict(username='admin', password=self.config['password']))
        r.raise_for_status()

        m = re.search(';stok=([\da-f]{32,})/', r.text)
        self.stok = m.group(1)

    def url(self, interface):
        return 'http://{h}/cgi-bin/luci/;stok={s}/api/net_accel/{i}'.format(
            h=self.config['hostname'],
            s=self.stok,
            i=interface)

    def deploy(self, nodes):
        '''Warning: All old ss nodes in the router will be deleted'''
        '''警告: 部署时将删除路由器中所有旧SS节点'''

        self.delete_ss_nodes()
        self.deploy_new_nodes(nodes)
        self.set_node(self.first_ss_node)
        self.router.open_web_admin()

    def deploy_new_nodes(self, nodes):
        for n in nodes:
            log.info('Deploying new node "{}"'.format(n.name))
            r = self.session.post(
                self.url('set_other_account'),
                dict(
                    type='ss',
                    alias='{0.name}: {0.test_result}'.format(n),
                    server=n.server,
                    server_port=n.port,
                    method=n.method,
                    password=n.password,
                    timeout=self.config['timeout']
                ))
            r.raise_for_status()

    @property
    def current_nodes(self):
        log.info('Getting current nodes...')
        r = self.session.get(self.url('get_custom_account_list'))
        r.raise_for_status()
        return r.json()['accounts']

    def delete_node(self, node):
        log.info('Deleting node "{}"'.format(node['alias']))
        r = self.session.get(
            self.url('del_other_account') + '?id={}'.format(node['id']))
        r.raise_for_status()
        return not r.json()['code']

    def delete_ss_nodes(self):
        for node in self.current_nodes:
            if node['type'] == 'ss':
                self.delete_node(node)

    @property
    def first_ss_node(self):
        for node in self.current_nodes:
            if node['type'] == 'ss':
                return node

    def set_node(self, node):
        log.info('Setting node "{}"'.format(node['alias']))
        url = self.url('set_net_accel') + \
            '?id={}&type=other'.format(node['id'])
        r = self.session.get(url)
        r.raise_for_status()
        return not r.json()['code']

    def open_web_admin(self):
        log.info('Opening web admin...')
        url = 'http://{0[hostname]}/cgi-bin/luci/web/net/accel?' \
            'username=admin&password={0[password]}'.format(self.config)
        webbrowser.open(url)
