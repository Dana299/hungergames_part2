from flask import Blueprint
from flask_socketio import SocketIO

socketio = SocketIO()
log_buffer = list()
bp = Blueprint('main', __name__)

from .app import create_app

app = create_app()

from main import routes

app.register_blueprint(blueprint=bp)
socketio.init_app(app)
app.logger.info("app started")
