__author__ = 'dan'

from docker import Client
import random
import config_parser as parser



cli = Client(base_url='tcp://192.168.98.99:4243')

# proto = 'tcp'
#
# config_ports = parser.config_params('images')['test_multiple_port'].split()
#
# append_to = str(random.randrange(1025, 65000, 2))
#
# my_new_list = [x + '/' + proto + ':'+ str(random.randrange(1025, 65000, 2)) for x in config_ports]
#
# print my_new_list
#
#
# my_dict_port_list = dict(map(str, x.split(':')) for x in my_new_list)
#
# print my_dict_port_list

config_ports = parser.config_params('images')['test_internal_port'].split()

print config_ports

my_new_list = [x + ':'+ str(random.randrange(1025, 65000, 2)) for x in config_ports]

print my_new_list

my_dict_port_list = dict(map(str, x.split(':')) for x in my_new_list)

print my_dict_port_list

container_id = cli.create_container(
    image='eg_ngphp', hostname='wtfplm', ports=config_ports,
    host_config=cli.create_host_config(port_bindings=my_dict_port_list),
    name='wtf')

cli.start(container=container_id.get('Id'))

