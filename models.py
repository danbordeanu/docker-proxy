from flask import Flask
import config_parser as parser
from flask_sqlalchemy import SQLAlchemy
import json

app = Flask(__name__)


def make_the_connection():
    """
    this function is making the connection and map app name with schema
    :return:
    """
    try:
        app.config['SQLALCHEMY_DATABASE_URI'] = parser.config_params('dbname')['location_name_db']
    except ImportError:
        print 'no db connection availabe'
        app.logger.info('no db connection available'
                        )


db = SQLAlchemy(app)

make_the_connection()


class MountPoints(db.Model):
    """
    let's create the mount points table
    """
    __tablename__ = 'mount'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    owner = db.Column(db.String(80), unique=True)
    mount_point = db.Column(db.String(200))
    volume_name = db.Column(db.String(200))
    size_plan = db.Column(db.String(80))

    def __init__(self, owner, mount_point, volume_name, size_plan):
        self.owner = owner
        self.mount_point = mount_point
        self.volume_name = volume_name
        self.size_plan = size_plan

    def __repr__(self):
        """
        return only the mount point
        """
        return str(self.mount_point)


class ContainerNames(db.Model):
    """
    let's do ContainerNames tables
    """
    __tablename__ = 'containers'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # name
    name_of_container = db.Column(db.String(80))  # , unique=True)
    # hostname
    hostname = db.Column(db.String(80))
    # owner will be used also for login
    owner = db.Column(db.String(100))
    # password
    password = db.Column(db.String(200))
    # public port for container
    public_port = db.Column(db.Integer, unique=True)
    # service name
    service_name = db.Column(db.String(100))

    def __init__(self, name_of_container, hostname, owner, password, public_port, service_name):
        self.name_of_container = name_of_container
        self.hostname = hostname
        self.owner = owner
        self.password = password
        assert isinstance(public_port, object)
        self.public_port = public_port
        self.service_name = service_name

    def __repr__(self):
        """
        return json
        """
        return json.dumps(
            {'name_of_container': self.name_of_container, 'hostname': self.hostname,
             'owner': self.owner, 'password': self.password, 'public_port': self.public_port,
             'service_name': self.service_name})
