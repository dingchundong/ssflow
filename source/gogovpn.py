# coding: utf8

import re
import requests
from common import *


def gogovpn(**kwargs):
    '''kwargs: service, email, password'''

    get_from_config_if_none(['service', 'email', 'password'])

    base = 'http://www.gogovpn.org/{}/user'.format(kwargs['service'])
    url = dict(
        login='{}/_login.php'.format(base),
        ss_login='{}/index.php'.format(base),
        ss_hosts='{}/node.php'.format(base))

    log.info('Logging in GOGOVPN as {}'.format(kwargs['email']))

    session = requests.session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    r = session.post(url.get('login'), dict(
        email=kwargs['email'],
        passwd=kwargs['password'],
        remember_me='on'))

    r.raise_for_status()

    try:
        r = r.json()
    except:
        raise Exception('Unknown error.')

    if r.get('ok') != '1':
        try:
            msg = r.get('msg').encode('utf8')
        except:
            msg = 'None.'
        raise Exception('Failed to login: {}'.format(msg))

    log.info('Getting SS login')
    r = session.get(url.get('ss_login'))
    r.raise_for_status()

    try:
        port = find_value('端口', '\d+', r.content)
        password = find_value('密码', '\w+', r.content)
        method = find_value('加密方式', '[\w\-]+', r.content)
    except:
        raise Exception('Your service may have been disabled.')

    log.info('Getting SS hosts')
    r = session.get(url.get('ss_hosts'))
    r.raise_for_status()
    hosts = re.findall(
        r'<b[^>]*>\s*(\w[\w\-]*\.gogovpn\.org)\s*</b>',
        r.content)

    nodes = Nodes()

    i = 0
    all = len(hosts)
    for host in hosts:
        i += 1
        log.info('Initializing {}... ({}/{})'.format(host, i, all))
        nodes.append(Node(host, port, password, method))

    return nodes


def find_value(search, value_pattern, string):
    rp = r'{s}\s*(?::|：)?\s*(?:<code>)?\s*(\b{vp})\s*<'.format(
        s=search, vp=value_pattern)
    return re.search(rp, string).group(1)
