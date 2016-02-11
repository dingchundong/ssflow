# coding: utf8

import sys
import re
import os
import ctypes
import time
import datetime
import threading
import logging as log

import pyping
import requests
from tabulate import tabulate

from socket import gethostbyname
from ConfigParser import ConfigParser

BASE_DIR = os.path.split(os.path.realpath(__file__))[0]
CONFIG_FILE = os.path.join(BASE_DIR, 'ssflow.config')
TLD_LIST_FILE = os.path.join(BASE_DIR, 'tld_list.txt')

if not os.path.isfile(CONFIG_FILE):
    raise Exception('Config file not found: {}'.format(CONFIG_FILE))

config = ConfigParser()
config.read(CONFIG_FILE)

with open(TLD_LIST_FILE, 'r') as fp:
    TLD_LIST = fp.readlines()
TLD_LIST = map(lambda x: x.strip(), TLD_LIST)
TLD_LIST = [x.lower() for x in TLD_LIST if x and x[0] != '#']

log.basicConfig(level=log.INFO, format='%(levelname)s: %(message)s')

if sys.platform.startswith('win32'):
    run_as_root = ctypes.windll.shell32.IsUserAnAdmin() != 0
    default_timer = time.clock
else:
    run_as_root = os.getuid() == 0
    default_timer = time.time

if run_as_root:
    log.info('Got root access, will ping in ICMP mode')
else:
    log.info('No root access, will ping in UDP mode')


class ConfigBased(object):
    def __init__(
            self,
            section=None, ints=[], floats=[], bools=[],
            **config):

        if section is None and config:
            self.config = config
        else:
            if section is None:
                section = self.__class__.__name__.lower()
            self.config = get_config(section, ints, floats, bools)


class Node(object):
    count = 0

    def __init__(self, host, port, password, method, name=None):
        Node.count += 1
        self.ping_own_id = id(Node) + Node.count & 0xFFFF

        self.host = host
        self.port = int(port)
        self.password = password
        self.method = method

        self._ip = None
        host_is_ip = False

        if re.match(r'(\d+\.){3}\d+', host):
            self._ip = host
            host_is_ip = True

        if name is not None:
            self.name = name
        elif host_is_ip:
            self.name = host
        else:
            name = self.host.lower()
            for i in xrange(2):
                for x in TLD_LIST:
                    x = '.' + x
                    if name.endswith(x):
                        name = name[:-len(x)]
                        last_match = x

            if name == 'www':
                name += last_match

            name = name.rsplit('.', 1)
            if name[0] == 'www':
                name = name[-1]
            else:
                name = name[0]
            self.name = name.upper()

        self.deploy_config = get_config('deploy')

        self.ping_results = PingResults()

    def ping(self, timeout=1000):
        if self.ip:
            r = pyping.Ping(
                self.ip, timeout,
                own_id=self.ping_own_id,
                udp=not run_as_root,
            ).do()
            self.ping_results.append(r)
            return r

    @property
    def server(self):
        return self.deploy_config['server'].format(
            ip=self.ip,
            host=self.host)

    @property
    def ip(self):
        if not self._ip:
            try:
                self._ip = gethostbyname(self.host)
            except Exception:
                log.warning(
                    'Failed to resolve domain name: {}'.format(self.host))
            else:
                log.info('{0.host} => {0._ip}'.format(self))
                return self._ip
        return self._ip

    def resolve_host(self):
        return self.ip

    @property
    def score(self):
        if self.ping_results.rtts:
            return (1 + self.ping_results.loss_rate * 20)**2 \
                * (self.ping_results.min * 0.1 +
                   self.ping_results.avg * 0.9)

    @property
    def available(self):
        if self.ping_results:
            return set(self.ping_results) != {None}

    @property
    def test_result(self):
        if self.available:
            # server/ip/host/loss_rate/min/avg/max/score
            data = dict(
                server=self.server,
                ip=self.ip,
                host=self.host,
                loss_rate=self.ping_results.loss_rate,
                min=self.ping_results.min,
                avg=self.ping_results.avg,
                max=self.ping_results.max,
                score=self.score
            )
            return self.deploy_config['test_result'].format(**data)
        elif self.available is False:
            return 'NOT AVAILABLE'


