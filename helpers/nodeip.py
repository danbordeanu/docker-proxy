import config_parser as parser
import paramiko
import json
import ast


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
