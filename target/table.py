# coding: utf8

from tabulate import tabulate
# from common import log


class Table(object):
    def __init__(self, tablefmt='simple'):
        self.tablefmt = tablefmt

    def deploy(self, nodes):
        l = list()
        i = 0
        for n in nodes:
            i += 1
            l.append([
                i,
                n.name,
                n.test_result,
                len(n.ping_results),
                n.server,
                n.port,
                n.password,
                n.method])

        print(tabulate(
            l, headers=[
                '#',
                'NAME',
                'RESULT',
                'COUNT',
                'SERVER',
                'PORT',
                'PASSWORD',
                'METHOD'
            ], tablefmt=self.tablefmt))
