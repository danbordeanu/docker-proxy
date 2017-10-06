from sqlalchemy import text

from models.models import db


def storage_sum():
    """
    function to check storage
    this will sum up all rows from db
    this is used just to see how much storage is alocated
    !!!!NB!!!! Not real space
    :return:
    """
    storage_sum = []
    sql_storage_sum = db.engine.execute(text('select sum(size_plan) from mount'))
    for row in sql_storage_sum:
        storage_sum.append(row[0])
    return storage_sum