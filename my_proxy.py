from flask import Flask, request, abort, Response, url_for
from flask import jsonify
import connect_docker_server as make_connection
import config_parser as parser
from sqlalchemy.sql import exists
import random_generator as random_generator_function
import json
from functools import wraps
import validate_hostname as validatehostname
from werkzeug.security import generate_password_hash
from sqlalchemy import text
import volume_size as volumesize
from models import db
import models as my_sql_stuff
from celery import Celery

import time



app = Flask(__name__)

app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

class InvalidUsage(Exception):
    """
    class to return specific return type codes
    """
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


def require_appkey(view_function):
    """
    simple appkey validation
    it will check presence of the header secretkey with value 123
    :param view_function:
    :return:
    """

    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        if request.headers.get('secretkey') and request.headers.get('secretkey') \
                == parser.config_params('proxy')['secretkey']:
            return view_function(*args, **kwargs)
        else:
            abort(401)

    return decorated_function


def give_me_something_unique(name_of_container, hostname, owner, password, service_name):
    """
    let's generate random and unique port
    :rtype : object
    """
    # generate random port
    new_port = random_generator_function.generator_instance.random_port()
    if db.session.query(exists().where(my_sql_stuff.ContainerNames.public_port == new_port)).scalar():
        app.logger.info('there is a port assigned already, try to make a new one')
        try:
            new_port = random_generator_function.generator_instance.random_port()
            app.logger.info('try to insert, if working we god, if not we try again in excepetion')
            db.session.add(
                my_sql_stuff.ContainerNames(name_of_container, hostname, owner, generate_password_hash(password),
                               new_port, service_name))
            db.session.commit()
        except:
            app.logger.info('again we failed, we try again')
            new_port = random_generator_function.generator_instance.random_port()
            db.session.add(
                my_sql_stuff.ContainerNames(name_of_container, hostname, owner, generate_password_hash(password),
                               new_port, service_name))
            db.session.commit()
    else:
        app.logger.info('port doesn\'t exists, good to go')
        db.session.add(
            my_sql_stuff.ContainerNames(name_of_container, hostname, owner, generate_password_hash(password),
                           new_port, service_name))
        db.session.commit()
    return new_port


def give_me_mount_point(owner, size_plan):
    """
    this function will generate a shared tmpfs volume, the size should always be in M
    let's insert mount points into table, user is unique, every user will have unique mount points
    """
    if db.session.query(exists().where(my_sql_stuff.MountPoints.owner == owner)).scalar():
        #if user exists we will reuse the same volume
        new_volume = my_sql_stuff.MountPoints.query.filter_by(owner=owner).first()
        new_volume_str = str(new_volume)
        app.logger.info('This user has already a volume assigned {0}'.format(new_volume_str[21:]))
        return new_volume_str[21:]
    else:
        # seems this is a new user and we will create a new mount point for him
        my_random = random_generator_function.generator_instance.random_volume()
        size = 'size=' + size_plan
        # this will create a new volume
        new_volume = make_connection.connect_docker_server().create_volume(name=owner + my_random, driver='local',
                                                                           driver_opts={'type': 'tmpfs',
                                                                                        'device': 'tmpfs',
                                                                                        'o': size})

        new_volume_created = new_volume['Mountpoint'][:-6]
        new_volume_name = new_volume['Name']
        app.logger.info('new volume created:{0} for user:{1} with name {2}'.format(new_volume_created, owner, new_volume_name))
        db.session.add(my_sql_stuff.MountPoints(owner, new_volume_created, new_volume_name, size_plan))
        db.session.commit()
        return str(new_volume['Name'])


