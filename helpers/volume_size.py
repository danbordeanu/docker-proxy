import config_parser as parser
import paramiko
import json


def volume_size(name_id):

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(parser.config_params('ssh')['server'], port=22,
                username=parser.config_params('ssh')['user'],
                password=parser.config_params('ssh')['password'])
    except paramiko.AuthenticationException:
        print 'issues with the connection'

    #get total.
    #my_command_total = "docker inspect -f '{{ range .Mounts }}{{ .Source }}{{ end }}' %s | xargs sudo du -shm| sed 's/\s.*$//'"%name_id
    my_command_total = "docker inspect -f '{{ range .Mounts }}{{ .Source }}{{ end }}' %s | xargs sudo df -h | sed -n 2p | awk '{print $2}'"%name_id
    # get free
    my_command_free = "docker inspect -f '{{ range .Mounts }}{{ .Source }}{{ end }}' %s | xargs sudo df -h | sed -n 2p | awk '{print $4}'"%name_id
    #get used
    my_command_used = "docker inspect -f '{{ range .Mounts }}{{ .Source }}{{ end }}' %s | xargs sudo df -h | sed -n 2p | awk '{print $3}'"%name_id
    #
    stdin, stdout, stderr = ssh.exec_command(my_command_total)
    storage_total = stdout.read().rstrip()
    stdin, stdout, stderr = ssh.exec_command(my_command_free)
    storage_free = stdout.read().rstrip()
    stdin, stdout, stderr = ssh.exec_command(my_command_used)
    storage_used = stdout.read().rstrip()
    json_create = json.dumps({"stats": dict(total='%s', free='%s', used='%s')})%(storage_total, storage_free, storage_used)
    print json_create
    return json_create

