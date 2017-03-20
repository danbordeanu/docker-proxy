import random
import config_parser as parser
import string


def rand_port():
    """
    this function will generate the random port for the container, excluding a specific list of ports
    https://superuser.com/questions/188058/which-ports-are-considered-unsafe-on-chrome
    :return:
    """
    my_excluded = parser.config_params('rand_exclusion')['exclude_ports'].split()
    random_port_value = None
    while random_port_value in my_excluded or random_port_value is None:
        random_port_value = random.randrange(1025, 65000, 2)
    return random_port_value


def rand_volume():
    """
    this is will return a random volume name
    :return:
    """
    my_random_volume = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return my_random_volume