@celery.task
def docker_create(name_id, username, password, service, diskspace, image_name, internal_port, exec_this, cap_add_value,
                  privileged, plex_secret_token, plex_server_name):
    """
    this function will create the container
    :rtype : object
    :return:
    """
    #check if there is a container with the same name, anyway useless because docker is doing same thing
    #we can remove this in the future
    if db.session.query(exists().where(my_sql_stuff.ContainerNames.name_of_container == name_id)).scalar():
        raise InvalidUsage('there is a vm already with this name', status_code=404)



    #to the magic, generate unique port, make the shared volume
    my_new_volume = give_me_mount_point(username, diskspace)

    #making the list of ports from config
    #appending random values
    #making a dict of port from config and random ports

    my_new_list = [x + ':' + str(give_me_something_unique(name_id, name_id, username, password, service)) for x in internal_port]
    my_dict_port_list = dict(map(str, x.split(':')) for x in my_new_list)

    try:
        app.logger.info('Generating and inserting in db a new allocated port {0}'.format(my_new_list))
        where_to_mount = my_new_volume + parser.config_params('mount')['where_to_mount_dir']
        app.logger.info('We will mount in this location {0}'.format(where_to_mount))

        #here we make the list of ports from confing into a string
        #and remove / tcp udp
        #make removed string into a list and use it in ports
        internal_port_udp_tcp_removed = ''.join(c for c in ' '.join(internal_port) if c not in '/;udp;tcp').split()

        #creating the container
        response = make_connection.connect_docker_server().create_container(image=image_name, hostname=name_id,
                                                                            ports=internal_port_udp_tcp_removed,
                                                                            environment={'ACCESS_TOKEN': plex_secret_token,
                                                                                         'SERVER_NAME': plex_server_name,
                                                                                         'MANUAL_PORT': my_dict_port_list.values()[0]},
                                                                            host_config=make_connection.connect_docker_server().create_host_config(
                                                                                cap_add=[cap_add_value],
                                                                                binds=[where_to_mount],
                                                                                port_bindings=my_dict_port_list,
                                                                                privileged=privileged, cpuset_cpus='0', cpu_period=100000,
                                                                                mem_limit=parser.config_params('container_settings')['memory']),
                                                                            command=exec_this, name=name_id)
        #starting the container
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
    except:
            #this will delete the table raw where added port and name in ContainerNames
            my_sql_stuff.ContainerNames.query.filter_by(name_of_container=name_id).delete()
            db.session.commit()
            app.logger.error('An error occurred creating the container')
            raise InvalidUsage('can\'t make this container', status_code=404)


def storage_sum():
    """
    function to check storage
    this will sum up all rows from db
    this is used just to see how much storage is alocated
    !!!!NB!!!! Not real space
    :return:
    """
    sql_storage_sum = db.engine.execute(text('select sum(size_plan) from mount'))
    storage_sum = []
    for row in sql_storage_sum:
            storage_sum.append(row[0])
    return storage_sum


@app.route ('/api/seedboxes/storage', methods=['GET'])
@require_appkey
def storage():
    """
    curl -i -H "secretkey:1234" http://localhost:5000/api/seedboxes/storage
    return alocated storage from db
    :return:
    """
    app.logger.info('Received request for alocated disk space')
    dat = "'disk_space_allocated': '{0}'".format(storage_sum())
    resp = Response(response=dat, status=200, mimetype="application/json")
    return resp

@app.route ('/api/seedboxes/logs/<string:container_id>', methods=['GET'])
@require_appkey
def logs(container_id):
    """
    this function will retunr logs of started container, useful for softether to get the vpn keys
    curl -i -H 'secretkey:1234'  http://localhost:5000/api/seedboxes/logs/vm6690_ssh
    :param container_id:
    :return:
    """
    app.logger.info('Received request for container logs for container {0}'.format(container_id))
    try:
        logs_obj = make_connection.connect_docker_server().logs(container_id, stream=False)
        resp = Response(response=logs_obj, status=200, mimetype="application/txt")
        return resp
    except:
        raise InvalidUsage('There is no container with this name', status_code=200)

@app.route('/api/seedboxes/stats/<string:container_id>', methods=['GET'])
@require_appkey
def stats(container_id):
    """
    get statistics from container
    curl -i -H 'secretkey:1234'  http://localhost:5000/api/seedboxes/stats/vm6690_ssh
    :param container_id:
    :return:
    """
    app.logger.info('Received request for container stats for container {0}'.format(container_id))
    try:
        stats_obj = make_connection.connect_docker_server().stats(container_id, decode=True, stream=False)
        return jsonify(stats_obj)
    except:
        raise InvalidUsage('There is no container with this name', status_code=200)


