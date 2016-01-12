# coding: utf8

from tabulate import tabulate


def table(nodes, tablefmt='simple'):

    l = list()
    i = 0
    for n in nodes:
        score = n.score()
        if score is None:
            score = ''
        else:
            score = '{:.1f}'.format(n.score())

        i += 1
        l.append([
            i,
            n.short,
            n.test_result(short=False, score=False),
            score,
            n.ip_or_host(),
            n.port,
            n.password,
            n.method])

    return tabulate(
        l, headers=[
            'INDEX',
            'NAME',
            'LOSS/MIN/AVG/MAX',
            'SCORE',
            'HOST',
            'PORT',
            'PASSWORD',
            'METHOD'
        ], tablefmt=tablefmt)
