## Synopsis

This is an API rest proxy. It's handling PUT/POST requests to handle docker container management

## Code Example

Function creating the container

```python
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
```
        
Ex:

```
~curl -i -H "secretkey:1234" -H "Content-Type: application/json" -X POST -d '{"username":"pulifricimare","password": "123456789", "options": 
{"diskspace":"512M","service":"plex"},"plex":{"plex_secret_token":"41Zs4dupjB2KeVskbQyb","plex_server_name":"localhost_test"}}' http://localhost:5000/api/seedboxes/new/plex1
```

## Motivation

In order to have full control from a frontend to the docker server, a proxy able to hande a specific set of REST API calls had to be created

## Installation

Code must be installed in /opt/proxy and runned using gunicorn for better performance

### Gunicorn

Sample of gunicorn.service file


```
[Unit]
Description=gunicorn daemon
After=network.target
After=syslog.target

[Service]
User=sysadmin
Group=sysadmin

Enviroment=sitedir=/opt/proxy
ExecStart=/usr/bin/gunicorn --bind 127.0.0.1:4000 --chdir /opt/proxy  wsgi:app --log-file /var/log/gunicorn/gunicorn.log --log-level DEBUG
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s TERM $MAINPID
PrivateTmp=true
```

### Database

#### Mysql

For MYSQL **config.ini** must be changed

```
[dbname]
location_name_db: mysql://proxy_db_user:9911@localhost/proxy_db
```

#### Sqlite3

For sqlite3 **config.ini** must be changed

```
[dbname]
location_name_db: sqlite:////tmp/test.db
```

#### DB init

In order to install db tables

```python
from models import db
db.create_all()
```

#### Docker server settings

Docker server storage must be in **/data/docker**

Sample of the docker.service configuration file

```
[Unit]
Description=Docker Application Container Engine
Documentation=https://docs.docker.com
After=network.target docker.socket
Requires=docker.socket

[Service]
Type=notify
ExecStart=/usr/bin/dockerd -g /data/docker -H tcp://127.0.0.1:4243 -H unix:///var/run/docker.sock --storage-opt dm.basesize=2048Mb --debug
ExecReload=/bin/kill -s HUP $MAINPID
LimitNOFILE=infinity
LimitNPROC=infinity
LimitCORE=infinity
TasksMax=infinity
TimeoutStartSec=0
Delegate=yes
KillMode=process
[Install]
WantedBy=multi-user.target
```

#### Ssh login setup

Ssh login must be enabled for root user (this is used to monitor disk usage of the container volumes)

in **config.ini**

```
[ssh]
user: user
password: password
server: 192.168.98.99
```

User **must** have read wright in **/data/docker**


## API Reference

[Api documentation and requests](https://docs.google.com/spreadsheets/d/1dNXysy8pBEoM8M0qyzARihbboUXdAt57Yh3Idn2TWXc/edit?pli=1#gid=0)

## Tests

In order to test the proxy, call curl commands

EX:

```
curl -i -H "secretkey:1234" -H "Content-Type: application/json" -X POST -d '{"username":"dan","password": "123456789", "options": {"diskspace":"512M","service":"ssh"}}' http://localhost:5000/api/seedboxes/new/ssh1000
```

after, check if instance is running calling: ```docker ps -a```

If instance is running connect to it by using ```ssh root@localhost -p port_value``` Password is **screencast**

## Contributors

Dan

## License

Use it on your own risk :)