@app.route('/api/seedboxes/management/<string:container_id>', methods=['POST'])
@require_appkey
def management(container_id):
    """
    this function will restart/stop/kill an instace
    curl -i -H 'secretkey:1234' -H "Content-Type: application/json" -X POST -d
    '{"action":"start" }' http://localhost:5000/api/seedboxes/management/b90ea5517564
    :param container_id:
    :return:
    """
    content = request.json
    app.logger.info('Do action {0} for container{1}'.format(content['action'], container_id))
    #stop container
    if content['action'] == 'stop':
        make_connection.connect_docker_server().stop(container_id, timeout=10)
    #restart container
    if content['action'] == 'restart':
        make_connection.connect_docker_server().restart(container_id, timeout=10)
    #start container after stop
    if content['action'] == 'start':
        make_connection.connect_docker_server().start(container_id)
    #kill container, main process
    if content['action'] == 'kill':
        make_connection.connect_docker_server().kill(container_id, timeout=10)
    #delete container, force
    if content['action'] == 'delete':
        make_connection.connect_docker_server().remove_container(container_id, force=True)
        assert isinstance(my_sql_stuff.ContainerNames.query.filter_by(name_of_container=container_id).delete, object)
        my_sql_stuff.ContainerNames.query.filter_by(name_of_container=container_id).delete()
        db.session.commit()
    dat = '{0}"container_id": "{1}", "action": "{2}"{3}'.format('{', container_id, content['action'], '}')
    resp = Response(response=dat, status=200, mimetype="application/json")
    return resp


@app.route('/api/seedboxes/execute/<string:name_id>', methods=['POST'])
@require_appkey
def executecommands(name_id):
    """
    this function will execute commands on the container
    curl -i -H "secretkey:1234" -H "Content-Type: application/json" -X POST -d
    '{"command":"htpasswd -b -c /etc/nginx/.htpasswd test test"}' http://arisvm:5000/api/seedboxes/execute/rtorrent

    :param name_id:
    :return:
    """
    try:
        content = request.json
        app.logger.info('executing command:{0} for container:{1}'.format(content['command'], name_id))
        exec_command = make_connection.connect_docker_server().exec_create(name_id, content['command'], tty=False, stderr=True, privileged=True)
        make_connection.connect_docker_server().exec_start(exec_command)
        exec_inspect = make_connection.connect_docker_server().exec_inspect(exec_command)
        return jsonify(exec_inspect)
    except:
         raise InvalidUsage('can\'t execute command on non existing/not running container', status_code=404)


