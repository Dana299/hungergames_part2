import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml
from celery import Celery, Task
from dotenv import load_dotenv
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from main import socketio
from main.logger import WebSocketHandler

db = SQLAlchemy()

BASE_PATH = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_PATH, ".env"))


def create_app():
    app = Flask(__name__)
    app.config.from_file(str(BASE_PATH) + '/config.yaml', load=yaml.safe_load)

    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://{}:{}@{}/{}'.format(
        os.getenv('POSTGRES_USER', 'flask'),
        os.getenv('POSTGRES_PASSWORD', ''),
        os.getenv('POSTGRES_HOST', 'localhost'),
        os.getenv('POSTGRES_DB', 'flask')
    )

    db.init_app(app)
    migrate = Migrate(app=app, db=db)

    configure_logging(app=app)

    app.config.from_mapping(
        CELERY=dict(
            broker_url="redis://{}:6379".format(os.getenv("BROKER_URL_HOST")),
            result_backend="redis://{}:6379".format(os.getenv("RESULT_BACKEND_HOST")),
            task_ignore_result=True,
            broker_connection_retry_on_startup=True,
        ),
    )

    celery_init_app(app)
    return app


def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app


def add_file_handler(app: Flask, conf: dict):
    formatter = conf["FORMATTER"]
    handler_args = conf["HANDLER"]
    level = conf["LEVEL"]

    handler = RotatingFileHandler(**handler_args)
    handler.setLevel(level)

    log_formatter = logging.Formatter(**formatter)
    handler.setFormatter(log_formatter)

    app.logger.addHandler(handler)


def add_websocket_handler(app: Flask, socket_obj: SocketIO, conf: dict):
    formatter = conf["FORMATTER"]
    event_name = conf["EVENT_NAME"]
    namespace = conf["NAMESPACE"]
    level = conf["LEVEL"]

    handler = WebSocketHandler(
        socket_obj=socket_obj,
        event_name=event_name,
        level=level,
        namespace=namespace,
    )
    formatter = logging.Formatter(**formatter)
    handler.setFormatter(formatter)

    app.logger.addHandler(handler)


def configure_logging(app: Flask):
    level = app.config["LOGGING"]["LEVEL"]
    app.logger.setLevel(level)

    file_conf = app.config["LOGGING"]["FILE"]
    add_file_handler(app=app, conf=file_conf)

    # add websocket handler for realtime logs monitoring
    ws_conf = app.config["LOGGING"]["WEBSOCKET"]
    add_websocket_handler(app=app, socket_obj=socketio, conf=ws_conf)
