import ast
import json
from functools import wraps

from celery import Celery
from flask import Flask, request, abort, Response
from flask import jsonify
from sqlalchemy.sql import exists

import helpers.config_parser as parser
import helpers.connect_docker_server as make_connection
import helpers.nodeip as swarnodeip
import helpers.validate_hostname as validatehostname
import helpers.volume_size as volumesize
from helpers.docker_create import docker_create
from helpers.storage_sum import storage_sum
from helpers.swarm_create import swarm_create
from models import models as my_sql_stuff
from models.models import db

app = Flask(__name__)

app.config['CELERY_BROKER_URL'] = 'redis://lulu:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://lulu:6379/0'
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


@app.route('/api/seedboxes/storage', methods=['GET'])
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


@app.route('/api/seedboxes/logs/<string:container_id>', methods=['GET'])
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
    # TODO mve this in a separate function and do one single call for the actions
    content = request.json
    app.logger.info('Do action {0} for container{1}'.format(content['action'], container_id))
    # stop container
    if content['action'] == 'stop':
        try:
            make_connection.connect_docker_server().stop(container_id, timeout=10)
            dat = '{0}"container_id": "{1}", "action": "{2}"{3}'.format('{', container_id, content['action'], '}')
        except Exception as e:
            app.logger.error('problem stopping the container: {0}'.format(e))
            dat = 'there was a problem with {0} action'.format(content['action'])
    # restart container
    if content['action'] == 'restart':
        try:
            make_connection.connect_docker_server().restart(container_id, timeout=10)
            dat = '{0}"container_id": "{1}", "action": "{2}"{3}'.format('{', container_id, content['action'], '}')
        except Exception as e:
            app.logger.error('problem restarting the container: {0}'.format(e))
            dat = 'there was a problem with {0} action'.format(content['action'])
    # start container after stop
    if content['action'] == 'start':
        try:
            make_connection.connect_docker_server().start(container_id)
            dat = '{0}"container_id": "{1}", "action": "{2}"{3}'.format('{', container_id, content['action'], '}')
        except Exception as e:
            app.logger.error('problem starting the container: {0}'.format(e))
            dat = 'there was a problem with {0} action'.format(content['action'])
    # kill container, main process
    if content['action'] == 'kill':
        try:
            make_connection.connect_docker_server().kill(container_id, timeout=10)
            dat = '{0}"container_id": "{1}", "action": "{2}"{3}'.format('{', container_id, content['action'], '}')
        except Exception as e:
            app.logger.error('problem  killing the container: {0}'.format(e))
            dat = 'there was a problem with {0} action'.format(content['action'])
    # delete container, force
    if content['action'] == 'delete':
        try:
            make_connection.connect_docker_server().remove_container(container_id, force=True)
            assert isinstance(my_sql_stuff.ContainerNames.query.filter_by(name_of_container=container_id).delete,
                              object)
            my_sql_stuff.ContainerNames.query.filter_by(name_of_container=container_id).delete()
            db.session.commit()
            dat = '{0}"container_id": "{1}", "action": "{2}"{3}'.format('{', container_id, content['action'], '}')
        except Exception as e:
            app.logger.error('problem deleting the container: {0}'.format(e))
            dat = 'there was a problem with {0} action'.format(content['action'])
    resp = Response(response=dat, status=200, mimetype="application/json")
    return resp


@app.route('/api/seedboxes/executeswarm/<string:name_id>', methods=['POST'])
@require_appkey
def executecommandsswarm(name_id):
    """
    this function will execute commnads on the node ip for a specific container
    curl -i -H "secretkey:1234" -H "Content-Type: application/json" -X POST -d
    '{"command":"htpasswd -b -c /etc/nginx/.htpasswd test test", "nodeip":"81.171.24.247"}'
    http://localhost:5000/api/seedboxes/executeswarm/cd7fae77c1749009
    :param name_id:
    :param container_id:
    :param node_ip:
    :return:
    """
    content = request.json
    app.logger.info('executing command:{0} for container id:{1} on node ip:{2}'.format(content['command'], name_id,
                                                                                       content['nodeip']))
    return Response(swarnodeip.nodeipexecute(content['nodeip'], name_id, content['command']),
                    mimetype='application/json')

