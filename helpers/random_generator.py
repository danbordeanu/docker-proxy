import random
import string
import config_parser as parser


class RandomGenerator:
    """
    this class is generating random stuff
    """

    def __init__(self, min_interval, max_interval):
        """
        :param min_interval:
        :param max_interval:
        :return:
        """
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.salt = 2
        self.my_excluded = parser.config_params('rand_exclusion')['exclude_ports'].split()
        self.range = 6

    def random_port(self):
        """
        this function will generate a number port excluded the restricted ports
        :return:
        """
        random_port_value = None
        while random_port_value in self.my_excluded or random_port_value is None:
            random_port_value = random.randrange(self.min_interval, self.max_interval, self.salt)
        return random_port_value

    def random_volume(self):
        """
        this function will generate a random string for volumes
        :return:
        """
        my_random_volume = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(self.range))
        return my_random_volume


generator_instance = RandomGenerator(1024, 65535)
