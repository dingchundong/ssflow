# coding: utf8

from source import gogovpn
from target import hiwifi


def deploy(source, target):
    nodes = source()
    nodes.test()
    nodes.deploy(target)


if __name__ == '__main__':
    deploy(gogovpn, hiwifi)
