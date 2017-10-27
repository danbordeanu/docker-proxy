from sqlalchemy import exists

from helpers import random_generator as random_generator_function, connect_docker_server as make_connection
from models import models as my_sql_stuff
from models.models import db
from flask import Flask


def give_me_mount_point(owner, size_plan):
    """
    this function will generate a shared tmpfs volume, the size should always be in M
    let's insert mount points into table, user is unique, every user will have unique mount points
    """
    app = Flask(__name__)
    if db.session.query(exists().where(my_sql_stuff.MountPoints.owner == owner)).scalar():
        # if user exists we will reuse the same volume
        new_volume = my_sql_stuff.MountPoints.query.filter_by(owner=owner).first()
        new_volume_str = str(new_volume)
        print new_volume_str
        app.logger.info('This user has already a volume assigned {0}'.format(new_volume_str.split('/')[-1]))
        return new_volume_str.split('/')[-1]
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
        app.logger.info(
            'new volume created:{0} for user:{1} with name {2}'.format(new_volume_created, owner, new_volume_name))
        db.session.add(my_sql_stuff.MountPoints(owner, new_volume_created, new_volume_name, size_plan))
        db.session.commit()
        return str(new_volume['Name'])