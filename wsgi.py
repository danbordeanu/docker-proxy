__author__ = 'dan'

from my_proxy import app
"""
used to start withg gunicorn
gunicorn --bind 0.0.0.0:5000 wsgi:app

"""
if __name__ == "__main__":
    app.run()