@app.route('/api/seedboxes/new/<string:name_id>', methods=['POST'])
@require_appkey
def makevm(name_id):
    """
    curl -i -H "secretkey:1234" -H "Content-Type: application/json" -X POST -d '{"username":"dan","password":
    "123456789", "options": {"diskspace":"500m","service":"ssh"}}' http://localhost:5000/api/seedboxes/new/sshdan
    this will create a container
    we parse the json data and take username/password and we insert this into db
    :param name_id:
    :return:
    """
    content = request.json
    my_request = json.dumps(content)

    app.logger.info('Username {0}, passwd:{1}, diskspace:{2}, service:{3}'.format(content['username'],
                                                                                  content['password'],
                                                                                  content['options']['diskspace'],
                                                                                  content['options']['service']))


    #check if the hostname is valid, should not contain strange stuff
    if not validatehostname.isvalidhostname(name_id):
        raise InvalidUsage('invalid hostname', status_code=404)

    #check if we have plex related stuff
    if my_request.find('plex') != -1:
        plex_secret_token = content['plex']['plex_secret_token']
        plex_server_name = content['plex']['plex_server_name']
    else:
        plex_secret_token = ''
        plex_server_name = ''

    # TODO convert this to dictionary or invent something smarter than if else

    #create ssh container
    if content['options']['service'] == 'ssh':
        image_name = parser.config_params('images')['ssh_image_name']
        exec_this = ''
        cap_value = 'NET_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['ssh_internal_port'].split()


    #create web container
    if content['options']['service'] == 'web':
        image_name = parser.config_params('images')['web_image_name']
        exec_this = 'python app.py'
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['web_internal_port'].split()

    #create rtorrent container
    if content['options']['service'] == 'rtorrent':
        image_name = parser.config_params('images')['rtorrent_image_name']
        exec_this = ''
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['rtorrent_internal_port'].split()

    #create rutorrent container
    if content['options']['service'] == 'rutorrent':
        image_name = parser.config_params('images')['rutorrent_image_name']
        exec_this = ''
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['rutorrent_internal_port'].split()

    #create transmission container
    if content['options']['service'] == 'transmission':
        image_name = parser.config_params('images')['transmission_image_name']
        exec_this = ''
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['transmission_internal_port'].split()

    #create deluge container
    if content['options']['service'] == 'deluge':
        image_name = parser.config_params('images')['deluge_image_name']
        exec_this = ''
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['deluge_internal_port'].split()

    #create openvpn over udp container
    if content['options']['service'] == 'openvpnudp':
        image_name = parser.config_params('images')['openvpnudp_image_name']
        exec_this = ''
        cap_value = 'NET_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['openvpnudp_internal_port'].split()

    #create owncloud container
    if content['options']['service'] == 'owncloud':
        image_name = parser.config_params('images')['owncloud_image_name']
        exec_this = ''
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['owncloud_internal_port'].split()

    #create nginxphp container
    if content['options']['service'] == 'nginxphp':
        image_name = parser.config_params('images')['ngphp_image_name']
        exec_this = ''
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['ngphp_internal_port'].split()

    #create mariadb container
    if content['options']['service'] == 'mariadb':
        image_name = parser.config_params('images')['mariadb_image_name']
        exec_this = ''
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['mariadb_internal_port'].split()

    #create plex container
    if content['options']['service'] == 'plex':
        image_name = parser.config_params('images')['plex_image_name']
        exec_this = ''
        cap_value = 'NET_ADMIN'
        privileged = True
        internal_port = parser.config_params('images')['plex_internal_port'].split()

    #create sftp container
    if content['options']['service'] == 'sftp':
        image_name = parser.config_params('images')['sftp_image_name']
        exec_this = ''
        cap_value = 'NET_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['sftp_internal_port'].split()

    new_container = docker_create.delay(name_id, content['username'], content['password'],
                                        content['options']['service'],
                      content['options']['diskspace'], image_name, internal_port, exec_this, cap_value, privileged,
                                  plex_secret_token, plex_server_name)
    app.logger.info('New container ID for redis is {0}'.format(new_container.id))
    return jsonify(), 202, dict(Location=url_for('taskstatus', task_id=new_container.id))


@app.route('/api/seedboxes/pending/<string:task_id>')
@require_appkey
# start in a console this > celery2 worker -A my_proxy.celery --loglevel=info
def taskstatus(task_id):
    task = docker_create.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'current': 0,
            'total': 1,
            'status': 'Pending...'
        }
    elif task.state != 'FAILURE':
        app.logger.info('Info about the new  container'.format(task.result))
        app.logger.info('Task - create_container state is {0}'.format(task.state))
        app.logger.info('Task - create_container current is {0}'.format(task.info.get('current', 0)))
        app.logger.info('Task - create_container total is {0}'.format(task.info.get('total', 1)))
        app.logger.info('Task - create_container status is {0}'.format(task.info.get('status', '')))
        response = task.result
        if 'result' in task.info:
            response['result'] = task.info['result']
    else:
        # something went wrong in the background job
        ## print task.result
        response = {
            'state': task.state,
            'current': 1,
            'total': 1,
            'reason': 'maybe there is a container with the same name'
            # 'status': str(task.result),  # this is the exception raised
        }
    return jsonify(response)

@app.route('/api/seedboxes/volumeusage/<string:name_id>', methods=['GET'])
@require_appkey
def volumeusage(name_id):
        usage = volumesize.volume_size(name_id)
        return Response(usage, mimetype='application/json')

