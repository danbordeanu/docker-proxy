__author__ = 'danbordeanu'

import unittest

from config_parser import check_if_config_exists
import config_parser as parser
import random_generator as random_generator_function


class Md5Test(unittest.TestCase):

    def test_is_there_config(self):
        """
        Test if there is config file
        :return:
        """
        print 'test 1 - test if there is config file in place'
        self.assertTrue(check_if_config_exists('config.ini'), 'Uhhh, no config file')

    def test_random_port_generator_not_restricred(self):
        """
        Test if random generated port is not in restricted list
        :return:
        """
        print 'test 2 - test if random generated port is not in the excluded list'
        my_excluded_list = parser.config_params('rand_exclusion')['exclude_ports'].split()
        my_port = random_generator_function.generator_instance.random_port()
        for i in my_excluded_list:
            self.assertNotEqual(my_port, i, 'This port should not be generated')

    def test_random_port_generator_is_int(self):
        """
        test if random port is generating an int
        :return:
        """
        print 'test 3 - test if generated radom port is int'
        assert type(random_generator_function.generator_instance.random_port()) is int, \
            'returned port is not integer {0}'.format(random_generator_function.generator_instance.random_port())

    def test_random_volume_is_string(self):
        """
        test of random volume name is str
        :return:
        """
        print 'test 4 - test if generated random volume is str'
        assert type(random_generator_function.generator_instance.random_volume()) is str, \
            'returner random volume is not str {0}'.format(random_generator_function.generator_instance.random_volume())
if __name__ == '__main__':
    unittest.main()