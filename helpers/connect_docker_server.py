import config_parser as parser
import docker
import os
import pytest


# from docker import Client



def requires_api_version(version):
    """
    Force validation of a docker API version, will fail if version < 1.24
    This function could be made as a decorator to force api validation before usage of docker API
    :rtype : object
    EX:
    import requires_api_version
    @requires_api_version('1.21')
    :param version:
    :return:
    """
    test_version = os.environ.get(
        'DOCKER_TEST_API_VERSION', docker.constants.DEFAULT_DOCKER_API_VERSION
    )
    return pytest.mark.skipif(
        docker.utils.version_lt(test_version, version),
        reason='API version is too low (< {0})'.format(version)
    )


@requires_api_version('1.24')
def connect_docker_server():
    """
    this function will connect to docker server endpoint
    :rtype : object
    :return:
    """
    server_address = parser.config_params('server')['server_address']
    try:
        cli = docker.APIClient(base_url=server_address)
        cli.info()
        return cli
    except:
        print 'no connection to the server :('

connect = connect_docker_server()

# TODO we need to remove this in the future

# old python docker connection
# def connect_docker_server():
#     server_address = parser.config_params('server')['server_address']
#     try:
#         cli = Client(base_url=server_address)
#         cli.info()
#         return cli
#     except:
#         print 'no connection to the server :('
#
#
# connect = connect_docker_server()
