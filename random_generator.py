__author__ = 'dan'

import random
import config_parser as parser


def rand():
    """
    this function will generate the random port for the container, excluding a specific list of ports
    https://superuser.com/questions/188058/which-ports-are-considered-unsafe-on-chrome
    :return:
    """
    my_excluded = parser.config_params('rand_exclusion')['exclude_ports'].split()
    r = None
    while r in my_excluded or r is None:
        r = random.randrange(1025, 65000, 2)
    return r

