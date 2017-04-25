import config_parser as parser
import paramiko
import json
import ast


# TODO make this as a class

def nodeip(name_id):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(parser.config_params('sshswarmmaster')['server'], port=22,
                    username=parser.config_params('sshswarmmaster')['user'],
                    password=parser.config_params('sshswarmmaster')['password'])
    except paramiko.AuthenticationException:
        print 'issues with the connection'

    my_node_info = '{0} %s '.format(parser.config_params('nodeip')['command']) % name_id
    stdin, stdout, stderr = ssh.exec_command(my_node_info)
    node_info = stdout.read().rstrip()
    json_create = json.dumps({"Swarm container info": '%s'}) % (ast.literal_eval(node_info))
    return json_create


def nodeipexecute(node_ip, container_id, command):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(node_ip, port=22,
                    username=parser.config_params('sshswarmmaster')['user'],
                    password=parser.config_params('sshswarmmaster')['password'])
    except paramiko.AuthenticationException:
        print 'issues with the connection to the swarm node'

    my_node_exec = 'docker exec {0} {1}'.format(container_id, command)
    stdin, stdout, stderr = ssh.exec_command(my_node_exec)
    stderr_print = stderr.read().rstrip()
    stdout_print = stdout.read().rstrip()
    json_create = json.dumps({"Swarm exec command status output": dict(stderr='%s', stdout='%s')}) % (
    stderr_print, stdout_print)
    return json_create
