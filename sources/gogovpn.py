# coding: utf8

import re
import requests
from common import log, ConfigBased, Nodes


class GoGoVPN(ConfigBased):
    def __init__(self, section=None, **config):
        super(GoGoVPN, self).__init__(section, **config)
        self.session = requests.session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

    def get_nodes(self):
        base = 'http://www.gogovpn.org/{}/user'.format(self.config['service'])
        url = dict(
            login='{}/_login.php'.format(base),
            ss_login='{}/index.php'.format(base),
            ss_hosts='{}/node.php'.format(base))

        log.info('Logging in GOGOVPN as {}'.format(self.config['email']))

        r = self.session.post(url.get('login'), dict(
            email=self.config['email'],
            passwd=self.config['password'],
            remember_me='on'))

        r.raise_for_status()

        try:
            r = r.json()
        except:
            raise Exception('Unknown error.')

        if r.get('ok') != '1':
            try:
                msg = r.get('msg').encode()
            except:
                msg = 'None.'
            raise Exception('Failed to login: {}'.format(msg))

        log.info('Getting SS login')
        r = self.session.get(url.get('ss_login'))
        r.raise_for_status()

        try:
            port = self.find_value('端口', '\d+', r.content)
            password = self.find_value('密码', '\w+', r.content)
            method = self.find_value('加密方式', '[\w\-]+', r.content)
        except:
            raise Exception('Your service may have been disabled.')

        log.info('Getting SS hosts')
        r = self.session.get(url.get('ss_hosts'))
        r.raise_for_status()
        hosts = re.findall(
            r'<b[^>]*>\s*(\w[\w\-]*\.gogovpn\.org)\s*</b>',
            r.content)

        nodes = Nodes()
        nodes.get_nodes(hosts, port, password, method)
        return nodes

    @staticmethod
    def find_value(search, value_pattern, string):
        rp = r'{s}\s*(?::|：)?\s*(?:<code>)?\s*(\b{vp})\s*<'.format(
            s=search, vp=value_pattern)
        return re.search(rp, string).group(1)
