# coding: utf8


import common
from source import Cloudss
from target import Hiwifi


def deploy(source, target):
    nodes = source().get_nodes()
    nodes.test()
    nodes.deploy_to(target())
    common.log.info('Done!')


if __name__ == '__main__':
    deploy(Cloudss, Hiwifi)
