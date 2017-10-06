from helpers import config_parser as parser, connect_docker_server as make_connection
from helpers.give_me_mount_point import give_me_mount_point
from helpers.give_me_something_unique import give_me_something_unique
from celery import Celery
from models import models as my_sql_stuff
from models.models import db
from flask import Flask

app = Flask(__name__)
app.config['CELERY_BROKER_URL'] = 'redis://lulu:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://lulu:6379/0'
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

@celery.task
def docker_create(name_id, username, password, service, diskspace, image_name, internal_port, exec_this, cap_add_value,
                  privileged, plex_secret_token, plex_server_name):
    """
    this function will create the container
    :rtype : object
    :return:
    """

    # to the magic, generate unique port, make the shared volume
    my_new_volume = give_me_mount_point(username, diskspace)

    # making the list of ports from config
    # appending random values
    # making a dict of port from config and random ports

    my_new_list = [x + ':' + str(give_me_something_unique(name_id, name_id, username, password, service)) for x in
                   internal_port]
    my_dict_port_list = dict(map(str, x.split(':')) for x in my_new_list)

    try:
        app.logger.info('Generating and inserting in db a new allocated port {0}'.format(my_new_list))
        where_to_mount = my_new_volume + parser.config_params('mount')['where_to_mount_dir']
        app.logger.info('We will mount in this location {0}'.format(where_to_mount))

        # here we make the list of ports from confing into a string
        # and remove / tcp udp
        # make removed string into a list and use it in ports
        internal_port_udp_tcp_removed = ''.join(c for c in ' '.join(internal_port) if c not in '/;udp;tcp').split()

        # creating the container
        response = make_connection.connect_docker_server().create_container(image=image_name, hostname=name_id,
                                                                            ports=internal_port_udp_tcp_removed,
                                                                            environment={
                                                                                'ACCESS_TOKEN': plex_secret_token,
                                                                                'SERVER_NAME': plex_server_name,
                                                                                'MANUAL_PORT':
                                                                                    my_dict_port_list.values()[0]},
                                                                            host_config=make_connection.connect_docker_server().create_host_config(
                                                                                cap_add=[cap_add_value],
                                                                                binds=[where_to_mount],
                                                                                port_bindings=my_dict_port_list,
                                                                                privileged=privileged, cpuset_cpus='0',
                                                                                cpu_period=100000,
                                                                                mem_limit=parser.config_params(
                                                                                    'container_settings')['memory']),
                                                                            command=exec_this, name=name_id)
        # starting the container
        make_connection.connect_docker_server().start(container=response.get('Id'))

        result_new_container = make_connection.connect.inspect_container(response.get('Id'))
        new_hostname = result_new_container['Config']['Hostname']
        new_name = result_new_container['Name']
        new_exposed_ports = result_new_container['Config']['ExposedPorts']
        app.logger.info('New container with hostname {0} and name {1} exposed ports {2} created'.format(new_hostname,
                                                                                                        new_name,
                                                                                                        new_exposed_ports))
        app.logger.info('New container created with id {0}'.format(name_id))
        return result_new_container
    except Exception as e:
        # this will delete the table raw where added port and name in ContainerNames
        my_sql_stuff.ContainerNames.query.filter_by(name_of_container=name_id).delete()
        db.session.commit()
        app.logger.error('An error occurred creating the container:{0}'.format(e))