@app.route('/api/seedboxes/execute/<string:name_id>', methods=['POST'])
@require_appkey
def executecommands(name_id):
    """
    this function will execute commands on the container
    curl -i -H "secretkey:1234" -H "Content-Type: application/json" -X POST -d
    '{"command":"htpasswd -b -c /etc/nginx/.htpasswd test test"}' http://localhost:5000/api/seedboxes/execute/rtorrent

    :param name_id:
    :return:
    """
    try:
        content = request.json
        app.logger.info('executing command:{0} for container:{1}'.format(content['command'], name_id))
        exec_command = make_connection.connect_docker_server().exec_create(name_id, content['command'], tty=False,
                                                                           stderr=True, privileged=True)
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


    # check if the hostname is valid, should not contain strange stuff
    if not validatehostname.isvalidhostname(name_id):
        raise InvalidUsage('invalid hostname', status_code=404)

    # check if we have plex related stuff
    if my_request.find('plex') != -1:
        plex_secret_token = content['plex']['plex_secret_token']
        plex_server_name = content['plex']['plex_server_name']
    else:
        plex_secret_token = ''
        plex_server_name = ''

    # TODO convert this to dictionary or invent something smarter than if else

    # create ssh container
    if content['options']['service'] == 'ssh':
        image_name = parser.config_params('images')['ssh_image_name']
        exec_this = ''
        cap_value = 'NET_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['ssh_internal_port'].split()


    # create web container
    if content['options']['service'] == 'web':
        image_name = parser.config_params('images')['web_image_name']
        exec_this = 'python app.py'
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['web_internal_port'].split()

    # create rtorrent container
    if content['options']['service'] == 'rtorrent':
        image_name = parser.config_params('images')['rtorrent_image_name']
        exec_this = ''
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['rtorrent_internal_port'].split()

    # create rutorrent container
    if content['options']['service'] == 'rutorrent':
        image_name = parser.config_params('images')['rutorrent_image_name']
        exec_this = ''
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['rutorrent_internal_port'].split()

    # create transmission container
    if content['options']['service'] == 'transmission':
        image_name = parser.config_params('images')['transmission_image_name']
        exec_this = ''
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['transmission_internal_port'].split()

    # create deluge container
    if content['options']['service'] == 'deluge':
        image_name = parser.config_params('images')['deluge_image_name']
        exec_this = ''
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['deluge_internal_port'].split()

    # create openvpn over udp container
    if content['options']['service'] == 'openvpnudp':
        image_name = parser.config_params('images')['openvpnudp_image_name']
        exec_this = ''
        cap_value = 'NET_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['openvpnudp_internal_port'].split()

    # create owncloud container
    if content['options']['service'] == 'owncloud':
        image_name = parser.config_params('images')['owncloud_image_name']
        exec_this = ''
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['owncloud_internal_port'].split()

    # create nginxphp container
    if content['options']['service'] == 'nginxphp':
        image_name = parser.config_params('images')['ngphp_image_name']
        exec_this = ''
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['ngphp_internal_port'].split()

    # create mariadb container
    if content['options']['service'] == 'mariadb':
        image_name = parser.config_params('images')['mariadb_image_name']
        exec_this = ''
        cap_value = 'SYS_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['mariadb_internal_port'].split()

    # create plex container
    if content['options']['service'] == 'plex':
        image_name = parser.config_params('images')['plex_image_name']
        exec_this = ''
        cap_value = 'NET_ADMIN'
        privileged = True
        internal_port = parser.config_params('images')['plex_internal_port'].split()

    # create sftp container
    if content['options']['service'] == 'sftp':
        image_name = parser.config_params('images')['sftp_image_name']
        exec_this = ''
        cap_value = 'NET_ADMIN'
        privileged = False
        internal_port = parser.config_params('images')['sftp_internal_port'].split()

    if db.session.query(exists().where(my_sql_stuff.ContainerNames.name_of_container == name_id)).scalar():
        raise InvalidUsage('There is already a container with this name', status_code=200)
    else:
        new_container = docker_create.delay(name_id, content['username'], content['password'],
                                            content['options']['service'],
                                            content['options']['diskspace'], image_name, internal_port, exec_this,
                                            cap_value, privileged,
                                            plex_secret_token, plex_server_name)
        app.logger.info('New container ID for redis is {0}'.format(new_container.id))
        return jsonify(response=new_container.id)


