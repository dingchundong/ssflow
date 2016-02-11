# coding: utf8

import os
import re
import sys
import subprocess
import BaseHTTPServer
import threading
import shlex

from common import ConfigBased, log, Nodes


if sys.platform != 'darwin':
    raise Exception('Sorry, this module only supports OS X.')

pac_doc = None


class Shadowsocks_libev_OSX(ConfigBased):

    MODULE_DIR = os.path.split(os.path.realpath(__file__))[0]
    HELPER_INSTALLER_PATH = os.path.join(MODULE_DIR, 'install_helper.sh')
    HELPER_SOURCE_PATH = os.path.join(MODULE_DIR, 'shadowsocks_sysconf')
    HELPER_PATH = '/Library/Application Support/' + \
        'ShadowsocksX/shadowsocks_sysconf'

    LOCAL_PORT = 1080

    def __init__(self, section='shadowsocks_libev_osx', **config):
        super(Shadowsocks_libev_OSX, self).__init__(section, **config)
        self.pac_server = None
        self.make_sure_helper_installed()
        self.ss_local_path = expand_path(self.config['ss_local_path'])

    def make_sure_helper_installed(self):
        if os.path.isfile(self.HELPER_PATH):
            return
        os.chmod(self.HELPER_INSTALLER_PATH, 0o755)
        os.chmod(self.HELPER_SOURCE_PATH, 0o755)
        script = 'do shell script "{}" with administrator privileges'.format(
            self.HELPER_INSTALLER_PATH)
        pipe = subprocess.Popen(
            ['osascript', '-e', script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE)
        if pipe.wait():
            raise Exception('Failed to install proxy helper.')

    def deploy(self, node, mode='auto'):
        '''mode: auto/global'''
        if mode not in ('auto', 'global'):
            raise ValueError('mode: auto/global')
        if isinstance(node, Nodes):
            node = node[0]
        log.info('Using: {0.name}: {0.test_result}'.format(node))
        self.run_ss_local(node)

        if mode == 'auto':
            self.pac_server = PACServer(self.config['pac_path'])
            self.pac_server.start()
            self.set_sys_proxy('auto')
        elif mode == 'global':
            self.set_sys_proxy('global')

        try:
            self.ss_client_pipe.wait()
        except KeyboardInterrupt:
            self.terminate()

    def run_ss_local(self, node):
        log.info('Starting ss-local...')
        args = [
            self.ss_local_path,
            '-s', node.server,
            '-p', str(node.port),
            '-k', node.password,
            '-m', node.method,
            '-l', str(self.LOCAL_PORT)]
        args.extend(shlex.split(self.config['ext_args']))
        self.ss_client_pipe = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

    def set_sys_proxy(self, mode):
        pipe = subprocess.Popen(
            [self.HELPER_PATH, mode],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE)
        r = pipe.wait()
        if r or self.sys_proxy_status != mode:
            raise Exception('Failed to modify system proxy.')

        if mode != 'off':
            log.info('Proxy mode set to "{}".'.format(mode))

    @property
    def sys_proxy_status(self):
        r = subprocess.check_output(['scutil', '--proxy'])
        pac = re.search(
            r'ProxyAutoConfigEnable\s*:\s*(.+)', r).group(1)
        socks = re.search(
            r'SOCKSEnable\s*:\s*(.+)', r).group(1)
        if pac == '1':
            return 'auto'
        elif socks == '1':
            return 'global'
        else:
            return 'off'

    def terminate(self):
        log.info('Terminating SS service...')
        self.set_sys_proxy('off')
        if self.pac_server and self.pac_server.daemon_thread.is_alive():
            self.pac_server.terminate()
        if self.ss_client_pipe:
            self.ss_client_pipe.terminate()


class PACRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/proxy.pac':
            self.wfile.write(pac_doc)


class PACServer(object):
    def __init__(self, pac_path):
        global pac_doc
        pac_doc = load_file(pac_path)
        self.daemon = BaseHTTPServer.HTTPServer(
            ('127.0.0.1', 8090), PACRequestHandler)

        self.daemon_thread = threading.Thread(target=self.daemon.serve_forever)

    def start(self):
        if not self.daemon_thread.is_alive():
            self.daemon_thread.start()

    def terminate(self):
        if self.daemon_thread.is_alive():
            self.daemon.shutdown()


def load_file(path):
    path = expand_path(path)
    try:
        with open(path, 'r') as fp:
            doc = fp.read()
    except IOError:
        raise Exception('"{}" cannot be loaded.'.format(path))

    return doc


def expand_path(path):
    if path.startswith('~/'):
        path = os.path.expanduser('~') + path[1:]
    return path
