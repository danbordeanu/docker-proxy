from sqlalchemy import exists
from werkzeug.security import generate_password_hash
from flask import Flask
from helpers import random_generator as random_generator_function
from models import models as my_sql_stuff
from models.models import db


def give_me_something_unique(name_of_container, hostname, owner, password, service_name):
    """
    let's generate random and unique port
    :rtype : object
    """
    app = Flask(__name__)
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
        try:
            db.session.add(
                my_sql_stuff.ContainerNames(name_of_container, hostname, owner, generate_password_hash(password),
                                            new_port, service_name))
            db.session.commit()
        except Exception as e:
            app.logger.error('db issue during insert: {0}'.format(e))
    return new_port