@app.route('/api/seedboxes/swarm/<string:name_id>', methods=['POST'])
@require_appkey
def swarm(name_id):
    """
    curl -i -H "secretkey:1234" -H "Content-Type: application/json" -X POST -d '{"username":"dan","password":
    "123456789", "options": {"diskspace":"500m","service":"ssh"}}' http://localhost:5000/api/seedboxes/swarm/sshdan
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


    # check if the hostname is valid, should not contain strange stuff
    if not validatehostname.isvalidhostname(name_id):
        raise InvalidUsage('invalid hostname', status_code=404)

    # check if we have plex related stuff
    if my_request.find('plex') != -1:
        plex_secret_token = content['plex']['plex_secret_token']
        plex_server_name = content['plex']['plex_server_name']
    else:
        plex_secret_token = ''
        plex_server_name = ''

    # TODO convert this to dictionary or invent something smarter than if else

    # create ssh container
    if content['options']['service'] == 'ssh':
        image_name = parser.config_params('images')['ssh_image_name']
        exec_this = ''
        internal_port = ast.literal_eval(parser.config_params('images')['ssh_internal_swarm'])

    # create web container
    if content['options']['service'] == 'web':
        image_name = parser.config_params('images')['web_image_name']
        exec_this = 'python app.py'
        internal_port = ast.literal_eval(parser.config_params('images')['web_internal_swarm'])

    # create rtorrent container
    if content['options']['service'] == 'rtorrent':
        image_name = parser.config_params('images')['rtorrent_image_name']
        exec_this = ''
        internal_port = ast.literal_eval(parser.config_params('images')['rtorrent_internal_swarm'])

    # create rutorrent container
    if content['options']['service'] == 'rutorrent':
        image_name = parser.config_params('images')['rutorrent_image_name']
        exec_this = ''
        internal_port = ast.literal_eval(parser.config_params('images')['rutorrent_internal_swarm'])

    # create transmission container
    if content['options']['service'] == 'transmission':
        image_name = parser.config_params('images')['transmission_image_name']
        exec_this = ''
        internal_port = ast.literal_eval(parser.config_params('images')['transmission_internal_swarm'])

    # create deluge container
    if content['options']['service'] == 'deluge':
        image_name = parser.config_params('images')['deluge_image_name']
        exec_this = ''
        internal_port = ast.literal_eval(parser.config_params('images')['deluge_internal_swarm'])

    # create openvpn over udp container
    if content['options']['service'] == 'openvpnudp':
        image_name = parser.config_params('images')['openvpnudp_image_name']
        exec_this = ''
        internal_port = ast.literal_eval(parser.config_params('images')['openvpnudp_internal_swarm'])

    # create owncloud container
    if content['options']['service'] == 'owncloud':
        image_name = parser.config_params('images')['owncloud_image_name']
        exec_this = ''
        internal_port = ast.literal_eval(parser.config_params('images')['owncloud_internal_swarm'])

    # create nginxphp container
    if content['options']['service'] == 'nginxphp':
        image_name = parser.config_params('images')['ngphp_image_name']
        exec_this = ''
        internal_port = ast.literal_eval(parser.config_params('images')['ngphp_internal_swarm'])

    # create mariadb container
    if content['options']['service'] == 'mariadb':
        image_name = parser.config_params('images')['mariadb_image_name']
        exec_this = ''
        internal_port = ast.literal_eval(parser.config_params('images')['mariadb_internal_swarm'])

    # create plex container
    if content['options']['service'] == 'plex':
        image_name = parser.config_params('images')['plex_image_name']
        exec_this = ''
        internal_port = ast.literal_eval(parser.config_params('images')['plex_internal_swarm'])

    # create sftp container
    if content['options']['service'] == 'sftp':
        image_name = parser.config_params('images')['sftp_image_name']
        exec_this = ''
        internal_port = ast.literal_eval(parser.config_params('images')['sftp_internal_swarm'])

    if db.session.query(exists().where(my_sql_stuff.ContainerNames.name_of_container == name_id)).scalar():
        raise InvalidUsage('There is already a container with this name', status_code=200)
    else:
        new_container_swarm = swarm_create(name_id, content['username'], content['password'],
                                           content['options']['service'],
                                           image_name, exec_this, internal_port, plex_secret_token, plex_server_name)
        print new_container_swarm
        app.logger.info('New swarm container {0} created'.format(new_container_swarm))

    return jsonify(new_container_swarm)


@app.route('/api/seedboxes/pending/<string:task_id>')
@require_appkey
# start in a console this > celery2 worker -A my_proxy.celery --loglevel=info
def taskstatus(task_id):
    """
    this function will return the status of the container
    :param task_id:
    :return:
    """
    task = docker_create.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'current': 0,
            'total': 1,
            'status': 'Pending...'
        }
    elif task.state != 'FAILURE':
        app.logger.info('Info about the new  container {0}'.format(task.result))
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
            'status': str(task.result),  # this is the exception raised
        }
    return jsonify(response)


@app.route('/api/seedboxes/swarmnodeid/<string:name_id>', methods=['GET'])
@require_appkey
def nodeipdetector(name_id):
    """
    This function will return the node ip and the container id
    Ex: curl -i -H 'secretkey:1234'  http://localhost:5000/api/seedboxes/swarmnodeid/debugmeno113
    :param name_id:
    :return:
    """
    return Response(swarnodeip.nodeip(name_id), mimetype='application/json')


@app.route('/api/seedboxes/volumeusage/<string:name_id>', methods=['GET'])
@require_appkey
def volumeusage(name_id):
    """
    This funciton will return volume usage
    Ex: curl -i -H 'secretkey:1234'  http://localhost:5000/api/seedboxes/volumeusage/wtf
    :param name_id:
    :return:
    """
    return Response(volumesize.volume_size(name_id), mimetype='application/json')


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

    # let's do some checks

    if not db.session.query(exists().where(my_sql_stuff.ContainerNames.owner == user_to_be_deleted)).scalar():
        app.logger.info('There is no such username {0}'.format(user_to_be_deleted))
        raise InvalidUsage('there is no such username, nothing to delete, go away', status_code=404)
    else:
        try:
            # let's stop the containers
            for instance in db.session.query(my_sql_stuff.ContainerNames).group_by(
                    my_sql_stuff.ContainerNames.name_of_container).filter_by(owner=user_to_be_deleted).all():
                app.logger.info('Username {0} containers {1} will be deleted'.format(user_to_be_deleted,
                                                                                     instance.name_of_container))
                make_connection.connect_docker_server().remove_container(instance.name_of_container, force=True)

            # remove container names from db
            my_sql_stuff.ContainerNames.query.filter_by(owner=user_to_be_deleted).delete()

            # let's delete volume
            for volume in db.session.query(my_sql_stuff.MountPoints).filter_by(owner=user_to_be_deleted).limit(1):
                app.logger.info(
                    'Username {0} volume {1} will be deleted'.format(user_to_be_deleted, volume.volume_name))
                make_connection.connect_docker_server().remove_volume(volume.volume_name)

            # let's delete volume from db
            my_sql_stuff.MountPoints.query.filter_by(owner=user_to_be_deleted).delete()
            # commit db
            db.session.commit()

            resp = Response(response=dat, status=200)
        except:
            app.logger.info('something bad happened')
            raise InvalidUsage('something bad happened ', status_code=500)

    return resp


if __name__ == '__main__':
    app.run(debug=True)
