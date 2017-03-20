__author__ = 'danbordeanu'

import re

def isvalidhostname(hostname):
    """
    this function will validate if hostname is valid
    :param hostname:
    :return:
    """
    disallowed = re.compile("[^a-zA-Z\d\-]")
    return all(map(lambda x: len(x) and not disallowed.search(x), hostname.split(".")))