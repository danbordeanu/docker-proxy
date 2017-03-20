from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class ContainerNames(db.Model):
    __tablename__ = 'containers'
    id = db.Column(db.Integer, primary_key=True)
    name_of_container = db.Column(db.String(80), unique=True)

    def __init__(self, id, name_of_container):
        self.id = id
        self.name_of_container = name_of_container

    def __repr__(self):
        return 'container name ' % self.name_of_container