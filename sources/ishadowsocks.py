# coding: utf8

import re
import requests
from common import log, Nodes


class iShadowsocks(object):

    def __init__(self):

        self.session = requests.session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

    def get_nodes(self):
        log.info('Getting nodes from iShadowsocks...')
        r = self.session.get('http://www.ishadowsocks.com/')
        r.raise_for_status()

        m = re.findall(
            r'<h4>[^<]*服务器地址\s*(?::|：)\s*([\w\-\.]+)\s*</h4>\s*' +
            r'<h4>[^<]*端口\s*(?::|：)\s*(\d+)\s*</h4>\s*' +
            r'<h4>[^<]*密码\s*(?::|：)\s*(.*?)\s*</h4>\s*' +
            r'<h4>[^<]*加密方式\s*(?::|：)\s*([\w\-]+)\s*</h4>',
            r.content)

        nodes = Nodes()
        for n in m:
            nodes.get_nodes(
                hosts=(n[0],),
                port=n[1],
                password=n[2],
                method=n[3])

        return nodes