class Nodes(list):
    def __init__(self, *args, **kwargs):
        super(Nodes, self).__init__(*args, **kwargs)

    def __add__(self, y):
        return Nodes(super(Nodes, self).__add__(y))

    def get_nodes(self, hosts, port, password, method):
        method = method.lower()

        i = 0
        total = len(hosts)
        for host in hosts:
            i += 1
            log.info('Got node "{}" ({}/{})'.format(host, i, total))
            self.append(Node(host, port, password, method))

    def resolve_hosts(self):
        threads = list()
        for node in self:
            thread = threading.Thread(target=node.resolve_host, name=node.name)
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()

    def test(self, config_section=None, sort=True, **config):
        if config_section is None:
            config_section = 'ping'
        if not config:
            config = get_config(
                config_section,
                ints=[
                    'count',
                    'deadline',
                    'max_sleep',
                    'timeout',
                    'max_retries'])

        if not config['count'] or not config['deadline']:
            log.info('Test skipped.')
            return

        self.resolve_hosts()

        def do(node):
            if not node.ip:
                return
            done = 0
            while config['count'] < 0 or done < config['count']:
                try:
                    if terminated:
                        break
                    r = node.ping(timeout=config['timeout'])
                    if not r:
                        r = 0
                    if r < config['max_sleep']:
                        time.sleep((config['max_sleep'] - r) / 1000.0)
                    done += 1

                    if done == config['max_retries']:
                        if set(node.ping_results[
                                -config['max_retries']:]) == {None}:
                            log.warning('Failed to test {}'.format(node.name))
                            break
                except KeyboardInterrupt:
                    break

        threads = list()
        terminated = False
        for node in self:
            thread = threading.Thread(target=do, args=(node,), name=node.name)
            thread.start()
            threads.append(thread)

        start_time = default_timer()
        log.info('Test started.')

        round_a = 0
        interval_a = 1
        round_b = 0
        interval_b = 1

        while True:
            try:
                if not terminated:
                    past_time = default_timer() - start_time
                    if past_time // interval_a > round_a:
                        line = list()
                        for node in sorted(self, key=self.sort_key)[:10]:
                            line.append([
                                node.name,
                                node.test_result,
                                len(node.ping_results)])
                        tab = tabulate(
                            line,
                            headers=['NAME', 'RESULT', 'COUNT'],
                            tablefmt='simple')
                        log.info('Top 10 nodes:\n' + tab)
                        round_a = past_time // interval_a

                    if past_time // interval_b > round_b:
                        log_msg = 'Testing {}/{} nodes'.format(
                            len(threads),
                            len(self))
                        if config['deadline'] >= 0:
                            log_msg += ', {} remaining...'.format(
                                str(datetime.timedelta(seconds=round(
                                    config['deadline'] - past_time
                                ))).split('.')[0])
                        else:
                            log_msg += ', {} past...'.format(
                                str(datetime.timedelta(seconds=round(
                                    past_time
                                ))).split('.')[0])
                        log.info(log_msg)
                        round_b = past_time // interval_b

                    if config['deadline'] >= 0 and \
                            past_time >= config['deadline']:
                        terminated = True
            except KeyboardInterrupt:
                terminated = True

            try:
                threads = [t for t in threads if t.isAlive()]
                if not threads:
                    log.info('Test finished.')
                    break
                time.sleep(0.1)
            except KeyboardInterrupt:
                terminated = True
                log.info('Test terminated.')

        if sort:
            self.sort(key=self.sort_key)

    @staticmethod
    def sort_key(node):
        return node.score or 999999999999

    def available_nodes(self):
        return Nodes(n for n in self if n.available)

    def select(self, regex_pattern):
        return Nodes(n for n in self if re.search(
            regex_pattern, n.name, re.I))

    def deploy_to(self, target, **kwargs):
        return target.deploy(self, **kwargs)

    def hosts(self):
        r = list()
        for node in self:
            if node.ip:
                r.append('{}\t{}'.format(node.ip, node.host))
        return '\n'.join(r)


class PingResults(list):

    def __init__(self):
        super(PingResults, self).__init__()

    @property
    def rtts(self):
        return [r for r in self if r is not None]

    @property
    def min(self):
        '''min rtt'''
        if self.rtts:
            return min(self.rtts)

    @property
    def avg(self):
        '''average rtt'''
        if self.rtts:
            return sum(self.rtts) / len(self.rtts)

    @property
    def max(self):
        '''max rtt'''
        if self.rtts:
            return max(self.rtts)

    @property
    def loss_rate(self):
        '''loss rate'''
        if self:
            return float(len([r for r in self if r is None])) / len(self)


def get_config(section, ints=[], floats=[], bools=[]):
    r = dict()
    for k, v in config.items(section):
        r[k] = v

    for opt in ints:
        r[opt] = int(r[opt])
    for opt in floats:
        r[opt] = float(r[opt])
    for opt in bools:
        r[opt] = bool(r[opt])

    return r


def update_tlds():
    url = 'http://data.iana.org/TLD/tlds-alpha-by-domain.txt'
    r = requests.get(url)
    with open(TLD_LIST_FILE, 'w') as fp:
        fp.write(r.text)
