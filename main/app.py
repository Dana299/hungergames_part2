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

from main import log_buffer, socketio
from main.logger import LogBufferHandler, WebSocketHandler

db = SQLAlchemy()

BASE_PATH = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_PATH, ".env"))


def create_app(conf_file: str = "config.yaml"):
    """Creating app factory."""
    app = Flask(__name__)

    if not os.path.isabs(conf_file):
        conf_file = os.path.join(BASE_PATH, conf_file)

    if not conf_file.endswith(".yaml"):
        raise FileNotFoundError(
            f"Yaml config file not found in project directory, check that {conf_file} exist."
        )

    app.config.from_file(conf_file, load=yaml.safe_load)

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
    """Initialize celery app."""
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app


def configure_logging(app):
    """Set logger level and add necessary handlers."""

    logging_conf = app.config["LOGGING"]

    # setup global logging level
    level = logging_conf["LEVEL"]
    app.logger.setLevel(level)

    # add rotating file handler with app config
    file_conf = logging_conf["FILE"]
    _add_file_handler(app, file_conf)

    # add buffer handler for store all new log in memory
    buffer_conf = logging_conf["BUFFER"]
    _add_buffer_handler(app, buffer_conf)

    # add websocket handler for realtime logs monitoring
    ws_conf = logging_conf["WS"]
    _add_ws_handler(app, socketio, ws_conf)


def _add_file_handler(app, conf: dict):
    """Add rotation file log handler."""
    formatter_data = conf["FORMATTER"]
    handler_args = conf["HANDLER"]
    level = conf["LEVEL"]

    handler = RotatingFileHandler(**handler_args)
    handler.setLevel(level)

    log_formatter = logging.Formatter(**formatter_data)
    handler.setFormatter(log_formatter)

    app.logger.addHandler(handler)


def _add_buffer_handler(app, conf):
    """Set buffer handler that store all new logs."""
    formatter_conf = conf["FORMATTER"]
    level = conf["LEVEL"]
    max_size = conf["SHOWN_DEFAULT"]

    # use common dynamic list for buffer
    handler = LogBufferHandler(buffer_obj=log_buffer, max_size=max_size)
    handler.setLevel(level)

    formatter = logging.Formatter(**formatter_conf)
    handler.setFormatter(formatter)

    app.logger.addHandler(handler)


def _add_ws_handler(app, socket_obj, conf):
    """Set handler for realtime notification via websocket connection to all connected clients."""
    formatter_conf = conf["FORMATTER"]
    event_name = conf["EVENT_NAME"]
    namespace = conf["NAMESPACE"]
    level = conf["LEVEL"]

    handler = WebSocketHandler(socket_obj, event_name, level=level, namespace=namespace)
    formatter = logging.Formatter(**formatter_conf)
    handler.setFormatter(formatter)

    app.logger.addHandler(handler)
