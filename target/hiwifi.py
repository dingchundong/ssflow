# coding: utf8

import re
import paramiko
from common import log, ConfigBased


class Hiwifi(ConfigBased):

    def __init__(self, section=None, **config):
        super(Hiwifi, self).__init__(section, ints=['port'], **config)

        log.info('ssh {0[username]}@{0[hostname]} -p {0[port]}'.format(
            self.config))

        self.clinet = paramiko.SSHClient()
        self.clinet.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.clinet.connect(
            hostname=self.config['hostname'],
            username=self.config['username'],
            password=self.config['password'],
            port=self.config['port'])

        log.info('Getting base SS config')
        stdin, stdout, stderr = self.clinet.exec_command(
            'cat {}'.format(self.config['config_path']))
        current_config = ''.join(stdout)
        m = re.search(
            r'^config\s+interface\s+\'ssgoabroad\'$\n(?:^\s*option\s+.*$\n?)*',
            current_config, re.M)

        if m:
            self.base_config = m.group()
        else:
            self.base_config = ''

    def deploy(self, nodes):
        '''Warning: All old ss nodes in the router will be deleted'''
        '''警告: 部署时将删除路由器中所有旧SS节点'''

        log.info('Deploying new SS nodes')

        profiles = list()
        i = 0
        for node in nodes:
            i += 1
            profiles.append(self.format_node(i, node))
        profiles = '\n\n'.join(profiles)
        new_config = '\n\n'.join([self.base_config, profiles])

        s = None
        for line in new_config.split('\n'):
            s = '>>' if s else '>'
            log.info('... \t{}'.format(line))
            self.clinet.exec_command('echo "{l}" {s} {p}.tmp'.format(
                l=line,
                s=s,
                p=self.config['config_path']))
        self.clinet.exec_command(
            'mv {p} {p}.bak'.format(p=self.config['config_path']))
        self.clinet.exec_command(
            'mv {p}.tmp {p}'.format(p=self.config['config_path']))

    @staticmethod
    def format_node(index, node):
        return """config interface '{index}'
        option ss_server_des '{des}'
        option ss_server_ip '{ip}'
        option ss_server_port '{port}'
        option ss_password '{password}'
        option ss_method '{method}'""".format(
            index=index,
            des='{0.name}: {0.test_result}'.format(node),
            ip=node.server,
            port=node.port,
            password=node.password,
            method=node.method)
