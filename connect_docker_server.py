__author__ = 'danbordeanu'

import config_parser as parser
import docker


#TODO add tls

def connect_docker_server():
    server_address = parser.config_params('server')['server_address']
    try:
        cli = docker.APIClient(base_url=server_address)
        cli.info()
        return cli
    except:
        print 'no connection to the server :('


connect = connect_docker_server()
