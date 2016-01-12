# coding: utf8

import os.path
import time
import datetime
import pyping
import logging as log

from socket import gethostbyname
from ConfigParser import ConfigParser

CONFIG_FILE = 'deploy.config'

if not os.path.isfile(CONFIG_FILE):
    raise Exception('Config file not found: {}'.format(CONFIG_FILE))

config = ConfigParser()
config.read(CONFIG_FILE)

log.basicConfig(level=log.INFO, format='%(levelname)s: %(message)s')

udp = False
try:
    pyping.Ping('localhost', udp=udp).do()
except:
    udp = not udp

if udp:
    log.info('No root access, will ping in UDP mode')
else:
    log.info('Got root access, will ping in ICMP mode')


class Node(object):

    def __init__(self, host, port, password, method):
        self.host = host
        self.port = int(port)
        self.password = password
        self.method = method

        s = host.split('.', 2)
        i = 1 if s[0].lower() == 'www' else 0
        self.short = s[i].upper()

        self.pr = PingResult()
        self.get_ip()

    def get_ip(self):
        try:
            self.ip = gethostbyname(self.host)
        except Exception:
            log.warning('Failed to resolve domain name: {}'.format(self.host))
            self.ip = None
        else:
            log.info('{host} => {ip}'.format(host=self.host, ip=self.ip))
            return self.ip

    def ip_or_host(self):
        return self.ip or self.host

    def ping(self):
        if self.ip:
            r = pyping.Ping(self.ip, udp=udp).do()
            self.pr.append(r)
            return r

    def score(self):
        if self.pr.rtts():
            return (1 + self.pr.lr() * 20)**2 \
                * (self.pr.min() * 0.2 + self.pr.avg() * 0.8)

    def test_result(self, short=True, score=True):
        def fix(text=''):
            if score:
                s = self.score()
                if s is None:
                    s = ''
                else:
                    s = '={:.1f}'.format(s)
                text += s
            if short and text:
                return '{}: {}'.format(self.short, text)
            elif short and not text:
                return self.short
            else:
                return text

        if self.pr.rtts():
            return fix('{:.1%}/{:.0f}/{:.0f}/{:.0f}'.format(
                self.pr.lr(),
                self.pr.min(),
                self.pr.avg(),
                self.pr.max()))
        elif self.ip and not self.pr:
            return fix()
        else:
            return fix('FAILED')


class Nodes(list):
    def __init__(self, *args, **kwargs):
        super(Nodes, self).__init__(*args, **kwargs)

    def __add__(self, y):
        return Nodes(super(Nodes, self).__add__(y))

    def test(self, config_section=None, auto_sort=True, **kwargs):
        '''kwargs: option, value'''

        if config_section is None:
            config_section = 'ping'
        kwargs = kwargs or get_config(config_section)

        kwargs['option'] = kwargs['option'].lower()
        kwargs['value'] = int(kwargs['value'])
        start = datetime.datetime.now()

        if kwargs['option'] == 'time':
            kwargs['value'] = datetime.timedelta(seconds=kwargs['value'])

        def waiting(doing):
            global waiting_msg
            waiting_msg = 'Testing ping ({}'.format(doing)
            if kwargs['option'] == 'count':
                r = kwargs['value'] - doing
                if r < 0:
                    return False
                else:
                    waiting_msg += '/{})...'.format(kwargs['value'])
                    return True
            elif kwargs['option'] == 'time':
                r = kwargs['value'] - (datetime.datetime.now() - start)
                if r < datetime.timedelta():
                    return False
                else:
                    waiting_msg += '), {} remaining...'.format(
                        str(r).split('.')[0])
                    return True
            elif kwargs['option'] == 'skip':
                return False
            elif kwargs['option'] == 'persistent':
                waiting_msg += ')...'
                return True
            else:
                raise Exception(
                    'Unknown ping option: {}'.format(kwargs['option']))

        try:
            doing = 1
            while waiting(doing):
                log.info(waiting_msg)
                while True:
                    last_round = list()
                    for node in self:
                        last_round.append(node.ping())

                    if set(last_round) == {None}:
                        failing = True
                        for node in reversed(self):
                            del node.pr[-1]
                            if failing and node.pr:
                                if node.pr[-1] is None:
                                    del node.pr[-1]
                                else:
                                    failing = False
                        log.warning(
                            'Failed to ping ({}), retrying...'.format(doing))
                        time.sleep(1)
                    else:
                        break
                doing += 1
        except KeyboardInterrupt:
            log.warning('Test aborted.')

        if kwargs['option'] != 'skip':
            if auto_sort:
                self.sort(key=lambda n: n.score() or 99999999)
            for node in self:
                log.info('Result: {}'.format(node.test_result()))

    def deploy(self, target, **kwargs):
        return target(self, **kwargs)

    def hosts(self):
        r = list()
        for node in self:
            if node.ip:
                r.append('{}\t{}'.format(node.ip, node.host))
        return '\n'.join(r)

    def dnsmasq(self, server=None):
        r = list()
        if server:
            for node in self:
                r.append('server=/{}/{}'.format(node.host, server))
        else:
            for node in self:
                if node.ip:
                    r.append('address=/{}/{}'.format(node.host, node.ip))
        return '\n'.join(r)


class PingResult(list):

    def __init__(self):
        super(PingResult, self).__init__()

    def rtts(self):
        return [r for r in self if r is not None]

    def min(self):
        '''min rtt'''
        if self.rtts():
            return min(self.rtts())

    def avg(self):
        '''average rtt'''
        if self.rtts():
            return sum(self.rtts()) / len(self.rtts())

    def max(self):
        '''max rtt'''
        if self.rtts():
            return max(self.rtts())

    def lr(self):
        '''loss rate'''
        if self:
            return float(len([r for r in self if r is None])) / len(self)


def get_config(section):
    r = dict()
    for k, v in config.items(section):
        r[k] = v
    return r
