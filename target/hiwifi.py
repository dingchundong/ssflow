# coding: utf8

import re
import paramiko
from common import *


def hiwifi(nodes, **kwargs):
    '''kwargs: hostname, username, password, port, config_path'''

    get_from_config_if_none(
        ['hostname', 'username', 'password', 'port', 'config_path'])
    kwargs['port'] = int(kwargs['port'])

    log.info('ssh {u}@{h} -p {p}'.format(
        u=kwargs['username'],
        h=kwargs['hostname'],
        p=kwargs['port']))
    clinet = paramiko.SSHClient()
    clinet.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    clinet.connect(
        hostname=kwargs['hostname'],
        username=kwargs['username'],
        password=kwargs['password'],
        port=kwargs['port'])

    log.info('Getting base SS config')
    stdin, stdout, stderr = clinet.exec_command(
        'cat {}'.format(kwargs['config_path']))
    current_config = ''.join(stdout)
    m = re.search(
        r'^config\s+interface\s+\'ssgoabroad\'$\n(?:^\s*option\s+.*$\n?)*',
        current_config, re.M)

    if m:
        base_config = m.group()
    else:
        base_config = ''

    profiles = list()
    i = 0
    for n in nodes:
        i += 1
        profiles.append(format_node(i, n))
    profiles = '\n\n'.join(profiles)

    new_config = '\n\n'.join([base_config, profiles])

    log.info('Deploying new SS nodes')
    s = None
    for line in new_config.split('\n'):
        s = '>>' if s else '>'
        log.info('... \t{}'.format(line))
        clinet.exec_command('echo "{l}" {s} {p}.tmp'.format(
            l=line,
            s=s,
            p=kwargs['config_path']))
    clinet.exec_command('mv {p} {p}.bak'.format(p=kwargs['config_path']))
    clinet.exec_command('mv {p}.tmp {p}'.format(p=kwargs['config_path']))


def format_node(index, node):
    template = """config interface '{index}'
    option ss_server_des '{des}'
    option ss_server_ip '{ip}'
    option ss_server_port '{port}'
    option ss_password '{password}'
    option ss_method '{method}'"""

    return template.format(
        index=index,
        des=node.test_result(),
        ip=node.ip_or_host(),
        port=node.port,
        password=node.password,
        method=node.method)
