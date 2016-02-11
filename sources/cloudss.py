# coding: utf8

import re
import requests
from common import log, Nodes, ConfigBased


class CloudSS(ConfigBased):
    def __init__(self, section=None, **config):
        super(CloudSS, self).__init__(section, **config)
        self.session = requests.session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})
        self.url_base = 'http://www.cloudss.net'
        self.url_products = self.url('/clientarea.php?action=products')
        self.url_product_details = self.url(
            '/clientarea.php?action=productdetails&id=')
        self.token = ''

    def url(self, s):
        return self.url_base + s

    @property
    def product_ids(self):
        r = self.session.get(self.url_products)
        r.raise_for_status()
        m = re.search(
            r'name="token"[^<>]+?value="([\da-f]{40})"', r.content, re.I)
        self.token = m.group(1)

        r = self.session.post(
            url=self.url('/dologin.php'),
            data=dict(
                token=self.token,
                username=self.config['email'],
                password=self.config['password']),
            headers=dict(
                Referer=self.url_products))
        r.raise_for_status()

        m = re.search(
            re.escape('href="' + '/clientarea.php?action=productdetails') +
            r'\b[^"<>]+?\bid=(\d+)"', r.content, re.I)

        return m.groups()

    def get_nodes(self):
        log.info('Getting nodes from CloudSS...')
        url = self.url_product_details + self.product_ids[0]
        r = self.session.get(url)
        r.raise_for_status()
        # 节点列表, 加密方式, 连接端口, 连接密码
        method = self.find_value(r.content, '加密方式')
        port = self.find_value(r.content, '连接端口')
        password = self.find_value(r.content, '连接密码')
        hosts = self.find_value(r.content, '节点列表')
        hosts = re.findall('(?:[\w\-]+\.)+[\w\-]+', hosts)

        nodes = Nodes()
        nodes.get_nodes(hosts, port, password, method)
        return nodes

    @staticmethod
    def find_value(string, key):
        m = re.search(
            '<td>{}</td><td>(.+?)</td>'.format(key),
            string, re.DOTALL)
        return m.group(1)
