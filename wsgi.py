"""WSGI entry point.

    Development :  python wsgi.py
    Production  :  gunicorn -k gevent -w 3 -b 127.0.0.1:8102 wsgi:app
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=app.config["PORT"], debug=app.config["DEBUG"])