@app.route('/api/seedboxes/version', methods=['GET'])
@require_appkey
def version():
    """
    return versios of docker, used for whatever
    :return:
    curl -i -H 'secretkey:1234'  http://localhost:5000/api/seedboxes/version
    """
    try:
        if request.method == 'GET':
            my_docker_is = make_connection.connect.version()
            return jsonify(my_docker_is)
    except:
        raise InvalidUsage('Issues with the server', status_code=503)


@app.route('/api/seedboxes/query/<string:name>', methods=['GET'])
@require_appkey
def query(name):
    """
    look in the containers db and return values
    curl -i -H 'secretkey:1234'  http://localhost:5000/api/seedboxes/query/nginx
    :return:
    """
    try:
        result_search = make_connection.connect.search(name)
        return Response(json.dumps(result_search[:2]), mimetype='application/json')
    except:
        raise InvalidUsage('Issues with the server', status_code=503)


# this will investigate a existing container
@app.route('/api/seedboxes/investigate/<string:container_id>', methods=['GET'])
@require_appkey
def investigate(container_id):
    """
    investigare container, can be name or id
    curl -H 'secretkey:1234' http://localhost:5000/api/seedboxes/investigate/83f1ee418bc4975c1a76bbffb96fb914caeb13c0cea5d44010e3
    :return:
    """
    try:
        result_investigate = make_connection.connect.inspect_container(container_id)
        assert isinstance(result_investigate, object)
        app.logger.info('Received request for investigate for container {0}'.format(container_id))
        return jsonify(result_investigate)
    except:
        raise InvalidUsage('There is no such container', status_code=200)


@app.route('/api/seedboxes/showinstances', methods=['GET'])
@require_appkey
def showstuff():
    """
    this will return all instances of a specific user
    curl -H 'secretkey:1234' http://localhost:5000/api/seedboxes/showinstances?name_id=dan
    :return:
    """
    if 'name_id' in request.args:
        show_property_of_user = request.args['name_id']
        return jsonify(str(db.session.query(my_sql_stuff.ContainerNames).filter_by(owner=show_property_of_user).all()))
    else:
        raise InvalidUsage('Need a name of user to query database', status_code=200)


@app.route('/api/seedboxes/killuser', methods=['POST'])
@require_appkey
def killuser():
    """
    :return:
    this function will delete all user containers and volume attached to the containers
    curl -i -H "secretkey:1234" -H "Content-Type: application/json" -X POST  -d '{"username":"dan"}' http://localhost:5000/api/seedboxes/killuser
    """

    content = request.json
    user_to_be_deleted = format(content['username'])
    dat = 'All containers and volumes of username {0} have been deleted'.format(user_to_be_deleted)

    #let's do some checks

    if not db.session.query(exists().where(my_sql_stuff.ContainerNames.owner == user_to_be_deleted)).scalar():
        app.logger.info('There is no such username {0}'.format(user_to_be_deleted))
        raise InvalidUsage('there is no such username, nothing to delete, go away', status_code=404)
    else:
        try:
            #let's stop the containers
            for instance in db.session.query(my_sql_stuff.ContainerNames).group_by(
                    my_sql_stuff.ContainerNames.name_of_container).filter_by(owner=user_to_be_deleted).all():
                app.logger.info('Username {0} containers {1} will be deleted'.format(user_to_be_deleted, instance.name_of_container))
                make_connection.connect_docker_server().remove_container(instance.name_of_container, force=True)

            #remove container names from db
            my_sql_stuff.ContainerNames.query.filter_by(owner=user_to_be_deleted).delete()

            #let's delete volume
            for volume in db.session.query(my_sql_stuff.MountPoints).filter_by(owner=user_to_be_deleted).limit(1):
                app.logger.info('Username {0} volume {1} will be deleted'.format(user_to_be_deleted, volume.volume_name))
                make_connection.connect_docker_server().remove_volume(volume.volume_name)

            #let's delete volume from db
            my_sql_stuff.MountPoints.query.filter_by(owner=user_to_be_deleted).delete()
            #commit db
            db.session.commit()

            resp = Response(response=dat, status=200)
        except:
            app.logger.info('something bad happened')
            raise InvalidUsage('something bad happened ', status_code=500)

    return resp

if __name__ == '__main__':
    app.run(debug=True)
